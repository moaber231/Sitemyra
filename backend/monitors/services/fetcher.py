import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


USER_AGENT = "SitemyraMonitor/1.0"
MAX_RESPONSE_SIZE = 10 * 1024 * 1024
MAX_REDIRECTS = 5


class FetchError(Exception):
    pass


class SecurityError(FetchError):
    pass


@dataclass
class FetchResult:
    status_code: int | None
    response_time_ms: int | None
    content: bytes
    content_type: str
    error: str = ""


def _is_blocked_ip(ip: str) -> bool:
    address = ipaddress.ip_address(ip)

    # IPv4-mapped IPv6 (::ffff:127.0.0.1, ::ffff:10.0.0.1, ...) must be
    # judged by its INNER IPv4 address: the is_* flags on an IPv6Address
    # do not consult the mapping on all Python versions, which would
    # re-open the loopback/private bypass.
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped

    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
        or address.is_reserved
        or address.is_multicast
    )


def _resolve_and_validate_host(hostname: str) -> None:
    if not hostname:
        raise SecurityError("Invalid hostname.")

    lowered = hostname.lower().rstrip(".")

    blocked_hostnames = {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
    }

    if lowered in blocked_hostnames:
        raise SecurityError("Blocked destination.")

    try:
        direct_ip = ipaddress.ip_address(lowered)
    except ValueError:
        direct_ip = None

    if direct_ip is not None:
        if _is_blocked_ip(str(direct_ip)):
            raise SecurityError("Blocked destination.")
        return

    try:
        results = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        raise FetchError("DNS resolution failed.")

    addresses = {
        result[4][0]
        for result in results
        if result[4]
    }

    if not addresses:
        raise FetchError("DNS resolution failed.")

    for ip in addresses:
        if _is_blocked_ip(ip):
            raise SecurityError("Blocked destination.")


def validate_url_structure(url: str):
    """Static (DNS-free) URL checks shared by the HTTP engine and the
    browser request interceptor: scheme, host, credentials, port.

    Returns the parsed URL; raises SecurityError on any violation.

    NOTE: ``urlparse().port`` raises ``ValueError`` for out-of-range
    ports (e.g. ``:99999``). That must surface as a SecurityError here —
    an unhandled ValueError used to escape both engines and crash the
    monitor task instead of recording a blocked destination.
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() not in {"http", "https"}:
        raise SecurityError("Only HTTP and HTTPS URLs are supported.")

    if not parsed.hostname:
        raise SecurityError("Invalid URL.")

    if parsed.username or parsed.password:
        raise SecurityError("URLs containing credentials are not supported.")

    try:
        port = parsed.port
    except ValueError:
        raise SecurityError("Invalid URL port.")

    if port is not None and port not in {80, 443}:
        raise SecurityError("Only ports 80 and 443 are supported.")

    return parsed


def validate_url(url: str) -> None:
    parsed = validate_url_structure(url)
    _resolve_and_validate_host(parsed.hostname)


def _validate_redirect(response: httpx.Response) -> None:
    location = response.headers.get("location")

    if not location:
        return

    redirected = response.url.join(location)

    validate_url(str(redirected))


def fetch_url(url: str, timeout_seconds: int) -> FetchResult:
    validate_url(url)

    timeout = httpx.Timeout(
        connect=min(timeout_seconds, 30),
        read=timeout_seconds,
        write=timeout_seconds,
        pool=timeout_seconds,
    )

    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
    )

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            limits=limits,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.8",
            },
        ) as client:

            current_url = url

            for _ in range(MAX_REDIRECTS + 1):
                validate_url(current_url)

                start = time.monotonic()

                with client.stream("GET", current_url) as response:
                    elapsed_ms = int(
                        (__import__("time").monotonic() - start) * 1000
                    )

                    if response.is_redirect:
                        _validate_redirect(response)

                        location = response.headers.get("location")

                        if not location:
                            raise FetchError("Redirect without location.")

                        current_url = str(response.url.join(location))
                        continue

                    content_length = response.headers.get("content-length")

                    if content_length:
                        try:
                            if int(content_length) > MAX_RESPONSE_SIZE:
                                raise FetchError("Response too large.")
                        except ValueError:
                            pass

                    chunks = []
                    total = 0

                    for chunk in response.iter_bytes():
                        total += len(chunk)

                        if total > MAX_RESPONSE_SIZE:
                            raise FetchError("Response too large.")

                        chunks.append(chunk)

                    content = b"".join(chunks)

                    return FetchResult(
                        status_code=response.status_code,
                        response_time_ms=elapsed_ms,
                        content=content,
                        content_type=response.headers.get(
                            "content-type",
                            "",
                        ),
                    )

            raise FetchError("Too many redirects.")

    except SecurityError:
        raise
    except FetchError:
        raise
    except httpx.TimeoutException:
        raise FetchError("Connection timeout.")
    except httpx.ConnectError:
        raise FetchError("Connection failed.")
    except httpx.InvalidURL:
        raise FetchError("Invalid URL.")
    except httpx.HTTPError:
        raise FetchError("HTTP request failed.")
    except Exception:
        raise FetchError("Unexpected network error.")
