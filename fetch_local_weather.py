#!/usr/bin/env python3
"""
Read weather data from local weather station sensors.
Supports multiple input methods: serial port, USB, MQTT, file-based, HTTP endpoint.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Configuration - adjust based on your hardware
SENSOR_TYPE = os.getenv("WEATHER_SENSOR_TYPE", "file")  # file, serial, mqtt, http
DATA_PATH = Path(os.getenv("WEATHER_DATA_PATH", "/srv/doro_lab_projects/data/weather"))
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "weather/station")
HTTP_ENDPOINT = os.getenv("WEATHER_HTTP_ENDPOINT", "http://localhost:8080/weather")

def read_file_based_sensors():
    """Read from file-based sensor output (e.g., weather station daemon writing to files)"""
    data_file = DATA_PATH / "current.json"
    
    if not data_file.exists():
        return {
            "ok": False,
            "error": "Sensor data file not found",
            "path": str(data_file),
            "instructions": "Configure local weather station to write JSON to this path"
        }
    
    try:
        with open(data_file) as f:
            sensor_data = json.load(f)
        
        # Validate data freshness (should be updated within last 10 minutes)
        if "timestamp" in sensor_data:
            data_time = datetime.fromisoformat(sensor_data["timestamp"].replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - data_time).total_seconds()
            
            if age_seconds > 600:  # 10 minutes
                return {
                    "ok": False,
                    "error": "Sensor data is stale",
                    "age_seconds": age_seconds,
                    "last_update": sensor_data["timestamp"]
                }
        
        return {
            "ok": True,
            "source": "Local Weather Station (file)",
            "data": sensor_data,
            "read_at": datetime.now(timezone.utc).isoformat()
        }
    
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"Read error: {e}"}

def read_mqtt_sensors():
    """Read from MQTT broker (requires paho-mqtt library)"""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return {
            "ok": False,
            "error": "paho-mqtt not installed",
            "instructions": "pip install paho-mqtt"
        }
    
    # This would need a proper MQTT client implementation
    # Placeholder for now
    return {
        "ok": False,
        "error": "MQTT reader not implemented yet",
        "broker": MQTT_BROKER,
        "topic": MQTT_TOPIC
    }

def read_http_endpoint():
    """Read from HTTP endpoint (e.g., weather station REST API)"""
    import urllib.request
    import urllib.error
    
    try:
        with urllib.request.urlopen(HTTP_ENDPOINT, timeout=5) as response:
            sensor_data = json.loads(response.read().decode())
        
        return {
            "ok": True,
            "source": "Local Weather Station (HTTP)",
            "data": sensor_data,
            "endpoint": HTTP_ENDPOINT,
            "read_at": datetime.now(timezone.utc).isoformat()
        }
    
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"HTTP error: {e}", "endpoint": HTTP_ENDPOINT}
    except Exception as e:
        return {"ok": False, "error": f"Read error: {e}"}

def read_local_weather():
    """Main function to read from configured sensor type"""
    if SENSOR_TYPE == "file":
        return read_file_based_sensors()
    elif SENSOR_TYPE == "mqtt":
        return read_mqtt_sensors()
    elif SENSOR_TYPE == "http":
        return read_http_endpoint()
    else:
        return {
            "ok": False,
            "error": f"Unknown sensor type: {SENSOR_TYPE}",
            "valid_types": ["file", "mqtt", "http"]
        }

def parse_to_standard_format(raw_data):
    """Convert various local sensor formats to standardized format"""
    if not raw_data.get("ok"):
        return raw_data
    
    sensor_data = raw_data.get("data", {})
    
    # Try to extract standard fields (adapt field names based on your sensor output)
    # This is a flexible parser that handles different field naming conventions
    
    current = {}
    
    # Temperature (try multiple field names)
    for field in ["temperature", "temp", "temperature_c", "temp_c", "outdoor_temp"]:
        if field in sensor_data:
            current["temperature_c"] = float(sensor_data[field])
            break
    
    # Humidity
    for field in ["humidity", "rh", "humidity_pct", "relative_humidity"]:
        if field in sensor_data:
            current["humidity_pct"] = float(sensor_data[field])
            break
    
    # Pressure
    for field in ["pressure", "pressure_hpa", "barometric_pressure", "baro"]:
        if field in sensor_data:
            current["pressure_hpa"] = float(sensor_data[field])
            break
    
    # Wind speed
    for field in ["wind_speed", "wind", "wind_speed_kmh", "wind_kmh"]:
        if field in sensor_data:
            current["wind_speed_kmh"] = float(sensor_data[field])
            break
    
    # Wind direction
    for field in ["wind_direction", "wind_dir", "wind_direction_deg"]:
        if field in sensor_data:
            current["wind_direction_deg"] = float(sensor_data[field])
            break
    
    # Dewpoint (calculate if not provided)
    if "dewpoint" in sensor_data or "dewpoint_c" in sensor_data:
        current["dewpoint_c"] = float(sensor_data.get("dewpoint") or sensor_data.get("dewpoint_c"))
    elif "temperature_c" in current and "humidity_pct" in current:
        # Magnus formula
        tc = current["temperature_c"]
        rh = current["humidity_pct"]
        a, b = 17.27, 237.7
        alpha = ((a * tc) / (b + tc)) + (rh / 100.0)
        dewpoint = (b * alpha) / (a - alpha)
        current["dewpoint_c"] = round(dewpoint, 1)
    
    # Cloud cover (if available - most personal weather stations don't have this)
    for field in ["cloud_cover", "clouds", "cloud_cover_pct"]:
        if field in sensor_data:
            current["cloud_cover_pct"] = float(sensor_data[field])
            break
    
    # Visibility (rare on personal stations)
    for field in ["visibility", "visibility_km"]:
        if field in sensor_data:
            current["visibility_km"] = float(sensor_data[field])
            break
    
    return {
        "ok": True,
        "source": raw_data.get("source", "Local Weather Station"),
        "timestamp": raw_data.get("read_at", datetime.now(timezone.utc).isoformat()),
        "current": current,
        "raw": sensor_data,  # Include raw data for debugging
        "note": "Local sensor - cloud cover and visibility may not be available"
    }

if __name__ == "__main__":
    # Create data directory if it doesn't exist
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    
    raw_result = read_local_weather()
    
    if raw_result.get("ok"):
        formatted = parse_to_standard_format(raw_result)
        print(json.dumps(formatted, indent=2))
    else:
        print(json.dumps(raw_result, indent=2), file=sys.stderr)
        sys.exit(1)
