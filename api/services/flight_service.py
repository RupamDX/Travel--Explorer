"""
Flight service for handling flight-related operations
"""
import os
from typing import Dict, Any, Optional, List
from datetime import date, datetime, timedelta
import logging
import sys

# Add the backend directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.flight_search import FlightDataExtractor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FlightService:
    """
    Service for handling flight-related operations.
    Wraps the FlightDataExtractor to provide a clean API.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the flight service.
        
        Args:
            api_key: API key for SerpAPI
        """
        self.api_key = api_key or os.getenv("SERP_API_KEY")
        if not self.api_key:
            raise ValueError("SERP_API_KEY not provided")
        
        self.extractor = FlightDataExtractor(api_key=self.api_key)
    
    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        travel_class: int = 1,
        stops: int = 0,
        deep_search: bool = False
    ) -> Dict[str, Any]:
        """
        Search for flights.
        
        Args:
            origin: Origin IATA code
            destination: Destination IATA code
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Return date (YYYY-MM-DD)
            adults: Number of adults
            children: Number of children
            infants: Number of infants
            travel_class: Travel class (1: Economy, 2: Premium Economy, 3: Business, 4: First)
            stops: Maximum number of stops (0: direct, 1: one stop, 2: two stops)
            deep_search: Whether to perform a deep search
            
        Returns:
            Dictionary containing flight information
        """
        logger.info(f"Searching flights from {origin} to {destination} on {departure_date}")
        
        # Validate dates
        today = date.today()
        try:
            dep_date = datetime.strptime(departure_date, "%Y-%m-%d").date()
            
            if dep_date <= today:
                logger.warning(f"Invalid departure date: {departure_date}")
                return {"error": "Departure date must be in the future"}
            
            if return_date:
                ret_date = datetime.strptime(return_date, "%Y-%m-%d").date()
                if ret_date <= dep_date:
                    logger.warning(f"Invalid return date: {return_date}")
                    return {"error": "Return date must be after departure date"}
        except ValueError:
            logger.warning(f"Invalid date format: {departure_date} or {return_date}")
            return {"error": "Invalid date format. Use YYYY-MM-DD format."}
        
        # Search flights
        try:
            raw_data = self.extractor.search_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                deep_search=deep_search,
                travel_class=travel_class,
                adults=adults,
                children=children,
                infants_in_seat=infants,
                stops=stops
            )
            
            # Extract information
            flights = self.extractor.extract_important_flight_info(raw_data)
            return flights
        
        except Exception as e:
            logger.error(f"Error searching flights: {str(e)}")
            return {"error": str(e)}
    
    def get_flight_details(self, flight_id: str) -> Dict[str, Any]:
        """
        Get details for a specific flight.
        
        Args:
            flight_id: Flight ID
            
        Returns:
            Dictionary containing flight details
        """
        # In a real application, you would fetch flight details from a database
        # or an external API using the flight ID
        # This is a placeholder implementation
        return {"error": "Function not implemented - flight details would be fetched from a database"}
    
    def get_best_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Get the best flights based on price and duration.
        
        Args:
            origin: Origin IATA code
            destination: Destination IATA code
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Return date (YYYY-MM-DD)
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary containing the best flights
        """
        logger.info(f"Getting best flights from {origin} to {destination} on {departure_date}")
        
        flights = self.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            deep_search=True
        )
        
        if "error" in flights:
            return flights
        
        # Select the top flights
        outbound = flights.get("outbound_flights", [])[:max_results]
        return_flights = flights.get("return_flights", [])[:max_results]
        
        return {
            "search_info": flights.get("search_info", {}),
            "outbound_flights": outbound,
            "return_flights": return_flights
        }

    def get_available_airlines(self) -> List[str]:
        """
        Get a list of available airlines.
        
        Returns:
            List of airline codes
        """
        # In a real application, you would fetch this from a database
        # This is a placeholder implementation
        return [
            "AA", "UA", "DL", "LH", "BA", "AF", "KL", "IB", "QR", "EK",
            "TK", "SQ", "CX", "JL", "NH", "OZ", "CA", "MU", "CZ", "ET"
        ]

    def get_popular_routes(self) -> List[Dict[str, str]]:
        """
        Get a list of popular flight routes.
        
        Returns:
            List of popular routes
        """
        # In a real application, you would fetch this from a database
        # This is a placeholder implementation
        return [
            {"origin": "JFK", "destination": "LAX"},
            {"origin": "LHR", "destination": "JFK"},
            {"origin": "SFO", "destination": "HKG"},
            {"origin": "CDG", "destination": "DXB"},
            {"origin": "SIN", "destination": "SYD"}
        ]