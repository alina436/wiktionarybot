# parse.py
import re
from typing import Optional

from config import FR_GENDER_RE, FR_LABEL_RE, LINK_RE, LIEN_FR_RE, TAXFMT_RE, TEMPLATE_RE, HTML_TAG_RE, LANG_CONFIG, FR_LABEL_MAP

def normalize_lang(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip().lower()
    return s if s in LANG_CONFIG else None

def normalize_pos(pos: Optional[str], cfg) -> Optional[str]:
    if not pos:
        return None
    return cfg["pos_aliases"].get(pos.strip().lower())

def strip_html(s: str) -> str:
    return HTML_TAG_RE.sub("", s or "").strip()

def find_language_pos_section_index(sections, lang_header: str, pos_header: str):
    """Original — returns a single index for exact match (used for English and non-noun POS)."""
    in_lang = False
    for s in sections:
        line = strip_html(s.get("line", ""))
        level = str(s.get("level") or "")
        idx = s.get("index")
        if level == "2":
            in_lang = (line.lower() == lang_header.lower())
            continue
        if not in_lang:
            continue
        if level in {"3", "4", "5"} and line.lower() == pos_header.lower():
            return idx
    return None

def find_language_pos_section_indices(sections, lang_header: str, pos_header: str) -> list[tuple[str, str]]:
    """New — returns (header_text, index) tuples for all numbered variants (used for French nouns)."""
    in_lang = False
    results = []
    for s in sections:
        line = strip_html(s.get("line", ""))
        level = str(s.get("level") or "")
        idx = s.get("index")
        if level == "2":
            in_lang = (line.lower() == lang_header.lower())
            continue
        if not in_lang:
            continue
        if level in {"3", "4", "5"} and re.match(
            rf"^{re.escape(pos_header.lower())}(\s+\d+)?$", line.lower()
        ):
            results.append((line, idx))
    return results

def build_french_noun_sections(section_wikitexts: list[tuple[str, str]], max_defs: int = 50) -> list[dict]:
    """
    Takes [(header_text, wikitext), ...] and returns
    [{"section": ..., "gender": ..., "defs": [...]}, ...]
    """
    results = []
    for header, wikitext in section_wikitexts:
        lines = extract_definition_lines(wikitext, "fr", max_defs)
        header =  re.sub(r'\d+', '', header).strip() # remove numbering from header names
        defs = []
        for ln in lines:
            ln = ln.strip()
            if ln.startswith("- "):
                defs.append(ln[2:].strip())
            elif ln.startswith("  - "):
                defs.append(ln[4:].strip())
        results.append({
            "section": header.lower(),
            "gender": extract_french_gender(wikitext),
            "defs": defs,
        })
    return results

def clean_wikitext_line(s: str) -> str:
    def link_repl(m):
        if m.group(2):
            return m.group(2)
        return m.group(1) or m.group(3) or ""
    
    def label_repl(m):
        return f"({m.group(1)})"

    s = FR_LABEL_RE.sub(label_repl, s)

    s = LINK_RE.sub(link_repl, s)

    # French {{lien|word|fr}} keep the word
    s = LIEN_FR_RE.sub(r"\1", s)

    # English taxonomic names
    s = TAXFMT_RE.sub(r"\1", s)
    
    # references
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    s = re.sub(r"<ref[^>]*/>", "", s)

    # remove remaining templates
    for _ in range(3):
        s = TEMPLATE_RE.sub("", s)

    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s+", " ", s).strip()

    # keep letters, digits, accented Latin letters
    if not re.search(r"[A-Za-zÀ-ÿ0-9]", s):
        return ""
    if s in {".", "-", "–"}:
        return ""
    
    # FINAL CLEANUP
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    s = re.sub(r"\.\s*\.", ".", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s

def extract_definition_lines(pos_wikitext: str, lang, max_defs: int = 8) -> list[str]:
    out = []
    for raw in pos_wikitext.splitlines():
        line = raw.strip()

        # Skip headers
        if re.match(r"^=+[^=]+=+$", line):
            continue

        # Only handle # lines
        if line.startswith("# "):
            content = line[2:].strip()

            if lang == "en":
                m = re.match(r"\{\{([^|{}]+)\|en\|([^|{}]+)([^}]*)\}\}", content)
                if m:
                    template_name = m.group(1).strip().capitalize()
                    base_word = m.group(2).strip()
                    extras = m.group(3)
                    gloss_match = re.search(r"\|t=(.*?)(?=\|[a-z]+=|\}\})", extras + "}}")
                    if template_name.endswith(" of"):
                        if gloss_match:
                            gloss = clean_wikitext_line(gloss_match.group(1).strip())
                            out.append(f"- {template_name} {base_word} (\"{gloss}\")")
                        else:
                            out.append(f"- {template_name} {base_word}")
                        continue
            # fallback runs if no match or template didn't end in " of"
            cleaned = clean_wikitext_line(content)
            if cleaned:
                out.append("- " + cleaned)

        if len(out) >= max_defs:
            break

    return out

def extract_french_gender(pos_wikitext: str) -> Optional[str]:
    # Only scan the top to avoid false matches
    top = "\n".join(pos_wikitext.splitlines()[:20])
    m = FR_GENDER_RE.search(top)
    return m.group(1).lower() if m else None
