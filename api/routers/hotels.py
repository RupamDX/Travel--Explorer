"""
API router for hotel-related endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field

from api.services.hotel_service import HotelService

router = APIRouter()

# Models
class HotelSearchRequest(BaseModel):
    """Request model for hotel search"""
    city: str = Field(..., description="City name or IATA code")
    check_in_date: Optional[date] = Field(None, description="Check-in date")
    check_out_date: Optional[date] = Field(None, description="Check-out date")
    stay_nights: Optional[int] = Field(None, description="Number of nights to stay (for one-way trips)", ge=1, le=30)
    rating: float = Field(0.0, description="Minimum rating", ge=0.0, le=5.0)
    max_price: float = Field(1000.0, description="Maximum price per night", ge=0.0)
    amenities: List[str] = Field([], description="List of required amenities")
    max_results: int = Field(10, description="Maximum number of results to return", ge=1, le=50)

# Dependencies
def get_hotel_service() -> HotelService:
    """Dependency for hotel service"""
    return HotelService()

@router.get("/search", response_model=Dict[str, Any])
async def search_hotels(
    city: str = Query(..., description="City name or IATA code"),
    check_in_date: Optional[str] = Query(None, description="Check-in date (YYYY-MM-DD)"),
    check_out_date: Optional[str] = Query(None, description="Check-out date (YYYY-MM-DD)"),
    stay_nights: Optional[int] = Query(None, description="Number of nights to stay (for one-way trips)", ge=1, le=30),
    rating: float = Query(0.0, description="Minimum rating", ge=0.0, le=5.0),
    max_price: float = Query(1000.0, description="Maximum price per night", ge=0.0),
    amenities: Optional[str] = Query(None, description="Comma-separated list of required amenities"),
    max_results: int = Query(10, description="Maximum number of results to return", ge=1, le=50),
    hotel_service: HotelService = Depends(get_hotel_service)
) -> Dict[str, Any]:
    """
    Search for hotels.
    """
    try:
        # Format dates
        if check_in_date:
            try:
                datetime.strptime(check_in_date, "%Y-%m-%d")
                if check_out_date:
                    datetime.strptime(check_out_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
        # Parse amenities
        amenities_list = []
        if amenities:
            amenities_list = [a.strip() for a in amenities.split(",")]
        
        # Search hotels
        hotels = hotel_service.search_hotels(
            city=city,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            stay_nights=stay_nights,
            rating=rating,
            max_price=max_price,
            amenities=amenities_list,
            max_results=max_results
        )
        
        if "error" in hotels:
            raise HTTPException(status_code=400, detail=hotels["error"])
        
        return hotels
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=Dict[str, Any])
async def search_hotels_post(
    request: HotelSearchRequest,
    hotel_service: HotelService = Depends(get_hotel_service)
) -> Dict[str, Any]:
    """
    Search for hotels (POST method).
    """
    try:
        # Format dates
        check_in_date = request.check_in_date.strftime("%Y-%m-%d") if request.check_in_date else None
        check_out_date = request.check_out_date.strftime("%Y-%m-%d") if request.check_out_date else None
        
        # Search hotels
        hotels = hotel_service.search_hotels(
            city=request.city,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            stay_nights=request.stay_nights,
            rating=request.rating,
            max_price=request.max_price,
            amenities=request.amenities,
            max_results=request.max_results
        )
        
        if "error" in hotels:
            raise HTTPException(status_code=400, detail=hotels["error"])
        
        return hotels
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/amenities", response_model=List[str])
async def get_available_amenities(
    hotel_service: HotelService = Depends(get_hotel_service)
) -> List[str]:
    """
    Get a list of available hotel amenities for filtering.
    """
    try:
        return hotel_service.get_available_amenities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/details/{hotel_id}", response_model=Dict[str, Any])
async def get_hotel_details(
    hotel_id: str,
    hotel_service: HotelService = Depends(get_hotel_service)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific hotel.
    """
    try:
        hotel = hotel_service.get_hotel_details(hotel_id)
        if not hotel or "error" in hotel:
            raise HTTPException(status_code=404, detail=f"Hotel with ID {hotel_id} not found")
        return hotel
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))