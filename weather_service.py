import os
import requests
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class WeatherService:
    def __init__(self):
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        self.location = os.getenv('WEATHER_LOCATION', 'New York,US')
        self.base_url = 'https://api.openweathermap.org/data/2.5'

        if not self.api_key:
            raise ValueError("OPENWEATHER_API_KEY not found in environment variables")

    def get_today_weather(self) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/weather"
            params = {
                'q': self.location,
                'appid': self.api_key,
                'units': 'imperial'  # Use Fahrenheit, change to 'metric' for Celsius
            }

            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            weather_info = {
                'location': data['name'],
                'country': data['sys']['country'],
                'timestamp': datetime.now().isoformat(),
                'temperature': {
                    'current': data['main']['temp'],
                    'feels_like': data['main']['feels_like'],
                    'min': data['main']['temp_min'],
                    'max': data['main']['temp_max']
                },
                'weather': {
                    'main': data['weather'][0]['main'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon']
                },
                'details': {
                    'humidity': data['main']['humidity'],
                    'pressure': data['main']['pressure'],
                    'visibility': data.get('visibility', 0) / 1000,  # Convert to km
                    'wind_speed': data['wind']['speed'],
                    'wind_direction': data['wind'].get('deg', 0),
                    'cloudiness': data['clouds']['all']
                },
                'sun': {
                    'sunrise': datetime.fromtimestamp(data['sys']['sunrise']).strftime('%H:%M:%S'),
                    'sunset': datetime.fromtimestamp(data['sys']['sunset']).strftime('%H:%M:%S')
                }
            }

            return weather_info

        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather data: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

    def get_weather_summary(self) -> str:
        weather = self.get_today_weather()
        if not weather:
            return "Unable to fetch weather data"

        summary = f"""
Weather for {weather['location']}, {weather['country']}
{'-' * 40}
Current Temperature: {weather['temperature']['current']:.1f}°F
Feels Like: {weather['temperature']['feels_like']:.1f}°F
Today's Range: {weather['temperature']['min']:.1f}°F - {weather['temperature']['max']:.1f}°F

Conditions: {weather['weather']['description'].capitalize()}
Humidity: {weather['details']['humidity']}%
Wind: {weather['details']['wind_speed']} mph
Visibility: {weather['details']['visibility']:.1f} km
Cloudiness: {weather['details']['cloudiness']}%

Sunrise: {weather['sun']['sunrise']}
Sunset: {weather['sun']['sunset']}
"""
        return summary


if __name__ == "__main__":
    weather_service = WeatherService()
    print(weather_service.get_weather_summary())