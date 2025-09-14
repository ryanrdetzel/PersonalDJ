#!/usr/bin/env python3
"""
DJ Spot Planner - Calculates DJ spots based on configured schedule times
Uses precise timing configuration instead of automatic intervals
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict
import random
from pathlib import Path

class DJSpotPlanner:
    def __init__(self, schedule_config_file: str = "dj_schedule_config.json"):
        self.schedule_config_file = schedule_config_file
        self.schedule = self.load_dj_schedule()

    def load_dj_schedule(self) -> List[Dict]:
        """
        Load DJ schedule from configuration file
        """
        try:
            with open(self.schedule_config_file, 'r') as f:
                config = json.load(f)
            return config.get("schedules", [])
        except FileNotFoundError:
            print(f"Warning: DJ schedule config file {self.schedule_config_file} not found. Using empty schedule.")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing DJ schedule config: {e}. Using empty schedule.")
            return []

    def calculate_spot_positions(self, playlist_data: Dict) -> List[Dict]:
        """
        Calculate where to place DJ spots based on configured schedule times
        """
        songs = playlist_data.get("songs", [])
        if not songs or not self.schedule:
            return []

        # Get playlist start time
        config = playlist_data.get("config", {})
        if config.get("playlist_start_time"):
            playlist_start = datetime.fromisoformat(config["playlist_start_time"]).replace(second=0, microsecond=0)
        else:
            playlist_start = datetime.now().replace(second=0, microsecond=0)

        spots = []

        # Calculate cumulative durations for each song
        cumulative_durations = []
        total_duration = 0
        for song in songs:
            total_duration += song.get("duration_seconds", 180)
            cumulative_durations.append(total_duration)

        # Process each scheduled DJ spot
        for spot_number, schedule_item in enumerate(self.schedule, 1):
            target_time_str = schedule_item.get("time", "")
            content_tags = schedule_item.get("content", [])

            # Parse target time (format: "615" or "6:15")
            target_time = self.parse_time_string(target_time_str)
            if target_time is None:
                continue

            # Calculate target time as datetime
            target_datetime = playlist_start.replace(hour=target_time[0], minute=target_time[1], second=0, microsecond=0)

            # If target time is before playlist start, skip to next day
            if target_datetime < playlist_start:
                target_datetime += timedelta(days=1)

            # Calculate seconds from playlist start to target time
            target_seconds = (target_datetime - playlist_start).total_seconds()

            # Find the best song insertion point
            best_song_index = self.find_best_insertion_point(cumulative_durations, target_seconds)

            if best_song_index is not None:
                actual_time = playlist_start + timedelta(seconds=cumulative_durations[best_song_index-1] if best_song_index > 0 else 0)

                spot = {
                    "spot_number": spot_number,
                    "after_song_index": best_song_index,
                    "approximate_time": actual_time.strftime("%H:%M"),
                    "target_time": target_time_str,
                    "accumulated_minutes": cumulative_durations[best_song_index-1] / 60 if best_song_index > 0 else 0,
                    "content_tags": content_tags,
                    "type": self.determine_spot_type_from_tags(content_tags)
                }
                spots.append(spot)

        return spots

    def parse_time_string(self, time_str: str) -> tuple:
        """
        Parse time string in format "615" or "6:15" to (hour, minute)
        """
        try:
            if ":" in time_str:
                hour, minute = map(int, time_str.split(":"))
            else:
                # Format like "615" -> 6:15
                if len(time_str) == 3:
                    hour = int(time_str[0])
                    minute = int(time_str[1:3])
                elif len(time_str) == 4:
                    hour = int(time_str[0:2])
                    minute = int(time_str[2:4])
                else:
                    return None

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)
            return None
        except (ValueError, IndexError):
            return None

    def find_best_insertion_point(self, cumulative_durations: List[int], target_seconds: float) -> int:
        """
        Find the song index that provides the closest insertion point to target time
        """
        if not cumulative_durations:
            return None

        # If target is before first song ends, insert after first song
        if target_seconds <= cumulative_durations[0]:
            return 1

        # If target is after all songs, insert after last song
        if target_seconds >= cumulative_durations[-1]:
            return len(cumulative_durations)

        # Find the closest insertion point
        best_index = 1
        best_diff = abs(target_seconds - cumulative_durations[0])

        for i, duration in enumerate(cumulative_durations):
            diff = abs(target_seconds - duration)
            if diff < best_diff:
                best_diff = diff
                best_index = i + 1

        return best_index

    def determine_spot_type_from_tags(self, content_tags: List[str]) -> str:
        """
        Determine DJ spot type based on content tags from configuration
        Returns the primary content tag or a random one if multiple tags
        """
        if not content_tags:
            return "general"

        # Map content tags to internal types
        tag_mapping = {
            "weather": "weather",
            "events": "event_mention",
            "motivation": "motivation",
            "facts": "fun_fact",
            "jokes": "joke"
        }

        # Convert tags to internal types
        internal_types = [tag_mapping.get(tag, tag) for tag in content_tags]

        # Return a random type from the configured content
        return random.choice(internal_types)

    def generate_spot_requirements(self, spots: List[Dict], config: Dict, playlist_data: Dict = None) -> Dict:
        """
        Generate requirements for each DJ spot based on configuration
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
                "target_time": spot.get("target_time", ""),
                "content_tags": spot.get("content_tags", []),
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
            "schedule_config_file": self.schedule_config_file,
            "created_at": datetime.now().isoformat()
        }

    def determine_tone(self, spot_type: str, mood: str) -> str:
        """
        Determine the tone for the DJ spot
        """
        tone_map = {
            "weather": "informative and pleasant",
            "motivation": "inspiring and upbeat",
            "fun_fact": "curious and engaging",
            "joke": "lighthearted and funny",
            "event_mention": "excited and informative",
            "general": "friendly and engaging"
        }

        return tone_map.get(spot_type, "friendly and professional")

    def get_elements_for_type(self, spot_type: str) -> List[str]:
        """
        Get elements to include based on spot type
        """
        elements_map = {
            "weather": ["current_weather", "temperature", "weather_advice"],
            "motivation": ["inspirational_quote", "encouragement"],
            "fun_fact": ["interesting_fact", "did_you_know"],
            "joke": ["setup", "punchline"],
            "event_mention": ["event_details", "time_reference", "location_info"],
            "general": ["greeting", "music_transition"]
        }

        return elements_map.get(spot_type, ["general_content"])

def plan_dj_spots(playlist_file: str = "curated_playlist.json",
                  config_file: str = "playlist_config.json",
                  schedule_config_file: str = "dj_schedule_config.json") -> Dict:
    """
    Main function to plan DJ spots using configuration-based scheduling
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

    planner = DJSpotPlanner(schedule_config_file=schedule_config_file)

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
    Read playlist and output DJ spot plan using configuration-based scheduling
    """
    import argparse
    parser = argparse.ArgumentParser(description="Plan DJ spots using schedule configuration")
    parser.add_argument("--schedule-config", default="dj_schedule_config.json",
                       help="DJ schedule configuration file")
    args = parser.parse_args()

    spot_plan = plan_dj_spots(schedule_config_file=args.schedule_config)

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

    print(f"Planned {spot_plan['total_spots']} DJ spots using schedule configuration")
    for spot in spot_plan['spots']:
        content_tags = ', '.join(spot.get('content_tags', []))
        target_time = spot.get('target_time', 'N/A')
        actual_time = spot.get('approximate_time', 'N/A')
        print(f"  Spot {spot['spot_number']}: {spot['type']} (target: {target_time}, actual: ~{actual_time}) - Content: [{content_tags}]")
    print(f"Saved to: {output_file}")

    return spot_plan

if __name__ == "__main__":
    main()
