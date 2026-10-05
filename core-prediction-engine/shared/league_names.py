"""Tell which domestic league a BetPawa label and a Football-Data file describe."""

from __future__ import annotations

# (key, regions, phrases that must appear in the competition name)
_LEAGUES = (
    ("epl", {"england", "uk", "great britain"}, ("premier league",)),
    ("championship", {"england", "uk", "great britain"}, ("championship",)),
    ("laliga", {"spain", "espana"}, ("la liga", "laliga", "primera division")),
    ("seriea", {"italy", "italia"}, ("serie a",)),
    ("bundesliga", {"germany", "deutschland"}, ("bundesliga",)),
    ("ligue1", {"france"}, ("ligue 1", "ligue1")),
    ("eredivisie", {"netherlands", "holland"}, ("eredivisie",)),
    ("primeira", {"portugal"}, ("liga portugal", "primeira liga", "primeira")),
)


def league_key(label: str | None) -> str | None:
    """Stable league id, or None when the label is not one of the seeded leagues."""
    if not label or "/" not in label:
        return None
    parts = [part.strip().lower() for part in label.replace("—", "/").replace("–", "/").split("/") if part.strip()]
    if len(parts) < 2:
        return None
    competition = parts[-1]
    region = parts[-2]
    if region == "football":
        return None
    if "2." in competition or competition.startswith("2") or "segunda" in competition or "serie b" in competition:
        return None
    if "ligue 2" in competition or "laliga2" in competition or "la liga 2" in competition:
        return None
    for key, regions, phrases in _LEAGUES:
        if region not in regions:
            continue
        if any(phrase in competition for phrase in phrases):
            return key
    return None
