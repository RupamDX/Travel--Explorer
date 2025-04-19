"""
LLM Service for the Travel Explorer application.
This module provides LLM integration for generating itineraries and other text content.
"""
import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from serpapi import GoogleSearch
from snowflake.snowpark import Session
from snowflake.snowpark.functions import lower

# Load environment variables
load_dotenv()

# Configuration
SERP_API_KEY = os.getenv("SERP_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Validation
if not SERP_API_KEY:
    raise ValueError("SERP_API_KEY not found.")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found.")

# OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)
_snowflake_session = None
# Snowflake setup
def get_snowflake_session():
    """Get or create a Snowflake session."""
    global _snowflake_session
    if _snowflake_session is None:
        connection_parameters = {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "password": os.getenv("SNOWFLAKE_PASSWORD"),
            "role": os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
            "database": "FINAL_PROJECT",
            "schema": "MY_SCHEMA"
        }
        _snowflake_session = Session.builder.configs(connection_parameters).create()
    return _snowflake_session

# Restaurant functions
# Add a simple cache
_restaurant_cache = {}

def get_restaurants_from_snowflake(city):
    """Get restaurants from Snowflake with caching."""
    city_key = city.lower()
    
    # Check cache first
    if city_key in _restaurant_cache:
        return _restaurant_cache[city_key]
    
    # Query Snowflake
    session = get_snowflake_session()
    df = session.table("YELP_RESTAURANTS")
    results = (
        df.filter(lower(df["CITY"]) == city_key)
          .select("NAME", "ADDRESS", "URL", "RATING")
          .collect()
    )
    
    # Convert to list of dictionaries
    restaurants = []
    for row in results:
        restaurants.append({
            "NAME": row["NAME"],
            "ADDRESS": row["ADDRESS"],
            "URL": row["URL"],
            "RATING": row["RATING"]
        })
    
    # Cache the results
    _restaurant_cache[city_key] = restaurants
    
    return restaurants

def search_restaurants_from_web(city):
    """Search for restaurants from the web using SerpAPI."""
    try:
        search = GoogleSearch({
            "engine": "google_local",
            "q": f"top restaurants in {city}",
            "location": city,
            "api_key": SERP_API_KEY
        })
        results = search.get_dict()
        return [
            f"{r.get('title', '')} - {r.get('address', '')} - Rating: {r.get('rating', '')}/5"
            for r in results.get("local_results", [])[:5]
        ]
    except Exception as e:
        return [f"SerpAPI Error: {e}"]

# Attraction functions
def search_places(city):
    """Search for places to visit using SerpAPI."""
    try:
        search = GoogleSearch({
            "q": f"Top places to visit in {city}",
            "location": city,
            "api_key": SERP_API_KEY
        })
        results = search.get_dict()
        return [
            f"{r.get('title', '')}: {r.get('snippet', '')}"
            for r in results.get("organic_results", [])[:5]
        ]
    except Exception as e:
        return [f"SerpAPI Error: {e}"]

# Itinerary generation functions
def generate_itinerary(city, attractions, restaurants, dep_date, return_date, flight_info, hotel_info):
    """
    Generate a personalized travel itinerary using GPT-4.
    
    Args:
        city (str): Destination city
        attractions (list): List of recommended attractions
        restaurants (list): List of recommended restaurants
        dep_date (str): Departure date
        return_date (str): Return date
        flight_info (str): Flight details
        hotel_info (str): Hotel information
    
    Returns:
        str: Generated itinerary in travel blog format or error message
    """
    ret_string = return_date if return_date else "N/A"
    
    prompt = f"""
You are a professional travel planner assistant with expertise in creating engaging, practical itineraries. 
Create a personalized travel itinerary for {city.title()} that reads like a polished travel blog.

**Trip Details:**
- Destination: {city.title()}
- Travel Dates: {dep_date} to {ret_string}

**Travel Arrangements:**
✈️ Flights:
{flight_info}

🏨 Accommodation:
{hotel_info}

**Recommendations to Include:**
🌟 Must-See Attractions:
{chr(10).join(f"- {a}" for a in attractions)}

🍽️ Dining Options:
{chr(10).join(f"- {r}" for r in restaurants)}

**Itinerary Requirements:**
1. Format as a engaging travel blog post with clear daily sections
2. For each day include:
   - Suggested morning, afternoon, and evening activities
   - Breakfast, lunch, and dinner recommendations from provided list
   - Reasonable travel time estimates between locations
   - Balanced mix of sightseeing and relaxation
3. Include:
   - Brief, vivid descriptions of each location
   - Practical tips (best times to visit, what to wear, etc.)
   - Local transportation suggestions
4. Writing style: Friendly, informative, and inspiring
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7  # Allows for some creativity while staying practical
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {str(e)}"

# Function to use Anthropic Claude via MCP
async def generate_with_claude(city, attractions, restaurants, dep_date, return_date, flight_info, hotel_info):
    """
    Generate a personalized travel itinerary using Claude via MCP.
    
    This function communicates with the MCP server to use Claude for generation.
    """
    try:
        import json
        import subprocess
        import asyncio
        
        # Create the prompt
        ret_string = return_date if return_date else "N/A"
        
        prompt = f"""
You are a professional travel planner assistant with expertise in creating engaging, practical itineraries. 
Create a personalized travel itinerary for {city.title()} that reads like a polished travel blog.

**Trip Details:**
- Destination: {city.title()}
- Travel Dates: {dep_date} to {ret_string}

**Travel Arrangements:**
✈️ Flights:
{flight_info}

🏨 Accommodation:
{hotel_info}

**Recommendations to Include:**
🌟 Must-See Attractions:
{chr(10).join(f"- {a}" for a in attractions)}

🍽️ Dining Options:
{chr(10).join(f"- {r}" for r in restaurants)}

**Itinerary Requirements:**
1. Format as a engaging travel blog post with clear daily sections
2. For each day include:
   - Suggested morning, afternoon, and evening activities
   - Breakfast, lunch, and dinner recommendations from provided list
   - Reasonable travel time estimates between locations
   - Balanced mix of sightseeing and relaxation
3. Include:
   - Brief, vivid descriptions of each location
   - Practical tips (best times to visit, what to wear, etc.)
   - Local transportation suggestions
4. Writing style: Friendly, informative, and inspiring
"""
        
        # Create MCP request
        mcp_request = {
            "type": "text",
            "text": prompt
        }
        
        # Execute MCP client command
        cmd = [
            "python", "-m", "mcp.client.stdio", "generate", 
            "--server", "travel_explorer_mcp",
            "--json", json.dumps(mcp_request)
        ]
        
        # Run the MCP client command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Get the output
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            return f"MCP error: {stderr.decode()}"
        
        # Parse the MCP response
        try:
            mcp_response = json.loads(stdout.decode())
            return mcp_response.get("text", "No response from Claude")
        except json.JSONDecodeError:
            return stdout.decode()
            
    except Exception as e:
        return f"Claude MCP Error: {str(e)}"