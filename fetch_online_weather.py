#!/usr/bin/env python3
"""
Fetch weather and astronomy data from online API (OpenWeatherMap)
Provides cloud cover, visibility, and general weather conditions for observation planning.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.error

# Configuration
API_KEY = os.getenv("OPENWEATHER_API_KEY", "")  # Set via environment or config file
LAT = 48.2082
LON = 16.3738
LOCATION_NAME = "Vienna, Austria"

def fetch_weather_data():
    """Fetch current weather and forecast from OpenWeatherMap API"""
    if not API_KEY:
        return {
            "error": "API key not configured",
            "message": "Set OPENWEATHER_API_KEY environment variable",
            "demo_mode": True
        }
    
    try:
        # Current weather + forecast API call
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
        
        with urllib.request.urlopen(url, timeout=10) as response:
            current = json.loads(response.read().decode())
        
        # 5-day forecast
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
        
        with urllib.request.urlopen(forecast_url, timeout=10) as response:
            forecast = json.loads(response.read().decode())
        
        return {
            "ok": True,
            "current": current,
            "forecast": forecast,
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }
    
    except urllib.error.URLError as e:
        return {
            "error": f"Network error: {e}",
            "ok": False
        }
    except Exception as e:
        return {
            "error": f"API error: {e}",
            "ok": False
        }

def calculate_astronomy_data(dt=None):
    """Calculate basic astronomy data (moon phase approximation, twilight estimates)"""
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    # Simple moon phase calculation (approximate)
    # Known new moon: 2000-01-06 18:14 UTC
    days_since_new_moon = (dt - datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)).days
    lunar_month = 29.53059
    moon_phase_float = (days_since_new_moon % lunar_month) / lunar_month
    moon_age_days = days_since_new_moon % lunar_month
    
    # Determine phase name
    if moon_phase_float < 0.0625:
        phase_name = "New Moon"
    elif moon_phase_float < 0.1875:
        phase_name = "Waxing Crescent"
    elif moon_phase_float < 0.3125:
        phase_name = "First Quarter"
    elif moon_phase_float < 0.4375:
        phase_name = "Waxing Gibbous"
    elif moon_phase_float < 0.5625:
        phase_name = "Full Moon"
    elif moon_phase_float < 0.6875:
        phase_name = "Waning Gibbous"
    elif moon_phase_float < 0.8125:
        phase_name = "Last Quarter"
    else:
        phase_name = "Waning Crescent"
    
    # Illumination percentage (approximate)
    illumination = abs(0.5 - moon_phase_float) * 200 if moon_phase_float <= 0.5 else (1 - moon_phase_float) * 200
    illumination = max(0, min(100, illumination))
    
    # Approximate sunrise/sunset for Vienna (very rough - use real API for production)
    # These are placeholder values - real implementation should use proper calculations
    today = dt.date()
    sunrise = datetime.combine(today, datetime.min.time()).replace(hour=7, minute=15, tzinfo=timezone.utc)
    sunset = datetime.combine(today, datetime.min.time()).replace(hour=17, minute=45, tzinfo=timezone.utc)
    twilight_end = sunset + timedelta(minutes=50)
    twilight_start = sunrise - timedelta(minutes=50)
    
    return {
        "moon_phase": phase_name,
        "moon_illumination_pct": round(illumination, 1),
        "moon_age_days": round(moon_age_days, 1),
        "sun_rise": sunrise.isoformat(),
        "sun_set": sunset.isoformat(),
        "astronomical_twilight_end": twilight_end.isoformat(),
        "astronomical_twilight_start": twilight_start.isoformat(),
    }

def parse_to_forecast_format(weather_data):
    """Convert OpenWeatherMap data to our forecast format"""
    if not weather_data.get("ok"):
        return weather_data
    
    current = weather_data["current"]
    forecast_list = weather_data["forecast"].get("list", [])
    
    # Extract current conditions
    current_data = {
        "temperature_c": current["main"]["temp"],
        "feels_like_c": current["main"]["feels_like"],
        "humidity_pct": current["main"]["humidity"],
        "pressure_hpa": current["main"]["pressure"],
        "cloud_cover_pct": current["clouds"]["all"],
        "visibility_m": current.get("visibility", 10000),
        "visibility_km": current.get("visibility", 10000) / 1000,
        "wind_speed_kmh": current["wind"]["speed"] * 3.6,  # m/s to km/h
        "wind_direction_deg": current["wind"].get("deg", 0),
        "conditions": current["weather"][0]["description"] if current.get("weather") else "unknown",
        "icon": current["weather"][0]["icon"] if current.get("weather") else "",
    }
    
    # Calculate dewpoint (Magnus formula)
    tc = current_data["temperature_c"]
    rh = current_data["humidity_pct"]
    a, b = 17.27, 237.7
    alpha = ((a * tc) / (b + tc)) + (rh / 100.0)
    dewpoint = (b * alpha) / (a - alpha)
    current_data["dewpoint_c"] = round(dewpoint, 1)
    
    # Parse forecast (next 48 hours)
    forecast_48h = []
    for item in forecast_list[:16]:  # 16 x 3-hour intervals = 48 hours
        forecast_48h.append({
            "timestamp": item["dt_txt"],
            "temperature_c": item["main"]["temp"],
            "cloud_cover_pct": item["clouds"]["all"],
            "humidity_pct": item["main"]["humidity"],
            "wind_speed_kmh": item["wind"]["speed"] * 3.6,
            "conditions": item["weather"][0]["description"] if item.get("weather") else "",
        })
    
    # Calculate sky quality estimate based on cloud cover and visibility
    cloud_cover = current_data["cloud_cover_pct"]
    visibility = current_data["visibility_km"]
    
    if cloud_cover < 20 and visibility > 15:
        transparency = "excellent"
        quality_rating = 9.0
    elif cloud_cover < 40 and visibility > 10:
        transparency = "good"
        quality_rating = 7.5
    elif cloud_cover < 60 and visibility > 5:
        transparency = "moderate"
        quality_rating = 5.0
    else:
        transparency = "poor"
        quality_rating = 3.0
    
    return {
        "ok": True,
        "source": "OpenWeatherMap API",
        "timestamp": weather_data["fetched_at"],
        "location": LOCATION_NAME,
        "coordinates": {"lat": LAT, "lon": LON},
        "current": current_data,
        "forecast_48h": forecast_48h,
        "sky_quality_estimate": {
            "transparency": transparency,
            "rating": quality_rating,
            "based_on": "cloud cover and visibility from weather API"
        }
    }

if __name__ == "__main__":
    result = fetch_weather_data()
    
    if result.get("ok"):
        formatted = parse_to_forecast_format(result)
        print(json.dumps(formatted, indent=2))
    elif result.get("demo_mode"):
        # Output demo data structure
        demo_data = {
            "ok": False,
            "source": "OpenWeatherMap API (not configured)",
            "error": "API key required",
            "instructions": "Set OPENWEATHER_API_KEY environment variable",
            "demo": True
        }
        print(json.dumps(demo_data, indent=2))
    else:
        print(json.dumps(result, indent=2), file=sys.stderr)
        sys.exit(1)
