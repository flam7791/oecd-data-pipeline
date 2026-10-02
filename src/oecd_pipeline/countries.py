"""Country and aggregate names for the reference-area codes used by the OECD API."""

NAMES = {
    "AUS": "Australia", "AUT": "Austria", "BEL": "Belgium", "CAN": "Canada",
    "CHL": "Chile", "COL": "Colombia", "CRI": "Costa Rica", "CZE": "Czechia",
    "DNK": "Denmark", "EST": "Estonia", "FIN": "Finland", "FRA": "France",
    "DEU": "Germany", "GRC": "Greece", "HUN": "Hungary", "ISL": "Iceland",
    "IRL": "Ireland", "ISR": "Israel", "ITA": "Italy", "JPN": "Japan",
    "KOR": "Korea", "LVA": "Latvia", "LTU": "Lithuania", "LUX": "Luxembourg",
    "MEX": "Mexico", "NLD": "Netherlands", "NZL": "New Zealand", "NOR": "Norway",
    "POL": "Poland", "PRT": "Portugal", "SVK": "Slovak Republic", "SVN": "Slovenia",
    "ESP": "Spain", "SWE": "Sweden", "CHE": "Switzerland", "TUR": "Türkiye",
    "GBR": "United Kingdom", "USA": "United States",
    # Aggregates commonly available in OECD dataflows
    "OECD": "OECD total", "EA20": "Euro area (20 countries)",
    "EU27_2020": "European Union (27 countries from 2020)", "G7": "G7",
}


def country_name(code: str) -> str:
    """Return the readable name for a code, or the code itself if unknown."""
    return NAMES.get(code, code)
