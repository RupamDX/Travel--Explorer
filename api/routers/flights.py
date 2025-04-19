"""
API router for flight-related endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field

from api.services.flight_service import FlightService

router = APIRouter()

# Models
class FlightSearchRequest(BaseModel):
    """Request model for flight search"""
    origin: str = Field(..., description="Origin IATA code", min_length=3, max_length=3)
    destination: str = Field(..., description="Destination IATA code", min_length=3, max_length=3)
    departure_date: date = Field(..., description="Departure date")
    return_date: Optional[date] = Field(None, description="Return date (for round-trip)")
    adults: int = Field(1, description="Number of adults", ge=1, le=9)
    children: int = Field(0, description="Number of children", ge=0, le=9)
    infants: int = Field(0, description="Number of infants", ge=0, le=4)
    travel_class: int = Field(1, description="Travel class (1: Economy, 2: Premium Economy, 3: Business, 4: First)", ge=1, le=4)
    stops: int = Field(0, description="Maximum number of stops", ge=0, le=2)
    deep_search: bool = Field(False, description="Whether to perform a deep search")

# Dependencies
def get_flight_service() -> FlightService:
    """Dependency for flight service"""
    return FlightService()

@router.get("/search", response_model=Dict[str, Any])
async def search_flights(
    origin: str = Query(..., description="Origin IATA code", min_length=3, max_length=3),
    destination: str = Query(..., description="Destination IATA code", min_length=3, max_length=3),
    departure_date: str = Query(..., description="Departure date (YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="Return date (YYYY-MM-DD)"),
    adults: int = Query(1, description="Number of adults", ge=1, le=9),
    children: int = Query(0, description="Number of children", ge=0, le=9),
    infants: int = Query(0, description="Number of infants", ge=0, le=4),
    travel_class: int = Query(1, description="Travel class (1: Economy, 2: Premium Economy, 3: Business, 4: First)", ge=1, le=4),
    stops: int = Query(0, description="Maximum number of stops", ge=0, le=2),
    deep_search: bool = Query(False, description="Whether to perform a deep search"),
    flight_service: FlightService = Depends(get_flight_service)
) -> Dict[str, Any]:
    """
    Search for flights.
    """
    try:
        # Format dates
        try:
            datetime.strptime(departure_date, "%Y-%m-%d")
            if return_date:
                datetime.strptime(return_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
        # Search flights
        flights = flight_service.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            travel_class=travel_class,
            stops=stops,
            deep_search=deep_search
        )
        
        if "error" in flights:
            raise HTTPException(status_code=400, detail=flights["error"])
        
        return flights
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=Dict[str, Any])
async def search_flights_post(
    request: FlightSearchRequest,
    flight_service: FlightService = Depends(get_flight_service)
) -> Dict[str, Any]:
    """
    Search for flights (POST method).
    """
    try:
        # Format dates
        departure_date = request.departure_date.strftime("%Y-%m-%d")
        return_date = request.return_date.strftime("%Y-%m-%d") if request.return_date else None
        
        # Search flights
        flights = flight_service.search_flights(
            origin=request.origin,
            destination=request.destination,
            departure_date=departure_date,
            return_date=return_date,
            adults=request.adults,
            children=request.children,
            infants=request.infants,
            travel_class=request.travel_class,
            stops=request.stops,
            deep_search=request.deep_search
        )
        
        if "error" in flights:
            raise HTTPException(status_code=400, detail=flights["error"])
        
        return flights
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/best", response_model=Dict[str, Any])
async def get_best_flights(
    origin: str = Query(..., description="Origin IATA code", min_length=3, max_length=3),
    destination: str = Query(..., description="Destination IATA code", min_length=3, max_length=3),
    departure_date: str = Query(..., description="Departure date (YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="Return date (YYYY-MM-DD)"),
    max_results: int = Query(5, description="Maximum number of results to return", ge=1, le=10),
    flight_service: FlightService = Depends(get_flight_service)
) -> Dict[str, Any]:
    """
    Get the best flights based on price and duration.
    """
    try:
        # Format dates
        try:
            datetime.strptime(departure_date, "%Y-%m-%d")
            if return_date:
                datetime.strptime(return_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
        # Get best flights
        flights = flight_service.get_best_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            max_results=max_results
        )
        
        if "error" in flights:
            raise HTTPException(status_code=400, detail=flights["error"])
        
        return flights
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))