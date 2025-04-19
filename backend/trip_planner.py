# trip_planner.py

import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI
from pandas import DataFrame

from backend.flight_search import FlightDataExtractor
from backend.hotel_search import query_hotels
from backend.LLMchat import get_restaurants_from_snowflake, search_places

# Load API keys
load_dotenv()
SERP_API_KEY = os.getenv("SERP_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not SERP_API_KEY:
    raise ValueError("SERP_API_KEY not found in .env")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env")

# OpenAI client
_client = OpenAI(api_key=OPENAI_API_KEY)


def _parse_price(price: Any) -> Optional[float]:
    """Try to coerce price to float, else return None."""
    try:
        return float(price)
    except Exception:
        return None


def search_trip(
    origin: str,
    destination: str,
    departure_date: str,
    is_round_trip: bool,
    return_date: Optional[str],
    max_results: int = 5
) -> Dict[str, Any]:
    """
    Fetch flight options, hotel options, restaurants, and attractions.

    Returns a dict with keys:
      - flight_options: List of dicts {"label": str, "outbound": ..., "return": ... (opt)}
      - hotel_options: List of hotel dicts
      - restaurants: pandas.DataFrame
      - attractions: List[str]
      - departure_date, return_date
    """
    extractor = FlightDataExtractor(api_key=SERP_API_KEY)
    raw = extractor.search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date if is_round_trip else None
    )
    flights_info = extractor.extract_important_flight_info(raw)

    flight_options = []
    outbound = flights_info.get("outbound_flights", [])[:max_results]

    if is_round_trip:
        returning = flights_info.get("return_flights", [])[:max_results]
        for o, r in zip(outbound, returning):
            po = _parse_price(o.get("price"))
            pr = _parse_price(r.get("price"))
            total = po + pr if po is not None and pr is not None else None
            label = (
                f"Round‑trip: Out ${po or 'N/A'} ({o.get('duration')})  |  "
                f"Return ${pr or 'N/A'} ({r.get('duration')})  |  "
                f"Total ${total or 'N/A'}"
            )
            flight_options.append({"label": label, "outbound": o, "return": r})
    else:
        for f in outbound:
            po = _parse_price(f.get("price"))
            label = (
                f"One‑way: ${po or 'N/A'}  |  {f.get('duration')}  |  "
                f"{f.get('stops')} stops  |  {f.get('airlines')}"
            )
            flight_options.append({"label": label, "outbound": f})

    hotels = query_hotels(
        city=destination.lower(),
        rating=0.0,
        max_price=1e6,
        amenities=[]
    )[:max_results]

    restaurants: DataFrame = get_restaurants_from_snowflake(destination)
    attractions: List[str] = search_places(destination)

    return {
        "flight_options": flight_options,
        "hotel_options": hotels,
        "restaurants": restaurants,
        "attractions": attractions,
        "departure_date": departure_date,
        "return_date": return_date
    }


def generate_itinerary_text(
    flight_choice: Dict[str, Any],
    hotel_choice: Dict[str, Any],
    restaurants: DataFrame,
    attractions: List[str],
    num_days: Optional[int] = None
) -> str:
    """
    Call the OpenAI API to generate a day‑by‑day itinerary that
    interleaves attractions and restaurants.

    If num_days is provided (for one‑way trips), uses that; otherwise
    calculates days from return_date.
    """
    # Determine number of days
    if num_days is not None:
        days = num_days
    else:
        ret = flight_choice.get("return")
        dep_time = flight_choice["outbound"]["segments"][0]["departure"]["time"]
        dep = datetime.fromisoformat(dep_time)
        if ret:
            # assume return segment has a departure time
            ret_time = ret["segments"][0]["departure"]["time"]
            ret_dt = datetime.fromisoformat(ret_time)
            days = (ret_dt.date() - dep.date()).days + 1
        else:
            days = 1

    rest_list = []
    for _, row in restaurants.iterrows():
        rest_list.append(
            f"{row['NAME']} (Rating: {row['RATING']}) — {row['ADDRESS']} — {row['URL']}"
        )

    prompt_lines = [
        f"Create a detailed day-by-day itinerary for a {days}-day trip.",
        "",
        "Trip Details:",
        f"- Flight: {flight_choice['label']}",
        f"- Hotel: {hotel_choice.get('name')} (link: {hotel_choice.get('booking_link')})",
        "",
        "Attractions:",
    ]
    for a in attractions:
        prompt_lines.append(f"- {a}")
    prompt_lines.append("")
    prompt_lines.append("Restaurants:")
    for r in rest_list:
        prompt_lines.append(f"- {r}")
    prompt_lines.append("")
    prompt_lines.append(
        "Structure the itinerary as:\n"
        "Day 1:\n"
        "  Morning: …\n"
        "  Lunch: …\n"
        "  Afternoon: …\n"
        "  Dinner: …\n"
        "Interleave meals at restaurants between attractions."
    )

    response = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "\n".join(prompt_lines)}]
    )
    return response.choices[0].message.content
