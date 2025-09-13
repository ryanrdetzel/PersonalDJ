#!/usr/bin/env python3
"""
DJ Spot Planner - Calculates when and how many DJ spots to inject
Based on playlist duration and desired frequency
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict
import random
from pathlib import Path

class DJSpotPlanner:
    def __init__(self, minutes_between_spots: int = 20):
        self.minutes_between_spots = minutes_between_spots
        # Daily content that should be distributed across weekday slots
        self.daily_morning_content = ['dad_joke', 'kid_fact', 'history_fact', 'animal_fact']
        self.daily_evening_content = ['global_fact', 'country_comparison', 'weird_fact', 'gross_fact', 'animal_fact']
        self.used_content_today = set()

    def calculate_spot_positions(self, playlist_data: Dict) -> List[Dict]:
        """
        Calculate where to place DJ spots in the playlist
        """
        total_duration_seconds = playlist_data.get("total_duration_seconds", 0)
        songs = playlist_data.get("songs", [])

        if not songs:
            return []

        total_duration_minutes = total_duration_seconds / 60
        num_spots = int(total_duration_minutes / self.minutes_between_spots)

        spots = []
        accumulated_duration = 0
        songs_per_spot = max(1, len(songs) // (num_spots + 1))

        # Use playlist start time from config if available, otherwise use current time
        config = playlist_data.get("config", {})
        if config.get("playlist_start_time"):
            current_time = datetime.fromisoformat(config["playlist_start_time"]).replace(second=0, microsecond=0)
        else:
            current_time = datetime.now().replace(second=0, microsecond=0)

        # Reset daily content tracking for new playlist
        self.used_content_today = set()

        # Determine if this is a weekday (Monday=0, Sunday=6)
        is_weekday = current_time.weekday() < 5

        for i in range(num_spots):
            song_index = (i + 1) * songs_per_spot

            if song_index < len(songs):
                for j in range(min(song_index, len(songs))):
                    accumulated_duration += songs[j].get("duration_seconds", 180)

                spot_time = current_time + timedelta(seconds=accumulated_duration)

                spot = {
                    "spot_number": i + 1,
                    "after_song_index": song_index,
                    "approximate_time": spot_time.strftime("%H:%M"),
                    "accumulated_minutes": accumulated_duration / 60,
                    "type": self.determine_spot_type(spot_time, is_weekday)
                }
                spots.append(spot)

        return spots

    def determine_spot_type(self, spot_time: datetime, is_weekday: bool = True) -> str:
        """
        Determine what type of DJ spot based on time of day
        For weekdays, prioritize daily content during 6-8am and 4-6pm
        """
        hour = spot_time.hour
        types = []

        # Weekday morning content (6-8am)
        if is_weekday and hour in [6, 7, 8]:
            # Check for unused daily morning content
            available_morning = [content for content in self.daily_morning_content
                               if content not in self.used_content_today]
            if available_morning:
                selected = random.choice(available_morning)
                self.used_content_today.add(selected)
                return selected
            else:
                # Fallback to regular morning content
                types.extend(["morning_greeting", "weather", "daily_schedule", "motivation"])

        # Weekday evening content (4-6pm)
        elif is_weekday and hour in [16, 17, 18]:
            # Check for unused daily evening content
            available_evening = [content for content in self.daily_evening_content
                               if content not in self.used_content_today]
            if available_evening:
                selected = random.choice(available_evening)
                self.used_content_today.add(selected)
                return selected
            else:
                # Fallback to regular evening content
                types.extend(["evening_greeting", "dinner_suggestion", "afternoon_boost"])

        # Regular time-based content (weekends or non-priority hours)
        elif hour == 7:
            types.extend(["morning_greeting", "weather", "daily_schedule"])
        elif hour in [8, 9]:
            types.extend(["time_check", "motivation", "fun_fact"])
        elif hour == 12:
            types.extend(["lunch_reminder", "afternoon_greeting"])
        elif hour in [15, 16]:
            types.extend(["afternoon_boost", "trivia", "joke"])
        elif hour == 18:
            types.extend(["evening_greeting", "dinner_suggestion"])
        elif hour >= 20:
            types.extend(["evening_wind_down", "tomorrow_preview"])
        else:
            types.extend(["time_check", "music_info", "random_thought"])

        if spot_time.minute == 0:
            types.append("hour_announcement")

        return random.choice(types) if types else "general"

    def generate_spot_requirements(self, spots: List[Dict], config: Dict, playlist_data: Dict = None) -> Dict:
        """
        Generate requirements for each DJ spot
        """
        day_name = config.get("day_name", "Today")
        weather = config.get("weather", "clear")
        mood = config.get("mood", "energetic")
        genre = config.get("genre", "mixed")
        special_occasion = config.get("special_occasion")

        spot_requirements = []
        songs = playlist_data.get("songs", []) if playlist_data else []

        for spot in spots:
            # Get song context for this DJ spot
            after_song_index = spot.get("after_song_index", 0)

            # Last 2 songs that played (before this spot)
            recent_songs = []
            for i in range(max(0, after_song_index - 2), after_song_index):
                if i < len(songs):
                    song = songs[i]
                    recent_songs.append({
                        "title": song.get("title", "Unknown"),
                        "artist": song.get("artist", "Unknown Artist"),
                        "album": song.get("album", ""),
                        "status": "just_played"
                    })

            # Next 5 songs coming up (after this spot)
            upcoming_songs = []
            for i in range(after_song_index, min(after_song_index + 5, len(songs))):
                if i < len(songs):
                    song = songs[i]
                    upcoming_songs.append({
                        "title": song.get("title", "Unknown"),
                        "artist": song.get("artist", "Unknown Artist"),
                        "album": song.get("album", ""),
                        "status": "coming_up"
                    })

            requirement = {
                "spot_number": spot["spot_number"],
                "type": spot["type"],
                "approximate_time": spot["approximate_time"],
                # Preserve placement info so assembler can insert audio correctly
                "after_song_index": spot.get("after_song_index"),
                "accumulated_minutes": spot.get("accumulated_minutes"),
                "context": {
                    "day_name": day_name,
                    "weather": weather,
                    "mood": mood,
                    "genre": genre,
                    "special_occasion": special_occasion
                },
                "song_context": {
                    "recent_songs": recent_songs,
                    "upcoming_songs": upcoming_songs
                },
                "duration_target_seconds": random.randint(10, 30),
                "tone": self.determine_tone(spot["type"], mood),
                "include_elements": self.get_elements_for_type(spot["type"])
            }
            spot_requirements.append(requirement)

        return {
            "total_spots": len(spot_requirements),
            "spots": spot_requirements,
            "config": config,
            "created_at": datetime.now().isoformat()
        }

    def determine_tone(self, spot_type: str, mood: str) -> str:
        """
        Determine the tone for the DJ spot
        """
        tone_map = {
            "morning_greeting": "cheerful and welcoming",
            "weather": "informative and pleasant",
            "daily_schedule": "organized and helpful",
            "time_check": "casual and friendly",
            "motivation": "inspiring and upbeat",
            "fun_fact": "curious and engaging",
            "lunch_reminder": "caring and casual",
            "afternoon_boost": "energetic and encouraging",
            "trivia": "playful and interesting",
            "joke": "lighthearted and funny",
            "evening_greeting": "warm and relaxed",
            "dinner_suggestion": "thoughtful and appetizing",
            "evening_wind_down": "calm and soothing",
            "tomorrow_preview": "optimistic and forward-looking",
            "hour_announcement": "clear and pleasant",
            "music_info": "knowledgeable and enthusiastic",
            "random_thought": "philosophical and thought-provoking",
            # New daily content types
            "dad_joke": "lighthearted and playful",
            "kid_fact": "educational and enthusiastic",
            "history_fact": "engaging and informative",
            "animal_fact": "fun and fascinating",
            "global_fact": "worldly and interesting",
            "country_comparison": "insightful and curious",
            "weird_fact": "amusing and surprising",
            "gross_fact": "playfully disgusted but entertaining",
            "general": "friendly and engaging"
        }

        return tone_map.get(spot_type, "friendly and professional")

    def get_elements_for_type(self, spot_type: str) -> List[str]:
        """
        Get elements to include based on spot type
        """
        elements_map = {
            "morning_greeting": ["greeting", "day_name", "positive_message"],
            "weather": ["current_weather", "temperature", "weather_advice"],
            "daily_schedule": ["time", "day_activities", "reminder"],
            "time_check": ["current_time", "time_context"],
            "motivation": ["inspirational_quote", "encouragement"],
            "fun_fact": ["interesting_fact", "did_you_know"],
            "lunch_reminder": ["time", "meal_suggestion", "break_reminder"],
            "afternoon_boost": ["energy_boost", "stretch_reminder"],
            "trivia": ["trivia_question", "trivia_answer"],
            "joke": ["setup", "punchline"],
            "evening_greeting": ["evening_greeting", "day_reflection"],
            "dinner_suggestion": ["meal_idea", "recipe_tip"],
            "evening_wind_down": ["relaxation_tip", "gratitude"],
            "tomorrow_preview": ["tomorrow_weather", "tomorrow_tip"],
            "hour_announcement": ["hour", "time_message"],
            "music_info": ["artist_fact", "genre_info", "music_history"],
            "random_thought": ["philosophical_question", "observation"],
            # New daily content types
            "dad_joke": ["setup", "punchline", "family_friendly"],
            "kid_fact": ["fun_fact", "educational_content", "age_appropriate"],
            "history_fact": ["historical_event", "interesting_context", "did_you_know"],
            "animal_fact": ["animal_behavior", "fun_fact", "nature_info"],
            "global_fact": ["world_culture", "international_info", "global_perspective"],
            "country_comparison": ["cultural_difference", "interesting_contrast", "world_perspective"],
            "weird_fact": ["unusual_fact", "surprising_info", "quirky_knowledge"],
            "gross_fact": ["icky_but_interesting", "science_fact", "eww_factor"],
            "general": ["greeting", "music_transition"]
        }

        return elements_map.get(spot_type, ["general_content"])

def plan_dj_spots(playlist_file: str = "curated_playlist.json",
                  config_file: str = "playlist_config.json") -> Dict:
    """
    Main function to plan DJ spots
    """
    # Check if we have a playlist_dir in config (from step 1)
    with open(config_file, 'r') as f:
        config = json.load(f)

    # If playlist_dir exists, read files from there
    if "playlist_dir" in config:
        playlist_dir = Path(config["playlist_dir"])
        playlist_file = playlist_dir / "curated_playlist.json"
        config_file = playlist_dir / "playlist_config.json"

        # Re-read config from dated directory
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        playlist_dir = Path(".")

    # Read playlist data
    with open(playlist_file, 'r') as f:
        playlist_data = json.load(f)

    # Add config to playlist_data so calculate_spot_positions can access start time
    playlist_data["config"] = config

    planner = DJSpotPlanner(minutes_between_spots=20)

    spots = planner.calculate_spot_positions(playlist_data)
    spot_requirements = planner.generate_spot_requirements(spots, config, playlist_data)

    spot_requirements["playlist_info"] = {
        "total_songs": len(playlist_data.get("songs", [])),
        "total_duration_seconds": playlist_data.get("total_duration_seconds", 0)
    }

    # Add playlist_dir to output for next steps
    if 'playlist_dir' in locals():
        spot_requirements["playlist_dir"] = str(playlist_dir)

    return spot_requirements

def main():
    """
    Read playlist and output DJ spot plan
    """
    spot_plan = plan_dj_spots()

    # Get playlist directory from spot plan or use current directory
    if "playlist_dir" in spot_plan:
        playlist_dir = Path(spot_plan["playlist_dir"])
    else:
        # Try to get from config
        try:
            with open("playlist_config.json", 'r') as f:
                config = json.load(f)
                if "playlist_dir" in config:
                    playlist_dir = Path(config["playlist_dir"])
                else:
                    playlist_dir = Path(".")
        except:
            playlist_dir = Path(".")

    # Save to dated directory
    output_file = playlist_dir / "dj_spot_plan.json"
    with open(output_file, "w") as f:
        json.dump(spot_plan, f, indent=2)

    print(f"Planned {spot_plan['total_spots']} DJ spots")
    for spot in spot_plan['spots']:
        print(f"  Spot {spot['spot_number']}: {spot['type']} at ~{spot['approximate_time']}")
    print(f"Saved to: {output_file}")

    return spot_plan

if __name__ == "__main__":
    main()
