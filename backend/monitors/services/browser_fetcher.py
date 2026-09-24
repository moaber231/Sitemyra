"""Playwright-backed fetch with per-request SSRF interception.

Docs: docs/BROWSER-WORKER.md; plan D3 (lifecycle), D4 (SSRF), D5
(resource blocking).

- Browser lifecycle lives in :mod:`browser_pool` — one Chromium per
  prefork child, fresh incognito context per check, recycle by task
  count / RSS, restart on crash.
- EVERY request the page makes — the document, subresources (img/media/
  font/script/css), XHR/fetch, JS-driven navigations, and EACH
  HTTP-3xx redirect hop — passes through :class:`RequestPolicy`, which
  re-validates scheme, credentials, port, host blocklist, IP literals
  and (cached, budgeted) DNS results. Validation failure FAILS the
  request (fail-closed, same posture as the HTTP engine's
  ``validate_url``).
- Interception lives on the CDP ``Fetch`` domain
  (``Fetch.requestPaused``), NOT ``context.route``: Playwright's route
  handlers are never invoked for requests created by following an HTTP
  redirect (upstream issue microsoft/playwright#34994, verified
  in-container), so ``context.route`` would let a 3xx Location pointing
  at a private host be fetched without validation. Fetch.requestPaused
  fires for every request including redirect hops (verified
  in-container); requests are continued VERBATIM — Chromium's cookie
  jar, redirect and streaming behavior are untouched (nothing is
  proxied or re-fetched, so screenshot fidelity cannot drift).
- Residual gaps, documented honestly (docs/BROWSER-WORKER.md):
  DNS-rebinding TOCTOU (a safe IP at validation time that rebinds to a
  private IP at connect time — full mitigation needs an egress proxy)
  and WebSocket handshakes, which Fetch does not pause (verified
  in-container).
- The final (post-redirect) URL is re-validated as a belt-and-braces
  check after navigation.
- Resource blocking by monitor mode (D5): SCREENSHOT mode NEVER blocks
  (visual fidelity requirement, enforced here + unit test); dom/price
  block images/media/fonts only — HTML, CSS, JS and XHR always load —
  unless BROWSER_BLOCK_RESOURCES overrides (incl. "none").
- Wait strategy: ``goto(wait_until="load")`` + a bounded best-effort
  "networkidle" settle (BROWSER_IDLE_SETTLE_MS). Blind networkidle (the
  old behavior) made chatty pages burn the entire navigation timeout and
  then FAIL five retries later; quiet pages reach networkidle inside the
  settle window and render exactly as before, while chatty pages now
  proceed deterministically after the bounded window.
- SCREENSHOT_MAX_HEIGHT_PX (0 = disabled): when the page exceeds the
  cap the check FAILS EXPLICITLY — never a silent crop and never a
  silent discard.
"""

import logging
import os
import time
from dataclasses import dataclass
from time import perf_counter

from ..models import AdvancedMonitorConfig
from .browser_pool import pool
from .fetcher import (
    FetchError,
    SecurityError,
    _resolve_and_validate_host,
    validate_url,
    validate_url_structure,
)

logger = logging.getLogger(__name__)

# BROWSER_BLOCK_RESOURCES token -> Playwright resource_type.
_BLOCKING_TOKENS = {
    "images": "image",
    "image": "image",
    "media": "media",
    "fonts": "font",
    "font": "font",
}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def resource_types_to_block(mode: str) -> frozenset:
    """Which Playwright resource types this monitor mode may abort.

    SCREENSHOT mode NEVER blocks anything — fidelity requires every
    resource (hard requirement, enforced by test).
    dom/price block images/media/fonts by default (visible layout text
    and DOM structure do not depend on them); HTML/CSS/JS/XHR always
    load. ``BROWSER_BLOCK_RESOURCES`` overrides the dom/price default:
    a comma list ("images,media,fonts"), a subset ("fonts"), or
    "none"/""/off to disable blocking entirely.
    """
    if mode == AdvancedMonitorConfig.SCREENSHOT:
        return frozenset()
    raw = (os.getenv("BROWSER_BLOCK_RESOURCES", "images,media,fonts") or "").strip().lower()
    if raw in {"", "none", "off", "0"}:
        return frozenset()
    out = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        mapped = _BLOCKING_TOKENS.get(token)
        if mapped:
            out.add(mapped)
        else:
            logger.warning(
                "BROWSER_BLOCK_RESOURCES: unknown token %r ignored", token
            )
    return frozenset(out)


class RequestPolicy:
    """Per-check interception policy: SSRF validation + cost blocking.

    Created fresh for every check (DNS cache and lookup budget are
    per-check, so no state ever leaks between monitors/users).
    """

    def __init__(self, mode: str):
        self.mode = mode
        self.block_types = resource_types_to_block(mode)
        self.max_dns = _env_int("BROWSER_MAX_DNS_LOOKUPS", 200)
        self.dns_ttl = _env_int("BROWSER_DNS_CACHE_TTL_S", 60)
        self._dns_cache: dict[str, float] = {}
        self._dns_used = 0
        self.ssrf_blocked = 0
        self.cost_blocked = 0

    def validate(self, url: str) -> None:
        """Structure checks per URL + DNS validation per host (cached,
        budgeted). Raises SecurityError/FetchError on any violation."""
        parsed = validate_url_structure(url)
        hostname = parsed.hostname
        key = (hostname or "").lower().rstrip(".")
        now = time.monotonic()
        hit = self._dns_cache.get(key)
        if hit is not None and now - hit <= self.dns_ttl:
            return
        if self._dns_used >= self.max_dns:
            raise SecurityError("Per-check DNS validation budget exceeded.")
        self._dns_used += 1
        # Shared DNS + IP-literal/blocklist validation (fail-closed).
        _resolve_and_validate_host(hostname)
        self._dns_cache[key] = now

    def decide(self, url: str, resource_type: str) -> str:
        """Pure policy decision for ONE request.

        Returns ``"continue"``, ``"ssrf"`` (validation failed) or
        ``"cost"`` (the mode's resource blocking). Fail-closed: any
        validation doubt is ``"ssrf"``. ``resource_type`` is the CDP
        ``Fetch.requestPaused`` value, lower-cased (image/media/font/...).
        """
        try:
            self.validate(url)
        except (SecurityError, FetchError) as exc:
            self.ssrf_blocked += 1
            logger.warning(
                "browser request blocked by SSRF policy: %s (%s)",
                url[:200],
                exc,
            )
            return "ssrf"
        if resource_type in self.block_types:
            self.cost_blocked += 1
            return "cost"
        return "continue"

    def handle_cdp(self, session, params) -> None:
        """CDP ``Fetch.requestPaused`` handler: decide, then settle the
        paused request.

        Unexpected errors fail CLOSED — leaving a request paused would
        hang the page until the Celery hard time limit, so every path
        ends in exactly one continue/fail call (and a failure to settle
        a already-closed target is logged, never raised).
        """
        request_id = params.get("requestId")
        url = params.get("request", {}).get("url", "")
        resource_type = str(params.get("resourceType", "Other")).lower()
        try:
            action = self.decide(url, resource_type)
        except Exception:
            logger.exception(
                "interception handler error; failing request [url=%s]",
                url[:200],
            )
            action = "ssrf"
        try:
            if action == "continue":
                session.send(
                    "Fetch.continueRequest",
                    {"requestId": request_id},
                )
            else:
                session.send(
                    "Fetch.failRequest",
                    {
                        "requestId": request_id,
                        "errorReason": "BlockedByClient",
                    },
                )
        except Exception:
            logger.debug(
                "could not settle paused request (target likely closed)",
                exc_info=True,
            )


@dataclass
class BrowserResult:
    status_code: int
    response_time_ms: int
    html: str
    screenshot: bytes


class BrowserFetchError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def fetch_with_browser(
    url: str,
    timeout_seconds: int = 30,
    mode: str = AdvancedMonitorConfig.SCREENSHOT,
) -> BrowserResult:
    # Same SSRF guard as the lightweight HTTP engine, BEFORE a browser
    # exists: loopback, private/link-local/multicast/reserved IPs, cloud
    # metadata hosts, credentialed URLs and non-standard ports.
    # Non-retryable: re-resolving would fail identically on every retry.
    try:
        validate_url(url)
    except SecurityError as exc:
        raise BrowserFetchError(
            f"Blocked destination: {exc}",
            retryable=False,
        ) from exc
    except FetchError as exc:
        raise BrowserFetchError(
            str(exc),
            retryable=False,
        ) from exc

    # Explicit budgets (env): no Playwright operation may block forever.
    navigation_timeout_ms = max(1000, int(timeout_seconds) * 1000)
    page_timeout_ms = _env_int("BROWSER_PAGE_OP_TIMEOUT_MS", 30000)
    idle_settle_ms = _env_int("BROWSER_IDLE_SETTLE_MS", 3000)
    max_height_px = _env_int("SCREENSHOT_MAX_HEIGHT_PX", 0)
    capture_screenshot = mode == AdvancedMonitorConfig.SCREENSHOT

    policy = RequestPolicy(mode)

    started = perf_counter()

    def _browser_work():
        """ALL Playwright work — executed on the pool's driver thread.

        Playwright's sync API parks an asyncio loop as *running* in the
        thread that starts the driver (cleared only by ``stop()``), and
        Django refuses ORM access wherever it sees a running loop —
        while every DB write of this check happens in the Celery main
        thread AFTER this returns. Division: main thread = URL
        validation + DB, driver thread = browser (Phase G live fix;
        docs/BROWSER-WORKER.md).
        """
        pool.maybe_recycle()

        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        with pool.check_context(
            navigation_timeout_ms=navigation_timeout_ms,
            page_timeout_ms=page_timeout_ms,
        ) as context:
            page = context.new_page()
            # Interception on the CDP Fetch domain (see module
            # docstring): fires for EVERY request including HTTP-3xx
            # redirect hops, which context.route never sees
            # (microsoft/playwright#34994, verified in-container).
            # Installed before the first navigation is issued.
            session = context.new_cdp_session(page)
            session.on(
                "Fetch.requestPaused",
                lambda params: policy.handle_cdp(session, params),
            )
            session.send(
                "Fetch.enable",
                {"patterns": [{"urlPattern": "*"}]},
            )

            try:
                response = page.goto(
                    url,
                    wait_until="load",
                    timeout=navigation_timeout_ms,
                )
            except PlaywrightTimeoutError as exc:
                raise BrowserFetchError(
                    f"Browser navigation timed out after {timeout_seconds}s.",
                    retryable=True,
                ) from exc

            # Bounded best-effort idle settle (see module docstring):
            # quiet pages behave exactly like networkidle, chatty pages
            # proceed after the window instead of failing the check.
            try:
                page.wait_for_load_state("networkidle", timeout=idle_settle_ms)
            except PlaywrightTimeoutError:
                logger.debug(
                    "networkidle settle window elapsed; proceeding [url=%s]",
                    url[:200],
                )

            # Belt-and-braces: the FINAL URL (post-redirect) must pass
            # the same validation, even though each hop was intercepted.
            try:
                validate_url(page.url)
            except (SecurityError, FetchError) as exc:
                raise BrowserFetchError(
                    f"Blocked redirect destination: {exc}",
                    retryable=False,
                ) from exc

            if response is None:
                raise BrowserFetchError(
                    "Target page returned no response.",
                    retryable=True,
                )

            status_code = response.status

            if status_code == 429:
                raise BrowserFetchError(
                    "Target returned HTTP 429 Too Many Requests.",
                    retryable=True,
                )

            if status_code in {500, 502, 503, 504}:
                raise BrowserFetchError(
                    f"Target returned HTTP {status_code}.",
                    retryable=True,
                )

            if status_code in {401, 403, 404}:
                raise BrowserFetchError(
                    f"Target returned HTTP {status_code}.",
                    retryable=False,
                )

            if capture_screenshot:
                if max_height_px > 0:
                    height = page.evaluate(
                        "() => document.documentElement.scrollHeight"
                    )
                    if isinstance(height, (int, float)) and int(height) > max_height_px:
                        raise BrowserFetchError(
                            f"Page height {int(height)}px exceeds "
                            f"SCREENSHOT_MAX_HEIGHT_PX={max_height_px}px; "
                            "refusing to capture a cropped screenshot "
                            "(set SCREENSHOT_MAX_HEIGHT_PX=0 to disable).",
                            retryable=False,
                        )
                screenshot = page.screenshot(
                    full_page=True,
                    type="png",
                )
            else:
                # dom/price never read the screenshot: skip the full-page
                # render + PNG encode entirely.
                screenshot = b""

            elapsed_ms = int((perf_counter() - started) * 1000)
            html = page.content()

        return BrowserResult(
            status_code=status_code,
            response_time_ms=elapsed_ms,
            html=html,
            screenshot=screenshot,
        )

    try:
        return pool.run(_browser_work)
    except BrowserFetchError:
        raise
    except Exception as exc:
        raise BrowserFetchError(
            f"Browser fetch failed: {exc}",
            retryable=True,
        ) from exc
