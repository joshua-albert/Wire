"""
Beats: what the news is *about*, and where it is unusually busy.

Two things a desk editor wants that a headline list can't give them.

ENTITIES. Places, people and organisations pulled out of headlines so you can
read one subject end to end instead of scrolling for it.

ANOMALY. The part no aggregator does. Every country and beat gets a rolling
baseline. When somewhere that normally produces one story a day starts
producing seven, that gets flagged — before any outlet has decided it's a
story. This is "the small thing that could be big" measured at the level of a
place rather than a headline.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

from .common import norm_title, now_utc, parse_ts

# Countries and territories that generate news, with the words that signal
# them. Kept deliberately compact: demonyms, capitals, and common short forms.
GAZETTEER: dict[str, tuple[str, list[str]]] = {
    "Afghanistan": ("Asia", ["afghan", "kabul", "taliban", "kandahar"]),
    "Algeria": ("Africa", ["algerian", "algiers"]),
    "Argentina": ("Americas", ["argentine", "argentinian", "buenos aires"]),
    "Armenia": ("Eurasia", ["armenian", "yerevan", "karabakh"]),
    "Australia": ("Pacific", ["australian", "canberra", "sydney", "melbourne"]),
    "Austria": ("Europe", ["austrian", "vienna"]),
    "Azerbaijan": ("Eurasia", ["azerbaijani", "azeri", "baku"]),
    "Bangladesh": ("Asia", ["bangladeshi", "dhaka"]),
    "Belarus": ("Eurasia", ["belarusian", "minsk", "lukashenko"]),
    "Belgium": ("Europe", ["belgian", "brussels"]),
    "Bolivia": ("Americas", ["bolivian", "la paz"]),
    "Bosnia": ("Europe", ["bosnian", "sarajevo", "republika srpska"]),
    "Brazil": ("Americas", ["brazilian", "brasilia", "sao paulo", "rio de janeiro"]),
    "Bulgaria": ("Europe", ["bulgarian", "sofia"]),
    "Burkina Faso": ("Africa", ["burkina", "ouagadougou", "burkinabe"]),
    "Cambodia": ("Asia", ["cambodian", "phnom penh"]),
    "Cameroon": ("Africa", ["cameroonian", "yaounde"]),
    "Canada": ("Americas", ["canadian", "ottawa", "toronto", "quebec"]),
    "Chad": ("Africa", ["chadian", "ndjamena"]),
    "Chile": ("Americas", ["chilean", "santiago"]),
    "China": ("Asia", ["chinese", "beijing", "shanghai", "xi jinping", "prc"]),
    "Colombia": ("Americas", ["colombian", "bogota", "medellin"]),
    "Congo": ("Africa", ["congolese", "kinshasa", "goma", "drc"]),
    "Croatia": ("Europe", ["croatian", "zagreb"]),
    "Cuba": ("Americas", ["cuban", "havana"]),
    "Czechia": ("Europe", ["czech", "prague"]),
    "Denmark": ("Europe", ["danish", "copenhagen", "greenland"]),
    "Ecuador": ("Americas", ["ecuadorian", "quito", "guayaquil"]),
    "Egypt": ("Middle East", ["egyptian", "cairo", "sisi"]),
    "El Salvador": ("Americas", ["salvadoran", "bukele", "san salvador"]),
    "Estonia": ("Europe", ["estonian", "tallinn"]),
    "Ethiopia": ("Africa", ["ethiopian", "addis ababa", "tigray", "amhara"]),
    "Finland": ("Europe", ["finnish", "helsinki"]),
    "France": ("Europe", ["french", "paris", "macron", "marseille"]),
    "Georgia (country)": ("Eurasia", ["tbilisi", "georgian dream", "abkhazia"]),
    "Germany": ("Europe", ["german", "berlin", "bundestag", "munich"]),
    "Ghana": ("Africa", ["ghanaian", "accra"]),
    "Greece": ("Europe", ["greek", "athens"]),
    "Guatemala": ("Americas", ["guatemalan", "guatemala city"]),
    "Haiti": ("Americas", ["haitian", "port-au-prince"]),
    "Honduras": ("Americas", ["honduran", "tegucigalpa"]),
    "Hungary": ("Europe", ["hungarian", "budapest", "orban"]),
    "India": ("Asia", ["indian", "delhi", "mumbai", "modi", "kashmir"]),
    "Indonesia": ("Asia", ["indonesian", "jakarta", "papua"]),
    "Iran": ("Middle East", ["iranian", "tehran", "khamenei", "irgc"]),
    "Iraq": ("Middle East", ["iraqi", "baghdad", "basra", "kurdistan"]),
    "Ireland": ("Europe", ["irish", "dublin"]),
    "Israel": ("Middle East", ["israeli", "jerusalem", "tel aviv", "netanyahu", "idf"]),
    "Italy": ("Europe", ["italian", "rome", "meloni", "milan"]),
    "Ivory Coast": ("Africa", ["ivorian", "abidjan"]),
    "Japan": ("Asia", ["japanese", "tokyo", "osaka"]),
    "Jordan": ("Middle East", ["jordanian", "amman"]),
    "Kazakhstan": ("Eurasia", ["kazakh", "astana", "almaty"]),
    "Kenya": ("Africa", ["kenyan", "nairobi"]),
    "Kyrgyzstan": ("Eurasia", ["kyrgyz", "bishkek", "osh"]),
    "Laos": ("Asia", ["laotian", "vientiane"]),
    "Lebanon": ("Middle East", ["lebanese", "beirut", "hezbollah"]),
    "Libya": ("Africa", ["libyan", "tripoli", "benghazi"]),
    "Lithuania": ("Europe", ["lithuanian", "vilnius"]),
    "Madagascar": ("Africa", ["malagasy", "antananarivo"]),
    "Malaysia": ("Asia", ["malaysian", "kuala lumpur"]),
    "Mali": ("Africa", ["malian", "bamako", "wagner"]),
    "Mexico": ("Americas", ["mexican", "mexico city", "sheinbaum", "sinaloa"]),
    "Moldova": ("Europe", ["moldovan", "chisinau", "transnistria"]),
    "Mongolia": ("Asia", ["mongolian", "ulaanbaatar"]),
    "Morocco": ("Africa", ["moroccan", "rabat", "casablanca"]),
    "Mozambique": ("Africa", ["mozambican", "maputo", "cabo delgado"]),
    "Myanmar": ("Asia", ["burmese", "yangon", "naypyidaw", "rakhine", "junta"]),
    "Nepal": ("Asia", ["nepali", "nepalese", "kathmandu"]),
    "Netherlands": ("Europe", ["dutch", "amsterdam", "the hague"]),
    "New Zealand": ("Pacific", ["wellington", "auckland", "kiwi"]),
    "Nicaragua": ("Americas", ["nicaraguan", "managua", "ortega"]),
    "Niger": ("Africa", ["nigerien", "niamey"]),
    "Nigeria": ("Africa", ["nigerian", "abuja", "lagos", "boko haram"]),
    "North Korea": ("Asia", ["pyongyang", "kim jong", "dprk"]),
    "Norway": ("Europe", ["norwegian", "oslo"]),
    "Pakistan": ("Asia", ["pakistani", "islamabad", "karachi", "lahore"]),
    "Panama": ("Americas", ["panamanian", "panama city"]),
    "Papua New Guinea": ("Pacific", ["port moresby", "bougainville"]),
    "Paraguay": ("Americas", ["paraguayan", "asuncion"]),
    "Peru": ("Americas", ["peruvian", "lima"]),
    "Philippines": ("Asia", ["filipino", "philippine", "manila", "marcos"]),
    "Poland": ("Europe", ["polish", "warsaw", "tusk"]),
    "Portugal": ("Europe", ["portuguese", "lisbon"]),
    "Qatar": ("Middle East", ["qatari", "doha"]),
    "Romania": ("Europe", ["romanian", "bucharest"]),
    "Russia": ("Eurasia", ["russian", "moscow", "putin", "kremlin", "st petersburg"]),
    "Rwanda": ("Africa", ["rwandan", "kigali", "m23"]),
    "Saudi Arabia": ("Middle East", ["saudi", "riyadh", "jeddah", "mbs"]),
    "Senegal": ("Africa", ["senegalese", "dakar"]),
    "Serbia": ("Europe", ["serbian", "belgrade", "vucic"]),
    "Sierra Leone": ("Africa", ["freetown", "sierra leonean"]),
    "Singapore": ("Asia", ["singaporean"]),
    "Slovakia": ("Europe", ["slovak", "bratislava", "fico"]),
    "Somalia": ("Africa", ["somali", "mogadishu", "shabaab", "somaliland"]),
    "South Africa": ("Africa", ["johannesburg", "pretoria", "cape town", "ramaphosa"]),
    "South Korea": ("Asia", ["korean", "seoul"]),
    "South Sudan": ("Africa", ["juba", "south sudanese"]),
    "Spain": ("Europe", ["spanish", "madrid", "barcelona", "catalonia"]),
    "Sri Lanka": ("Asia", ["sri lankan", "colombo"]),
    "Sudan": ("Africa", ["sudanese", "khartoum", "darfur", "rsf"]),
    "Sweden": ("Europe", ["swedish", "stockholm"]),
    "Switzerland": ("Europe", ["swiss", "geneva", "zurich", "bern"]),
    "Syria": ("Middle East", ["syrian", "damascus", "aleppo", "idlib"]),
    "Taiwan": ("Asia", ["taiwanese", "taipei", "taiwan strait"]),
    "Tajikistan": ("Eurasia", ["tajik", "dushanbe"]),
    "Tanzania": ("Africa", ["tanzanian", "dodoma", "dar es salaam"]),
    "Thailand": ("Asia", ["thai", "bangkok"]),
    "Tunisia": ("Africa", ["tunisian", "tunis"]),
    "Turkey": ("Middle East", ["turkish", "ankara", "istanbul", "erdogan"]),
    "Uganda": ("Africa", ["ugandan", "kampala", "museveni"]),
    "Ukraine": ("Eurasia", ["ukrainian", "kyiv", "kharkiv", "odesa", "zelensky", "donetsk"]),
    "United Arab Emirates": ("Middle East", ["emirati", "dubai", "abu dhabi", "uae"]),
    "United Kingdom": ("Europe", ["british", "britain", "london", "downing street", "westminster"]),
    "United States": ("Americas", ["u s ", "american", "washington", "white house",
                                   "congress", "pentagon", "supreme court"]),
    "Uruguay": ("Americas", ["uruguayan", "montevideo"]),
    "Uzbekistan": ("Eurasia", ["uzbek", "tashkent"]),
    "Venezuela": ("Americas", ["venezuelan", "caracas", "maduro"]),
    "Vietnam": ("Asia", ["vietnamese", "hanoi", "ho chi minh"]),
    "Yemen": ("Middle East", ["yemeni", "sanaa", "houthi", "aden"]),
    "Zambia": ("Africa", ["zambian", "lusaka"]),
    "Zimbabwe": ("Africa", ["zimbabwean", "harare"]),
}

_LOOKUP = []
for country, (region, words) in GAZETTEER.items():
    for word in [country.lower().split(" (")[0]] + words:
        _LOOKUP.append((word, country, region))
_LOOKUP.sort(key=lambda x: -len(x[0]))

PROPER = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b")
NOT_ENTITIES = {
    "The", "This", "That", "There", "But", "And", "For", "With", "After", "Before",
    "New", "Live", "Breaking", "Update", "Report", "Video", "Watch", "Exclusive",
    "First", "Last", "More", "Amid", "How", "Why", "What", "Who", "When", "Where",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
}


def countries_in(text: str) -> list[tuple[str, str]]:
    """Which places does this headline touch?"""
    padded = f" {norm_title(text)} "
    found = {}
    for word, country, region in _LOOKUP:
        if f" {word.strip()} " in padded or padded.find(f" {word.strip()}") >= 0 and word in padded:
            if f" {word.strip()} " in padded:
                found[country] = region
    return sorted(found.items())


def entities_in(text: str) -> tuple[list[str], list[str]]:
    """
    Proper-noun candidates, and which of them appeared mid-headline.

    Nearly every headline starts with a capital letter, so first-word matches
    are mostly ordinary words in disguise — "Rail bridge collapses" yields
    "Rail". A phrase that also turns up away from the start is far more likely
    to be an actual name, and that single test removes most of the junk.
    """
    found, mid = [], []
    for match in PROPER.finditer(text):
        phrase = match.group(1)
        head = phrase.split()[0]
        if head in NOT_ENTITIES or len(phrase) < 4:
            continue
        if norm_title(phrase) in {w.lower() for w in NOT_ENTITIES}:
            continue
        found.append(phrase)
        if match.start() > 0:
            mid.append(phrase)
    return found, mid


def looks_generic(name: str) -> bool:
    """Single ordinary words that slip past capitalisation."""
    return " " not in name and name.lower() in GENERIC_WORDS


GENERIC_WORDS = set("""
rail bridge court police city state federal national public health energy water power
school district county board committee agency ministry department office union party
election vote budget report review inquiry appeal ruling order strike protest march
market bank fund plan bill law act case trial prison camp border force army navy
""".split())


def tag_thread(thread: dict) -> None:
    text = thread["title"]
    places = countries_in(text)
    thread["countries"] = [c for c, _ in places]
    thread["regions"] = sorted({r for _, r in places})
    found, mid = entities_in(text)
    keep = [n for n in found if not looks_generic(n)]
    thread["entities"] = keep[:6]
    thread["entities_mid"] = [n for n in mid if not looks_generic(n)][:6]


# ------------------------------------------------------------- the anomaly

def _cell(day: dict, date: str) -> dict:
    cell = day.get(date)
    if isinstance(cell, int):          # migrate the old count-only format
        cell = {"n": cell, "s": []}
    elif cell is None:
        cell = {"n": 0, "s": []}
    day[date] = cell
    return cell


def record_activity(state: dict, new_threads: list[dict]) -> None:
    """
    Log what each country and beat produced today, and who reported it.

    Recording the contributing sources matters: a spike that comes entirely
    from one newly-added feed is a change in this tool, not in the world.
    """
    log = state.setdefault("activity", {})
    today = now_utc().date().isoformat()

    for thread in new_threads:
        sources = sorted({m["source"] for m in thread.get("members", [])})[:8]
        keys = [f"country:{c}" for c in thread.get("countries", [])]
        keys += [f"tag:{t}" for t in thread.get("tags", [])]
        for key in keys:
            cell = _cell(log.setdefault(key, {}), today)
            cell["n"] += 1
            cell["s"] = sorted(set(cell["s"]) | set(sources))[:14]

    total = _cell(log.setdefault("__all__", {}), today)
    total["n"] += len(new_threads)

    # Keep three weeks. Enough for a baseline, small enough to commit.
    keep = sorted({d for days in log.values() for d in days})[-21:]
    keepset = set(keep)
    for key in list(log):
        log[key] = {d: n for d, n in log[key].items() if d in keepset}
        if not log[key]:
            del log[key]


def anomalies(state: dict, min_today: int = 3, z: float = 2.0,
              min_sources: int = 2) -> list[dict]:
    """
    Where is today unlike the last three weeks?

    Measured as *share of the day's output*, not raw count. Raw counts move
    whenever the tool does — a feed added, a feed down, a slow news Sunday —
    and a detector that fires on its own plumbing is worse than none. Share
    of voice cancels all of that out.

    A spike also has to come from at least two different sources. One feed
    having a busy morning is not a country having a bad day.
    """
    log = state.get("activity", {})
    today = now_utc().date().isoformat()
    totals = log.get("__all__", {})

    def share(day_key: str, count: int) -> float:
        cell = totals.get(day_key)
        total = cell["n"] if isinstance(cell, dict) else (cell or 0)
        return count / total if total else 0.0

    out = []
    for key, days in log.items():
        if key == "__all__":
            continue
        current_cell = _cell(dict(days), today) if today in days else {"n": 0, "s": []}
        current = current_cell["n"]
        if current < min_today or len(current_cell["s"]) < min_sources:
            continue

        history = []
        for date, cell in sorted(days.items()):
            if date == today:
                continue
            count = cell["n"] if isinstance(cell, dict) else cell
            history.append(share(date, count))
        if len(history) < 5:
            continue

        now_share = share(today, current)
        mean = statistics.fmean(history)
        spread = statistics.pstdev(history) or 0.01
        score = (now_share - mean) / spread
        if score >= z and now_share >= mean * 1.8:
            kind, name = key.split(":", 1)
            today_total = totals.get(today, {})
            today_total = (today_total["n"] if isinstance(today_total, dict)
                           else today_total or 0)
            # What this beat would have produced today at its usual share.
            expected = round(mean * today_total, 1) if today_total else round(mean, 2)
            out.append({"kind": kind, "name": name, "today": current,
                        "expected": expected, "sources": len(current_cell["s"]),
                        "z": round(score, 1)})

    return sorted(out, key=lambda a: a["z"], reverse=True)


def entity_index(threads: list[dict], minimum: int = 2) -> list[tuple[str, int]]:
    """
    Only names that earn a page.

    A candidate has to show up in more than one story, and — unless it's a
    country from the gazetteer — has to have appeared away from the start of
    a headline at least once. Countries are exempt because they're verified
    against a real list rather than guessed at.
    """
    counts, trusted = Counter(), set()
    for thread in threads:
        names = set(thread.get("entities", []) + thread.get("countries", []))
        for name in names:
            counts[name] += 1
        trusted.update(thread.get("entities_mid", []))
        trusted.update(thread.get("countries", []))

    return [(name, n) for name, n in counts.most_common(200)
            if n >= minimum and name in trusted][:140]


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
