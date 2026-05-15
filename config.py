# config.py
import re
from typing import Optional

HEADERS = {"User-Agent": "DiscordBot/1.0 (learning project)"}

LANG_CONFIG = {
    "en": {
        "api": "https://en.wiktionary.org/w/api.php",
        "lang_header": "English",
        "pos_aliases": {
            "noun": "Noun", "n": "Noun",
            "verb": "Verb", "v": "Verb",
            "adjective": "Adjective", "adj": "Adjective", "a": "Adjective",
            "adverb": "Adverb", "adv": "Adverb",
        },
        "fallback": ["Adjective", "Noun", "Verb", "Adverb", "Prepositional phrase"],
    },
    "fr": {
        "api": "https://fr.wiktionary.org/w/api.php",
        "lang_header": "Français",
        "pos_aliases": {
            "noun": "Nom commun", "n": "Nom commun",
            "verb": "Verbe", "v": "Verbe",
            "adjective": "Adjectif", "adj": "Adjectif", "a": "Adjectif",
            "adverb": "Adverbe", "adv": "Adverbe",
        },
        "fallback": ["Nom commun", "Verbe", "Adjectif", "Adverbe", ],
    },
}

# Parsing regexes
LINK_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]|\[\[([^\]]+)\]\]")
LIEN_FR_RE = re.compile(r"\{\{\s*lien\s*\|\s*([^|}]+)\s*\|\s*fr\s*\}\}", re.IGNORECASE)
TAXFMT_RE = re.compile(r"\{\{taxfmt\|([^|}]+)(?:\|[^}]*)?\}\}")
TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
HTML_TAG_RE = re.compile(r"<[^>]+>")
FR_GENDER_RE = re.compile(r"\{\{\s*(m|f|mf)\s*\}\}", re.IGNORECASE)
FR_LABEL_RE = re.compile(
    r"\{\{\s*([^|{}]+?)\s*\|\s*fr\s*\}\}",
    re.IGNORECASE
)

FR_LABEL_MAP = {
    "vulgaire": "[vulgaire]",
    "injurieux": "[injurieux]",
    "familier": "[familier]",
    "péjoratif": "[péjoratif]",
    "argot": "[argot]",
    "ironique": "[ironique]",
    "vieilli": "[vieilli]",
}