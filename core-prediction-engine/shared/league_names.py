"""Tell which domestic league a BetPawa label and a Football-Data file describe."""

from __future__ import annotations

# (key, regions, phrases that must start the competition name)
_LEAGUES = (
    ("epl", {"england", "uk", "great britain"}, ("premier league",)),
    ("championship", {"england", "uk", "great britain"}, ("championship",)),
    ("laliga", {"spain", "espana"}, ("la liga", "laliga", "primera division")),
    ("seriea", {"italy", "italia"}, ("serie a",)),
    ("bundesliga", {"germany", "deutschland"}, ("bundesliga",)),
    ("ligue1", {"france"}, ("ligue 1", "ligue1")),
    ("eredivisie", {"netherlands", "holland"}, ("eredivisie",)),
    ("primeira", {"portugal"}, ("liga portugal", "primeira liga", "primeira")),
    ("argentina", {"argentina"}, ("liga profesional", "primera division")),
    # Extra senior top flights, seeded from Football-Data.
    ("belgium", {"belgium"}, ("pro league",)),
    ("turkey", {"turkey"}, ("super lig",)),
    ("greece", {"greece"}, ("super league",)),
    ("scotland", {"scotland"}, ("premiership",)),
    ("japan", {"japan"}, ("j.league",)),
    ("sweden", {"sweden"}, ("allsvenskan",)),
    ("norway", {"norway"}, ("eliteserien",)),
    ("denmark", {"denmark"}, ("superliga",)),
    ("poland", {"poland"}, ("ekstraklasa",)),
    ("romania", {"romania"}, ("liga i",)),
    ("austria", {"austria"}, ("bundesliga",)),
    ("switzerland", {"switzerland"}, ("super league",)),
    ("finland", {"finland"}, ("veikkausliiga",)),
    ("ireland", {"ireland"}, ("premier division",)),
    ("mexico", {"mexico"}, ("liga mx",)),
    ("usa", {"usa", "united states"}, ("mls",)),
    ("china", {"china"}, ("chinese super league",)),
    ("brazil", {"brazil"}, ("serie a",)),
)

# Youth, women, reserve, cup and play-off editions are never the senior league.
_NOT_SENIOR_LEAGUE = (
    "women",
    "woman",
    "feminine",
    "femenino",
    "ladies",
    "girls",
    "u19",
    "u20",
    "u21",
    "u23",
    "youth",
    "junior",
    "reserve",
    "relegation",
    "promotion",
    "play-off",
    "playoff",
    "cup",
    "copa",
    "coupe",
    "trophy",
    "next pro",
)

# Lower divisions we deliberately leave out (Championship is the exception above).
_LOWER_DIVISION = (
    "2.",
    "3.",
    "4.",
    "segunda",
    "serie b",
    "serie c",
    "division 2",
    "divisao 2",
    "liga 2",
    "liga 3",
    "liga ii",
    "liga iii",
    "ligue 2",
    "laliga2",
    "la liga 2",
    "1. lig",
    "1. division",
    "first division",
    "regionalliga",
    "oberliga",
    "superettan",
)


def league_key(label: str | None) -> str | None:
    """Stable league id, or None when the label is not one of the seeded senior leagues."""
    if not label or "/" not in label:
        return None
    parts = [
        part.strip().lower()
        for part in label.replace("—", "/").replace("–", "/").split("/")
        if part.strip()
    ]
    if len(parts) < 2:
        return None
    competition = parts[-1]
    region = parts[-2]
    if region == "football":
        return None
    if any(term in competition for term in _NOT_SENIOR_LEAGUE):
        return None
    if any(term in competition for term in _LOWER_DIVISION):
        return None
    # A trailing tier number, e.g. "Liga Portugal 2", "Bundesliga 3", "Primera B".
    if competition.rstrip().endswith((" 2", " 3", " 4", " b", " ii")):
        return None
    for key, regions, phrases in _LEAGUES:
        if region not in regions:
            continue
        if any(competition.startswith(phrase) for phrase in phrases):
            return key
    return None
