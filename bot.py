# bot.py
import os
from typing import Optional
import logging
import re

import discord
from discord.ext import commands

from config import LANG_CONFIG
from wiktionary_client import get_sections, fetch_section_wikitext
from parse import normalize_lang, normalize_pos, find_language_pos_section_index, find_language_pos_section_indices, extract_definition_lines, extract_french_gender, strip_html, build_french_noun_sections

intents = discord.Intents.default()
intents.message_content = True

debug = False

bot = commands.Bot(command_prefix="!", intents=intents)

# key: (guild_id, channel_id)
DEFINE_SESSIONS = {}

def session_key(ctx):
    return (getattr(ctx.guild, "id", None), ctx.channel.id)

def session_defs(sess):
    """Flat list of (section_label, gender, def_text) for any session type."""
    if "fr_sections" in sess:
        out = []
        for sec in sess["fr_sections"]:
            for d in sec["defs"]:
                out.append((sec["section"], sec.get("gender"), d))
        return out
    gender = sess.get("gender")
    return [(sess["pos"], gender, d) for d in sess.get("defs", [])]

async def send_current_definition(ctx, sess):
    word = sess["word"]
    pos = sess["pos"]
    i = sess["i"]
    gender_text = {"m": ", masculin", "f": ", féminin"}

    if "fr_sections" in sess:
        offset = 0
        for sec in sess["fr_sections"]:
            sec_defs = sec["defs"]
            if i < offset + len(sec_defs):
                local_i = i - offset
                gender = sec.get("gender")
                total = sum(len(s["defs"]) for s in sess["fr_sections"])
                msg = (
                    f"**{word}** ({sec['section']}{gender_text.get(gender, '')}) [{i+1}/{total}]\n"
                    f"{sec_defs[local_i]}\n"
                )
                await ctx.send(msg)
                return
            offset += len(sec_defs)
        await ctx.send(f"No definitions stored for **{word}** ({pos}).")
        return

    defs = sess["defs"]
    gender = sess.get("gender")
    if not defs:
        await ctx.send(f"No definitions stored for **{word}** ({pos}).")
        return
    msg = (
        f"**{word}** ({pos}{gender_text.get(gender, '')}) [{i+1}/{len(defs)}]\n"
        f"{defs[i]}\n"
    )
    await ctx.send(msg)

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.command()
async def define(ctx, arg1: str, arg2: Optional[str] = None, arg3: Optional[str] = None):
    try:
        lang = "en"
        word = arg1
        pos_raw = arg2

        maybe_lang = normalize_lang(arg1)
        if maybe_lang:
            lang = maybe_lang
            word = arg2 if arg2 else ""
            pos_raw = arg3

        if not word:
            await ctx.send("Usage: `!define <word>` or `!define <lang> <word> [pos]` (lang: en, fr)")
            return

        cfg = LANG_CONFIG[lang]
        requested_pos = normalize_pos(pos_raw, cfg)

        sections = await get_sections(word, cfg["api"])

        pos_try_order = [requested_pos] if requested_pos else cfg["fallback"]
        
        # --- POS resolution ---
        is_fr_noun = lang == "fr" and any(
            (normalize_pos(p, cfg) or p).lower().rstrip(" 0123456789") == "nom commun"
            for p in pos_try_order
        )

        fr_sections = None
        chosen_pos = None
        chosen_idx = None

        if is_fr_noun:
            for p in pos_try_order:
                matches = find_language_pos_section_indices(sections, cfg["lang_header"], p)
                if matches:
                    chosen_pos = p
                    section_wikitexts = [
                        (header, await fetch_section_wikitext(word, idx, cfg["api"]))
                        for header, idx in matches
                    ]
                    fr_sections = build_french_noun_sections(section_wikitexts, max_defs=50)
                    break
        else:
            for p in pos_try_order:
                idx = find_language_pos_section_index(sections, cfg["lang_header"], p)
                if idx:
                    chosen_pos = p
                    chosen_idx = idx
                    break

        # --- Fallback: any POS section under the language ---
        if not fr_sections and not chosen_idx:
            in_lang = False
            for s in sections:
                line = strip_html(s.get("line", ""))
                level = str(s.get("level") or "")
                idx = s.get("index")
                if level == "2":
                    in_lang = (line.lower() == cfg["lang_header"].lower())
                    continue
                if not in_lang:
                    continue
                if level in {"3", "4", "5"}:
                    chosen_pos = line
                    chosen_idx = idx
                    break

        if fr_sections:
            if debug:
                for sec in fr_sections:
                    print(f"DEBUG: section {sec['section']} gender={sec['gender']} defs={sec['defs']}")
            if not any(sec["defs"] for sec in fr_sections):
                await ctx.send(f"No usable definitions found for **{word}** ({chosen_pos}).")
                return
            key = session_key(ctx)
            DEFINE_SESSIONS[key] = {
                "word": word,
                "pos": "nom commun",
                "lang": lang,
                "fr_sections": fr_sections,  # list of {section, gender, defs}
                "i": 0,
            }
        else:
            pos_wikitext = await fetch_section_wikitext(word, chosen_idx, cfg["api"])
            base_pos = (chosen_pos or "").lower().rstrip(" 0123456789")
            gender = None
            if lang == "fr" and base_pos == "nom commun":
                gender = extract_french_gender(pos_wikitext)
            lines = extract_definition_lines(pos_wikitext, lang=lang, max_defs=50)
            if debug:
                print(f"DEBUG: pos_wikitext for {word} ({chosen_pos}):\n{pos_wikitext}\n")
                print(f"DEBUG: extracted lines:\n{lines}\n")
            defs = []
            for ln in lines:
                ln = ln.strip()
                if ln.startswith("- "):
                    defs.append(ln[2:].strip())
                elif ln.startswith("  - "):
                    defs.append(ln[4:].strip())
            if not defs:
                await ctx.send(f"No usable definitions found for **{word}** ({chosen_pos}).")
                return
            key = session_key(ctx)
            DEFINE_SESSIONS[key] = {
                "word": word,
                "pos": base_pos,
                "defs": defs,
                "i": 0,
                "lang": lang,
                "gender": gender,
            }

        await send_current_definition(ctx, DEFINE_SESSIONS[key])

    except Exception as e:
        import traceback
        traceback.print_exc()
        print("DEFINE ERROR:", repr(e), flush=True)
        await ctx.send("Error while fetching/parsing")

@define.error
async def define_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!define <word>`")

@bot.command()
async def next(ctx):
    key = session_key(ctx)
    sess = DEFINE_SESSIONS.get(key)
    if not sess:
        await ctx.send("No active definition session. Use `!define <word>` first.")
        return
    total = sum(len(s["defs"]) for s in sess["fr_sections"]) if "fr_sections" in sess else len(sess.get("defs", []))
    if not total:
        await ctx.send("Session has no definitions.")
        return
    sess["i"] = (sess["i"] + 1) % total
    await send_current_definition(ctx, sess)

@bot.command()
async def all(ctx):
    key = session_key(ctx)
    sess = DEFINE_SESSIONS.get(key)
    if not sess:
        await ctx.send("No active definition session. Use `!define <word>` first.")
        return

    word = sess["word"]
    sec_label = sess["pos"]
    if "fr_sections" in sess:
        gender = sess["fr_sections"][0].get("gender")
        print(gender)
    gender_text = {"m": ", masculin", "f": ", féminin"}
    flat = session_defs(sess)

    if not flat:
        await ctx.send("Session has no definitions.")
        return

    header = f"**{word}** ({sec_label}{gender_text.get(gender, '')})\n"
    lines = []
    for i, (sec_label, gender, d) in enumerate(flat):
        lines.append(f"{i+1}. {d}")

    numbered = "\n".join(lines)
    msg = header + numbered
    if len(msg) <= 2000:
        await ctx.send(msg)
    else:
        await ctx.send(header)
        chunk = ""
        for line in lines:
            line += "\n"
            if len(chunk) + len(line) > 1900:
                await ctx.send(chunk)
                chunk = line
            else:
                chunk += line
        if chunk:
            await ctx.send(chunk)

@bot.command()
@commands.is_owner()
async def raw(ctx, lang_or_word: str, word_or_none: Optional[str] = None):
    """Fetch and display raw wikitext for a word — for debugging parse issues."""
    maybe_lang = normalize_lang(lang_or_word)
    if maybe_lang and word_or_none:
        lang, word = maybe_lang, word_or_none
    else:
        lang, word = "en", lang_or_word

    cfg = LANG_CONFIG[lang]
    try:
        sections = await get_sections(word, cfg["api"])
        section_list = "\n".join(
            f"[{s['index']}] L{s['level']} {strip_html(s.get('line',''))}"
            for s in sections
        )
        await ctx.send(f"**Sections for '{word}':**\n```\n{section_list[:1800]}\n```")
    except Exception:
        await ctx.send("Failed to fetch sections.")

token = os.environ.get("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(token.strip())
