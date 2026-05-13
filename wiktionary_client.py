# wiktionary_client.py
import aiohttp
from config import HEADERS

# One session shared for the bot's lifetime, set in bot.py on startup
_session: aiohttp.ClientSession | None = None

def set_session(session: aiohttp.ClientSession) -> None:
    global _session
    _session = session

def _get_session() -> aiohttp.ClientSession:
    if _session is None:
        raise RuntimeError("HTTP session not initialised — call set_session() first")
    return _session

async def get_sections(word: str, api_url: str) -> list:
    params = {
        "action": "parse",
        "format": "json",
        "page": word,
        "prop": "sections",
        "redirects": 1,
    }
    async with _get_session().get(api_url, params=params) as r:
        r.raise_for_status()
        data = await r.json()
        if "error" in data:
            raise ValueError(f"Wiktionary: {data['error'].get('info', 'unknown error')}")
        return data["parse"]["sections"]

async def fetch_section_wikitext(word: str, section_index: str, api_url: str) -> str:
    params = {
        "action": "parse",
        "format": "json",
        "page": word,
        "prop": "wikitext",
        "section": section_index,
        "redirects": 1,
    }
    async with _get_session().get(api_url, params=params) as r:
        r.raise_for_status()
        data = await r.json()
        if "error" in data:
            raise ValueError(f"Wiktionary: {data['error'].get('info', 'unknown error')}")
        return data["parse"]["wikitext"]["*"]