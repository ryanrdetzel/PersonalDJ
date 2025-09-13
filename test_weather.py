#!/usr/bin/env python3

from weather_service import WeatherService
import json

def test_weather_api():
    print("Testing OpenWeather API Integration")
    print("=" * 50)

    try:
        weather_service = WeatherService()

        print(f"Location: {weather_service.location}")
        print(f"API Key configured: {'Yes' if weather_service.api_key else 'No'}")
        print()

        print("Fetching weather data...")
        weather_data = weather_service.get_today_weather()

        if weather_data:
            print("\nRaw JSON Response:")
            print(json.dumps(weather_data, indent=2))

            print("\n" + "=" * 50)
            print("Formatted Weather Summary:")
            print(weather_service.get_weather_summary())
        else:
            print("Failed to fetch weather data. Please check your API key and location.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_weather_api()