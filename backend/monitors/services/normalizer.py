import hashlib
import re

from bs4 import BeautifulSoup


def normalize_html(content: bytes, content_type: str) -> str:
    encoding = "utf-8"

    match = re.search(
        r"charset=([^\s;]+)",
        content_type,
        flags=re.IGNORECASE,
    )

    if match:
        encoding = match.group(1).strip("\"'")

    try:
        html = content.decode(encoding, errors="replace")
    except (LookupError, UnicodeError):
        html = content.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")

    for element in soup(
        ["script", "style", "noscript", "template"]
    ):
        element.decompose()

    text = soup.get_text(" ", strip=True)

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_content(content: bytes, content_type: str) -> str:
    content_type_lower = content_type.lower()

    if (
        "text/html" in content_type_lower
        or "application/xhtml+xml" in content_type_lower
        or not content_type_lower
    ):
        return normalize_html(content, content_type)

    try:
        return content.decode("utf-8", errors="replace").strip()
    except UnicodeDecodeError:
        return ""


def content_hash(content: bytes, content_type: str) -> str:
    normalized = normalize_content(
        content,
        content_type,
    )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()
