"""Single-browser lifecycle for the dedicated prefork browser worker.

Docs: docs/BROWSER-WORKER.md, docs/OPTIMIZATION-PLAN.md (D3).

Rules enforced here:
- ONE Chromium process per prefork worker child, started lazily on first
  use — never pooled across processes or threads (Playwright's sync API
  is greenlet-bound to the process that launched it; the worker runs
  prefork, concurrency 1).
- Every check gets a FRESH incognito BrowserContext (cookies,
  localStorage, sessionStorage and auth state are never shared between
  monitors, checks or users). Callers close it via the context manager.
- Chromium is recycled after BROWSER_MAX_TASKS checks and, optionally,
  when the process-tree RSS exceeds BROWSER_MAX_RSS_MB (checked between
  checks, never mid-check; the Celery hard time limit covers runaways).
- A crashed/closed browser is detected (``is_connected``) and relaunched
  automatically on the next check; a crash mid-check tears the browser
  down immediately so nothing stale survives.
- Launch flags always include ``--disable-dev-shm-usage``: Chromium
  writes to /tmp instead of /dev/shm, which Docker caps at 64 MB by
  default (verified in-container — see BROWSER-WORKER.md).

RSS measurement reads /proc. If it cannot be read (non-Linux, restricted
permissions) the RSS recycle is SKIPPED with a single warning — task-
count recycling and the Celery hard time limit still bound the browser
(fail-safe heuristic: never fail loud on an unreadable number).
"""

import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Chromium in Docker: never rely on /dev/shm (64 MB default cap).
LAUNCH_ARGS = ("--disable-dev-shm-usage",)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def process_tree_rss_mb(pid: int | None = None) -> float | None:
    """Sum VmRSS (MB) of ``pid`` and all its descendants via /proc.

    Returns None when anything is unreadable (fail-safe: callers skip
    RSS-based recycling instead of guessing).
    """
    root = os.getpid() if pid is None else pid
    try:
        children: dict[int, list[int]] = {}
        rss_kb: dict[int, float] = {}
        with os.scandir("/proc") as entries:
            pids = [e.name for e in entries if e.name.isdigit()]
        for name in pids:
            try:
                with open(f"/proc/{name}/stat", "rb") as fh:
                    stat = fh.read().decode("utf-8", "replace")
                # comm may contain spaces/parens: split after last ')'.
                fields = stat.rsplit(")", 1)[1].split()
                ppid = int(fields[1])
                with open(f"/proc/{name}/status", "rb") as fh:
                    kb = 0.0
                    for line in fh:
                        if line.startswith(b"VmRSS:"):
                            kb = float(line.split()[1])
                            break
                pid_num = int(name)
                children.setdefault(ppid, []).append(pid_num)
                rss_kb[pid_num] = kb
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        return None

    total_kb = 0.0
    seen: set[int] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        total_kb += rss_kb.get(current, 0.0)
        stack.extend(children.get(current, ()))

    if root not in seen:
        return None  # /proc readable but not our own process: fail safe
    return total_kb / 1024.0


def _playwright_starter():
    """Start a Playwright sync driver. Imported lazily so this module
    itself never requires Playwright (API container safety)."""
    from playwright.sync_api import sync_playwright

    return sync_playwright().start()


class BrowserPool:
    """Per-child browser singleton — NOT a cross-process pool."""

    def __init__(
        self,
        starter=None,
        *,
        max_tasks: int | None = None,
        max_rss_mb: int | None = None,
        launch_timeout_ms: int | None = None,
    ):
        self._starter = starter or _playwright_starter
        self.max_tasks = (
            max_tasks
            if max_tasks is not None
            else _env_int("BROWSER_MAX_TASKS", 50)
        )
        self.max_rss_mb = (
            max_rss_mb
            if max_rss_mb is not None
            else _env_int("BROWSER_MAX_RSS_MB", 1024)
        )
        self.launch_timeout_ms = (
            launch_timeout_ms
            if launch_timeout_ms is not None
            else _env_int("BROWSER_LAUNCH_TIMEOUT_MS", 30000)
        )
        self._driver = None
        self._browser = None
        self._checks_in_life = 0
        self._rss_warned = False
        self._driver_executor = None
        self.launches = 0
        self.recycles = 0

    # -- lifecycle -------------------------------------------------------

    def _start(self) -> None:
        driver = self._starter()
        try:
            browser = driver.chromium.launch(
                headless=True,
                args=list(LAUNCH_ARGS),
                timeout=self.launch_timeout_ms,
            )
        except BaseException:
            try:
                driver.stop()
            except Exception:
                logger.debug("driver cleanup after failed launch", exc_info=True)
            raise
        self._driver = driver
        self._browser = browser
        self._checks_in_life = 0
        self.launches += 1
        logger.info(
            "browser launched [launches=%d rss_mb=%s]",
            self.launches,
            process_tree_rss_mb(),
        )

    def _ensure(self):
        browser = self._browser
        if browser is not None:
            try:
                if browser.is_connected():
                    return browser
            except Exception:
                pass
            self._teardown(reason="stale-browser")
        self._start()
        return self._browser

    def _teardown(self, reason: str) -> None:
        browser, self._browser = self._browser, None
        driver, self._driver = self._driver, None
        if browser is not None:
            try:
                browser.close()
            except Exception:
                logger.debug("browser close failed (%s)", reason, exc_info=True)
        if driver is not None:
            try:
                driver.stop()
            except Exception:
                logger.debug("driver stop failed (%s)", reason, exc_info=True)
        self._checks_in_life = 0

    def shutdown(self) -> None:
        """Full teardown (used by tests and clean worker shutdown)."""
        executor, self._driver_executor = self._driver_executor, None
        if executor is None:
            self._teardown(reason="shutdown")
            return
        # Driver objects are thread-bound: stop them on the thread that
        # started them, then retire that thread.
        try:
            executor.submit(self._teardown, "shutdown").result(timeout=60)
        except Exception:
            logger.debug(
                "driver-thread teardown failed; falling back to a "
                "direct stop",
                exc_info=True,
            )
            self._teardown(reason="shutdown")
        executor.shutdown(wait=True, cancel_futures=True)

    def run(self, func, *args, **kwargs):
        """Execute ``func`` on the pool's single dedicated driver thread.

        Returns its result, re-raising any exception it raised there.

        Why this exists (Phase G live discovery — docs/BROWSER-WORKER.md):
        Playwright's sync API parks an asyncio event loop as *running* in
        the thread that called ``sync_playwright().start()`` — the
        registry entry clears only on ``stop()``. The pool deliberately
        keeps the driver alive between checks, so any Django ORM call in
        that thread afterwards raises ``SynchronousOnlyOperation`` — and
        every check writes its ``MonitorCheck`` row AFTER the browser
        returns. Division of labour: the Celery main thread does all DB
        work and never enters Playwright; this thread does all Playwright
        work and never touches Django. ``max_workers=1`` yields both
        properties at once — one persistent thread for the driver's whole
        lifetime (Playwright's greenlet/driver affinity) and naturally
        serialized checks (worker concurrency is 1 anyway).
        """
        if self._driver_executor is None:
            from concurrent.futures import ThreadPoolExecutor

            self._driver_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="browser-driver"
            )
        return self._driver_executor.submit(func, *args, **kwargs).result()

    # -- recycling -------------------------------------------------------

    def maybe_recycle(self) -> None:
        """Between-check housekeeping: recycle by task count or RSS.

        Never called mid-check. RSS is a heuristic: unreadable -> skip
        (single warning), over threshold -> recycle.
        """
        if self._browser is None:
            return
        reason = None
        if self.max_tasks > 0 and self._checks_in_life >= self.max_tasks:
            reason = f"task_count={self._checks_in_life}>={self.max_tasks}"
        elif self.max_rss_mb > 0:
            rss = process_tree_rss_mb()
            if rss is None:
                if not self._rss_warned:
                    logger.warning(
                        "process RSS unreadable; skipping RSS-based browser "
                        "recycle (task-count recycle and Celery hard limit "
                        "still bound the browser)"
                    )
                    self._rss_warned = True
            elif rss > self.max_rss_mb:
                reason = f"rss={rss:.0f}MB>max_rss={self.max_rss_mb}MB"
        if reason:
            self.recycle(reason)

    def recycle(self, reason: str) -> None:
        self.recycles += 1
        logger.info("recycling browser (%s)", reason)
        self._teardown(reason=reason)

    # -- per-check context ----------------------------------------------

    @contextmanager
    def check_context(
        self,
        *,
        navigation_timeout_ms: int,
        page_timeout_ms: int,
    ):
        """Fresh incognito context for ONE check; closed in finally.

        Explicit navigation/page-op timeouts are set on the context so no
        Playwright operation can block indefinitely — the Celery hard
        limit stays the final kill switch behind these.
        """
        browser = self._ensure()
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
        )
        context.set_default_navigation_timeout(navigation_timeout_ms)
        context.set_default_timeout(page_timeout_ms)
        try:
            yield context
        except BaseException:
            # Crash detection: a dead browser must not linger as "live".
            try:
                alive = self._browser is not None and self._browser.is_connected()
            except Exception:
                alive = False
            if not alive:
                self._teardown(reason="crash-during-check")
            raise
        finally:
            try:
                context.close()
            except Exception:
                logger.debug(
                    "context close failed (browser likely recycled)",
                    exc_info=True,
                )
            self._checks_in_life += 1

    # -- diagnostics -----------------------------------------------------

    def stats(self) -> dict:
        alive = False
        if self._browser is not None:
            try:
                alive = self._browser.is_connected()
            except Exception:
                alive = False
        return {
            "alive": alive,
            "launches": self.launches,
            "recycles": self.recycles,
            "checks_in_life": self._checks_in_life,
            "max_tasks": self.max_tasks,
            "max_rss_mb": self.max_rss_mb,
        }


# Module-level singleton: every prefork child gets its OWN copy after
# fork; only task execution (in the child) ever touches it — the worker
# parent never launches a browser.
pool = BrowserPool()
