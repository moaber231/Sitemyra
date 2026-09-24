"""Phase D browser-worker tests (docs/OPTIMIZATION-PLAN.md D1-D10).

Covered:
- SSRF: static structure validation (out-of-range ports must raise
  SecurityError, not ValueError), IP-literal blocking including
  IPv4-mapped IPv6, the host blocklist, the request-interceptor policy
  (every URL incl. simulated redirect hops and subresources), the
  per-check DNS budget (fail-closed), and DNS caching.
- Resource blocking: mode matrix — screenshot NEVER blocks (hard
  requirement), dom/price block images/media/fonts only, BROWSER_BLOCK_RESOURCES
  env override incl. "none".
- Browser lifecycle (fakes, no Chromium): lazy launch, fresh context per
  check closed unconditionally, recycle by task count, RSS recycle with
  fail-safe on unreadable /proc, automatic restart after a crash,
  explicit launch flags (--disable-dev-shm-usage) and timeouts.
- Error handling: DOM/price selector ValueErrors become RECORDED monitor
  failures — never an unhandled Celery exception.
- Real-Chromium integration (auto-skipped when Chromium is unavailable,
  e.g. inside the API image): storage isolation between checks,
  interception coverage for subresources and redirect hops, live abort
  of blocked subresources, non-root launch with --disable-dev-shm-usage.
"""

import asyncio
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from django.test import SimpleTestCase, TestCase

from accounts.models import User
from monitors.models import (
    AdvancedMonitorConfig,
    ChangeDiff,
    Monitor,
    MonitorCheck,
)
from monitors.services.browser_fetcher import (
    BrowserFetchError,
    BrowserResult,
    RequestPolicy,
    _env_int,
    fetch_with_browser,
    resource_types_to_block,
)
from monitors.services.browser_pool import (
    BrowserPool,
    process_tree_rss_mb,
)
from monitors.services.fetcher import (
    FetchError,
    SecurityError,
    validate_url,
    validate_url_structure,
)


# ---------------------------------------------------------------------------
# Structure validation (HTTP engine + shared with the interceptor)
# ---------------------------------------------------------------------------


class UrlStructureValidationTests(SimpleTestCase):
    def test_out_of_range_port_is_security_error_not_value_error(self):
        # urlparse().port raises ValueError for ":99999"; both engines must
        # surface it as a blocked destination, never an unhandled ValueError.
        with self.assertRaises(SecurityError):
            validate_url("http://example.com:99999/")
        with self.assertRaises(SecurityError):
            validate_url_structure("http://example.com:99999/")
        with self.assertRaises(SecurityError):
            validate_url("http://example.com:-1/")

    def test_nonstandard_port_blocked(self):
        with self.assertRaises(SecurityError):
            validate_url("http://example.com:8080/")

    def test_credentials_in_url_blocked(self):
        with self.assertRaises(SecurityError):
            validate_url("https://user:pass@example.com/")

    def test_non_http_scheme_blocked(self):
        with self.assertRaises(SecurityError):
            validate_url("ftp://example.com/")
        with self.assertRaises(SecurityError):
            validate_url("file:///etc/passwd")

    def test_localhost_blocked(self):
        with self.assertRaises(SecurityError):
            validate_url("http://localhost/")

    def test_metadata_hostname_blocked(self):
        with self.assertRaises(SecurityError):
            validate_url("http://metadata.google.internal/computeMetadata/v1/")
        with self.assertRaises(SecurityError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_private_ip_literals_blocked(self):
        for url in (
            "http://10.0.0.1/",
            "http://192.168.1.10/",
            "http://127.0.0.1/",
            "http://172.16.0.1/",
        ):
            with self.assertRaises(SecurityError, msg=url):
                validate_url(url)

    def test_ipv4_mapped_ipv6_blocked(self):
        # ::ffff:10.0.0.1 / ::ffff:127.0.0.1 must be judged by the inner
        # IPv4 address — the mapping is not consulted by all is_* flags.
        for url in (
            "http://[::ffff:10.0.0.1]/",
            "http://[::ffff:127.0.0.1]/",
            "http://[::ffff:169.254.169.254]/",
        ):
            with self.assertRaises(SecurityError, msg=url):
                validate_url(url)

    def test_decimal_ipv4_blocked(self):
        # 2130706433 == 127.0.0.1 (inet_aton semantics; verified resolving
        # to loopback inside the container) — must never be fetched.
        with self.assertRaises(FetchError):
            validate_url("http://2130706433/")

    def test_public_ip_literal_allowed(self):
        # No false positives: a plain public IP passes with no DNS needed.
        validate_url("http://93.184.216.34/")

    def test_mapped_public_ipv4_is_not_blocked(self):
        from monitors.services.fetcher import _is_blocked_ip

        self.assertTrue(_is_blocked_ip("::ffff:169.254.169.254"))
        self.assertTrue(_is_blocked_ip("::ffff:10.1.2.3"))
        self.assertFalse(_is_blocked_ip("::ffff:93.184.216.34"))
        self.assertFalse(_is_blocked_ip("93.184.216.34"))


# ---------------------------------------------------------------------------
# Resource blocking policy (D5)
# ---------------------------------------------------------------------------


class ResourceBlockingPolicyTests(SimpleTestCase):
    def test_screenshot_mode_never_blocks(self):
        # HARD REQUIREMENT: screenshots must render with full fidelity even
        # if an operator tries to enable blocking via the environment.
        with mock.patch.dict(
            os.environ,
            {"BROWSER_BLOCK_RESOURCES": "images,media,fonts"},
        ):
            self.assertEqual(
                resource_types_to_block(AdvancedMonitorConfig.SCREENSHOT),
                frozenset(),
            )

    def test_dom_and_price_default_to_images_media_fonts(self):
        for mode in (AdvancedMonitorConfig.DOM, AdvancedMonitorConfig.PRICE):
            self.assertEqual(
                resource_types_to_block(mode),
                frozenset({"image", "media", "font"}),
            )

    def test_document_markup_script_and_xhr_are_never_blocked(self):
        block = resource_types_to_block(AdvancedMonitorConfig.DOM)
        for resource_type in (
            "document",
            "stylesheet",
            "script",
            "xhr",
            "fetch",
        ):
            self.assertNotIn(resource_type, block)

    def test_env_none_disables_blocking(self):
        for value in ("none", "off", "0", ""):
            with mock.patch.dict(os.environ, {"BROWSER_BLOCK_RESOURCES": value}):
                self.assertEqual(
                    resource_types_to_block(AdvancedMonitorConfig.DOM),
                    frozenset(),
                )

    def test_env_subset_only_blocks_named_types(self):
        with mock.patch.dict(os.environ, {"BROWSER_BLOCK_RESOURCES": "fonts"}):
            self.assertEqual(
                resource_types_to_block(AdvancedMonitorConfig.DOM),
                frozenset({"font"}),
            )

    def test_env_unknown_token_is_ignored_not_fatal(self):
        with mock.patch.dict(
            os.environ,
            {"BROWSER_BLOCK_RESOURCES": "fonts,bogus"},
        ):
            self.assertEqual(
                resource_types_to_block(AdvancedMonitorConfig.DOM),
                frozenset({"font"}),
            )

    def test_env_int_knob_override(self):
        with mock.patch.dict(os.environ, {"SCREENSHOT_MAX_HEIGHT_PX": "1234"}):
            self.assertEqual(_env_int("SCREENSHOT_MAX_HEIGHT_PX", 0), 1234)
        self.assertEqual(_env_int("SCREENSHOT_MAX_HEIGHT_PX", 0), 0)


# ---------------------------------------------------------------------------
# Request interceptor policy (D4) — uses IP literals: no DNS, no network
# ---------------------------------------------------------------------------


class _FakeCdpSession:
    def __init__(self):
        self.sent = []

    def send(self, method, params=None):
        self.sent.append((method, params))


def _paused(url, resource_type="Document", request_id="r1"):
    return {
        "requestId": request_id,
        "request": {"url": url},
        "resourceType": resource_type,
    }


class RequestPolicyTests(SimpleTestCase):
    def _decide(self, policy, url, resource_type="document"):
        return policy.decide(url, resource_type)

    def test_private_ip_document_blocked(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        action = self._decide(policy, "http://10.0.0.5/internal")
        self.assertEqual(action, "ssrf")
        self.assertEqual(policy.ssrf_blocked, 1)
        self.assertEqual(policy.cost_blocked, 0)

    def test_metadata_subresource_blocked(self):
        # A subresource pointing at the cloud metadata service must be
        # blocked the same way the main document would be.
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        action = self._decide(
            policy,
            "http://169.254.169.254/latest/meta-data/",
            resource_type="image",
        )
        self.assertEqual(action, "ssrf")
        self.assertEqual(policy.ssrf_blocked, 1)

    def test_localhost_subresource_blocked(self):
        policy = RequestPolicy(AdvancedMonitorConfig.SCREENSHOT)
        self.assertEqual(
            self._decide(policy, "http://localhost/admin", "script"),
            "ssrf",
        )

    def test_redirect_hop_to_private_blocked(self):
        # A redirect hop is just another intercepted URL: same policy.
        policy = RequestPolicy(AdvancedMonitorConfig.SCREENSHOT)
        action = self._decide(policy, "http://127.0.0.1:80/")
        self.assertEqual(action, "ssrf")

    def test_out_of_range_port_blocked_in_interceptor(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        self.assertEqual(
            self._decide(policy, "http://example.com:99999/"),
            "ssrf",
        )

    def test_credentialed_url_blocked_in_interceptor(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        self.assertEqual(
            self._decide(policy, "http://user:pass@93.184.216.34/"),
            "ssrf",
        )

    def test_public_ip_document_allowed(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        self.assertEqual(
            self._decide(policy, "http://93.184.216.34/"),
            "continue",
        )

    def test_dom_mode_blocks_image_but_keeps_xhr_and_script(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        self.assertEqual(
            self._decide(policy, "http://93.184.216.34/logo.png", "image"),
            "cost",
        )
        self.assertEqual(policy.cost_blocked, 1)
        self.assertEqual(policy.ssrf_blocked, 0)
        self.assertEqual(
            self._decide(policy, "http://93.184.216.34/api", "xhr"),
            "continue",
        )
        self.assertEqual(
            self._decide(policy, "http://93.184.216.34/app.js", "script"),
            "continue",
        )

    def test_screenshot_mode_never_blocks_any_resource(self):
        # HARD REQUIREMENT at decision level: even a hostile
        # BROWSER_BLOCK_RESOURCES cannot make screenshot mode block.
        with mock.patch.dict(
            os.environ,
            {"BROWSER_BLOCK_RESOURCES": "images,media,fonts"},
        ):
            policy = RequestPolicy(AdvancedMonitorConfig.SCREENSHOT)
        self.assertEqual(policy.block_types, frozenset())
        self.assertEqual(
            self._decide(policy, "http://93.184.216.34/hero.png", "image"),
            "continue",
        )
        self.assertEqual(policy.cost_blocked, 0)
        self.assertEqual(policy.ssrf_blocked, 0)

    def test_dns_budget_fails_closed(self):
        with mock.patch.dict(os.environ, {"BROWSER_MAX_DNS_LOOKUPS": "0"}):
            policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        # Hostname URL with zero budget: DNS never happens, request blocked.
        with self.assertRaises(SecurityError):
            policy.validate("http://example.com/")
        self.assertEqual(
            self._decide(policy, "http://example.com/"),
            "ssrf",
        )

    def test_dns_result_cached_within_check(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        with mock.patch(
            "monitors.services.browser_fetcher._resolve_and_validate_host"
        ) as resolver:
            policy.validate("http://example.com/a")
            policy.validate("http://example.com/b")
        # Second request for the same host reuses the validation (1 lookup).
        self.assertEqual(resolver.call_count, 1)

    def test_dns_lookup_counted_toward_budget(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        with mock.patch(
            "monitors.services.browser_fetcher._resolve_and_validate_host"
        ) as resolver:
            policy.validate("http://example.com/")
            policy.max_dns = 1  # budget: only one real lookup allowed
            with self.assertRaises(SecurityError):
                policy.validate("http://other.example/")  # over budget
        self.assertEqual(resolver.call_count, 1)


class RequestPolicyCdpHandlerTests(SimpleTestCase):
    """handle_cdp: the exact code path Chromium hits per request."""

    def test_allowed_request_is_continued_verbatim(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        session = _FakeCdpSession()
        policy.handle_cdp(session, _paused("http://93.184.216.34/"))
        self.assertEqual(
            session.sent,
            [("Fetch.continueRequest", {"requestId": "r1"})],
        )
        self.assertEqual(policy.ssrf_blocked, 0)

    def test_private_request_is_failed_at_request_level(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        session = _FakeCdpSession()
        policy.handle_cdp(
            session,
            _paused("http://169.254.169.254/latest/meta-data/"),
        )
        self.assertEqual(
            session.sent,
            [
                (
                    "Fetch.failRequest",
                    {"requestId": "r1", "errorReason": "BlockedByClient"},
                )
            ],
        )
        self.assertEqual(policy.ssrf_blocked, 1)

    def test_cost_blocked_image_fails_but_xhr_continues(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        session = _FakeCdpSession()
        policy.handle_cdp(
            session,
            _paused("http://93.184.216.34/logo.png", "Image"),
        )
        self.assertEqual(session.sent[0][0], "Fetch.failRequest")
        self.assertEqual(policy.cost_blocked, 1)
        policy.handle_cdp(
            session,
            _paused("http://93.184.216.34/data", "XHR"),
        )
        self.assertEqual(session.sent[1][0], "Fetch.continueRequest")

    def test_screenshot_mode_continues_images_despite_hostile_env(self):
        with mock.patch.dict(
            os.environ,
            {"BROWSER_BLOCK_RESOURCES": "images,media,fonts"},
        ):
            policy = RequestPolicy(AdvancedMonitorConfig.SCREENSHOT)
        session = _FakeCdpSession()
        policy.handle_cdp(
            session,
            _paused("http://93.184.216.34/hero.png", "Image"),
        )
        self.assertEqual(session.sent[0][0], "Fetch.continueRequest")
        self.assertEqual(policy.cost_blocked, 0)

    def test_handler_fails_closed_on_unexpected_error(self):
        # An unexpected error must never continue the request NOR leave
        # it paused (which would hang the page until the Celery hard limit).
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        policy.validate = mock.Mock(side_effect=RuntimeError("boom"))
        session = _FakeCdpSession()
        policy.handle_cdp(session, _paused("http://93.184.216.34/"))
        self.assertEqual(session.sent[0][0], "Fetch.failRequest")

    def test_empty_params_do_not_raise(self):
        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        session = _FakeCdpSession()
        policy.handle_cdp(session, {})
        self.assertEqual(session.sent[0][0], "Fetch.failRequest")
        self.assertEqual(len(session.sent), 1)


# ---------------------------------------------------------------------------
# Browser lifecycle (fakes — no Chromium required)
# ---------------------------------------------------------------------------


class _FakeContext:
    def __init__(self, log):
        self.log = log
        self.closed = False
        self.default_nav_timeout = None
        self.default_timeout = None

    def set_default_navigation_timeout(self, ms):
        self.default_nav_timeout = ms

    def set_default_timeout(self, ms):
        self.default_timeout = ms

    def close(self):
        self.closed = True
        self.log.append("context-close")


class _FakeBrowser:
    def __init__(self, log):
        self.log = log
        self.connected = True
        self.contexts = []
        self.closed = False

    def new_context(self, **kwargs):
        context = _FakeContext(self.log)
        self.contexts.append(context)
        self.log.append("new-context")
        return context

    def is_connected(self):
        return self.connected

    def close(self):
        self.closed = True
        self.connected = False
        self.log.append("browser-close")


class _FakeDriver:
    def __init__(self, log, browsers):
        self.log = log
        self.browsers = browsers
        self.chromium_launch_kwargs = None
        self.stopped = False
        parent = self

        class _Chromium:
            def launch(self, **kwargs):
                parent.chromium_launch_kwargs = kwargs
                browser = _FakeBrowser(log)
                parent.browsers.append(browser)
                log.append("launch")
                return browser

        self.chromium = _Chromium()

    def stop(self):
        self.stopped = True
        self.log.append("driver-stop")


class BrowserDriverThreadTests(TestCase):
    """Phase G live regression: Playwright's sync API parks an asyncio
    loop as *running* in the thread that starts the driver (cleared only
    by ``stop()``). With the driver kept alive between checks, any Django
    query in that thread raises SynchronousOnlyOperation — a live
    end-to-end check hit exactly that after the browser returned. Browser
    work must run on ``pool.run()``'s dedicated thread; the main thread
    (Celery task body + Django signal handlers) must stay loop-free.
    """

    def setUp(self):
        self.pool = BrowserPool(starter=lambda: None)
        self.addCleanup(self.pool.shutdown)

    def test_run_executes_on_a_dedicated_thread(self):
        name = self.pool.run(lambda: threading.current_thread().name)
        self.assertIn("browser-driver", name)
        self.assertNotEqual(name, threading.current_thread().name)

    def test_run_returns_results_and_propagates_exceptions(self):
        self.assertEqual(self.pool.run(lambda a, b=0: a + b, 1, b=2), 3)

        def explode():
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            self.pool.run(explode)

    def test_parked_loop_on_driver_thread_never_reaches_main(self):
        # Simulate exactly what sync_playwright().start() leaves behind.
        def park_loop():
            asyncio.events._set_running_loop(asyncio.new_event_loop())
            return threading.current_thread().name

        driver_thread = self.pool.run(park_loop)
        self.assertNotEqual(driver_thread, threading.current_thread().name)

        # Main thread: still no running loop ...
        with self.assertRaises(RuntimeError):
            asyncio.get_running_loop()
        # ... so Django's ORM keeps working after browser work returns.
        self.assertFalse(Monitor.objects.filter(name="xy-z-never").exists())

        # Retire the parked loop on the driver thread (mirrors stop()).
        self.pool.run(lambda: asyncio.events._set_running_loop(None))

    def test_fetch_routes_all_browser_work_through_pool_run(self):
        sentinel = BrowserResult(
            status_code=200,
            response_time_ms=1,
            html="<html></html>",
            screenshot=b"png",
        )
        with mock.patch("monitors.services.browser_fetcher.pool") as fake:
            fake.run.return_value = sentinel
            result = fetch_with_browser("http://93.184.216.34/")
        self.assertIs(result, sentinel)
        self.assertEqual(fake.run.call_count, 1)
        self.assertTrue(callable(fake.run.call_args[0][0]))
        # Recycle, driver start and every page operation moved OFF the
        # main thread with the work itself.
        fake.maybe_recycle.assert_not_called()
        fake.check_context.assert_not_called()


class BrowserPoolLifecycleTests(SimpleTestCase):
    def _pool(self, **kwargs):
        self.log = []
        self.browsers = []
        self.drivers = []

        def starter():
            driver = _FakeDriver(self.log, self.browsers)
            self.drivers.append(driver)
            return driver

        return BrowserPool(starter=starter, **kwargs)

    def test_browser_launches_lazily_on_first_check(self):
        pool = self._pool()
        self.assertEqual(self.browsers, [])  # nothing at construction
        with pool.check_context(navigation_timeout_ms=1000, page_timeout_ms=2000):
            pass
        self.assertEqual(len(self.browsers), 1)
        self.assertEqual(pool.launches, 1)

    def test_fresh_context_per_check_and_always_closed(self):
        pool = self._pool()
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1) as ctx1:
            pass
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1) as ctx2:
            pass
        self.assertIsNot(ctx1, ctx2)  # isolated: never reused
        self.assertTrue(ctx1.closed)
        self.assertTrue(ctx2.closed)
        # Closed even when the check body raises (crash mid-check).
        with self.assertRaises(RuntimeError):
            with pool.check_context(
                navigation_timeout_ms=1, page_timeout_ms=1
            ) as ctx3:
                raise RuntimeError("navigation blew up")
        self.assertTrue(ctx3.closed)

    def test_explicit_launch_flags_and_timeouts(self):
        pool = self._pool()
        with pool.check_context(
            navigation_timeout_ms=12345, page_timeout_ms=6789
        ) as ctx:
            pass
        kwargs = self.drivers[0].chromium_launch_kwargs
        self.assertTrue(kwargs["headless"])
        self.assertIn("--disable-dev-shm-usage", kwargs["args"])
        self.assertEqual(kwargs["timeout"], 30000)  # BROWSER_LAUNCH_TIMEOUT_MS
        # Explicit Playwright timeouts are set on every context.
        self.assertEqual(ctx.default_nav_timeout, 12345)
        self.assertEqual(ctx.default_timeout, 6789)

    def test_recycles_after_max_tasks_and_relaunches(self):
        pool = self._pool(max_tasks=2, max_rss_mb=0)
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        self.assertFalse(self.browsers[0].closed)  # still fine after 2 checks
        pool.maybe_recycle()
        self.assertTrue(self.browsers[0].closed)
        self.assertEqual(pool.recycles, 1)
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        self.assertEqual(len(self.browsers), 2)  # relaunched

    def test_recycles_on_rss_over_threshold(self):
        pool = self._pool(max_tasks=0, max_rss_mb=500)
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        with mock.patch(
            "monitors.services.browser_pool.process_tree_rss_mb",
            return_value=900.0,
        ):
            pool.maybe_recycle()
        self.assertEqual(pool.recycles, 1)
        self.assertTrue(self.browsers[0].closed)

    def test_unreadable_rss_is_fail_safe_not_fatal(self):
        pool = self._pool(max_tasks=0, max_rss_mb=500)
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        with mock.patch(
            "monitors.services.browser_pool.process_tree_rss_mb",
            return_value=None,
        ):
            pool.maybe_recycle()  # must not raise, must not recycle
        self.assertEqual(pool.recycles, 0)
        self.assertTrue(pool.stats()["alive"])

    def test_crashed_browser_restarts_automatically(self):
        pool = self._pool()
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        self.browsers[0].connected = False  # Chromium died between checks
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        self.assertEqual(len(self.browsers), 2)  # fresh browser, no restart needed upstream

    def test_crash_mid_check_tears_down_stale_state(self):
        pool = self._pool()
        with self.assertRaises(RuntimeError):
            with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
                self.browsers[0].connected = False  # dies during the check
                raise RuntimeError("page crashed with the browser")
        self.assertFalse(pool.stats()["alive"])  # torn down, nothing stale
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        self.assertEqual(len(self.browsers), 2)

    def test_shutdown_closes_browser_and_driver(self):
        pool = self._pool()
        with pool.check_context(navigation_timeout_ms=1, page_timeout_ms=1):
            pass
        pool.shutdown()
        self.assertTrue(self.browsers[0].closed)
        self.assertTrue(self.drivers[0].stopped)
        self.assertFalse(pool.stats()["alive"])

    def test_process_tree_rss_reads_proc(self):
        if not os.path.isdir("/proc"):
            self.skipTest("/proc not available on this platform")
        rss = process_tree_rss_mb()
        if rss is None:
            self.skipTest("/proc unreadable here")
        self.assertIsInstance(rss, float)
        self.assertGreater(rss, 0)


# ---------------------------------------------------------------------------
# Error handling: selector ValueErrors -> recorded failure (D-requirements)
# ---------------------------------------------------------------------------


class AdvancedTaskErrorHandlingTests(TestCase):
    def setUp(self):
        from monitors.advanced_tasks import run_advanced_monitor

        self.run = run_advanced_monitor
        self.user = User.objects.create_user(
            email="sel@example.com",
            password="a-strong-password",
        )
        self.monitor = Monitor.objects.create(
            user=self.user,
            name="Selector monitor",
            url="https://example.com",
            check_interval=3600,
            timeout=15,
        )
        notify = mock.patch("notifications.services.dispatch_monitor_event")
        self.notify = notify.start()
        self.addCleanup(notify.stop)

    def _result(self, html):
        return BrowserResult(
            status_code=200,
            response_time_ms=42,
            html=html,
            screenshot=b"",
        )

    def _assert_failed(self, output, needle):
        self.assertEqual(output["status"], "failed")
        self.assertIn(needle, output["error"])
        # Exactly one recorded check — the failure is persisted, silent
        # nothing-happened states are not acceptable.
        checks = MonitorCheck.objects.filter(monitor=self.monitor)
        self.assertEqual(checks.count(), 1)
        check = checks.get()
        self.assertIn(needle, check.error)
        self.assertIsNone(check.status_code)
        self.monitor.refresh_from_db()
        self.assertIsNone(self.monitor.last_success_at)
        self.assertEqual(self.monitor.last_content_hash, "")
        # and no exception escaped the task (calling it would have raised)

    def test_dom_selector_mismatch_is_recorded_failure(self):
        AdvancedMonitorConfig.objects.create(
            monitor=self.monitor,
            mode=AdvancedMonitorConfig.DOM,
            selector="#does-not-exist",
        )
        with mock.patch(
            "monitors.advanced_tasks.fetch_with_browser",
            return_value=self._result("<html><body><p>hi</p></body></html>"),
        ):
            output = self.run(str(self.monitor.id))
        self._assert_failed(output, "DOM selector error")

    def test_price_selector_mismatch_is_recorded_failure(self):
        AdvancedMonitorConfig.objects.create(
            monitor=self.monitor,
            mode=AdvancedMonitorConfig.PRICE,
            selector="body",
            price_selector="#no-price-here",
            price_currency="USD",
        )
        with mock.patch(
            "monitors.advanced_tasks.fetch_with_browser",
            return_value=self._result("<html><body>$9.99</body></html>"),
        ):
            output = self.run(str(self.monitor.id))
        self._assert_failed(output, "Price selector error")

    def test_height_cap_failure_is_recorded(self):
        AdvancedMonitorConfig.objects.create(
            monitor=self.monitor,
            mode=AdvancedMonitorConfig.SCREENSHOT,
            selector="body",
        )
        with mock.patch(
            "monitors.advanced_tasks.fetch_with_browser",
            side_effect=BrowserFetchError("Page height 99999px exceeds cap.", retryable=False),
        ):
            output = self.run(str(self.monitor.id))
        self._assert_failed(output, "exceeds cap")

    def test_success_path_still_records_a_check(self):
        AdvancedMonitorConfig.objects.create(
            monitor=self.monitor,
            mode=AdvancedMonitorConfig.DOM,
            selector="body",
        )
        with mock.patch(
            "monitors.advanced_tasks.fetch_with_browser",
            return_value=self._result("<html><body>hello world</body></html>"),
        ):
            output = self.run(str(self.monitor.id))
        self.assertEqual(output["status"], "success")
        checks = MonitorCheck.objects.filter(monitor=self.monitor)
        self.assertEqual(checks.count(), 1)
        self.assertEqual(checks.get().error, "")
        # First successful check for this mode creates no DOM ChangeDiff
        # (nothing to compare against) and writes no orphan artifact.
        self.assertEqual(
            ChangeDiff.objects.filter(monitor=self.monitor).count(),
            0,
        )


# ---------------------------------------------------------------------------
# Real-Chromium integration (skipped when Chromium is unavailable)
# ---------------------------------------------------------------------------

_REAL_BROWSER = None


def _real_browser_available():
    global _REAL_BROWSER
    if _REAL_BROWSER is None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage"],
                    timeout=30000,
                )
                browser.close()
            _REAL_BROWSER = True
        except Exception:
            _REAL_BROWSER = False
    return _REAL_BROWSER


class _SiteHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence the dev server
        pass

    def do_GET(self):
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = (
            b"<html><body><h1>probe</h1>"
            b"<img src='http://169.254.169.254/latest/meta-data'>"
            b"</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RealChromiumIntegrationTests(SimpleTestCase):
    """Live proofs: interception coverage, isolation, abort wiring,
    non-root launch with --disable-dev-shm-usage (the probe)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _SiteHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        super().tearDownClass()

    def setUp(self):
        if not _real_browser_available():
            raise unittest.SkipTest(
                "Playwright/Chromium unavailable in this container "
                "(expected inside the API image)"
            )
        self.pool = BrowserPool()
        self.addCleanup(self.pool.shutdown)

    def test_chromium_launches_as_non_root_with_dev_shm_flag(self):
        # The probe in setUp already launched Chromium as this uid with
        # --disable-dev-shm-usage; record that this was a non-root run.
        if os.getuid() == 0:
            self.skipTest(
                "running as root; non-root launch is verified in the "
                "browser worker container (uid 10001)"
            )
        self.assertTrue(_real_browser_available())

    def test_fresh_context_per_check_isolates_storage(self):
        with self.pool.check_context(
            navigation_timeout_ms=10000, page_timeout_ms=10000
        ) as ctx1:
            page = ctx1.new_page()
            page.goto(self.base_url + "/", wait_until="domcontentloaded")
            page.evaluate("() => localStorage.setItem('k', 'secret')")
            self.assertEqual(
                page.evaluate("() => localStorage.getItem('k')"),
                "secret",
            )
        with self.pool.check_context(
            navigation_timeout_ms=10000, page_timeout_ms=10000
        ) as ctx2:
            page2 = ctx2.new_page()
            page2.goto(self.base_url + "/", wait_until="domcontentloaded")
            self.assertIsNone(
                page2.evaluate("() => localStorage.getItem('k')")
            )

    def test_cdp_interception_sees_docs_subresources_and_redirect_hops(self):
        from playwright.sync_api import Error as PlaywrightError

        seen = []

        with self.pool.check_context(
            navigation_timeout_ms=10000, page_timeout_ms=10000
        ) as ctx:
            page = ctx.new_page()
            session = ctx.new_cdp_session(page)

            def record(params):
                url = params["request"]["url"]
                seen.append(url)
                if "169.254.169.254" in url:
                    # Fail metadata requests so the test never waits on
                    # an unreachable link-local address.
                    session.send(
                        "Fetch.failRequest",
                        {
                            "requestId": params["requestId"],
                            "errorReason": "BlockedByClient",
                        },
                    )
                else:
                    session.send(
                        "Fetch.continueRequest",
                        {"requestId": params["requestId"]},
                    )

            session.on("Fetch.requestPaused", record)
            session.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

            page.goto(self.base_url + "/", wait_until="domcontentloaded")
            # The metadata SUBRESOURCE reached the handler.
            self.assertTrue(
                any("169.254.169.254" in url for url in seen),
                f"subresource never intercepted: {seen}",
            )
            self.assertIn(self.base_url + "/", seen)

            # The redirect HOP TARGET reaches the handler too — this is
            # exactly what context.route never sees (playwright#34994).
            before = len(seen)
            with self.assertRaises(PlaywrightError):
                page.goto(
                    self.base_url + "/redirect",
                    wait_until="domcontentloaded",
                )
            hops = seen[before:]
            self.assertTrue(
                any("/redirect" in url for url in hops),
                f"redirect source never intercepted: {hops}",
            )
            self.assertTrue(
                any("169.254.169.254" in url for url in hops),
                f"redirect hop target never intercepted: {hops}",
            )

    def test_policy_fails_blocked_subresource_live(self):
        # Live wiring proof: document allowed (local origin override),
        # the metadata IMG request hits the REAL RequestPolicy.handle_cdp
        # and is failed at request level without breaking the document.
        class _MetadataBlockedPolicy(RequestPolicy):
            def validate(self, url):
                if "169.254.169.254" in url:
                    raise SecurityError("Blocked destination.")
                # Local test origin (high port) intentionally allowed:
                # the validation RULES are unit-tested separately; this
                # test proves interception + fail wiring end to end.

        policy = _MetadataBlockedPolicy(AdvancedMonitorConfig.DOM)
        with self.pool.check_context(
            navigation_timeout_ms=10000, page_timeout_ms=10000
        ) as ctx:
            page = ctx.new_page()
            session = ctx.new_cdp_session(page)
            session.on(
                "Fetch.requestPaused",
                lambda params: policy.handle_cdp(session, params),
            )
            session.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

            page.goto(self.base_url + "/", wait_until="domcontentloaded")
            for _ in range(20):
                if policy.ssrf_blocked >= 1:
                    break
                page.wait_for_timeout(100)
            self.assertGreaterEqual(policy.ssrf_blocked, 1)
            # The document still rendered: blocking the image is safe.
            self.assertIn("probe", page.content())

    def test_ssrf_policy_fails_private_document_live(self):
        from playwright.sync_api import Error as PlaywrightError

        policy = RequestPolicy(AdvancedMonitorConfig.DOM)
        with self.pool.check_context(
            navigation_timeout_ms=10000, page_timeout_ms=10000
        ) as ctx:
            page = ctx.new_page()
            session = ctx.new_cdp_session(page)
            session.on(
                "Fetch.requestPaused",
                lambda params: policy.handle_cdp(session, params),
            )
            session.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

            with self.assertRaises(PlaywrightError):
                page.goto(self.base_url + "/", wait_until="domcontentloaded")
            self.assertGreaterEqual(policy.ssrf_blocked, 1)

    def test_redirect_hop_to_private_is_blocked_at_request_level(self):
        # THE redirect requirement: a302 whose Location points at a
        # metadata/private host must never be fetched by Chromium.
        # context.route cannot see this hop (upstream playwright#34994,
        # verified in-container) — CDP Fetch interception does.
        from playwright.sync_api import Error as PlaywrightError

        class _LocalOriginPolicy(RequestPolicy):
            def validate(self, url):
                if "127.0.0.1" in url:
                    return  # allow the local test origin (high port)
                super().validate(url)  # REAL rules for every other URL

        policy = _LocalOriginPolicy(AdvancedMonitorConfig.DOM)
        with self.pool.check_context(
            navigation_timeout_ms=10000, page_timeout_ms=10000
        ) as ctx:
            page = ctx.new_page()
            session = ctx.new_cdp_session(page)
            session.on(
                "Fetch.requestPaused",
                lambda params: policy.handle_cdp(session, params),
            )
            session.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

            with self.assertRaises(PlaywrightError):
                page.goto(
                    self.base_url + "/redirect",
                    wait_until="domcontentloaded",
                )
            # The source (127.0.0.1) was allowed by the test override, so
            # the ONLY blocked request is the hop to 169.254.169.254 —
            # failed before Chromium ever connected to it.
            self.assertGreaterEqual(policy.ssrf_blocked, 1)
