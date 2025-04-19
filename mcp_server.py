"""
MCP Server for Travel Explorer
This server provides enhanced trip planning capabilities using LLM integration.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import openai
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not found in environment variables.")
    raise ValueError("OPENAI_API_KEY is required.")

openai.api_key = OPENAI_API_KEY

# --- Models ---
class Traveler(BaseModel):
    adults: int = Field(1, description="Number of adults")
    children: int = Field(0, description="Number of children")

class Restaurant(BaseModel):
    name: str = Field(..., description="Restaurant name")
    rating: Optional[float] = Field(None, description="Restaurant rating")
    address: Optional[str] = Field(None, description="Restaurant address")
    url: Optional[str] = Field(None, description="Restaurant URL")

class ItineraryRequest(BaseModel):
    city: str = Field(..., description="Destination city")
    attractions: List[str] = Field(..., description="List of attractions")
    restaurants: List[Dict[str, Any]] = Field(..., description="List of restaurants")
    departure_date: str = Field(..., description="Departure date (YYYY-MM-DD)")
    return_date: Optional[str] = Field(None, description="Return date (YYYY-MM-DD)")
    flight_info: str = Field(..., description="Flight information")
    hotel_info: str = Field(..., description="Hotel information")
    interests: List[str] = Field([], description="List of user interests")
    trip_style: str = Field("balanced", description="Style of trip (relaxed, balanced, intensive)")
    budget_level: str = Field("medium", description="Budget level (budget, medium, luxury)")

class RecommendationRequest(BaseModel):
    city: str = Field(..., description="Destination city")
    interests: List[str] = Field([], description="List of user interests")
    budget: str = Field("medium", description="Budget level (budget, medium, luxury)")
    duration: int = Field(3, description="Trip duration in days", ge=1, le=30)
    travelers: Optional[Dict[str, Any]] = Field(None, description="Information about travelers")

# --- FastAPI App ---
app = FastAPI(
    title="MCP Server for Travel Explorer",
    description="Model Calling Protocol server for enhanced trip planning",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helper Functions ---
def format_date_display(date_str: str) -> str:
    """Format ISO date as human-readable format."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%A, %B %d, %Y")
    except:
        return date_str

def calculate_trip_length(departure_date: str, return_date: Optional[str] = None, default_nights: int = 3) -> int:
    """Calculate the number of days for the trip."""
    try:
        dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
        if return_date:
            ret_date = datetime.strptime(return_date, "%Y-%m-%d")
            return (ret_date - dep_date).days
        else:
            return default_nights
    except:
        return default_nights

def extract_daily_plans(itinerary: str) -> List[Dict[str, Any]]:
    """Extract structured daily plans from the generated itinerary."""
    daily_plans = []
    
    # Try to find day headers and their content
    day_pattern = r"Day\s+(\d+).*?:(.*?)(?=Day\s+\d+|$)"
    days = re.findall(day_pattern, itinerary, re.DOTALL | re.IGNORECASE)
    
    if not days:
        # Alternative pattern for when days are formatted differently
        day_pattern = r"Day\s+(\d+)(.*?)(?=Day\s+\d+|$)"
        days = re.findall(day_pattern, itinerary, re.DOTALL | re.IGNORECASE)
    
    for day_num, content in days:
        # Try to extract morning, afternoon, evening sections
        morning = re.search(r"Morning:?(.*?)(?=Afternoon|Lunch|Midday|Evening|Dinner|$)", content, re.DOTALL | re.IGNORECASE)
        afternoon = re.search(r"(?:Afternoon|Midday):?(.*?)(?=Evening|Dinner|$)", content, re.DOTALL | re.IGNORECASE)
        evening = re.search(r"(?:Evening|Night):?(.*?)$", content, re.DOTALL | re.IGNORECASE)
        
        # Try to extract meal information
        breakfast = re.search(r"Breakfast:?(.*?)(?=Lunch|Afternoon|Evening|Dinner|$)", content, re.DOTALL | re.IGNORECASE)
        lunch = re.search(r"Lunch:?(.*?)(?=Afternoon|Evening|Dinner|$)", content, re.DOTALL | re.IGNORECASE)
        dinner = re.search(r"Dinner:?(.*?)$", content, re.DOTALL | re.IGNORECASE)
        
        daily_plans.append({
            "day": int(day_num),
            "morning": morning.group(1).strip() if morning else "",
            "afternoon": afternoon.group(1).strip() if afternoon else "",
            "evening": evening.group(1).strip() if evening else "",
            "breakfast": breakfast.group(1).strip() if breakfast else "",
            "lunch": lunch.group(1).strip() if lunch else "",
            "dinner": dinner.group(1).strip() if dinner else ""
        })
    
    return daily_plans

def extract_highlights(itinerary: str) -> List[str]:
    """Extract key highlights from the generated itinerary."""
    highlights = []
    
    # Look for a highlights section
    highlights_section = re.search(r"Highlights:?(.*?)(?=Day\s+\d+|$)", itinerary, re.DOTALL | re.IGNORECASE)
    if highlights_section:
        # Extract bullet points
        bullets = re.findall(r"[•\-\*]\s+(.*?)(?=[•\-\*]|$)", highlights_section.group(1), re.DOTALL)
        if bullets:
            highlights = [bullet.strip() for bullet in bullets]
        else:
            # If no bullet points, split by newlines
            lines = highlights_section.group(1).strip().split("\n")
            highlights = [line.strip() for line in lines if line.strip()]
    
    # If no dedicated highlights section, try to extract key phrases
    if not highlights:
        # Look for phrases like "must-see", "highlight", "don't miss"
        highlight_phrases = re.findall(r"(?:must-see|highlight|don't miss|famous|popular|renowned).*?([\w\s']+)(?:\.|\,)", itinerary, re.IGNORECASE)
        if highlight_phrases:
            highlights = [h.strip() for h in highlight_phrases[:5]]  # Limit to top 5
    
    # If still no highlights, create dummy ones based on attractions
    if not highlights:
        attractions_pattern = r"(?:visit|explore|see).*?([\w\s']+)(?:\.|\,)"
        attractions = re.findall(attractions_pattern, itinerary, re.IGNORECASE)
        highlights = [a.strip() for a in attractions[:5] if len(a.strip()) > 3]
    
    return highlights[:5]  # Limit to 5 main highlights

def estimate_costs(itinerary: str, budget_level: str) -> Dict[str, float]:
    """Estimate daily costs based on budget level and itinerary content."""
    # Base costs by budget level
    base_costs = {
        "budget": {"accommodation": 75, "food": 40, "activities": 30, "transportation": 20},
        "medium": {"accommodation": 150, "food": 80, "activities": 60, "transportation": 40},
        "luxury": {"accommodation": 300, "food": 150, "activities": 120, "transportation": 80}
    }
    
    costs = base_costs.get(budget_level.lower(), base_costs["medium"])
    
    # Adjust based on certain keywords in itinerary
    if re.search(r"luxury|five-star|5-star|high-end|gourmet|exclusive", itinerary, re.IGNORECASE):
        costs["accommodation"] *= 1.2
        costs["food"] *= 1.2
    
    if re.search(r"museum|theater|show|concert|tour|guide", itinerary, re.IGNORECASE):
        costs["activities"] *= 1.15
    
    if re.search(r"taxi|uber|lyft|car service|private", itinerary, re.IGNORECASE):
        costs["transportation"] *= 1.3
    
    return costs

# --- API Endpoints ---
@app.get("/")
async def root():
    """Root endpoint returning server information."""
    return {
        "name": "MCP Server for Travel Explorer",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/generate/itinerary")
async def generate_itinerary(request: ItineraryRequest):
    """
    Generate a personalized travel itinerary using LLM.
    
    This endpoint uses OpenAI's GPT model to create detailed, day-by-day travel itineraries
    based on the provided destination, attractions, restaurants, and other parameters.
    """
    try:
        # Format dates for display
        departure_display = format_date_display(request.departure_date)
        return_display = format_date_display(request.return_date) if request.return_date else "N/A"
        
        # Calculate trip length
        trip_length = calculate_trip_length(
            request.departure_date, 
            request.return_date,
            default_nights=3
        )
        
        # Format restaurant data
        restaurant_list = []
        for r in request.restaurants:
            name = r.get("name", r.get("NAME", ""))
            if not name:
                continue
                
            rating = r.get("rating", r.get("RATING", "N/A"))
            address = r.get("address", r.get("ADDRESS", ""))
            restaurant_list.append(f"{name} (Rating: {rating}) - {address}")
        
        # Format attractions
        attraction_list = request.attractions
        
        # Build the prompt for the LLM
        prompt = f"""
You are an expert travel planner creating a detailed, personalized travel itinerary. Create a comprehensive day-by-day itinerary for a {trip_length}-day trip to {request.city}.

Trip Details:
- Destination: {request.city}
- Travel Dates: {departure_display} to {return_display}
- Trip Style: {request.trip_style.title()} (this determines the pace of activities)
- Budget Level: {request.budget_level.title()}
- Special Interests: {', '.join(request.interests)}

Travel Arrangements:
- Flight Info: {request.flight_info}
- Hotel Info: {request.hotel_info}

Available Attractions:
{chr(10).join(f"- {a}" for a in attraction_list)}

Recommended Restaurants:
{chr(10).join(f"- {r}" for r in restaurant_list[:10])}

Please create a detailed itinerary with:
1. A brief introduction and 3-5 key highlights of the trip
2. A day-by-day breakdown (Day 1, Day 2, etc.) with:
   - Morning activities
   - Recommended lunch spot
   - Afternoon activities
   - Recommended dinner spot
   - Evening activities or entertainment

Consider the trip style ({request.trip_style}) when planning the pace - balance sightseeing with relaxation and ensure travel times between attractions are reasonable. Include specific restaurant recommendations from the provided list.

Format the itinerary in a clean, well-organized structure with clear headings for each day and time period.
"""

        # Call OpenAI API to generate the itinerary
        response = openai.chat.completions.create(
            model="gpt-4",  # Adjust based on your requirements
            messages=[
                {"role": "system", "content": "You are an expert travel planner and itinerary creator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        
        # Extract the generated itinerary
        itinerary = response.choices[0].message.content
        
        # Extract daily plans, highlights, and estimated costs
        daily_plans = extract_daily_plans(itinerary)
        highlights = extract_highlights(itinerary)
        costs = estimate_costs(itinerary, request.budget_level)
        
        return {
            "itinerary": itinerary,
            "highlights": highlights,
            "daily_plans": daily_plans,
            "estimated_costs": costs
        }
    
    except Exception as e:
        logger.error(f"Error generating itinerary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate itinerary: {str(e)}")

@app.post("/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """
    Get personalized travel recommendations for a destination.
    
    This endpoint provides recommendations for attractions, restaurants, activities,
    and hotels based on the user's interests, budget, and trip duration.
    """
    try:
        # Default travelers if not provided
        travelers = request.travelers or {"adults": 1, "children": 0}
        
        # Build prompt for recommendations
        prompt = f"""
You are a travel expert providing recommendations for {request.city}. 

Trip Details:
- Duration: {request.duration} days
- Budget Level: {request.budget}
- Special Interests: {', '.join(request.interests) or "General sightseeing, food, and culture"}
- Travelers: {travelers.get("adults", 1)} adults, {travelers.get("children", 0)} children

Please provide recommendations in the following categories:
1. Top 5 attractions to visit
2. Top 5 restaurants to try 
3. Top 5 activities or experiences
4. Top 3 accommodation options

For each recommendation, provide a name, brief description (1-2 sentences), and why it's relevant to the traveler's interests or needs.

Format your response as a structured list with clear categories.
"""

        # Call OpenAI API for recommendations
        response = openai.chat.completions.create(
            model="gpt-4",  # Adjust based on your requirements
            messages=[
                {"role": "system", "content": "You are a travel expert with extensive knowledge of destinations worldwide."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Process the response to extract structured recommendations
        recommendation_text = response.choices[0].message.content
        
        # Process attractions
        attractions_section = re.search(r"(?:attractions|places to visit|sights).*?(?=restaurants|dining|eating|$)", recommendation_text, re.DOTALL | re.IGNORECASE)
        attractions = []
        if attractions_section:
            # Extract numbered or bulleted items
            items = re.findall(r"(?:\d+\.|[\*\-])\s+(.*?)(?=(?:\d+\.|[\*\-])|$)", attractions_section.group(0), re.DOTALL)
            for item in items:
                # Try to extract name and description
                parts = item.split(":", 1)
                if len(parts) > 1:
                    name = parts[0].strip()
                    description = parts[1].strip()
                else:
                    # Try to extract name and description with dash or hyphen
                    parts = item.split(" - ", 1)
                    if len(parts) > 1:
                        name = parts[0].strip()
                        description = parts[1].strip()
                    else:
                        # Just use the whole item as name
                        name = item.strip()
                        description = ""
                
                attractions.append({"name": name, "description": description})
        
        # Process restaurants
        restaurants_section = re.search(r"(?:restaurants|dining|places to eat).*?(?=activities|experiences|things to do|$)", recommendation_text, re.DOTALL | re.IGNORECASE)
        restaurants = []
        if restaurants_section:
            items = re.findall(r"(?:\d+\.|[\*\-])\s+(.*?)(?=(?:\d+\.|[\*\-])|$)", restaurants_section.group(0), re.DOTALL)
            for item in items:
                parts = item.split(":", 1)
                if len(parts) > 1:
                    name = parts[0].strip()
                    description = parts[1].strip()
                else:
                    parts = item.split(" - ", 1)
                    if len(parts) > 1:
                        name = parts[0].strip()
                        description = parts[1].strip()
                    else:
                        name = item.strip()
                        description = ""
                
                restaurants.append({
                    "name": name, 
                    "description": description,
                    "rating": 4.5,  # Placeholder, would typically come from a database
                    "address": request.city  # Placeholder
                })
        
        # Process activities
        activities_section = re.search(r"(?:activities|experiences|things to do).*?(?=accommodation|hotels|places to stay|$)", recommendation_text, re.DOTALL | re.IGNORECASE)
        activities = []
        if activities_section:
            items = re.findall(r"(?:\d+\.|[\*\-])\s+(.*?)(?=(?:\d+\.|[\*\-])|$)", activities_section.group(0), re.DOTALL)
            for item in items:
                parts = item.split(":", 1)
                if len(parts) > 1:
                    name = parts[0].strip()
                    description = parts[1].strip()
                else:
                    parts = item.split(" - ", 1)
                    if len(parts) > 1:
                        name = parts[0].strip()
                        description = parts[1].strip()
                    else:
                        name = item.strip()
                        description = ""
                
                activities.append({"name": name, "description": description})
        
        # Process hotels
        hotels_section = re.search(r"(?:accommodation|hotels|places to stay).*", recommendation_text, re.DOTALL | re.IGNORECASE)
        hotels = []
        if hotels_section:
            items = re.findall(r"(?:\d+\.|[\*\-])\s+(.*?)(?=(?:\d+\.|[\*\-])|$)", hotels_section.group(0), re.DOTALL)
            for item in items:
                parts = item.split(":", 1)
                if len(parts) > 1:
                    name = parts[0].strip()
                    description = parts[1].strip()
                else:
                    parts = item.split(" - ", 1)
                    if len(parts) > 1:
                        name = parts[0].strip()
                        description = parts[1].strip()
                    else:
                        name = item.strip()
                        description = ""
                
                price_level = ""
                if request.budget == "budget":
                    price_level = "$"
                elif request.budget == "medium":
                    price_level = "$$"
                else:
                    price_level = "$$$"
                
                hotels.append({
                    "name": name, 
                    "description": description,
                    "price_level": price_level,
                    "rating": 4.0  # Placeholder
                })
        
        return {
            "recommended_attractions": attractions,
            "recommended_restaurants": restaurants,
            "recommended_activities": activities,
            "recommended_hotels": hotels
        }
    
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")

@app.post("/analyze/preferences")
async def analyze_preferences(data: Dict[str, Any] = Body(...)):
    """
    Analyze user preferences based on their search history and selections.
    
    This endpoint examines a user's past searches and selected options to identify
    patterns and preferences for more personalized recommendations.
    """
    try:
        search_history = data.get("search_history", [])
        selected_options = data.get("selected_options", [])
        
        # In a real implementation, this would involve sophisticated analysis
        # For now, we'll return some dummy analysis
        return {
            "preferred_destinations": ["Paris", "Tokyo", "New York"],
            "preferred_hotel_amenities": ["Free WiFi", "Swimming Pool"],
            "preferred_activities": ["Museums", "Food Tours"],
            "budget_range": "medium",
            "travel_style": "balanced"
        }
    
    except Exception as e:
        logger.error(f"Error analyzing preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze preferences: {str(e)}")

# --- Main execution ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=port, reload=True)