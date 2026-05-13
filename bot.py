# bot.py
import os
import time
from typing import Optional
import logging
import re

import aiohttp
import discord
from discord.ext import commands, tasks

from config import LANG_CONFIG, gender_text
from wiktionary_client import get_sections, fetch_section_wikitext, set_session
from parse import normalize_lang, normalize_pos, find_language_pos_section_index, extract_definition_lines, extract_french_gender, strip_html

intents = discord.Intents.default()
intents.message_content = True

debug = False

SESSION_TTL = 3600  # seconds — drop a session after 1 hour of inactivity

bot = commands.Bot(command_prefix="!", intents=intents)

# key: (guild_id, channel_id)
DEFINE_SESSIONS: dict = {}

logging.basicConfig(
    level=logging.DEBUG if debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot")

# ── Lifecycle ──────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    timeout = aiohttp.ClientTimeout(total=15)
    http_session = aiohttp.ClientSession(headers={"User-Agent": "DiscordBot/1.0"}, timeout=timeout)
    set_session(http_session)
    bot._http_session = http_session          # hold a reference so we can close it
    prune_sessions.start()
    print(f"Logged in as {bot.user}", flush=True)

@bot.event
async def on_close():
    prune_sessions.cancel()
    session = getattr(bot, "_http_session", None)
    if session and not session.closed:
        await session.close()


# ── Background task: prune stale define sessions ───────────────────────────────

@tasks.loop(minutes=15)
async def prune_sessions():
    cutoff = time.monotonic() - SESSION_TTL
    stale = [k for k, v in DEFINE_SESSIONS.items() if v["last_used"] < cutoff]
    for k in stale:
        del DEFINE_SESSIONS[k]
    if stale:
        log.info("Pruned %d stale session(s)", len(stale))


# ── Helpers ────────────────────────────────────────────────────────────────────

def session_key(ctx):
    return (getattr(ctx.guild, "id", None), ctx.channel.id)

def touch_session(sess: dict) -> None:
    """Update last-used timestamp so active sessions don't get pruned."""
    sess["last_used"] = time.monotonic()


async def send_current_definition(ctx, sess):
    i = sess["i"]
    defs = sess["defs"]
    word = sess["word"]
    pos = sess["pos"]
    gender = sess.get("gender")

    msg = (
        f"**{word}** ({pos}{gender_text.get(gender, '')}) [{i+1}/{len(defs)}]\n"
        f"{defs[i]}\n"
    )
    await ctx.send(msg)


# ── Commands ───────────────────────────────────────────────────────────────────

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

        chosen_pos = None
        chosen_idx = None
        for p in pos_try_order:
            idx = find_language_pos_section_index(sections, cfg["lang_header"], p)
            if idx:
                chosen_pos = p
                chosen_idx = idx
                break

        if not chosen_idx:
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

        if not chosen_idx:
            await ctx.send(f"No definition found for **{word}**.")
            return

        pos_wikitext = await fetch_section_wikitext(word, chosen_idx, cfg["api"])
        gender = None
        base_pos = re.sub(r"\s*\d+$", "", chosen_pos or "").lower()
        if lang == "fr" and base_pos == "nom commun":
            gender = extract_french_gender(pos_wikitext)

        lines = extract_definition_lines(pos_wikitext, lang=lang, max_defs=50)

        if debug:
            log.debug("pos_wikitext for %r (%s):\n%s", word, chosen_pos, pos_wikitext)

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
            "last_used": time.monotonic(),
        }

        await send_current_definition(ctx, DEFINE_SESSIONS[key])

    except Exception as e:
        log.exception("Error in !define for word=%r", word)
        await ctx.send("Error while fetching/parsing.")

@define.error
async def define_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!define <word>`")

@bot.command()
async def next(ctx):
    key = session_key(ctx)
    sess = DEFINE_SESSIONS.get(key)

    if not sess:
        await ctx.send("No active session. Use `!define <word>` first.")
        return

    wrapping = sess["i"] == len(sess["defs"]) - 1
    sess["i"] = (sess["i"] + 1) % len(sess["defs"])
    touch_session(sess)

    if wrapping:
        await ctx.send("*(Back to the first definition.)*")

    await send_current_definition(ctx, sess)

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
        log.exception("!raw failed for %r", word)
        await ctx.send("Failed to fetch sections.")


token = os.environ.get("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(token.strip())