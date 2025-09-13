#!/usr/bin/env python3
"""
Playlist Selector - Determines the music style/genre for the day
Based on day of week, weather, and other factors
Creates a dated directory for all playlist files
"""

import json
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
import random
from pathlib import Path
import os

class MusicGenre(Enum):
    # Actual genres from database
    INDIE_ROCK = "Indie Rock"
    INDIE = "Indie"
    HIP_HOP = "Hip Hop"
    ROCK = "Rock"
    ART_POP = "Art Pop"
    ART_ROCK = "Art Rock"
    ALTERNATIVE_DANCE = "Alternative Dance"
    GARAGE_ROCK = "Garage Rock"
    PUNK = "Punk"
    POP = "Pop"
    R_AND_B = "R&B"
    RAP = "Rap"
    COUNTRY = "Country"
    INDIE_FOLK = "Indie Folk"
    OTHER = "Other"  # For Unknown/untagged songs
    MIXED = "mixed"  # For all genres

class MoodType(Enum):
    ENERGETIC = "energetic"
    RELAXED = "relaxed"
    FOCUSED = "focused"
    PARTY = "party"
    MORNING = "morning"
    EVENING = "evening"

def get_day_based_genre() -> Dict:
    """
    Determine music style based on day of week
    """
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour

    weekend = weekday >= 5

    config = {
        "timestamp": now.isoformat(),
        "day_name": now.strftime("%A"),
        "is_weekend": weekend,
        "hour": hour
    }

    if weekend:
        if hour < 10:
            config["genre"] = MusicGenre.INDIE_FOLK.value
            config["mood"] = MoodType.MORNING.value
            config["energy_level"] = 3
        elif hour < 14:
            config["genre"] = MusicGenre.INDIE_ROCK.value
            config["mood"] = MoodType.ENERGETIC.value
            config["energy_level"] = 8
        elif hour < 18:
            config["genre"] = MusicGenre.MIXED.value
            config["mood"] = MoodType.PARTY.value
            config["energy_level"] = 9
        else:
            config["genre"] = MusicGenre.ALTERNATIVE_DANCE.value
            config["mood"] = MoodType.EVENING.value
            config["energy_level"] = 6
    else:
        if hour < 9:
            config["genre"] = MusicGenre.OTHER.value
            config["mood"] = MoodType.MORNING.value
            config["energy_level"] = 4
        elif hour < 12:
            config["genre"] = MusicGenre.INDIE.value
            config["mood"] = MoodType.FOCUSED.value
            config["energy_level"] = 5
        elif hour < 17:
            config["genre"] = MusicGenre.ROCK.value
            config["mood"] = MoodType.FOCUSED.value
            config["energy_level"] = 6
        else:
            config["genre"] = MusicGenre.ART_ROCK.value
            config["mood"] = MoodType.RELAXED.value
            config["energy_level"] = 3

    return config

def get_weather_modifier(config: Dict) -> Dict:
    """
    Get current weather and apply music modifications
    """
    try:
        from weather_service import WeatherService
        weather_service = WeatherService()
        weather_data = weather_service.get_today_weather()

        if weather_data:
            # Get main weather condition and format it nicely
            weather_main = weather_data['weather']['main'].lower()
            description = weather_data['weather']['description']
            temp_f = weather_data['temperature']['current']

            # Map OpenWeather conditions to our simpler categories and detailed description
            weather_map = {
                'clear': 'sunny',
                'clouds': 'cloudy',
                'rain': 'rainy',
                'drizzle': 'rainy',
                'thunderstorm': 'stormy',
                'snow': 'snowy',
                'mist': 'cloudy',
                'fog': 'cloudy',
                'haze': 'cloudy'
            }

            simple_weather = weather_map.get(weather_main, weather_main)
            config["weather"] = f"{simple_weather} and {temp_f:.0f}°F"
            config["weather_description"] = description
            config["temperature"] = temp_f

            # Apply mood modifications based on weather
            if weather_main in ['rain', 'drizzle', 'thunderstorm']:
                config["mood"] = MoodType.RELAXED.value
                config["energy_level"] = max(1, config["energy_level"] - 2)
            elif weather_main == 'clear':
                config["energy_level"] = min(10, config["energy_level"] + 1)
            elif weather_main == 'snow':
                config["mood"] = MoodType.RELAXED.value
                config["energy_level"] = max(2, config["energy_level"] - 1)
            elif temp_f > 75:  # Hot weather
                config["energy_level"] = min(10, config["energy_level"] + 1)
            elif temp_f < 40:  # Cold weather
                config["energy_level"] = max(2, config["energy_level"] - 1)

        else:
            # Fallback to random weather if API fails
            weather_conditions = ["sunny", "cloudy", "rainy", "snowy"]
            config["weather"] = random.choice(weather_conditions)

    except Exception as e:
        print(f"Weather API error: {e}")
        # Fallback to random weather
        weather_conditions = ["sunny", "cloudy", "rainy", "snowy"]
        config["weather"] = random.choice(weather_conditions)

    return config

def get_special_occasion_modifier(config: Dict) -> Dict:
    """
    Check for holidays or special occasions
    """
    now = datetime.now()

    if now.month == 12 and now.day == 25:
        config["special_occasion"] = "Christmas"
        config["genre"] = "holiday"
    elif now.month == 10 and now.day == 31:
        config["special_occasion"] = "Halloween"
        config["genre"] = "spooky"
    elif now.month == 7 and now.day == 4:
        config["special_occasion"] = "Independence Day"
        config["genre"] = MusicGenre.ROCK.value

    return config

def get_event_configuration() -> Dict:
    """
    Get event configuration from environment or default settings
    """
    # Get iCal URLs from environment variable or use empty list
    ical_urls_env = os.getenv('ICAL_URLS', '')
    ical_urls = [url.strip() for url in ical_urls_env.split(',') if url.strip()] if ical_urls_env else []

    event_config = {
        "ical_urls": ical_urls,
        "mention_events": len(ical_urls) > 0,  # Only mention if URLs configured
        "event_mention_frequency": "moderate",  # low, moderate, high
        "include_all_day_events": True,
        "max_events_per_mention": 3,
        "preferred_mention_times": {
            "morning": ["today", "tonight"],
            "afternoon": ["tonight", "tomorrow"],
            "evening": ["tonight", "tomorrow", "this_week"]
        }
    }

    return event_config

def select_playlist_config(start_datetime: datetime = None) -> Dict:
    """
    Main function to determine today's playlist configuration
    """
    config = get_day_based_genre()
    config = get_weather_modifier(config)
    config = get_special_occasion_modifier(config)

    # Add playlist start time
    if start_datetime:
        config["playlist_start_time"] = start_datetime.isoformat()
        config["playlist_start_hour"] = start_datetime.hour
    else:
        now = datetime.now()
        config["playlist_start_time"] = now.isoformat()
        config["playlist_start_hour"] = now.hour

    config["playlist_duration_hours"] = 8
    config["songs_per_hour"] = 15
    config["total_songs"] = config["playlist_duration_hours"] * config["songs_per_hour"]

    config["preferences"] = {
        "avoid_explicit": True,
        "prefer_instrumental": config["mood"] == MoodType.FOCUSED.value,
        "max_song_length_minutes": 7,
        "min_song_length_minutes": 2
    }

    # Add event configuration
    config["events"] = get_event_configuration()

    return config

def main():
    """
    Create dated directory and output playlist configuration as JSON
    """
    import argparse

    parser = argparse.ArgumentParser(description="Generate playlist configuration")
    parser.add_argument("--start-time", help="Start time in HH:MM format")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD format")
    args = parser.parse_args()

    # Parse start datetime
    start_datetime = None
    if args.start_time or args.start_date:
        start_date = args.start_date if args.start_date else datetime.now().strftime("%Y-%m-%d")
        start_time = args.start_time if args.start_time else "08:00"

        try:
            start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        except ValueError as e:
            print(f"Error parsing start time: {e}")
            return

    # Create dated directory
    date_for_dir = start_datetime.strftime("%Y-%m-%d") if start_datetime else datetime.now().strftime("%Y-%m-%d")
    playlist_dir = Path("playlists") / date_for_dir
    playlist_dir.mkdir(parents=True, exist_ok=True)

    # Store the directory path in environment variable for other scripts
    os.environ["PLAYLIST_DIR"] = str(playlist_dir)

    config = select_playlist_config(start_datetime)
    config["playlist_dir"] = str(playlist_dir)
    config["date"] = date_for_dir

    print(json.dumps(config, indent=2))
    print(f"\nPlaylist directory: {playlist_dir}")

    # Save config in the dated directory
    config_file = playlist_dir / "playlist_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    # Also save in root for backward compatibility (will remove later)
    with open("playlist_config.json", "w") as f:
        json.dump(config, f, indent=2)

    return config

if __name__ == "__main__":
    main()