# wiktionary.py
import requests
from config import HEADERS

def get_sections(word: str, api_url: str):
    params = {
        "action": "parse",
        "format": "json",
        "page": word,
        "prop": "sections",
        "redirects": 1,
    }
    r = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()["parse"]["sections"]

def fetch_section_wikitext(word: str, section_index: str, api_url: str) -> str:
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
    return r.json()["parse"]["wikitext"]["*"]
