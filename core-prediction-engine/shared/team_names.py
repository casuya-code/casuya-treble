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
    "ca",
    "club",
}
_TAIL = {"city", "town", "county", "hotspur", "wanderers", "albion", "united", "utd"}

# Letters that NFKD does not split into base + mark (Polish, Nordic, German...).
_FOLD = str.maketrans(
    {
        "\u0142": "l",  # ł
        "\u00f8": "o",  # ø
        "\u0111": "d",  # đ
        "\u00f0": "d",  # ð
        "\u00fe": "th",  # þ
        "\u00df": "ss",  # ß
        "\u00e6": "ae",  # æ
        "\u0153": "oe",  # œ
        "\u0127": "h",  # ħ
        "\u0131": "i",  # dotless i
        "\u014b": "n",  # ŋ
    }
)

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
    "argentinos jrs": "argentinos juniors",
    "argentinos juniors": "argentinos juniors",
    "atl tucuman": "atletico tucuman",
    "atletico tucuman": "atletico tucuman",
    "estudiantes l p": "estudiantes",
    "estudiantes de la plata": "estudiantes",
    "estudiantes la plata": "estudiantes",
    "san martin s j": "san martin san juan",
    "san martin san juan": "san martin san juan",
    "dep riestra": "deportivo riestra",
    "deportivo riestra": "deportivo riestra",
    "ind rivadavia": "independiente rivadavia",
    "independiente rivadavia": "independiente rivadavia",
    "gimnasia l p": "gimnasia la plata",
    "gimnasia la plata": "gimnasia la plata",
    "gimnasia y esgrima la plata": "gimnasia la plata",
    "talleres cordoba": "talleres",
    "talleres": "talleres",
    "sarmiento junin": "sarmiento",
    "sarmiento": "sarmiento",
    "central cordoba": "central cordoba",
    "central cordoba santiago": "central cordoba",
    "instituto cordoba": "instituto",
    "colon santa fe": "colon",
    "colon": "colon",
    # Extra leagues seeded July 2026: bookmaker long names against the short files.
    "ifk goteborg": "goteborg",
    "ik sirius": "sirius",
    "if brommapojkarna": "brommapojkarna",
    "vasteraas sk": "vasteras sk",
    "odense boldklub": "odense",
    "seinajoen jk": "sjk",
    "rks rakow czestochowa": "rakow",
    "ks cracovia krakow": "cracovia",
    "zaglebie lubin": "zaglebie",
    "corvinul hunedoara 1921": "corvinul",
    "acs sepsi osk sfantu gheorghe": "sepsi sf gheorghe",
    "dinamo bucuresti 1948": "dinamo bucuresti",
    "din bucuresti": "dinamo bucuresti",
    "deportivo toluca": "toluca",
    "sk beveren": "beveren",
    "fagiano okayama": "okayama",
    "kyoto sanga": "kyoto",
    "machida zelvia": "machida",
    "urawa red diamonds": "urawa reds",
}


def _normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().translate(_FOLD).replace("'", "").replace(".", " ")
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
