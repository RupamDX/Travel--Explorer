"""
Improved Streamlit application for Travel Explorer with automatic connection handling
"""
import os
import json
import time
import requests
from datetime import date, timedelta
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '.env')
)
load_dotenv(dotenv_path)

# API URLs
API_URL = os.getenv("API_URL", "http://localhost:8000/api")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

# IATA to city name mapping
iata_city_mapping = {
    "ATL": "atlanta", "AUS": "austin", "BOS": "boston", "ORD": "chicago", "DFW": "dallas",
    "DEN": "denver", "IAH": "houston", "IND": "indianapolis", "LAS": "las_vegas",
    "LAX": "los_angeles", "MIA": "miami", "BNA": "nashville", "JFK": "new_york",
    "PHL": "philadelphia", "PHX": "phoenix", "SAT": "san_antonio", "SFO": "san_francisco",
    "SJC": "san_jose", "SEA": "seattle", "IAD": "washington_dc"
}

# --- Helper Functions ---
def wait_for_connections(max_retries=5, retry_delay=1):
    """
    Wait for API and MCP connections with automatic retries.
    Returns: Tuple of (api_available, mcp_available)
    """
    api_available = False
    mcp_available = False
    
    # Try to connect to API with retries
    for attempt in range(max_retries):
        try:
            # First try API health
            api_response = requests.get(f"{API_URL}/health", timeout=2)
            if api_response.status_code == 200:
                api_available = True
                # If API is available, check MCP status
                try:
                    mcp_status_response = requests.get(f"{API_URL}/trips/mcp-status", timeout=2)
                    if mcp_status_response.status_code == 200:
                        mcp_available = mcp_status_response.json().get("available", False)
                except:
                    # Try direct MCP check
                    try:
                        mcp_response = requests.get(f"{MCP_SERVER_URL}/health", timeout=2)
                        if mcp_response.status_code == 200:
                            mcp_available = True
                    except:
                        pass
                break
        except:
            # If connection fails, wait and retry
            time.sleep(retry_delay)
            continue
    
    return api_available, mcp_available

def _display_flight_card(opt: dict):
    """Display a flight card in the UI."""
    st.write(f"**Price:** {opt['price']} | **Duration:** {opt['duration']} | **Stops:** {opt['stops']} | **Airlines:** {opt['airlines']}")
    if opt.get("layovers"):
        st.write("**Layovers:**")
        for lv in opt["layovers"]:
            st.write(f"- {lv['airport']} ({lv['duration']})")
    st.write("**Segments:**")
    for seg in opt["segments"]:
        st.write(f"- {seg['airline']} {seg['flight_number']} | {seg['departure']} → {seg['arrival']} ({seg['duration']})")
    st.markdown("---")

def _display_hotel_card(hotel: dict):
    """Display a hotel card in the UI."""
    st.markdown(f"**{hotel['name']}**")
    st.write(f"Class: {hotel.get('class', 'N/A')}★  •  Rating: {hotel.get('rating', 'N/A')}/5 ({hotel.get('reviews', 'N/A')} reviews)")
    st.write(f"Price: {hotel.get('price', {}).get('nightly', 'N/A')}/night  •  Total: {hotel.get('price', {}).get('total', 'N/A')}")
    st.write("Amenities:", ", ".join(hotel.get("key_amenities", [])))
    st.markdown(f"[Book]({hotel.get('booking_link', '#')})", unsafe_allow_html=True)
    st.markdown("---")

# --- Main Streamlit App ---
st.set_page_config(page_title="Travel Explorer", layout="wide")
st.title("Travel Explorer")

# Check connections (with hidden progress)
with st.empty():
    api_available, mcp_available = wait_for_connections()

# Discreet status display in sidebar instead of error messages
with st.sidebar:
    st.title("System Status")
    
    # API Status
    api_status = "✅ Connected" if api_available else "❌ Disconnected"
    st.markdown(f"**API Server:** {api_status}")
    
    # MCP Status
    mcp_status = "✅ Available" if mcp_available else "❌ Unavailable"
    st.markdown(f"**MCP Server:** {mcp_status}")
    
    # Connection Details (collapsed by default)
    with st.expander("Connection Details"):
        st.markdown(f"**API URL:** `{API_URL}`")
        st.markdown(f"**MCP URL:** `{MCP_SERVER_URL}`")
    
    # Refresh button (discretely placed in the sidebar)
    if st.button("Refresh Connections"):
        st.rerun()

# Create tabs
tabs = st.tabs(["Explore Hotels", "Explore Flights", "Trip Planner"])
tab_hotels, tab_flights, tab_trip = tabs

# If API is not available, show a friendly message
if not api_available:
    st.info("The system is currently initializing. Some features may be temporarily unavailable. Please wait a moment and try refreshing the page.")
    
# ---- HOTELS TAB ----
with tab_hotels:
    # ... [rest of your hotel tab code, unchanged] ...
    # Initialize session state
    if "hotel_results" not in st.session_state:
        st.session_state.hotel_results = []
    if "hotel_page" not in st.session_state:
        st.session_state.hotel_page = 0

    # Callbacks for pagination
    def prev_hotel_page():
        st.session_state.hotel_page -= 1

    def next_hotel_page():
        st.session_state.hotel_page += 1

    # Search inputs
    city = st.selectbox(
        "Choose a city",
        sorted([
            "atlanta", "austin", "boston", "chicago", "dallas", "denver", "houston",
            "indianapolis", "las_vegas", "los_angeles", "miami", "nashville", "new york",
            "philadelphia", "phoenix", "san_antonio", "san_francisco", "san_jose", "seattle", "washington_dc"
        ])
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        min_rating = st.slider("Minimum Rating", 0.0, 5.0, 0.0, step=0.1)
    with col2:
        max_price = st.number_input("Max Nightly Price ($)", 0.0, 10000.0, 1000.0)
    with col3:
        amenities_input = st.text_input("Other Amenities (comma-separated)")

    st.markdown("#### Enable specific amenities:")
    pet_friendly = st.checkbox("Pet-Friendly")
    kid_friendly = st.checkbox("Kid-friendly / Child-friendly")
    airport_shuttle = st.checkbox("Airport shuttle")
    free_breakfast = st.checkbox("Free breakfast")

    # Only show search button if API is available
    search_button = st.button("Search Hotels", disabled=not api_available)
    
    if search_button:
        st.session_state.hotel_page = 0
        amenities_list = [a.strip() for a in amenities_input.split(",")] if amenities_input else []
        if pet_friendly:
            amenities_list.append("Pet-friendly")
        if kid_friendly:
            amenities_list.append("Child-friendly")
        if airport_shuttle:
            amenities_list.append("Airport shuttle")
        if free_breakfast:
            amenities_list.append("Free breakfast")
        
        # API call to search hotels
        with st.spinner("Searching for Hotels..."):
            amenities_param = ",".join(amenities_list) if amenities_list else None
            try:
                response = requests.get(
                    f"{API_URL}/hotels/search",
                    params={
                        "city": city,
                        "rating": min_rating,
                        "max_price": max_price,
                        "amenities": amenities_param,
                        "max_results": 50  # Get more results for pagination
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.hotel_results = data.get("hotels", [])
                else:
                    st.error(f"Error searching hotels: {response.text}")
            except Exception as e:
                st.error(f"Error connecting to API: {str(e)}")

    # Pagination display
    results = st.session_state.hotel_results
    total_results = len(results)
    hotels_per_page = 5
    start = st.session_state.hotel_page * hotels_per_page
    end = start + hotels_per_page
    current_page = results[start:end]

    if current_page:
        for hotel in current_page:
            st.markdown(f"### {hotel['name']}")
            st.write(
                f"**Class:** {hotel.get('class', 'N/A')}  |  **Rating:** {hotel.get('rating')}"
            )
            st.write(
                f"**Nightly Price:** {hotel.get('price', {}).get('nightly', 'N/A')}  |  **Total:** {hotel.get('price', {}).get('total', 'N/A')}"
            )
            st.write(
                f"**Key Amenities:** {', '.join(hotel.get('key_amenities', []))}"
            )
            st.write(
                f"**Location Highlights:** {', '.join(hotel.get('location_highlights', []))}"
            )
            st.markdown(f"[Booking Link]({hotel.get('booking_link')})", unsafe_allow_html=True)
            st.markdown("---")

        col_prev, _, col_next = st.columns([1, 4, 1])
        with col_prev:
            if st.session_state.hotel_page > 0:
                st.button("Prev", key="prev_hotels", on_click=prev_hotel_page)
        with col_next:
            if end < total_results:
                st.button("Next", key="next_hotels", on_click=next_hotel_page)
    else:
        if results:
            st.info("No more results to show.")
        else:
            st.info("Search to explore hotel options.")

# ---- FLIGHTS TAB ----
with tab_flights:
    st.subheader("Explore Flights")

    # ... [rest of your flights tab code, unchanged except making the search button respect api_available] ...
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        origin_f = st.text_input("Origin Airport Code", "BOS").upper().strip()
    with col_f2:
        destination_f = st.text_input("Destination Airport Code", "LAX").upper().strip()

    col_f3, col_f4 = st.columns(2)
    with col_f3:
        departure_date_f = st.date_input("Departure Date", value=date.today() + timedelta(days=1))
    with col_f4:
        include_return = st.checkbox("Include Return Date", value=False)
        if include_return:
            return_date_f = st.date_input("Return Date", value=departure_date_f + timedelta(days=7))
        else:
            return_date_f = None

    today = date.today()
    if departure_date_f <= today:
        st.warning("Please select a departure date in the future for valid flight results.")
    if include_return and return_date_f and return_date_f <= departure_date_f:
        st.warning("Please select a return date after the departure date for valid flight results.")

    # Only show search button if API is available
    search_button = st.button("Search Flights", disabled=not api_available)
    
    if search_button:
        if departure_date_f <= today:
            st.error("Invalid dates selected. Please choose flight dates in the future.")
        elif include_return and return_date_f and return_date_f <= departure_date_f:
            st.error("Invalid dates selected. Return date must be after departure date.")
        else:
            dep_date = departure_date_f.strftime("%Y-%m-%d")
            ret_date = return_date_f.strftime("%Y-%m-%d") if return_date_f else None

            # API call to search flights
            with st.spinner("Searching for Flights..."):
                try:
                    response = requests.get(
                        f"{API_URL}/flights/best",
                        params={
                            "origin": origin_f,
                            "destination": destination_f,
                            "departure_date": dep_date,
                            "return_date": ret_date,
                            "max_results": 5
                        }
                    )
                    
                    if response.status_code == 200:
                        flights = response.json()
                        
                        if flights and not flights.get("error"):
                            st.subheader("Flight Search Results")
                            st.markdown("**Trip Summary:**")
                            info = flights.get("search_info", {})
                            st.write(f"Route: {info.get('origin')} → {info.get('destination')}")
                            st.write(f"Departure Date: {info.get('departure_date')}")
                            st.write(f"Return Date: {info.get('return_date', 'One Way')}")
                            st.markdown("---")

                            # Outbound
                            if flights.get("outbound_flights"):
                                st.markdown("#### Outbound Flights")
                                for opt in flights["outbound_flights"]:
                                    st.write(f"**Price:** {opt['price']}  |  **Duration:** {opt['duration']}  |  **Stops:** {opt['stops']}  |  **Airlines:** {opt['airlines']}")
                                    if opt.get("layovers"):
                                        st.write("**Layovers:**")
                                        for lv in opt["layovers"]:
                                            st.write(f"  - {lv['airport']} ({lv['duration']}){'  (overnight)' if lv.get('overnight') else ''}")
                                    st.write("**Segments:**")
                                    for seg in opt["segments"]:
                                        st.write(f"  - {seg['airline']} {seg['flight_number']} | {seg['departure']} @ {seg['time_dep']} → {seg['arrival']} @ {seg['time_arr']} | {seg['duration']} | {seg['aircraft']}")
                                    st.markdown("---")
                            else:
                                st.info("No outbound flight options available.")

                            # Return
                            if include_return:
                                if flights.get("return_flights"):
                                    st.markdown("#### Return Flights")
                                    for opt in flights["return_flights"]:
                                        st.write(f"**Price:** {opt['price']}  |  **Duration:** {opt['duration']}  |  **Stops:** {opt['stops']}  |  **Airlines:** {opt['airlines']}")
                                        if opt.get("layovers"):
                                            st.write("**Layovers:**")
                                            for lv in opt["layovers"]:
                                                st.write(f"  - {lv['airport']} ({lv['duration']}){'  (overnight)' if lv.get('overnight') else ''}")
                                        st.write("**Segments:**")
                                        for seg in opt["segments"]:
                                            st.write(f"  - {seg['airline']} {seg['flight_number']} | {seg['departure']} @ {seg['time_dep']} → {seg['arrival']} @ {seg['time_arr']} | {seg['duration']} | {seg['aircraft']}")
                                        st.markdown("---")
                                else:
                                    st.info("No return flight options available.")
                        else:
                            st.error("No flight data found or an error occurred during the search.")
                    else:
                        st.error(f"Error searching flights: {response.text}")
                except Exception as e:
                    st.error(f"Error connecting to API: {str(e)}")

# ---- TRIP PLANNER TAB ----
with tab_trip:
    st.subheader("Trip Planner")

    # ... [rest of your trip planner tab code, mostly unchanged but with api_available checks] ...
    # --- Input Fields ---
    col1, col2 = st.columns(2)
    with col1:
        origin_t = st.text_input("Origin IATA Code", "BOS").upper().strip()
        destination_t = st.text_input("Destination IATA Code", "LAX").upper().strip()
    with col2:
        trip_type = st.radio("Trip Type", ["One-way", "Round-trip"], key="trip_type")
        dep_date_t = st.date_input(
            "Departure Date",
            value=date.today() + timedelta(days=1),
            min_value=date.today() + timedelta(days=1),
            key="dep_date"
        )
        return_date_t = (
            st.date_input(
                "Return Date",
                value=dep_date_t + timedelta(days=7),
                min_value=dep_date_t + timedelta(days=1),
                key="ret_date"
            )
            if trip_type == "Round-trip"
            else None
        )

    # Trip Preferences
    st.markdown("### Trip Preferences")
    col_pref1, col_pref2, col_pref3 = st.columns(3)
    
    with col_pref1:
        interests = st.multiselect(
            "Interests",
            options=["Sightseeing", "Food & Dining", "Shopping", "Museums", "Nature", "Adventure", "Nightlife", "Family", "Art", "History", "Sports"],
            default=["Sightseeing", "Food & Dining"]
        )
    
    with col_pref2:
        trip_style = st.select_slider(
            "Trip Pace",
            options=["Relaxed", "Balanced", "Intensive"],
            value="Balanced"
        )
    
    with col_pref3:
        budget_level = st.select_slider(
            "Budget Level",
            options=["Budget", "Medium", "Luxury"],
            value="Medium"
        )

    # --- One-way stay duration ---
    stay_nights = None
    if trip_type == "One-way":
        stay_nights = st.number_input(
            "How many nights will you stay?",
            min_value=1,
            max_value=30,
            value=3,
            key="trip_stay_nights"
        )

    # --- Validate inputs ---
    valid = (
        len(origin_t) == 3 and origin_t.isalpha() and
        len(destination_t) == 3 and destination_t.isalpha() and
        dep_date_t > date.today() and
        (return_date_t is None or return_date_t > dep_date_t)
    )

    # Initialize session state for trip planner
    if "outbound_flights" not in st.session_state:
        st.session_state.outbound_flights = None
    if "return_flights" not in st.session_state:
        st.session_state.return_flights = None
    if "selected_outbound" not in st.session_state:
        st.session_state.selected_outbound = None
    if "selected_return" not in st.session_state:
        st.session_state.selected_return = None
    if "hotel_results" not in st.session_state:
        st.session_state.hotel_results = []
    if "selected_hotel" not in st.session_state:
        st.session_state.selected_hotel = None

    # --- Search Trip Button ---
    # Only show search button if API is available
    search_button = st.button("Search Trip", key="search_trip", disabled=not api_available)

    if search_button and valid:
        # Format dates
        dep = dep_date_t.strftime("%Y-%m-%d")
        ret = return_date_t.strftime("%Y-%m-%d") if return_date_t else None

        # --- Flight Search ---
        with st.spinner("Searching for Flights..."):
            try:
                # Outbound flight search
                response = requests.get(
                    f"{API_URL}/flights/best",
                    params={
                        "origin": origin_t,
                        "destination": destination_t,
                        "departure_date": dep,
                        "return_date": None,  # Always one-way first
                        "max_results": 5
                    }
                )
                
                if response.status_code == 200:
                    outbound_flights = response.json()
                    st.session_state.outbound_flights = outbound_flights
                else:
                    st.error(f"Error searching outbound flights: {response.text}")
                    outbound_flights = {"error": "API error"}
                    st.session_state.outbound_flights = outbound_flights

                # Return flight search (if round-trip)
                if trip_type == "Round-trip" and return_date_t:
                    response = requests.get(
                        f"{API_URL}/flights/best",
                        params={
                            "origin": destination_t,
                            "destination": origin_t,
                            "departure_date": ret,
                            "return_date": None,
                            "max_results": 5
                        }
                    )
                    
                    if response.status_code == 200:
                        return_flights = response.json()
                        st.session_state.return_flights = return_flights
                    else:
                        st.error(f"Error searching return flights: {response.text}")
                        st.session_state.return_flights = None
            
            except Exception as e:
                st.error(f"Error connecting to API: {str(e)}")
                st.session_state.outbound_flights = {"error": str(e)}
                st.session_state.return_flights = None

        # Reset selections
        st.session_state.selected_outbound = None
        st.session_state.selected_return = None

        # --- Hotel Search ---
        # compute check‐in/out
        check_in_date = dep
        if trip_type == "Round-trip":
            check_out_date = ret
            stay_duration = (return_date_t - dep_date_t).days
        else:
            check_out_date = (dep_date_t + timedelta(days=stay_nights)).strftime("%Y-%m-%d")
            stay_duration = stay_nights

        with st.spinner("Searching for Hotels..."):
            try:
                response = requests.get(
                    f"{API_URL}/hotels/search",
                    params={
                        "city": destination_t,
                        "check_in_date": check_in_date,
                        "check_out_date": check_out_date,
                        "stay_nights": stay_duration,
                        "max_results": 10
                    }
                )
                
                if response.status_code == 200:
                    hotel_data = response.json()
                    st.session_state.hotel_results = hotel_data.get("hotels", [])
                else:
                    st.error(f"Error searching hotels: {response.text}")
                    st.session_state.hotel_results = []
            
            except Exception as e:
                st.error(f"Error connecting to API: {str(e)}")
                st.session_state.hotel_results = []
            
            st.session_state.selected_hotel = None

    # --- Display Flights ---
    outbound_flights = st.session_state.outbound_flights
    return_flights = st.session_state.return_flights

    if outbound_flights and not outbound_flights.get("error"):
        st.subheader("Trip Search Results")
        st.markdown("**Trip Summary:**")
        info = outbound_flights["search_info"]
        st.write(f"Route: {info['origin']} → {info['destination']}")
        st.write(f"Departure Date: {info['departure_date']}")
        st.write(f"Return Date: {info.get('return_date', 'One Way')}")
        st.markdown("---")

        # ---- Outbound Selection ----
        sel_out = st.session_state.get("selected_outbound")
        if sel_out:
            st.markdown("### ✅ Outbound Flight (Selected)")
            _display_flight_card(sel_out)
            if st.button("Change Outbound Selection", key="change_out"):
                st.session_state.selected_outbound = None
                st.rerun()
        else:
            st.markdown("### Outbound Flights")
            for i, opt in enumerate(outbound_flights["outbound_flights"]):
                _display_flight_card(opt)
                if st.button(f"Select Outbound {i+1}", key=f"sel_out_{i}"):
                    st.session_state.selected_outbound = opt
                    st.rerun()

        # ---- Return Selection ----
        if trip_type == "Round-trip" and return_flights:
            sel_ret = st.session_state.get("selected_return")
            if sel_ret:
                st.markdown("### ✅ Return Flight (Selected)")
                _display_flight_card(sel_ret)
                if st.button("Change Return Selection", key="change_ret"):
                    st.session_state.selected_return = None
                    st.rerun()
            else:
                st.markdown("### Return Flights")
                for i, opt in enumerate(return_flights["outbound_flights"]):
                    _display_flight_card(opt)
                    if st.button(f"Select Return {i+1}", key=f"sel_ret_{i}"):
                        st.session_state.selected_return = opt
                        st.rerun()

    # --- Display Hotels ---
    hotels = st.session_state.get("hotel_results", [])
    if hotels:
        st.markdown("## 🏨 Hotel Selection")
        sel_hotel = st.session_state.get("selected_hotel")

        if sel_hotel:
            st.markdown("### ✅ Hotel (Selected)")
            _display_hotel_card(sel_hotel)
            if st.button("Change Hotel Selection", key="change_hotel"):
                st.session_state.selected_hotel = None
                st.rerun()
        else:
            st.markdown("### Choose a Hotel")
            for i, hotel in enumerate(hotels[:5]):  # Limit to 5 hotels for simplicity
                _display_hotel_card(hotel)
                if st.button(f"Select Hotel {i+1}", key=f"sel_hotel_{i}"):
                    st.session_state.selected_hotel = hotel
                    st.rerun()
        
        # ✅ Generate Itinerary Button (only shown when both flight and hotel are selected)
        if st.session_state.get("selected_outbound") and st.session_state.get("selected_hotel"):
            # Only enable the button if MCP is available or we can use fallback
            generate_button = st.button(
                "Generate Itinerary", 
                key="generate_itinerary_btn",
                disabled=(not api_available)
            )
            
            if generate_button:
                # Get city name from IATA code
                city_name = iata_city_mapping.get(destination_t.upper(), destination_t.lower())
                
                # Format flight details
                outbound = st.session_state["selected_outbound"]
                flight_info = f"Outbound: {outbound['airlines']}, {outbound['price']}, {outbound['duration']}, Stops: {outbound['stops']}"

                if trip_type == "Round-trip" and st.session_state.get("selected_return"):
                    ret = st.session_state["selected_return"]
                    flight_info += f"\nReturn: {ret['airlines']}, {ret['price']}, {ret['duration']}, Stops: {ret['stops']}"

                # Format hotel details
                hotel = st.session_state["selected_hotel"]
                hotel_info = f"{hotel['name']} | {hotel.get('price', {}).get('nightly', 'N/A')} per night, Total: {hotel.get('price', {}).get('total', 'N/A')} | Rating: {hotel.get('rating', 'N/A')} | Amenities: {', '.join(hotel.get('key_amenities', []))}"

                # Calculate stay duration
                if trip_type == "Round-trip" and return_date_t:
                    stay_duration = (return_date_t - dep_date_t).days
                else:
                    stay_duration = stay_nights

                # Prepare interests list
                interests_list = [interest.lower() for interest in interests]
                
                # Generate itinerary via API
                with st.spinner("Generating your personalized itinerary..."):
                    try:
                        # Convert dates to strings before sending to API
                        departure_date_str = dep_date_t.strftime("%Y-%m-%d")
                        return_date_str = return_date_t.strftime("%Y-%m-%d") if return_date_t else None
                        
                        # Try with retries
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                # Call the trips/plan endpoint
                                response = requests.post(
                                    f"{API_URL}/trips/plan",
                                    json={
                                        "destination": destination_t,
                                        "departure_date": departure_date_str,
                                        "return_date": return_date_str if trip_type == "Round-trip" else None,
                                        "stay_nights": stay_nights if trip_type == "One-way" else None,
                                        "flight": {
                                            "outbound": outbound,
                                            "return": st.session_state.get("selected_return") if trip_type == "Round-trip" else None
                                        },
                                        "hotel": hotel,
                                        "interests": interests_list,
                                        "trip_style": trip_style.lower(),
                                        "budget_level": budget_level.lower()
                                    },
                                    timeout=30  # Longer timeout for itinerary generation
                                )
                                
                                if response.status_code == 200:
                                    trip_data = response.json()
                                    itinerary = trip_data.get("itinerary", "")
                                    highlights = trip_data.get("highlights", [])
                                    daily_plans = trip_data.get("daily_plans", [])
                                    estimated_costs = trip_data.get("estimated_costs", {})
                                    source = trip_data.get("source", "unknown")
                                    
                                    # Show the generated plan
                                    st.markdown("### 📔 Your Personalized Itinerary")
                                    
                                    # Source info
                                    if source == "mcp":
                                        st.success("✨ Enhanced itinerary generated by MCP")
                                    else:
                                        st.info(f"Itinerary generated using {source}")
                                    
                                    # Highlights section
                                    if highlights:
                                        st.markdown("#### ✨ Trip Highlights")
                                        for highlight in highlights:
                                            st.markdown(f"- {highlight}")
                                        st.markdown("---")
                                    
                                    # Estimated costs
                                    if estimated_costs:
                                        st.markdown("#### 💰 Estimated Daily Costs")
                                        costs_col1, costs_col2 = st.columns(2)
                                        with costs_col1:
                                            st.markdown(f"**Accommodation:** ${estimated_costs.get('accommodation', 0):.2f}")
                                            st.markdown(f"**Food:** ${estimated_costs.get('food', 0):.2f}")
                                        with costs_col2:
                                            st.markdown(f"**Activities:** ${estimated_costs.get('activities', 0):.2f}")
                                            st.markdown(f"**Transportation:** ${estimated_costs.get('transportation', 0):.2f}")
                                        
                                        # Total
                                        total = sum(estimated_costs.values())
                                        st.markdown(f"**Total Daily:** ${total:.2f}")
                                        st.markdown(f"**Trip Total ({stay_duration} days):** ${total * stay_duration:.2f}")
                                        st.markdown("---")
                                    
                                    # Daily plans
                                    if daily_plans:
                                        st.markdown("#### 📆 Daily Schedule")
                                        
                                        # Create tabs for each day
                                        day_tabs = st.tabs([f"Day {plan['day']}" for plan in daily_plans])
                                        
                                        for i, day_tab in enumerate(day_tabs):
                                            with day_tab:
                                                plan = daily_plans[i]
                                                col1, col2 = st.columns(2)
                                                
                                                with col1:
                                                    st.subheader("Activities")
                                                    st.markdown("**Morning:**")
                                                    st.markdown(plan.get("morning", ""))
                                                    
                                                    st.markdown("**Afternoon:**")
                                                    st.markdown(plan.get("afternoon", ""))
                                                    
                                                    st.markdown("**Evening:**")
                                                    st.markdown(plan.get("evening", ""))
                                                
                                                with col2:
                                                    st.subheader("Meals")
                                                    st.markdown("**Breakfast:**")
                                                    st.markdown(plan.get("breakfast", ""))
                                                    
                                                    st.markdown("**Lunch:**")
                                                    st.markdown(plan.get("lunch", ""))
                                                    
                                                    st.markdown("**Dinner:**")
                                                    st.markdown(plan.get("dinner", ""))
                                        
                                        st.markdown("---")
                                    
                                    # Full itinerary
                                    st.markdown("#### 📝 Complete Itinerary")
                                    st.markdown(itinerary)
                                    
                                    # Exit the retry loop on success
                                    break
                                    
                                else:
                                    # Only show error on last retry attempt
                                    if attempt == max_retries - 1:
                                        st.error(f"Error generating itinerary: {response.text}")
                                    time.sleep(2)  # Wait before retrying
                            
                            except requests.Timeout:
                                if attempt == max_retries - 1:
                                    st.warning("Itinerary generation is taking longer than expected. Please try again.")
                            
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    st.error(f"Error connecting to API: {str(e)}")
                                time.sleep(2)  # Wait before retrying
                    
                    except Exception as e:
                        st.error(f"Error processing request: {str(e)}")