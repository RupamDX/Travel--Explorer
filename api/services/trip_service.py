"""
Trip service for handling trip planning operations
"""
import os
import sys
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, date, timedelta
import pandas as pd
import requests

# Add the backend directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from backend.LLMchat import search_places, get_restaurants_from_snowflake, generate_itinerary
from backend.trip_planner import generate_itinerary_text

# Import MCP client
from api.mcp.client import MCPClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TripService:
    """
    Service for handling trip planning operations.
    Integrates with the MCP client for enhanced functionality.
    """
    
    def __init__(
        self, 
        serp_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        mcp_url: Optional[str] = None,
        mcp_api_key: Optional[str] = None
    ):
        """
        Initialize the trip service.
        
        Args:
            serp_api_key: API key for SerpAPI
            openai_api_key: API key for OpenAI
            mcp_url: URL for the MCP server
            mcp_api_key: API key for the MCP server
        """
        self.serp_api_key = serp_api_key or os.getenv("SERP_API_KEY")
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.serp_api_key:
            logger.warning("SERP_API_KEY not found in environment variables.")
        
        # Initialize MCP client
        self.mcp_client = MCPClient(
            base_url=mcp_url or os.getenv("MCP_SERVER_URL"),
            api_key=mcp_api_key or os.getenv("MCP_API_KEY")
        )
        
        # Check MCP server status
        try:
            health_response = self.mcp_client.health_check()
            self.mcp_available = health_response.get("status") == "healthy"
            logger.info(f"MCP server status: {'Available' if self.mcp_available else 'Unavailable'}")
        except Exception as e:
            logger.warning(f"MCP server not available: {str(e)}. Using fallback methods.")
            self.mcp_available = False
    
    def _get_city_name(self, destination: str) -> str:
        """
        Convert IATA code to city name if needed.
        
        Args:
            destination: Destination city or IATA code
            
        Returns:
            City name
        """
        # Map IATA code to city name if applicable
        if len(destination) == 3 and destination.isalpha() and destination.isupper():
            iata_city_mapping = {
                "ATL": "atlanta", "AUS": "austin", "BOS": "boston", "ORD": "chicago", 
                "DFW": "dallas", "DEN": "denver", "IAH": "houston", "IND": "indianapolis", 
                "LAS": "las_vegas", "LAX": "los_angeles", "MIA": "miami", "BNA": "nashville", 
                "JFK": "new_york", "PHL": "philadelphia", "PHX": "phoenix", "SAT": "san_antonio", 
                "SFO": "san_francisco", "SJC": "san_jose", "SEA": "seattle", "IAD": "washington_dc"
            }
            return iata_city_mapping.get(destination, destination.lower())
        
        return destination.lower()
    
    def plan_trip(
        self,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        stay_nights: Optional[int] = None,
        flight: Optional[Dict[str, Any]] = None,
        hotel: Optional[Dict[str, Any]] = None,
        interests: List[str] = None,
        trip_style: str = "balanced",
        budget_level: str = "medium"
    ) -> Dict[str, Any]:
        """
        Plan a trip with the specified parameters.
        
        Args:
            destination: Destination city or IATA code
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Return date (YYYY-MM-DD)
            stay_nights: Number of nights to stay (for one-way trips)
            flight: Selected flight information
            hotel: Selected hotel information
            interests: List of user interests
            trip_style: Style of the trip (relaxed, balanced, intensive)
            budget_level: Budget level (budget, medium, luxury)
            
        Returns:
            Dictionary containing the trip plan
        """
        logger.info(f"Planning trip to {destination} from {departure_date} to {return_date or 'N/A'}")
        
        if interests is None:
            interests = ["sightseeing", "food", "culture"]
        
        # Calculate stay duration
        if return_date:
            dep = datetime.strptime(departure_date, "%Y-%m-%d").date()
            ret = datetime.strptime(return_date, "%Y-%m-%d").date()
            duration = (ret - dep).days
        else:
            duration = stay_nights or 3  # Default to 3 nights
        
        # Normalize city name
        city_name = self._get_city_name(destination)
        
        # Fetch attractions and restaurants ONCE and store in variables
        try:
            attractions = search_places(city_name)
            logger.info(f"Found {len(attractions)} attractions for {city_name}")
        except Exception as e:
            logger.error(f"Error fetching attractions: {str(e)}")
            attractions = []
        
        # Store restaurants data to avoid duplicate queries
        restaurant_data = None
        try:
            restaurants = get_restaurants_from_snowflake(city_name)
            
            # Convert to a standard format for reuse
            if isinstance(restaurants, pd.DataFrame):
                restaurant_data = restaurants.to_dict('records')
                logger.info(f"Found {len(restaurants)} restaurants for {city_name}")
            else:
                restaurant_data = restaurants
                logger.info(f"Found {len(restaurant_data)} restaurants for {city_name}")
        except Exception as e:
            logger.error(f"Error fetching restaurants: {str(e)}")
            restaurant_data = []
        
        # Format flight and hotel info
        flight_info = "Not specified"
        if flight:
            outbound = flight.get("outbound", {})
            flight_info = (
                f"Outbound: {outbound.get('airlines', 'N/A')}, "
                f"{outbound.get('price', 'N/A')}, "
                f"{outbound.get('duration', 'N/A')}, "
                f"Stops: {outbound.get('stops', 'N/A')}"
            )
            
            if return_date and "return" in flight:
                ret = flight["return"]
                flight_info += (
                    f"\nReturn: {ret.get('airlines', 'N/A')}, "
                    f"{ret.get('price', 'N/A')}, "
                    f"{ret.get('duration', 'N/A')}, "
                    f"Stops: {ret.get('stops', 'N/A')}"
                )
        
        hotel_info = "Not specified"
        if hotel:
            hotel_info = (
                f"{hotel.get('name', 'N/A')} | "
                f"{hotel.get('price', {}).get('nightly', 'N/A')} per night, "
                f"Total: {hotel.get('price', {}).get('total', 'N/A')} | "
                f"Rating: {hotel.get('rating', 'N/A')} | "
                f"Amenities: {', '.join(hotel.get('key_amenities', []))}"
            )
        
        # Try to use MCP for enhanced itinerary generation
        if self.mcp_available:
            logger.info("Using MCP server for itinerary generation")
            try:
                # Use the already fetched restaurant data instead of fetching again
                mcp_response = self.mcp_client.generate_itinerary(
                    city=city_name,
                    attractions=attractions,
                    restaurants=restaurant_data,  # Use stored data
                    departure_date=departure_date,
                    return_date=return_date,
                    flight_info=flight_info,
                    hotel_info=hotel_info,
                    interests=interests,
                    trip_style=trip_style,
                    budget_level=budget_level
                )
                
                if "error" not in mcp_response:
                    logger.info("Successfully generated itinerary with MCP")
                    return {
                        "itinerary": mcp_response.get("itinerary", ""),
                        "highlights": mcp_response.get("highlights", []),
                        "daily_plans": mcp_response.get("daily_plans", []),
                        "estimated_costs": mcp_response.get("estimated_costs", {}),
                        "source": "mcp"
                    }
                else:
                    logger.error(f"Error from MCP: {mcp_response.get('error')}")
            except Exception as e:
                logger.error(f"Error using MCP for itinerary generation: {str(e)}")
        
        # Fallback to legacy method if MCP is not available or failed
        logger.info("Falling back to legacy itinerary generation")
        try:
            # Use the already fetched data instead of fetching again
            try:
                itinerary = generate_itinerary(
                    city=city_name,
                    attractions=attractions,  # Use stored data
                    restaurants=restaurant_data,  # Use stored data 
                    dep_date=departure_date,
                    return_date=return_date,
                    flight_info=flight_info,
                    hotel_info=hotel_info
                )
                return {
                    "itinerary": itinerary,
                    "highlights": [],
                    "daily_plans": [],
                    "estimated_costs": {},
                    "source": "legacy_llm"
                }
            except Exception as e:
                logger.error(f"Error using primary legacy method: {str(e)}")
                # If that fails, try the alternative method
                itinerary = generate_itinerary_text(
                    flight_choice={"label": flight_info, "outbound": flight.get("outbound", {})},
                    hotel_choice=hotel or {},
                    restaurants=restaurant_data,  # Use stored data
                    attractions=attractions,  # Use stored data
                    num_days=duration
                )
                
                return {
                    "itinerary": itinerary,
                    "highlights": [],
                    "daily_plans": [],
                    "estimated_costs": {},
                    "source": "legacy_alternative"
                }
        except Exception as e:
            logger.error(f"All itinerary generation methods failed: {str(e)}")
            return {"error": f"Failed to generate itinerary: {str(e)}"}
    
    def get_travel_recommendations(
        self,
        destination: str,
        interests: List[str] = None,
        budget: str = "medium",
        duration: int = 3,
        travelers: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Get travel recommendations based on user interests.
        
        Args:
            destination: Destination city
            interests: List of user interests
            budget: Budget level (budget, medium, luxury)
            duration: Trip duration in days
            travelers: Information about travelers (adults, children, etc.)
            
        Returns:
            Dictionary containing recommendations
        """
        if interests is None:
            interests = ["sightseeing", "food", "culture"]
        
        if travelers is None:
            travelers = {"adults": 1, "children": 0}
        
        # Normalize city name
        city_name = self._get_city_name(destination)
        
        # Try to use MCP for recommendations
        if self.mcp_available:
            logger.info(f"Using MCP server for travel recommendations for {city_name}")
            try:
                return self.mcp_client.get_travel_recommendations(
                    city=city_name,
                    interests=interests,
                    budget=budget,
                    duration=duration,
                    travelers=travelers
                )
            except Exception as e:
                logger.error(f"Error using MCP for recommendations: {str(e)}")
                # Fall back to simple method
        
        # Fallback: fetch basic recommendations
        logger.info(f"Falling back to basic recommendations for {city_name}")
        attractions = search_places(city_name)
        restaurants = get_restaurants_from_snowflake(city_name)
        
        # Convert restaurants DataFrame to list of dicts if needed
        restaurant_list = restaurants
        if isinstance(restaurants, pd.DataFrame):
            restaurant_list = restaurants.to_dict('records')
        
        return {
            "recommended_attractions": [
                {"name": attr.split(":")[0], "description": attr.split(":", 1)[1].strip() if ":" in attr else ""} 
                for attr in attractions
            ],
            "recommended_restaurants": restaurant_list,
            "recommended_activities": [],  # No activity data in legacy mode
            "recommended_hotels": [],  # No hotel recommendations in legacy mode
            "source": "legacy"
        }