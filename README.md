# wiktionary-bot

A Discord bot that fetches word definitions from [Wiktionary](https://www.wiktionary.org/), with support for English and French. Definitions are displayed one at a time and can be stepped through interactively.

---

## Features

- Look up definitions for English and French words
- Filter by part of speech (noun, verb, adjective, adverb)
- French nouns: gender detection (masculin/féminin) and support for multiple noun sections
- Step through definitions one at a time or display all at once
- Clean output: wikitext templates, HTML, and formatting artifacts are stripped

---

## Commands

| Command | Description |
|---|---|
| `!define <word>` | Define a word in English |
| `!define <lang> <word>` | Define a word in a specific language (`en` or `fr`) |
| `!define <lang> <word> <pos>` | Define a word with a specific part of speech |
| `!next` | Show the next definition in the current session |
| `!all` | Show all definitions for the current session |
| `!ping` | Check that the bot is running |
| `!raw [lang] <word>` | *(Owner only)* Show raw Wiktionary section structure for debugging |

**Supported POS shorthands:** `n` / `noun`, `v` / `verb`, `adj` / `adjective`, `adv` / `adverb`

### Examples

```
!define ephemeral
!define fr boue
!define fr chien n
!define en run verb
```

---

## Project Structure

```
bot.py                 # Discord bot, commands, session management
config.py              # Language configs, POS aliases, parsing regexes
parse.py               # Wikitext parsing, definition extraction
wiktionary_client.py   # Wiktionary API client (async wrappers over requests)
```

---

## Setup

### Requirements

- Python 3.10+
- A Discord bot token

### Install dependencies

```bash
pip install discord.py requests
```

### Configure

Set your Discord bot token as an environment variable:

```bash
export DISCORD_TOKEN=your_token_here
```

### Run

```bash
python bot.py
```

---

## Adding a Language

New languages can be added in `config.py` by extending `LANG_CONFIG` with:

- `api` — Wiktionary API URL for that language edition
- `lang_header` — the language section heading as it appears on that Wiktionary (e.g. `"English"`, `"Français"`)
- `pos_aliases` — mapping of user-facing shorthands to canonical POS header names
- `fallback` — ordered list of POS headers to try when none is specified

French-specific parsing logic (gender extraction, multiple noun sections) lives in `parse.py` and `bot.py` and would need to be extended to support similar features for other languages.

---

## Notes

- Sessions are scoped per channel (and per guild for servers). Each `!define` call starts a new session and resets the index.
- The bot uses the Wiktionary `parse` API and runs HTTP requests in a thread pool executor to avoid blocking the event loop.
- Definition output is capped at 50 entries per lookup to avoid excessively long responses.
