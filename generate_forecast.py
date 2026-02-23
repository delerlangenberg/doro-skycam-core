#!/usr/bin/env python3
"""
Combined forecast generator for astronomy observation planning.
Merges online API data and local sensor data, calculates observation windows.
"""

import json
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = Path("/srv/doro_lab_projects/skycam/forecast.json")
LOCATION_NAME = "DORO Lab Observatory · IT:U Austria"
LAT, LON = 48.2082, 16.3738
ELEVATION_M = 171

def run_fetcher(script_name):
    """Run a data fetcher script and return parsed JSON result"""
    script_path = SCRIPT_DIR / script_name
    
    if not script_path.exists():
        return {"ok": False, "error": f"Script not found: {script_name}"}
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        else:
            return {
                "ok": False,
                "error": result.stderr or "Script execution failed",
                "script": script_name
            }
    
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timeout", "script": script_name}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Invalid JSON output: {e}", "script": script_name}
    except Exception as e:
        return {"ok": False, "error": str(e), "script": script_name}

def calculate_observation_windows(online_data, local_data, astronomy_data):
    """Calculate best observation windows based on combined weather data"""
    windows = []
    now = datetime.now(timezone.utc)
    
    # Use online data for cloud forecast if available
    if online_data.get("ok") and "forecast_48h" in online_data:
        forecast = online_data["forecast_48h"]
        
        # Group into observation periods
        periods = [
            {
                "name": "Tonight",
                "start": now.replace(hour=18, minute=0, second=0, microsecond=0),
                "end": now.replace(hour=23, minute=0, second=0, microsecond=0),
            },
            {
                "name": "Late Night",
                "start": now.replace(hour=23, minute=30, second=0, microsecond=0),
                "end": (now + timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0),
            },
            {
                "name": "Tomorrow Evening",
                "start": (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0),
                "end": (now + timedelta(days=1)).replace(hour=23, minute=30, second=0, microsecond=0),
            }
        ]
        
        for period in periods:
            # Find forecast entries within this period
            period_forecasts = []
            for f in forecast:
                # Parse timestamp and ensure timezone awareness
                ts = datetime.fromisoformat(f["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                
                if period["start"] <= ts <= period["end"]:
                    period_forecasts.append(f)
            
            if not period_forecasts:
                continue
            
            # Calculate average cloud cover
            avg_clouds = sum(f["cloud_cover_pct"] for f in period_forecasts) / len(period_forecasts)
            
            # Calculate quality rating
            if avg_clouds < 20:
                quality = "excellent"
                rating = 9.5
                targets = ["Faint galaxies", "Nebulae", "Star clusters", "Deep-sky imaging"]
            elif avg_clouds < 40:
                quality = "good"
                rating = 7.5
                targets = ["Planets", "Bright deep-sky objects", "Moon features"]
            elif avg_clouds < 60:
                quality = "moderate"
                rating = 5.0
                targets = ["Planets", "Moon", "Bright stars"]
            else:
                quality = "poor"
                rating = 3.0
                targets = ["Not recommended for observation"]
            
            # Moon interference (simplified - should use real moon altitude calculation)
            moon_illumination = astronomy_data.get("moon_illumination_pct", 50)
            if moon_illumination > 80:
                moon_interference = "high"
                rating -= 1.5
            elif moon_illumination > 40:
                moon_interference = "moderate"
                rating -= 0.5
            else:
                moon_interference = "minimal"
            
            rating = max(0, min(10, rating))
            
            duration = (period["end"] - period["start"]).total_seconds() / 3600
            
            windows.append({
                "period": period["name"],
                "start": period["start"].isoformat(),
                "end": period["end"].isoformat(),
                "duration_hours": round(duration, 2),
                "quality": quality,
                "rating": round(rating, 1),
                "avg_cloud_cover_pct": round(avg_clouds, 1),
                "moon_interference": moon_interference,
                "recommended_targets": targets,
                "notes": f"Average cloud cover: {avg_clouds:.0f}%, Moon: {moon_illumination:.0f}% illuminated"
            })
    
    return windows

def calculate_basic_astronomy():
    """Calculate astronomy data (moon phase, twilight)"""
    now = datetime.now(timezone.utc)
    today = now.date()
    
    # Simple moon phase calculation
    days_since_new_moon = (now - datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)).days
    lunar_month = 29.53059
    moon_phase_float = (days_since_new_moon % lunar_month) / lunar_month
    
    phase_names = [
        "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
        "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"
    ]
    phase_idx = int(moon_phase_float * 8) % 8
    phase_name = phase_names[phase_idx]
    
    illumination = abs(0.5 - moon_phase_float) * 200 if moon_phase_float <= 0.5 else (1 - moon_phase_float) * 200
    illumination = max(0, min(100, illumination))
    
    # Approximate sun times for Vienna latitude
    sunrise = datetime.combine(today, datetime.min.time()).replace(hour=7, minute=15, tzinfo=timezone.utc)
    sunset = datetime.combine(today, datetime.min.time()).replace(hour=17, minute=45, tzinfo=timezone.utc)
    twilight_end = sunset + timedelta(minutes=50)
    twilight_start = sunrise - timedelta(minutes=50)
    
    # Approximate moon rise/set (simplified)
    moon_rise = sunrise + timedelta(minutes=int(moon_phase_float * 720))
    moon_set = sunset + timedelta(minutes=int(moon_phase_float * 720))
    
    darkness_duration = (twilight_start - twilight_end).total_seconds() / 3600
    
    return {
        "moon_phase": phase_name,
        "moon_illumination_pct": round(illumination, 1),
        "moon_rise": moon_rise.isoformat(),
        "moon_set": moon_set.isoformat(),
        "sun_rise": sunrise.isoformat(),
        "sun_set": sunset.isoformat(),
        "astronomical_twilight_end": twilight_end.isoformat(),
        "astronomical_twilight_start": twilight_start.isoformat(),
        "darkness_duration_hours": round(abs(darkness_duration), 1),
    }

def merge_weather_sources(online_data, local_data):
    """Merge online and local weather data, preferring local for current conditions"""
    merged = {
        "temperature_c": None,
        "humidity_pct": None,
        "pressure_hpa": None,
        "dewpoint_c": None,
        "wind_speed_kmh": None,
        "wind_direction_deg": None,
        "cloud_cover_pct": None,
        "visibility_km": None,
        "conditions": "Unknown",
    }
    
    # Prefer local data for direct measurements (temp, humidity, pressure, wind)
    if local_data.get("ok") and "current" in local_data:
        local_current = local_data["current"]
        for key in ["temperature_c", "humidity_pct", "pressure_hpa", "dewpoint_c", "wind_speed_kmh", "wind_direction_deg"]:
            if key in local_current and local_current[key] is not None:
                merged[key] = local_current[key]
    
    # Use online data for cloud cover and visibility (usually not available locally)
    if online_data.get("ok") and "current" in online_data:
        online_current = online_data["current"]
        for key in ["cloud_cover_pct", "visibility_km", "conditions"]:
            if key in online_current and (merged[key] is None or key in ["cloud_cover_pct", "visibility_km", "conditions"]):
                merged[key] = online_current[key]
        
        # Fill in any missing values from online source
        for key in merged.keys():
            if merged[key] is None and key in online_current:
                merged[key] = online_current[key]
    
    return merged

def generate_combined_forecast():
    """Main function to generate combined forecast from all sources"""
    print("Fetching online weather data...", file=sys.stderr)
    online_data = run_fetcher("fetch_online_weather.py")
    
    print("Fetching local weather data...", file=sys.stderr)
    local_data = run_fetcher("fetch_local_weather.py")
    
    print("Calculating astronomy data...", file=sys.stderr)
    astronomy_data = calculate_basic_astronomy()
    
    print("Merging data sources...", file=sys.stderr)
    current_weather = merge_weather_sources(online_data, local_data)
    
    print("Calculating observation windows...", file=sys.stderr)
    observation_windows = calculate_observation_windows(online_data, local_data, astronomy_data)
    
    # Calculate sky quality estimate
    cloud_cover = current_weather.get("cloud_cover_pct", 50)
    visibility = current_weather.get("visibility_km", 10)
    
    if cloud_cover < 20 and visibility > 15:
        transparency = "excellent"
        seeing = "good"
        overall_rating = 9.0
    elif cloud_cover < 40 and visibility > 10:
        transparency = "good"
        seeing = "moderate"
        overall_rating = 7.0
    elif cloud_cover < 60:
        transparency = "moderate"
        seeing = "moderate"
        overall_rating = 5.0
    else:
        transparency = "poor"
        seeing = "poor"
        overall_rating = 3.0
    
    # Build final combined forecast
    forecast = {
        "source": "Combined: Online API + Local Sensors",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": LOCATION_NAME,
        "coordinates": {
            "lat": LAT,
            "lon": LON,
            "elevation_m": ELEVATION_M
        },
        "data_sources": {
            "online": {
                "available": online_data.get("ok", False),
                "source": online_data.get("source", "Not available"),
                "error": online_data.get("error") if not online_data.get("ok") else None
            },
            "local": {
                "available": local_data.get("ok", False),
                "source": local_data.get("source", "Not available"),
                "error": local_data.get("error") if not local_data.get("ok") else None
            }
        },
        "current": current_weather,
        "astronomy": astronomy_data,
        "sky_quality": {
            "transparency": transparency,
            "seeing": seeing,
            "overall_rating": overall_rating,
            "sqm_mag_per_arcsec2": 19.5 if transparency == "excellent" else 18.5,  # Estimate
            "notes": "Based on combined weather observations"
        },
        "observation_windows": observation_windows,
        "forecast_48h": online_data.get("forecast_48h", []) if online_data.get("ok") else [],
        "educational_notes": {
            "transparency": "Atmospheric transparency: how clear the air is. Excellent transparency means you can see fainter objects.",
            "seeing": "Atmospheric seeing: stability of the atmosphere. Good seeing means stars appear sharp, not twinkling excessively.",
            "sqm": "Sky Quality Meter reading in magnitudes per square arcsecond. Higher values = darker sky. Urban: 17-18, Rural: 20-21.",
            "moon_phase": "Moon phase affects sky darkness. New moon is best for deep-sky observation; full moon is best for lunar details.",
            "astronomical_twilight": "When the sun is 18° below horizon. True darkness for astronomy begins after evening twilight."
        },
        "tips_for_students": [
            "Check cloud cover forecast before planning observation sessions",
            "Moon-free periods (new moon ± 3 days) are best for deep-sky objects",
            "Allow 20-30 minutes for your eyes to dark-adapt before observing faint objects",
            "Low humidity and stable temperature indicate good seeing conditions",
            "Use red flashlight to preserve night vision while taking notes"
        ]
    }
    
    return forecast

if __name__ == "__main__":
    try:
        forecast = generate_combined_forecast()
        
        # Write to output file
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(forecast, f, indent=2)
        
        print(f"\nForecast written to: {OUTPUT_FILE}", file=sys.stderr)
        print(f"Online data: {'OK' if forecast['data_sources']['online']['available'] else 'UNAVAILABLE'}", file=sys.stderr)
        print(f"Local data: {'OK' if forecast['data_sources']['local']['available'] else 'UNAVAILABLE'}", file=sys.stderr)
        
        # Also print to stdout for testing
        print(json.dumps(forecast, indent=2))
        
    except Exception as e:
        print(f"Error generating forecast: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
