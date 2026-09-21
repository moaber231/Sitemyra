from dataclasses import dataclass
from time import perf_counter

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .fetcher import FetchError, SecurityError, validate_url


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
) -> BrowserResult:
    # Same SSRF guard as the lightweight HTTP engine: block loopback,
    # private/link-local/multicast/reserved IPs, cloud metadata hosts,
    # credentialed URLs, and non-standard ports — BEFORE a browser exists.
    # Non-retryable: re-resolving would fail identically on every retry.
    # (Residual DNS-rebinding gap between validation and navigation is
    # accepted; full mitigation would require an egress proxy.)
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

    timeout_ms = timeout_seconds * 1000
    started = perf_counter()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)

            try:
                page = browser.new_page(
                    viewport={
                        "width": 1440,
                        "height": 900,
                    },
                )

                try:
                    response = page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=timeout_ms,
                    )
                except PlaywrightTimeoutError as exc:
                    raise BrowserFetchError(
                        f"Browser navigation timed out after {timeout_seconds}s.",
                        retryable=True,
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

                screenshot = page.screenshot(
                    full_page=True,
                    type="png",
                )

                elapsed_ms = int(
                    (perf_counter() - started) * 1000
                )

                return BrowserResult(
                    status_code=status_code,
                    response_time_ms=elapsed_ms,
                    html=page.content(),
                    screenshot=screenshot,
                )

            finally:
                browser.close()

    except BrowserFetchError:
        raise
    except Exception as exc:
        raise BrowserFetchError(
            f"Browser fetch failed: {exc}",
            retryable=True,
        ) from exc
