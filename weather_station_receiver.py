#!/usr/bin/env python3
"""
Weather Station Integration for SkyWatch Observatory
Accepts weather data from multiple sources and updates /srv/doro_lab_projects/data/weather/current.json

Supported input methods:
1. HTTP POST endpoint (SkyWatch can push JSON)
2. File watcher (Boltwood/CloudSensor text files)
3. MQTT subscription
4. Direct file updates
"""

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
import subprocess

WEATHER_OUTPUT = Path("/srv/doro_lab_projects/data/weather/current.json")

def ensure_weather_dir():
    """Create weather directory if needed"""
    WEATHER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

def read_current_weather() -> Dict:
    """Read current weather JSON file"""
    if WEATHER_OUTPUT.exists():
        return json.loads(WEATHER_OUTPUT.read_text())
    return {}

def write_weather(data: Dict):
    """Write weather data to file"""
    ensure_weather_dir()
    # Add timestamp if not present
    if "timestamp" not in data:
        data["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    WEATHER_OUTPUT.write_text(json.dumps(data, indent=2))
    print(f"✓ Weather updated: {WEATHER_OUTPUT}")

def parse_boltwood_file(filepath: Path) -> Optional[Dict]:
    """Parse Boltwood weather station file (.dat format)
    
    Expected format:
    -10.5, 023, 998, 56, 45, 0.2, OK
    (temperature, wind_direction, pressure, humidity, dew_point, wind_speed, status)
    """
    try:
        content = filepath.read_text().strip()
        parts = [p.strip() for p in content.split(',')]
        
        if len(parts) >= 7:
            return {
                "temperature_c": float(parts[0]),
                "wind_direction_deg": int(parts[1]),
                "pressure_hpa": float(parts[2]),
                "humidity_pct": float(parts[3]),
                "dewpoint_c": float(parts[4]),
                "wind_speed_kmh": float(parts[5]) * 3.6,  # m/s to km/h
                "station_status": parts[6],
                "station_name": "Boltwood CloudSensor",
                "source_file": str(filepath),
            }
    except Exception as e:
        print(f"Error parsing Boltwood file: {e}")
    return None

def parse_cloudsensor_file(filepath: Path) -> Optional[Dict]:
    """Parse AAG CloudSensor text file
    
    Expected format (key=value, one per line):
    temperature=12.5
    humidity=65
    pressure=1013.25
    wind_speed=5.2
    wind_direction=270
    """
    try:
        data = {}
        content = filepath.read_text()
        for line in content.strip().split('\n'):
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip()
        
        weather = {}
        
        # Map common field names
        if 'temperature' in data:
            weather['temperature_c'] = float(data['temperature'])
        if 'humidity' in data:
            weather['humidity_pct'] = float(data['humidity'])
        if 'pressure' in data:
            weather['pressure_hpa'] = float(data['pressure'])
        if 'wind_speed' in data:
            weather['wind_speed_kmh'] = float(data['wind_speed'])
        if 'wind_direction' in data:
            weather['wind_direction_deg'] = float(data['wind_direction'])
        if 'dewpoint' in data or 'dew_point' in data:
            key = 'dewpoint' if 'dewpoint' in data else 'dew_point'
            weather['dewpoint_c'] = float(data[key])
        
        if weather:
            weather['station_name'] = 'AAG CloudSensor'
            weather['source_file'] = str(filepath)
            return weather
    
    except Exception as e:
        print(f"Error parsing CloudSensor file: {e}")
    return None

def parse_json_weather(data: Dict) -> Optional[Dict]:
    """Normalize JSON weather data from any source"""
    try:
        # Map various field name conventions
        normalized = {}
        
        field_map = {
            # Temperature
            'temp': 'temperature_c',
            'temperature': 'temperature_c',
            'temp_c': 'temperature_c',
            't': 'temperature_c',
            # Humidity
            'humidity': 'humidity_pct',
            'rh': 'humidity_pct',
            'relative_humidity': 'humidity_pct',
            # Pressure
            'pressure': 'pressure_hpa',
            'press': 'pressure_hpa',
            'p': 'pressure_hpa',
            # Wind
            'wind_speed': 'wind_speed_kmh',
            'wind_speed_kmh': 'wind_speed_kmh',
            'wind': 'wind_speed_kmh',
            'wind_dir': 'wind_direction_deg',
            'wind_direction': 'wind_direction_deg',
            # Dew point
            'dewpoint': 'dewpoint_c',
            'dew_point': 'dewpoint_c',
            'dp': 'dewpoint_c',
        }
        
        for key, value in data.items():
            target_key = field_map.get(key.lower(), key)
            if target_key in field_map.values():
                try:
                    normalized[target_key] = float(value)
                except (ValueError, TypeError):
                    pass
        
        return normalized if normalized else None
    except Exception as e:
        print(f"Error parsing JSON weather: {e}")
    return None

def update_from_json(json_data: str):
    """Update weather from JSON string"""
    try:
        data = json.loads(json_data)
        normalized = parse_json_weather(data)
        if normalized:
            current = read_current_weather()
            current.update(normalized)
            write_weather(current)
            return True
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
    return False

def update_from_file(filepath: str):
    """Update weather from file (auto-detect format)"""
    path = Path(filepath)
    
    if not path.exists():
        print(f"File not found: {path}")
        return False
    
    # Try Boltwood format first (.dat)
    if path.suffix == '.dat':
        weather = parse_boltwood_file(path)
        if weather:
            current = read_current_weather()
            current.update(weather)
            write_weather(current)
            return True
    
    # Try CloudSensor format (.txt)
    elif path.suffix == '.txt':
        weather = parse_cloudsensor_file(path)
        if weather:
            current = read_current_weather()
            current.update(weather)
            write_weather(current)
            return True
    
    # Try JSON
    elif path.suffix == '.json':
        try:
            data = json.loads(path.read_text())
            normalized = parse_json_weather(data)
            if normalized:
                current = read_current_weather()
                current.update(normalized)
                write_weather(current)
                return True
        except json.JSONDecodeError:
            pass
    
    print(f"Could not parse weather file: {path}")
    return False

def start_http_server(port: int = 8765):
    """Start simple HTTP server to receive weather POSTs from SkyWatch
    
    SkyWatch can POST JSON to: http://localhost:8765/weather
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class WeatherHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == '/weather':
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                
                if update_from_json(body):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "message": "Weather updated"}).encode())
                else:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "Invalid weather data"}).encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            # Suppress default logging
            pass
    
    server = HTTPServer(('0.0.0.0', port), WeatherHandler)
    print(f"🌍 Weather HTTP server running on :{port}")
    print(f"   POST weather JSON to: http://localhost:{port}/weather")
    server.serve_forever()

def generate_sample_data():
    """Generate sample weather data for testing"""
    import random
    from datetime import datetime, timezone
    
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": round(random.uniform(-5, 25), 1),
        "humidity_pct": round(random.uniform(30, 90), 1),
        "pressure_hpa": round(random.uniform(1000, 1030), 1),
        "wind_speed_kmh": round(random.uniform(0, 30), 1),
        "wind_direction_deg": random.randint(0, 360),
        "dewpoint_c": round(random.uniform(-10, 15), 1),
        "station_name": "DORO Lab Simulated Sensors",
        "note": "Generated sample data - replace with real sensor readings"
    }
    write_weather(data)
    print("✓ Sample weather data generated")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weather Station Integration")
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # JSON input
    json_parser = subparsers.add_parser('json', help='Update from JSON string')
    json_parser.add_argument('data', help='JSON weather data')
    
    # File input
    file_parser = subparsers.add_parser('file', help='Update from file')
    file_parser.add_argument('path', help='Weather file path')
    
    # HTTP server
    server_parser = subparsers.add_parser('server', help='Run HTTP receiver')
    server_parser.add_argument('--port', type=int, default=8765, help='HTTP port')
    
    # Sample data
    subparsers.add_parser('sample', help='Generate sample weather data')
    
    # Status
    subparsers.add_parser('status', help='Show current weather')
    
    args = parser.parse_args()
    
    if args.command == 'json':
        update_from_json(args.data)
    elif args.command == 'file':
        update_from_file(args.path)
    elif args.command == 'server':
        start_http_server(args.port)
    elif args.command == 'sample':
        generate_sample_data()
    elif args.command == 'status':
        weather = read_current_weather()
        print(json.dumps(weather, indent=2))
    else:
        parser.print_help()
