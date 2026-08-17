"""
Translate foreign-language headlines into English.

The real long tail isn't Reuters' Africa desk — it's the Ukrainian regional
paper, the Indonesian daily, the Turkish local wire. Those outlets break
things days before an English-language outlet notices. This pulls them raw
and translates only the headline, which is cheap and good enough to decide
whether to click.

Three providers, tried in this order:
  DEEPL_API_KEY        best quality, free tier is 500k chars/month
  LIBRETRANSLATE_URL   self-hosted or public instance, no key needed
  (default)            Google's public translate endpoint, unofficial

Everything is cached forever by text hash, so each headline costs one call
once. If every provider fails the original headline is shown untouched —
translation never blocks the run.
"""

from __future__ import annotations

import json
import os
import time

import requests

from .common import UA, digest

MAX_PER_RUN = 400
TIMEOUT = 12


def _deepl(text: str, key: str) -> str | None:
    try:
        host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
        response = requests.post(
            f"https://{host}/v2/translate",
            data={"auth_key": key, "text": text, "target_lang": "EN"},
            timeout=TIMEOUT,
        )
        if response.ok:
            return response.json()["translations"][0]["text"]
    except Exception:  # noqa: BLE001
        return None
    return None


def _libre(text: str, base: str, source_lang: str) -> str | None:
    try:
        response = requests.post(
            base.rstrip("/") + "/translate",
            json={"q": text, "source": source_lang or "auto", "target": "en",
                  "format": "text"},
            timeout=TIMEOUT,
        )
        if response.ok:
            return response.json().get("translatedText")
    except Exception:  # noqa: BLE001
        return None
    return None


def _google_public(text: str, source_lang: str) -> str | None:
    """Unofficial endpoint. No key, no guarantees — treat as best effort."""
    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": source_lang or "auto", "tl": "en",
                    "dt": "t", "q": text},
            headers={"User-Agent": UA},
            timeout=TIMEOUT,
        )
        if not response.ok:
            return None
        chunks = json.loads(response.text)[0]
        return "".join(chunk[0] for chunk in chunks if chunk and chunk[0])
    except Exception:  # noqa: BLE001
        return None
    return None


def translate_headlines(items: list[dict], state: dict, enabled: bool) -> int:
    """Fill in item['title_en'] for anything not already in English."""
    if not enabled:
        return 0

    cache = state.setdefault("translations", {})
    deepl_key = os.environ.get("DEEPL_API_KEY")
    libre_url = os.environ.get("LIBRETRANSLATE_URL")

    pending = [i for i in items if i.get("lang", "en") != "en"]
    translated = 0
    failures = 0

    for item in pending:
        key = digest(item["title"], 16)
        if key in cache:
            item["title_en"] = cache[key]
            continue
        if translated >= MAX_PER_RUN or failures >= 8:
            continue

        source_lang = item.get("lang", "auto")
        result = None
        if deepl_key:
            result = _deepl(item["title"], deepl_key)
        if result is None and libre_url:
            result = _libre(item["title"], libre_url, source_lang)
        if result is None:
            result = _google_public(item["title"], source_lang)

        if result:
            cache[key] = result
            item["title_en"] = result
            translated += 1
            time.sleep(0.25)
        else:
            failures += 1

    if len(cache) > 40000:
        for key in list(cache)[: len(cache) - 30000]:
            del cache[key]

    if pending:
        print(f"translate: {translated} new, {len(pending) - translated} cached or skipped"
              + (f", {failures} failures" if failures else ""))
    return translated


def display_title(record: dict) -> str:
    """What actually goes on the page."""
    return record.get("title_en") or record["title"]
