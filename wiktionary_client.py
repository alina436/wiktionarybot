# wiktionary.py
import requests
import asyncio
from config import HEADERS


class PageNotFoundError(Exception):
    """Raised when Wiktionary has no page for the requested word."""
    def __init__(self, word: str):
        self.word = word
        super().__init__(f"Wiktionary has no page for '{word}'.")


def _raise_for_api_error(error: dict, word: str) -> None:
    if error.get("code") == "missingtitle":
        raise PageNotFoundError(word)
    raise ValueError(f"Wiktionary: {error.get('info', 'unknown error')}")


def _get_sections_sync(word: str, api_url: str) -> list:
    params = {
        "action": "parse",
        "format": "json",
        "page": word,
        "prop": "sections",
        "redirects": 1,
    }
    r = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        _raise_for_api_error(data["error"], word)
    return data["parse"]["sections"]

def _fetch_section_wikitext_sync(word: str, section_index: str, api_url: str) -> str:
    params = {
        "action": "parse",
        "format": "json",
        "page": word,
        "prop": "wikitext",
        "section": section_index,
        "redirects": 1,
    }
    r = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        _raise_for_api_error(data["error"], word)
    return data["parse"]["wikitext"]["*"]

async def get_sections(word: str, api_url: str) -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_sections_sync, word, api_url)

async def fetch_section_wikitext(word: str, section_index: str, api_url: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_section_wikitext_sync, word, section_index, api_url)