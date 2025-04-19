"""
FastAPI main application for Travel Explorer
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Import routers
from api.routers import flights, hotels, trips

# Load environment variables from .env file
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Travel Explorer API",
    description="API for the Travel Explorer application",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://34.58.131.194:8501"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(flights.router, prefix="/api/flights", tags=["flights"])
app.include_router(hotels.router, prefix="/api/hotels", tags=["hotels"])
app.include_router(trips.router, prefix="/api/trips", tags=["trips"])

@app.get("/", tags=["root"])
async def root():
    """Root endpoint that returns API info"""
    return {
        "message": "Welcome to the Travel Explorer API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }
# Alias health endpoint so Docker can see it
@app.get("/health", tags=["health"])
async def root_health_check():
    return {"status": "healthy"}
# Health check endpoint
@app.get("/api/health", tags=["health"])
async def api_health_check():
    """API health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)