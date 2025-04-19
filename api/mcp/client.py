"""
MCP Client for Trip Planning
"""
import os
import requests
import logging
from typing import Dict, Any, Optional, List, Union
import json

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Client for interacting with the MCP (Model Calling Protocol) server for Trip Planning.
    
    This class handles communication with the MCP server to:
    1. Generate personalized travel itineraries
    2. Get recommendations for attractions and activities
    3. Analyze user preferences for better suggestions
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the MCP client.
        
        Args:
            base_url: Base URL for the MCP server
            api_key: API key for authentication
        """
        self.base_url = base_url or os.getenv("MCP_SERVER_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("MCP_API_KEY", "")
        
        if not self.api_key:
            logger.warning("No MCP API key provided. Some functionality may be limited.")
    
    def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the MCP server.
        
        Args:
            endpoint: API endpoint to call
            method: HTTP method (GET, POST, etc.)
            data: Request payload
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=data)
            elif method.upper() == "POST":
                headers["Content-Type"] = "application/json"
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to MCP server: {str(e)}")
            return {"error": str(e)}
    
    def generate_itinerary(self, 
                          city: str, 
                          attractions: List[str], 
                          restaurants: List[Dict[str, Any]], 
                          departure_date: str, 
                          return_date: Optional[str], 
                          flight_info: str, 
                          hotel_info: str,
                          interests: List[str] = None,
                          trip_style: str = "balanced",
                          budget_level: str = "medium") -> Dict[str, Any]:
        """
        Generate a personalized travel itinerary.
        
        Args:
            city: Destination city
            attractions: List of attractions
            restaurants: List of restaurants
            departure_date: Departure date
            return_date: Return date (None for one-way trips)
            flight_info: Flight information string
            hotel_info: Hotel information string
            interests: List of user interests
            trip_style: Style of the trip (relaxed, balanced, intensive)
            budget_level: Budget level (budget, medium, luxury)
            
        Returns:
            Dictionary containing the generated itinerary
        """
        endpoint = "/generate/itinerary"
        
        # Convert restaurant data to a format suitable for the MCP server
        restaurant_data = []
        for r in restaurants:
            # Handle both DataFrame rows and dictionaries
            if hasattr(r, 'to_dict'):
                r = r.to_dict()
            
            restaurant_data.append({
                "name": r.get("NAME", r.get("name", "")), 
                "rating": r.get("RATING", r.get("rating", 0)), 
                "address": r.get("ADDRESS", r.get("address", "")),
                "url": r.get("URL", r.get("url", ""))
            })
        
        data = {
            "city": city,
            "attractions": attractions,
            "restaurants": restaurant_data,
            "departure_date": departure_date,
            "return_date": return_date,
            "flight_info": flight_info,
            "hotel_info": hotel_info,
            "interests": interests or [],
            "trip_style": trip_style,
            "budget_level": budget_level
        }
        
        return self._make_request(endpoint, method="POST", data=data)
    
    def get_travel_recommendations(self, 
                                 city: str, 
                                 interests: List[str] = None,
                                 budget: str = "medium",
                                 duration: int = 3,
                                 travelers: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get travel recommendations based on user interests.
        
        Args:
            city: Destination city
            interests: List of user interests
            budget: Budget level (budget, medium, luxury)
            duration: Trip duration in days
            travelers: Information about travelers (adults, children, etc.)
            
        Returns:
            Dictionary containing recommendations
        """
        endpoint = "/recommendations"
        
        data = {
            "city": city,
            "interests": interests or ["sightseeing", "food", "culture"],
            "budget": budget,
            "duration": duration,
            "travelers": travelers or {"adults": 1, "children": 0}
        }
        
        return self._make_request(endpoint, method="POST", data=data)
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the MCP server.
        
        Returns:
            Dictionary containing health status
        """
        endpoint = "/health"
        return self._make_request(endpoint, method="GET")