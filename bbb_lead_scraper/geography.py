from __future__ import annotations

import re

import pandas as pd

from bbb_lead_scraper.normalize import clean_text

ALLOWED_COUNTIES = {
    "Del Norte",
    "Humboldt",
    "Trinity",
    "Mendocino",
    "Lake",
    "Sonoma",
    "Napa",
    "Solano",
    "Marin",
    "Contra Costa",
    "San Francisco",
    "Alameda",
    "San Mateo",
}

CITY_TO_COUNTY = {
    # Del Norte
    "crescent city": "Del Norte",
    "smith river": "Del Norte",
    "klamath": "Del Norte",
    "gasquet": "Del Norte",
    # Humboldt
    "eureka": "Humboldt",
    "arcata": "Humboldt",
    "fortuna": "Humboldt",
    "mckinleyville": "Humboldt",
    "rio dell": "Humboldt",
    "trinidad": "Humboldt",
    "garberville": "Humboldt",
    "ferndale": "Humboldt",
    "hoopa": "Humboldt",
    "blue lake": "Humboldt",
    "scotia": "Humboldt",
    "willow creek": "Humboldt",
    "loleta": "Humboldt",
    "hydesville": "Humboldt",
    # Trinity
    "weaverville": "Trinity",
    "hayfork": "Trinity",
    "lewiston": "Trinity",
    "trinity center": "Trinity",
    "junction city": "Trinity",
    "burnt ranch": "Trinity",
    "douglas city": "Trinity",
    "hyampom": "Trinity",
    # Mendocino
    "ukiah": "Mendocino",
    "fort bragg": "Mendocino",
    "willits": "Mendocino",
    "mendocino": "Mendocino",
    "point arena": "Mendocino",
    "boonville": "Mendocino",
    "laytonville": "Mendocino",
    "covelo": "Mendocino",
    "redwood valley": "Mendocino",
    "hopland": "Mendocino",
    "gualala": "Mendocino",
    "philo": "Mendocino",
    # Lake
    "lakeport": "Lake",
    "clearlake": "Lake",
    "kelseyville": "Lake",
    "middletown": "Lake",
    "lower lake": "Lake",
    "lucerne": "Lake",
    "nice": "Lake",
    "cobb": "Lake",
    "hidden valley lake": "Lake",
    "clearlake oaks": "Lake",
    # Sonoma
    "santa rosa": "Sonoma",
    "petaluma": "Sonoma",
    "rohnert park": "Sonoma",
    "sebastopol": "Sonoma",
    "healdsburg": "Sonoma",
    "sonoma": "Sonoma",
    "windsor": "Sonoma",
    "cloverdale": "Sonoma",
    "cotati": "Sonoma",
    "guerneville": "Sonoma",
    "geyserville": "Sonoma",
    # Napa
    "napa": "Napa",
    "american canyon": "Napa",
    "calistoga": "Napa",
    "st helena": "Napa",
    "st. helena": "Napa",
    "yountville": "Napa",
    # Solano
    "vallejo": "Solano",
    "fairfield": "Solano",
    "vacaville": "Solano",
    "benicia": "Solano",
    "suisun city": "Solano",
    "dixon": "Solano",
    "rio vista": "Solano",
    "elmira": "Solano",
    # Marin
    "san rafael": "Marin",
    "novato": "Marin",
    "mill valley": "Marin",
    "sausalito": "Marin",
    "larkspur": "Marin",
    "corte madera": "Marin",
    "san anselmo": "Marin",
    "fairfax": "Marin",
    "tiburon": "Marin",
    "belvedere": "Marin",
    "ross": "Marin",
    "greenbrae": "Marin",
    "kentfield": "Marin",
    "marin city": "Marin",
    "woodacre": "Marin",
    "point reyes station": "Marin",
    "san geronimo": "Marin",
    # Contra Costa
    "richmond": "Contra Costa",
    "concord": "Contra Costa",
    "walnut creek": "Contra Costa",
    "lafayette": "Contra Costa",
    "san ramon": "Contra Costa",
    "orinda": "Contra Costa",
    "el sobrante": "Contra Costa",
    "danville": "Contra Costa",
    "moraga": "Contra Costa",
    "pleasant hill": "Contra Costa",
    "martinez": "Contra Costa",
    "san pablo": "Contra Costa",
    "kensington": "Contra Costa",
    "brentwood": "Contra Costa",
    "alamo": "Contra Costa",
    "pinole": "Contra Costa",
    "pittsburg": "Contra Costa",
    "hercules": "Contra Costa",
    "clayton": "Contra Costa",
    "oakley": "Contra Costa",
    "antioch": "Contra Costa",
    "el cerrito": "Contra Costa",
    "bay point": "Contra Costa",
    "rodeo": "Contra Costa",
    "crockett": "Contra Costa",
    "discovery bay": "Contra Costa",
    "knightsen": "Contra Costa",
    "byron": "Contra Costa",
    "pacheco": "Contra Costa",
    # San Francisco
    "san francisco": "San Francisco",
    "sf": "San Francisco",
    # Alameda
    "oakland": "Alameda",
    "berkeley": "Alameda",
    "hayward": "Alameda",
    "san leandro": "Alameda",
    "alameda": "Alameda",
    "albany": "Alameda",
    "emeryville": "Alameda",
    "pleasanton": "Alameda",
    "fremont": "Alameda",
    "livermore": "Alameda",
    "castro valley": "Alameda",
    "piedmont": "Alameda",
    "dublin": "Alameda",
    "newark": "Alameda",
    "union city": "Alameda",
    "san lorenzo": "Alameda",
    "sunol": "Alameda",
    # San Mateo
    "daly city": "San Mateo",
    "south san francisco": "San Mateo",
    "s san fran": "San Mateo",
    "so san francisco": "San Mateo",
    "ssf": "San Mateo",
    "san mateo": "San Mateo",
    "redwood city": "San Mateo",
    "burlingame": "San Mateo",
    "pacifica": "San Mateo",
    "san carlos": "San Mateo",
    "millbrae": "San Mateo",
    "san bruno": "San Mateo",
    "belmont": "San Mateo",
    "half moon bay": "San Mateo",
    "menlo park": "San Mateo",
    "foster city": "San Mateo",
    "hillsborough": "San Mateo",
    "brisbane": "San Mateo",
    "colma": "San Mateo",
    "atherton": "San Mateo",
    "portola valley": "San Mateo",
    "woodside": "San Mateo",
    "east palo alto": "San Mateo",
    "moss beach": "San Mateo",
    "el granada": "San Mateo",
    "san gregorio": "San Mateo",
    "la honda": "San Mateo",
}

ZIP_TO_COUNTY = {
    # San Mateo ZIPs that share the 940 prefix with non-target Santa Clara cities.
    **{z: "San Mateo" for z in [
        "94002", "94005", "94010", "94014", "94015", "94019", "94020", "94021",
        "94025", "94027", "94028", "94030", "94037", "94038", "94044", "94061",
        "94062", "94063", "94065", "94066", "94070", "94074", "94080",
    ]},
    # Solano ZIPs outside the otherwise allowed 945 prefix.
    **{z: "Solano" for z in ["95620", "95625", "95687", "95688", "95690", "95696"]},
    # Trinity ZIPs in the broader 960 prefix.
    **{z: "Trinity" for z in ["96010", "96024", "96041", "96046", "96048", "96052", "96091", "96093"]},
}

ZIP_PREFIX_TO_COUNTY = {
    "941": "San Francisco",
    "944": "San Mateo",
    "945": "Allowed 945 ZIP County",
    "946": "Alameda",
    "947": "Alameda",
    "948": "Contra Costa",
    "949": "Marin",
    "954": "Allowed 954 ZIP County",
    "955": "Allowed 955 ZIP County",
}


def extract_zip_from_row(row: pd.Series) -> str:
    for column in ("zip", "address", "google_address"):
        value = clean_text(row.get(column, ""))
        match = re.search(r"\b(\d{5})(?:-\d{4})?\b", value)
        if match:
            return match.group(1)
    return ""


def infer_county(row: pd.Series) -> str:
    city = clean_text(row.get("city", "")).lower()
    if city in CITY_TO_COUNTY:
        return CITY_TO_COUNTY[city]
    if city:
        return ""

    zip_code = extract_zip_from_row(row)
    if zip_code in ZIP_TO_COUNTY:
        return ZIP_TO_COUNTY[zip_code]

    county = ZIP_PREFIX_TO_COUNTY.get(zip_code[:3], "")
    if county.startswith("Allowed "):
        city_county = CITY_TO_COUNTY.get(city, "")
        if city_county:
            return city_county
        return county.replace("Allowed ", "").replace(" ZIP County", "")
    return county


def filter_allowed_counties(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["county"] = out.apply(infer_county, axis=1)
    return out[out["county"].isin(ALLOWED_COUNTIES)].copy()
