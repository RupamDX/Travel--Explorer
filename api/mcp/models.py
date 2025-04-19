"""
Pydantic models for MCP integration
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import date, datetime

class Restaurant(BaseModel):
    """Restaurant model"""
    name: str
    rating: float = Field(0.0, ge=0, le=5)
    address: Optional[str] = None
    url: Optional[str] = None

class Attraction(BaseModel):
    """Attraction model"""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None

class ItineraryRequest(BaseModel):
    """Request model for generating an itinerary"""
    city: str
    attractions: List[str]
    restaurants: List[Dict[str, Any]]
    departure_date: str
    return_date: Optional[str] = None
    flight_info: str
    hotel_info: str
    interests: List[str] = []
    trip_style: str = "balanced"
    budget_level: str = "medium"

class RecommendationRequest(BaseModel):
    """Request model for getting travel recommendations"""
    destination: str
    interests: List[str] = []
    budget: str = "medium"
    duration: int = Field(3, ge=1, le=30)
    travelers: Optional[Dict[str, Any]] = None

class DailyPlan(BaseModel):
    """Model for a daily plan in the itinerary"""
    day: int
    morning: Optional[str] = None
    afternoon: Optional[str] = None
    evening: Optional[str] = None
    breakfast: Optional[str] = None
    lunch: Optional[str] = None
    dinner: Optional[str] = None

class ItineraryResponse(BaseModel):
    """Response model for generated itinerary"""
    itinerary: str
    highlights: List[str] = []
    daily_plans: List[Dict[str, Any]] = []
    estimated_costs: Dict[str, float] = {}

class RecommendationResponse(BaseModel):
    """Response model for travel recommendations"""
    recommended_attractions: List[Dict[str, Any]] = []
    recommended_restaurants: List[Dict[str, Any]] = []
    recommended_activities: List[Dict[str, Any]] = []
    recommended_hotels: List[Dict[str, Any]] = []

class PreferenceAnalysisRequest(BaseModel):
    """Request model for preference analysis"""
    search_history: List[Dict[str, Any]] = []
    selected_options: List[Dict[str, Any]] = []

class PreferenceAnalysisResponse(BaseModel):
    """Response model for preference analysis"""
    preferred_destinations: List[str] = []
    preferred_hotel_amenities: List[str] = []
    preferred_activities: List[str] = []
    budget_range: str = ""
    travel_style: str = ""