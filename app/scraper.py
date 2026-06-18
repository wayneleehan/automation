"""Fetch webpages and extract readable article content."""

from typing import TypedDict

import requests
import trafilatura
from bs4 import BeautifulSoup


REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = "chat-to-obsidian/0.1"


class ScrapeResult(TypedDict):
    """Stable result shape for webpage extraction."""

    url: str
    title: str
    text: str
    success: bool
    error: str | None


def _extract_with_beautifulsoup(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    content = soup.find("article") or soup.find("main") or soup.body or soup
    text = content.get_text(" ", strip=True)
    return title, text


def fetch_webpage_content(url: str) -> ScrapeResult:
    """Fetch a URL, preferring Trafilatura with a BeautifulSoup fallback."""

    errors: list[str] = []

    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.bare_extraction(
                downloaded,
                url=url,
                with_metadata=True,
                include_comments=False,
                as_dict=True,
            )
            if extracted and str(extracted.get("text", "")).strip():
                return {
                    "url": url,
                    "title": str(extracted.get("title") or "Untitled"),
                    "text": str(extracted["text"]).strip(),
                    "success": True,
                    "error": None,
                }
            errors.append("Trafilatura could not extract readable text.")
        else:
            errors.append("Trafilatura could not download the webpage.")
    except Exception as exc:
        errors.append(f"Trafilatura failed: {exc}")

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        title, text = _extract_with_beautifulsoup(response.text)

        if not text:
            errors.append("BeautifulSoup could not extract readable text.")
        else:
            return {
                "url": url,
                "title": title or "Untitled",
                "text": text,
                "success": True,
                "error": None,
            }
    except requests.RequestException as exc:
        errors.append(f"Fallback request failed: {exc}")
    except Exception as exc:
        errors.append(f"BeautifulSoup fallback failed: {exc}")

    return {
        "url": url,
        "title": "",
        "text": "",
        "success": False,
        "error": " ".join(errors),
    }
