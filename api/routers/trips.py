"""
API router for trip planning endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field

from api.services.trip_service import TripService
from api.mcp.models import ItineraryRequest, RecommendationRequest

router = APIRouter()

# Models
class TripPlanRequest(BaseModel):
    """Request model for trip planning"""
    destination: str = Field(..., description="Destination city or IATA code")
    departure_date: date = Field(..., description="Departure date")
    return_date: Optional[date] = Field(None, description="Return date (for round-trip)")
    stay_nights: Optional[int] = Field(None, description="Number of nights to stay (for one-way trips)", ge=1, le=30)
    flight: Optional[Dict[str, Any]] = Field(None, description="Selected flight information")
    hotel: Optional[Dict[str, Any]] = Field(None, description="Selected hotel information")
    interests: List[str] = Field([], description="List of user interests")
    trip_style: str = Field("balanced", description="Style of trip (relaxed, balanced, intensive)")
    budget_level: str = Field("medium", description="Budget level (budget, medium, luxury)")

# Dependencies
def get_trip_service() -> TripService:
    """Dependency for trip service"""
    return TripService()

@router.post("/plan", response_model=Dict[str, Any])
async def plan_trip(
    request: TripPlanRequest,
    trip_service: TripService = Depends(get_trip_service)
) -> Dict[str, Any]:
    """
    Plan a trip with the specified parameters.
    
    This endpoint uses the MCP server for enhanced itinerary generation if available.
    Otherwise, it falls back to the legacy method.
    """
    try:
        # Format dates
        departure_date = request.departure_date.strftime("%Y-%m-%d")
        return_date = request.return_date.strftime("%Y-%m-%d") if request.return_date else None
        
        # Plan trip
        trip_plan = trip_service.plan_trip(
            destination=request.destination,
            departure_date=departure_date,
            return_date=return_date,
            stay_nights=request.stay_nights,
            flight=request.flight,
            hotel=request.hotel,
            interests=request.interests,
            trip_style=request.trip_style,
            budget_level=request.budget_level
        )
        
        if "error" in trip_plan:
            raise HTTPException(status_code=400, detail=trip_plan["error"])
        
        return trip_plan
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations", response_model=Dict[str, Any])
async def get_travel_recommendations(
    destination: str = Query(..., description="Destination city or IATA code"),
    interests: Optional[str] = Query(None, description="Comma-separated list of user interests"),
    budget: str = Query("medium", description="Budget level (budget, medium, luxury)"),
    duration: int = Query(3, description="Trip duration in days", ge=1, le=30),
    adults: int = Query(1, description="Number of adults", ge=1),
    children: int = Query(0, description="Number of children", ge=0),
    trip_service: TripService = Depends(get_trip_service)
) -> Dict[str, Any]:
    """
    Get travel recommendations based on user interests.
    """
    try:
        # Parse interests
        interests_list = []
        if interests:
            interests_list = [i.strip() for i in interests.split(",")]
        
        # Travelers info
        travelers = {
            "adults": adults,
            "children": children
        }
        
        # Get recommendations
        recommendations = trip_service.get_travel_recommendations(
            destination=destination,
            interests=interests_list,
            budget=budget,
            duration=duration,
            travelers=travelers
        )
        
        if "error" in recommendations:
            raise HTTPException(status_code=400, detail=recommendations["error"])
        
        return recommendations
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recommendations", response_model=Dict[str, Any])
async def get_travel_recommendations_post(
    request: RecommendationRequest,
    trip_service: TripService = Depends(get_trip_service)
) -> Dict[str, Any]:
    """
    Get travel recommendations based on user interests (POST method).
    """
    try:
        # Default travelers if not provided
        travelers = request.travelers or {"adults": 1, "children": 0}
        
        # Get recommendations
        recommendations = trip_service.get_travel_recommendations(
            destination=request.destination,
            interests=request.interests,
            budget=request.budget,
            duration=request.duration,
            travelers=travelers
        )
        
        if "error" in recommendations:
            raise HTTPException(status_code=400, detail=recommendations["error"])
        
        return recommendations
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/itinerary", response_model=Dict[str, Any])
async def generate_itinerary(
    request: ItineraryRequest,
    trip_service: TripService = Depends(get_trip_service)
) -> Dict[str, Any]:
    """
    Generate a personalized travel itinerary.
    
    This endpoint uses the MCP server for enhanced itinerary generation if available.
    Otherwise, it falls back to the legacy method.
    """
    try:
        # Calculate stay duration
        stay_nights = None
        if request.departure_date and request.return_date:
            dep = datetime.strptime(request.departure_date, "%Y-%m-%d").date()
            ret = datetime.strptime(request.return_date, "%Y-%m-%d").date()
            stay_nights = (ret - dep).days
        
        # Construct a dummy flight object to satisfy the API
        flight = {
            "outbound": {
                "airlines": request.flight_info.split(',')[0] if ',' in request.flight_info else request.flight_info
            }
        }
        
        # Construct a dummy hotel object
        hotel = {
            "name": request.hotel_info.split('|')[0].strip() if '|' in request.hotel_info else request.hotel_info
        }
        
        # Generate itinerary through the trip planning service
        result = trip_service.plan_trip(
            destination=request.city,
            departure_date=request.departure_date,
            return_date=request.return_date,
            stay_nights=stay_nights,
            flight=flight,
            hotel=hotel,
            interests=request.interests,
            trip_style=request.trip_style,
            budget_level=request.budget_level
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mcp-status", response_model=Dict[str, bool])
async def check_mcp_status(
    trip_service: TripService = Depends(get_trip_service)
) -> Dict[str, bool]:
    """
    Check if the MCP server is available.
    """
    return {"available": trip_service.mcp_available}