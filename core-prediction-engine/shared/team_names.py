"""Join bookmaker names to Football-Data abbreviations."""

from __future__ import annotations

import unicodedata

_STOP = {
    "fc",
    "afc",
    "cf",
    "sc",
    "ac",
    "bc",
    "vfl",
    "tsv",
    "sv",
    "rcd",
    "cd",
    "ud",
    "de",
    "calcio",
    "clube",
    "ado",
    "rb",
    "rc",
}
_TAIL = {"city", "town", "county", "hotspur", "wanderers", "albion", "united", "utd"}

# Short Football-Data names and the longer names BetPawa prints, one key each.
_ALIASES = {
    "man city": "manchester city",
    "manchester city": "manchester city",
    "man united": "manchester united",
    "man utd": "manchester united",
    "manchester utd": "manchester united",
    "nottm forest": "nottingham forest",
    "nottingham forest": "nottingham forest",
    "spurs": "tottenham",
    "wolves": "wolves",
    "wolverhampton": "wolves",
    "west brom": "west brom",
    "west bromwich": "west brom",
    "qpr": "qpr",
    "queens park rangers": "qpr",
    "sheffield weds": "sheffield wednesday",
    "sheffield wednesday": "sheffield wednesday",
    "ath bilbao": "athletic bilbao",
    "athletic club": "athletic bilbao",
    "ath madrid": "atletico madrid",
    "real betis": "betis",
    "espanol": "espanyol",
    "espanyol": "espanyol",
    "real sociedad": "sociedad",
    "rayo vallecano": "vallecano",
    "deportivo la coruna": "la coruna",
    "deportivo": "la coruna",
    "racing santander": "santander",
    "celta vigo": "celta",
    "real oviedo": "oviedo",
    "paris sg": "paris sg",
    "paris saint germain": "paris sg",
    "psg": "paris sg",
    "sp lisbon": "sporting",
    "sporting cp": "sporting",
    "sporting lisbon": "sporting",
    "sporting lisboa": "sporting",
    "sporting portugal": "sporting",
    "sp braga": "braga",
    "sporting braga": "braga",
    "vitoria guimaraes": "guimaraes",
    "borussia dortmund": "dortmund",
    "ein frankfurt": "eintracht frankfurt",
    "eintracht frankfurt": "eintracht frankfurt",
    "bayer leverkusen": "leverkusen",
    "bayer 04 leverkusen": "leverkusen",
    "mgladbach": "monchengladbach",
    "borussia monchengladbach": "monchengladbach",
    "monchengladbach": "monchengladbach",
    "gladbach": "monchengladbach",
    "cologne": "koln",
    "bayern munchen": "bayern munich",
    "for sittard": "fortuna sittard",
    "fortuna sittard": "fortuna sittard",
    "psv eindhoven": "psv",
    "az alkmaar": "az",
    "nec": "nijmegen",
    "nec nijmegen": "nijmegen",
    "inter milan": "inter",
    "internazionale": "inter",
}


def _normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("'", "").replace(".", " ")
    cleaned = []
    for char in text:
        cleaned.append(char if char.isalnum() else " ")
    return " ".join("".join(cleaned).split())


def _drop_club_words(text: str) -> str:
    tokens = [token for token in text.split() if token not in _STOP]
    while tokens and tokens[0].isdigit():
        tokens.pop(0)
    while len(tokens) > 1 and tokens[-1] in _TAIL:
        tokens.pop()
    return " ".join(tokens)


def team_key(name: str) -> str:
    """One key for a club, whether the feed uses a short or a full name."""
    text = _normalize(name)
    if text in _ALIASES:
        return _ALIASES[text]
    trimmed = _drop_club_words(text)
    if trimmed in _ALIASES:
        return _ALIASES[trimmed]
    return trimmed
