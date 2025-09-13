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
    Placeholder for weather-based modifications
    In future, this will call a weather API
    """
    weather_conditions = ["sunny", "cloudy", "rainy", "snowy"]
    weather = random.choice(weather_conditions)

    config["weather"] = weather

    if weather == "rainy":
        config["mood"] = MoodType.RELAXED.value
        config["energy_level"] = max(1, config["energy_level"] - 2)
    elif weather == "sunny":
        config["energy_level"] = min(10, config["energy_level"] + 1)

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

def select_playlist_config() -> Dict:
    """
    Main function to determine today's playlist configuration
    """
    config = get_day_based_genre()
    config = get_weather_modifier(config)
    config = get_special_occasion_modifier(config)

    config["playlist_duration_hours"] = 8
    config["songs_per_hour"] = 15
    config["total_songs"] = config["playlist_duration_hours"] * config["songs_per_hour"]

    config["preferences"] = {
        "avoid_explicit": True,
        "prefer_instrumental": config["mood"] == MoodType.FOCUSED.value,
        "max_song_length_minutes": 7,
        "min_song_length_minutes": 2
    }

    return config

def main():
    """
    Create dated directory and output playlist configuration as JSON
    """
    # Create dated directory
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    playlist_dir = Path("playlists") / date_str
    playlist_dir.mkdir(parents=True, exist_ok=True)

    # Store the directory path in environment variable for other scripts
    os.environ["PLAYLIST_DIR"] = str(playlist_dir)

    config = select_playlist_config()
    config["playlist_dir"] = str(playlist_dir)
    config["date"] = date_str

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