# get_hotels_from_api.py

import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
SERP_API_KEY = os.getenv("SERP_API_KEY")


class HotelDataExtractor:
    def __init__(self, api_key: str = SERP_API_KEY, base_url: str = "https://serpapi.com/search"):
        if not api_key:
            raise ValueError("Missing SerpAPI key")
        self.api_key = api_key
        self.base_url = base_url

    def fetch_raw_hotels(
        self,
        city: str,
        check_in_date: str,
        check_out_date: str
    ) -> Dict[str, Any]:
        params = {
            "engine": "google_hotels",
            "q": f"{city} hotels",
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "hl": "en",
            "gl": "us",
            "api_key": self.api_key
        }
        try:
            resp = requests.get(self.base_url, params=params)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"[HotelDataExtractor] Request failed: {e}")
            return {}

    def extract_important_hotel_info(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        if not raw or 'properties' not in raw:
            return {"error": "No hotel data found or invalid response format"}

        hotels = []
        for item in raw.get('properties', []):
            hotels.append({
                "name": item.get('name', 'N/A'),
                "class": item.get('extracted_hotel_class', item.get('hotel_class', 'N/A')),
                "rating": item.get('overall_rating', 'N/A'),
                "reviews": item.get('reviews', 'N/A'),
                "price": {
                    "nightly": item.get('rate_per_night', {}).get('lowest', 'N/A'),
                    "total": item.get('total_rate', {}).get('lowest', 'N/A'),
                },
                "key_amenities": item.get('amenities', [])[:10],
                "location_highlights": [
                    f"{place['name']} ({place['transportation'][0]['duration']} by {place['transportation'][0]['type']})"
                    for place in item.get('nearby_places', [])[:3]
                    if place.get('transportation')
                ],
                "images": [img.get('thumbnail', 'N/A') for img in item.get('images', [])[:5]],
                "booking_link": item.get('link', 'N/A')
            })

        return {
            "query": raw.get("search_parameters", {}).get("q", "N/A"),
            "dates": {
                "check_in": raw.get("search_parameters", {}).get("check_in_date", "N/A"),
                "check_out": raw.get("search_parameters", {}).get("check_out_date", "N/A")
            },
            "hotels": hotels,
            "total": len(hotels)
        }

    def get_hotels(
        self,
        city: str,
        departure_date: str,
        return_date: Optional[str] = None,
        stay_nights: int = 3
    ) -> Dict[str, Any]:
        """
        Compute check-in/check-out from return_date or stay_nights,
        fetch, and extract hotel options.
        """
        check_in = datetime.strptime(departure_date, "%Y-%m-%d")
        if return_date:
            check_out = datetime.strptime(return_date, "%Y-%m-%d")
        else:
            check_out = check_in + timedelta(days=stay_nights)

        check_in_str = check_in.strftime("%Y-%m-%d")
        check_out_str = check_out.strftime("%Y-%m-%d")

        raw_data = self.fetch_raw_hotels(city, check_in_str, check_out_str)
        return self.extract_important_hotel_info(raw_data)


# --- Optional test block ---
if __name__ == "__main__":
    extractor = HotelDataExtractor()
    hotels = extractor.get_hotels(
        city="Los Angeles",
        departure_date="2025-04-25",
        return_date="None",
        stay_nights=4
    )
    from pprint import pprint
    pprint(hotels)
