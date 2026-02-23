# SkyCam Weather & Forecast System

This directory contains scripts for fetching and combining weather data from multiple sources for astronomy observation planning.

## Overview

The forecast system combines data from:
1. **Online Weather API** (OpenWeatherMap) - provides cloud cover, visibility, and forecast
2. **Local Weather Station** - provides precise on-site temperature, humidity, wind, pressure

## Scripts

- `fetch_online_weather.py` - Fetch data from OpenWeatherMap API
- `fetch_local_weather.py` - Read data from local weather station sensors
- `generate_forecast.py` - Combine all sources and generate observation windows

## Configuration

### Option 1: Online Weather API (OpenWeatherMap)

1. Get a free API key from https://openweathermap.org/api
2. Set environment variable:
   ```bash
   export OPENWEATHER_API_KEY="your_api_key_here"
   ```

3. Or configure in systemd service:
   ```bash
   sudo systemctl edit update-forecast.service
   ```
   Add:
   ```ini
   [Service]
   Environment="OPENWEATHER_API_KEY=your_key_here"
   ```

### Option 2: Local Weather Station

#### File-based (default)

Configure your weather station to write JSON to:
```
/srv/doro_lab_projects/data/weather/current.json
```

Expected format:
```json
{
  "timestamp": "2026-02-16T10:30:00Z",
  "temperature": 14.8,
  "humidity": 67.5,
  "pressure": 1014.2,
  "wind_speed": 11.2,
  "wind_direction": 315
}
```

The script accepts flexible field names (temperature/temp/temp_c, etc.)

#### HTTP endpoint

If your weather station has a REST API:
```bash
export WEATHER_SENSOR_TYPE="http"
export WEATHER_HTTP_ENDPOINT="http://localhost:8080/weather"
```

#### MQTT (future)

For MQTT-based weather stations:
```bash
export WEATHER_SENSOR_TYPE="mqtt"
export MQTT_BROKER="localhost"
export MQTT_TOPIC="weather/station"
pip install paho-mqtt
```

## Automated Updates

To enable automatic forecast updates every 15 minutes:

```bash
# Copy systemd files
sudo cp /srv/doro_lab_projects/services/astronomy/update-forecast.* /etc/systemd/system/

# Enable and start timer
sudo systemctl daemon-reload
sudo systemctl enable update-forecast.timer
sudo systemctl start update-forecast.timer

# Check status
sudo systemctl status update-forecast.timer
sudo systemctl list-timers update-forecast*
```

## Manual Update

Generate forecast on-demand:
```bash
cd /srv/doro_lab_projects/apps/astronomy/skycam
python3 generate_forecast.py
```

Output is written to:
```
/srv/doro_lab_projects/skycam/forecast.json
```

## Testing

Test individual data sources:

```bash
# Test online API
python3 fetch_online_weather.py

# Test local sensors
python3 fetch_local_weather.py

# Generate combined forecast
python3 generate_forecast.py
```

## Data Priority

When both sources are available:
- **Local sensors** are used for: temperature, humidity, pressure, wind
- **Online API** is used for: cloud cover, visibility, weather conditions, 48h forecast

This provides the most accurate local measurements while leveraging cloud/visibility data from weather services.

## Troubleshooting

### Online API not working
- Check API key is set correctly
- Verify internet connectivity
- Check API quota/limits: https://openweathermap.org/price

### Local sensors not working
- Verify file exists: `/srv/doro_lab_projects/data/weather/current.json`
- Check file permissions (readable by script)
- Verify timestamp is recent (< 10 minutes old)
- Check JSON format is valid

### View logs
```bash
sudo journalctl -u update-forecast.service -f
```

## Advanced Configuration

### Change update frequency

Edit timer file:
```bash
sudo systemctl edit update-forecast.timer
```

Change `OnUnitActiveSec=15min` to desired interval (e.g., `5min`, `30min`, `1h`)

### Custom location

Edit `generate_forecast.py`:
```python
LAT, LON = 48.2082, 16.3738  # Your coordinates
LOCATION_NAME = "Your Observatory Name"
```

## Web Interface

View forecast at:
- Human-friendly: http://10.0.0.100/skycam/forecast
- JSON API: http://10.0.0.100/skycam/api/forecast

The forecast page shows:
- Current sky quality and weather
- Best observation windows (next 48 hours)
- Moon/sun information
- Data source status (online vs local)
- Educational tips for students
