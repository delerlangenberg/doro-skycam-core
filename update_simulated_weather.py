#!/usr/bin/env python3
"""
Update simulated weather data for testing/demo purposes.
Generates realistic weather data with natural variations.
Use only when no real weather station is available.
"""

import json
import random
from datetime import datetime, timezone
from pathlib import Path

WEATHER_FILE = Path("/srv/doro_lab_projects/data/weather/current.json")

def generate_realistic_weather():
    """Generate realistic weather data with natural variations"""
    
    # Read previous values to create smooth transitions
    previous = {}
    if WEATHER_FILE.exists():
        try:
            previous = json.loads(WEATHER_FILE.read_text())
        except:
            pass
    
    # Start with base values or previous values
    temp = previous.get("temperature_c", 18.0)
    humidity = previous.get("humidity_pct", 60.0)
    pressure = previous.get("pressure_hpa", 1013.0)
    wind_speed = previous.get("wind_speed_kmh", 5.0)
    wind_dir = previous.get("wind_direction_deg", 180.0)
    
    # Add small random variations (realistic changes over 5-min intervals)
    temp += random.uniform(-0.3, 0.3)
    humidity += random.uniform(-2.0, 2.0)
    pressure += random.uniform(-0.2, 0.2)
    wind_speed += random.uniform(-1.0, 1.0)
    wind_dir += random.uniform(-15, 15)
    
    # Keep values in realistic ranges
    temp = max(5.0, min(35.0, temp))
    humidity = max(20.0, min(95.0, humidity))
    pressure = max(980.0, min(1040.0, pressure))
    wind_speed = max(0.0, min(50.0, wind_speed))
    wind_dir = wind_dir % 360
    
    # Calculate dewpoint (Magnus formula)
    a, b = 17.27, 237.7
    alpha = ((a * temp) / (b + temp)) + (humidity / 100.0)
    dewpoint = (b * alpha) / (a - alpha)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": round(temp, 1),
        "humidity_pct": round(humidity, 1),
        "pressure_hpa": round(pressure, 1),
        "wind_speed_kmh": round(wind_speed, 1),
        "wind_direction_deg": round(wind_dir, 1),
        "dewpoint_c": round(dewpoint, 1),
        "station_name": "DORO Lab Simulated Sensors",
        "note": "Simulated data - replace with real sensor readings"
    }

if __name__ == "__main__":
    # Ensure directory exists
    WEATHER_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate and write new data
    weather_data = generate_realistic_weather()
    WEATHER_FILE.write_text(json.dumps(weather_data, indent=2))
    
    print(f"Updated: {WEATHER_FILE}")
    print(f"Temp: {weather_data['temperature_c']}°C, "
          f"Humidity: {weather_data['humidity_pct']}%, "
          f"Pressure: {weather_data['pressure_hpa']} hPa")
