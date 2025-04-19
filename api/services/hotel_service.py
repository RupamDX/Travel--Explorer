"""
Hotel service for handling hotel-related operations
"""
import os
import sys
from typing import Dict, Any, Optional, List
import logging

# Add the backend directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.hotel_search import query_hotels
try:
    from backend.get_hotels_from_api import HotelDataExtractor
except ImportError:
    # Define a placeholder HotelDataExtractor if the module is not available
    class HotelDataExtractor:
        def __init__(self, api_key):
            self.api_key = api_key
        
        def get_hotels(self, city, departure_date=None, return_date=None, stay_nights=None):
            return {"hotels": [], "error": "HotelDataExtractor not available"}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HotelService:
    """
    Service for handling hotel-related operations.
    """
    
    def __init__(self, api_key: Optional[str] = None, pinecone_api_key: Optional[str] = None):
        """
        Initialize the hotel service.
        
        Args:
            api_key: API key for SerpAPI
            pinecone_api_key: API key for Pinecone
        """
        self.api_key = api_key or os.getenv("SERP_API_KEY")
        self.pinecone_api_key = pinecone_api_key or os.getenv("PINECONE_API_KEY")
        
        if not self.api_key:
            raise ValueError("SERP_API_KEY not provided")
        
        # Initialize HotelDataExtractor for API-based search
        try:
            self.hotel_extractor = HotelDataExtractor(api_key=self.api_key)
            self.api_search_available = True
        except Exception as e:
            logger.warning(f"Failed to initialize HotelDataExtractor: {str(e)}")
            self.api_search_available = False
    
    def search_hotels(
        self,
        city: str,
        check_in_date: Optional[str] = None,
        check_out_date: Optional[str] = None,
        stay_nights: Optional[int] = None,
        rating: float = 0.0,
        max_price: float = 1000.0,
        amenities: List[str] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search for hotels using vector search or API.
        
        Args:
            city: City name
            check_in_date: Check-in date (YYYY-MM-DD)
            check_out_date: Check-out date (YYYY-MM-DD)
            stay_nights: Number of nights to stay
            rating: Minimum rating
            max_price: Maximum price per night
            amenities: List of required amenities
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary containing hotel information
        """
        logger.info(f"Searching hotels in {city}")
        
        if amenities is None:
            amenities = []
        
        try:
            # If we have check-in/out dates, use direct API search
            if check_in_date and (check_out_date or stay_nights) and self.api_search_available:
                return self.search_hotels_api(
                    city=city,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    stay_nights=stay_nights,
                    max_results=max_results
                )
            
            # Otherwise use the vector search
            hotels = query_hotels(
                city=city,
                rating=rating,
                max_price=max_price,
                amenities=amenities,
                top_k=max_results
            )
            
            return {"hotels": hotels, "count": len(hotels)}
        
        except Exception as e:
            logger.error(f"Error searching hotels: {str(e)}")
            return {"error": str(e), "hotels": []}
    
    def search_hotels_api(
        self,
        city: str,
        check_in_date: str,
        check_out_date: Optional[str] = None,
        stay_nights: Optional[int] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search for hotels using the SerpAPI.
        
        Args:
            city: City name or IATA code
            check_in_date: Check-in date (YYYY-MM-DD)
            check_out_date: Check-out date (YYYY-MM-DD)
            stay_nights: Number of nights to stay
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary containing hotel information
        """
        logger.info(f"Searching hotels in {city} from {check_in_date} to {check_out_date or 'N/A'}")
        
        if not self.api_search_available:
            return {"error": "API search not available", "hotels": []}
        
        try:
            # If city is IATA code (3 uppercase letters), use it directly
            # Otherwise, normalize the city name
            city_param = city.upper() if (len(city) == 3 and city.isalpha() and city.isupper()) else city.lower()
            
            hotel_data = self.hotel_extractor.get_hotels(
                city=city_param,
                departure_date=check_in_date,
                return_date=check_out_date,
                stay_nights=stay_nights
            )
            
            # Limit the number of results
            hotels = hotel_data.get("hotels", [])[:max_results]
            
            return {"hotels": hotels, "count": len(hotels)}
        
        except Exception as e:
            logger.error(f"Error searching hotels via API: {str(e)}")
            return {"error": str(e), "hotels": []}
    
    def get_hotel_details(self, hotel_id: str) -> Dict[str, Any]:
        """
        Get details for a specific hotel.
        
        Args:
            hotel_id: Hotel ID
            
        Returns:
            Dictionary containing hotel details
        """
        # In a real application, you would fetch hotel details from a database
        # or an external API using the hotel ID
        # This is a placeholder implementation
        return {"error": "Function not implemented - hotel details would be fetched from a database"}
    
    def filter_hotels(
        self,
        hotels: List[Dict[str, Any]],
        rating: float = 0.0,
        max_price: float = 1000.0,
        amenities: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter hotels based on criteria.
        
        Args:
            hotels: List of hotels
            rating: Minimum rating
            max_price: Maximum price per night
            amenities: List of required amenities
            
        Returns:
            Filtered list of hotels
        """
        if amenities is None:
            amenities = []
        
        filtered = []
        
        for hotel in hotels:
            # Check rating
            hotel_rating = float(hotel.get("rating", 0))
            if hotel_rating < rating:
                continue
            
            # Check price
            try:
                price_str = hotel.get("price", {}).get("nightly", "0").replace("$", "").replace(",", "")
                price = float(price_str)
                if price > max_price:
                    continue
            except (ValueError, AttributeError):
                # Skip if price can't be parsed
                continue
            
            # Check amenities
            hotel_amenities = hotel.get("key_amenities", [])
            if amenities:
                if not all(a.lower() in [ha.lower() for ha in hotel_amenities] for a in amenities):
                    continue
            
            filtered.append(hotel)
        
        return filtered
    
    def get_available_amenities(self) -> List[str]:
        """
        Get a list of available hotel amenities for filtering.
        
        Returns:
            List of available amenities
        """
        # In a real application, you would fetch this from a database
        # This is a placeholder list of common amenities
        return [
            "Free WiFi",
            "Swimming Pool",
            "Fitness Center",
            "Spa",
            "Restaurant",
            "Bar",
            "Room Service",
            "Business Center",
            "Pet-friendly",
            "Airport Shuttle",
            "Free Breakfast",
            "Child-friendly",
            "Parking",
            "Accessible Rooms",
            "Air Conditioning",
            "Concierge",
            "Hot Tub/Jacuzzi",
            "Laundry Service",
            "Non-smoking Rooms",
            "Meeting Rooms"
        ]
    
    def get_popular_destinations(self) -> List[Dict[str, Any]]:
        """
        Get a list of popular destinations.
        
        Returns:
            List of popular destinations
        """
        # In a real application, you would fetch this from a database
        # This is a placeholder implementation
        return [
            {"city": "New York", "code": "NYC", "country": "USA"},
            {"city": "Paris", "code": "PAR", "country": "France"},
            {"city": "London", "code": "LON", "country": "UK"},
            {"city": "Tokyo", "code": "TYO", "country": "Japan"},
            {"city": "Rome", "code": "ROM", "country": "Italy"}
        ]