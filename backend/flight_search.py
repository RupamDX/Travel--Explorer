# flight_search.py

import os
import requests
import json
from dotenv import load_dotenv
from typing import Optional, Union, Dict, Any, List

# Load environment variables (including SERP API key)
load_dotenv()
SERP_API_KEY = os.getenv("SERP_API_KEY")


class FlightDataExtractor:
    """
    Search Google Flights via SerpAPI as two one-way calls when return_date is given,
    then stitch outbound and return legs together.
    """

    def __init__(self, api_key: str, base_url: str = "https://serpapi.com/search.json"):
        self.api_key = api_key
        self.base_url = base_url

    def _raw_one_way(
        self,
        origin: str,
        destination: str,
        date: str,
        deep_search: bool,
        travel_class: int,
        adults: int,
        children: int,
        infants_in_seat: int,
        infants_on_lap: int,
        stops: int,
        sort_by: int,
        hl: str,
        gl: str,
        **advanced_filters
    ) -> Dict[str, Any]:
        """Internal: fetch raw JSON for a single one-way leg."""
        params = {
            "engine":          "google_flights",
            "departure_id":    origin,
            "arrival_id":      destination,
            "outbound_date":   date,
            "type":            2,  # one-way
            "deep_search":     deep_search,
            "travel_class":    travel_class,
            "adults":          adults,
            "children":        children,
            "infants_in_seat": infants_in_seat,
            "infants_on_lap":  infants_on_lap,
            "stops":           stops,
            "sort_by":         sort_by,
            "hl":              hl,
            "gl":              gl,
            "api_key":         self.api_key,
        }
        params.update(advanced_filters)
        resp = requests.get(self.base_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        deep_search: bool = False,
        travel_class: int = 1,
        adults: int = 1,
        children: int = 0,
        infants_in_seat: int = 0,
        infants_on_lap: int = 0,
        stops: int = 0,
        sort_by: int = 1,
        hl: str = "en",
        gl: str = "us",
        **advanced_filters
    ) -> Dict[str, Any]:
        """
        If return_date is provided, do two one-way searches:
        1) origin -> destination on departure_date
        2) destination -> origin on return_date
        """
        outbound_raw = self._raw_one_way(
            origin, destination, departure_date,
            deep_search, travel_class, adults, children,
            infants_in_seat, infants_on_lap, stops, sort_by,
            hl, gl, **advanced_filters
        )

        return_raw = None
        if return_date:
            return_raw = self._raw_one_way(
                destination, origin, return_date,
                deep_search, travel_class, adults, children,
                infants_in_seat, infants_on_lap, stops, sort_by,
                hl, gl, **advanced_filters
            )

        return {
            "outbound_raw": outbound_raw,
            "return_raw":   return_raw
        }

    def extract_important_flight_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the paired raw JSON into structured outbound_flights and return_flights.
        """
        outbound = data.get("outbound_raw", {})
        return_block = data.get("return_raw")

        info = {
            "search_info": {
                "origin":         self._loc(outbound.get("airports", []), "departure"),
                "destination":    self._loc(outbound.get("airports", []), "arrival"),
                "departure_date": outbound.get("search_parameters", {}).get("outbound_date", "N/A"),
                "return_date":    outbound.get("search_parameters", {}).get("return_date", return_block and return_block.get("search_parameters", {}).get("outbound_date"))
            },
            "price_insights": self._pi(outbound.get("price_insights", {})),
            "outbound_flights": self._coll(outbound),
            "return_flights":   self._coll(return_block) if return_block else []
        }

        return info

    def _coll(self, block: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collect and detail flights from a raw block of best_flights + other_flights."""
        if not block:
            return []
        flights = []
        for section in ("best_flights", "other_flights"):
            for f in block.get(section, []):
                flights.append(f)
        flights.sort(key=lambda x: x.get("price", float("inf")))
        return [self._detail(f) for f in flights]

    def _loc(self, airports: list, direction: str) -> Dict[str, str]:
        if not airports or not airports[0].get(direction):
            return {"code":"N/A","name":"N/A","city":"N/A","country":"N/A"}
        ap = airports[0][direction][0]
        return {
            "code":    ap["airport"]["id"],
            "name":    ap["airport"]["name"],
            "city":    ap.get("city",""),
            "country": ap.get("country","")
        }

    def _pi(self, pi: dict) -> Dict[str, Any]:
        if not pi:
            return {"lowest_price":"N/A","price_level":"N/A","typical_range":"N/A"}
        return {
            "lowest_price":      pi.get("lowest_price","N/A"),
            "price_level":       pi.get("price_level","N/A"),
            "typical_range":     pi.get("typical_price_range","N/A")
        }

    def _detail(self, f: dict) -> Dict[str, Any]:
        info = {
            "price":    f.get("price","N/A"),
            "duration": self._fmt(f.get("total_duration",0)),
            "stops":    len(f.get("layovers",[])),
            "airlines": ", ".join({seg.get("airline","") for seg in f.get("flights",[])}),
            "layovers": [],
            "segments": []
        }
        for lv in f.get("layovers",[]):
            info["layovers"].append({
                "airport": lv.get("id","N/A"),
                "duration": self._fmt(lv.get("duration",0)),
                "overnight": lv.get("overnight",False)
            })
        for seg in f.get("flights",[]):
            info["segments"].append({
                "airline":       seg.get("airline","N/A"),
                "flight_number": seg.get("flight_number",""),
                "departure":     seg["departure_airport"]["id"],
                "arrival":       seg["arrival_airport"]["id"],
                "time_dep":      seg["departure_airport"]["time"],
                "time_arr":      seg["arrival_airport"]["time"],
                "duration":      self._fmt(seg.get("duration",0)),
                "aircraft":      seg.get("airplane","N/A")
            })
        return info

    def _fmt(self, minutes: Union[int,float]) -> str:
        if not isinstance(minutes,(int,float)) or minutes<=0:
            return "N/A"
        hrs, mins = divmod(int(minutes),60)
        if hrs and mins:
            return f"{hrs}h {mins}m"
        if hrs:
            return f"{hrs}h"
        return f"{mins}m"


if __name__ == "__main__":
    if not SERP_API_KEY:
        print("Set SERP_API_KEY in .env")
        exit(1)

    ext = FlightDataExtractor(api_key=SERP_API_KEY)
    combined = ext.search_flights(
        origin="BOS",
        destination="LAX",
        departure_date="2025-04-25",
        return_date="2025-04-28",
        deep_search=True
    )
    info = ext.extract_important_flight_info(combined)
    print(json.dumps(info, indent=2))
