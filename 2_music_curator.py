#!/usr/bin/env python3
"""
Music Curator - Selects songs based on genre and play history
Uses SQLite to track what has been played recently
"""

import json
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import os

class MusicDatabase:
    def __init__(self, db_path="music_history.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS music_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                genre TEXT,
                duration_seconds INTEGER,
                energy_level INTEGER,
                explicit BOOLEAN,
                instrumental BOOLEAN,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS play_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id INTEGER,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                playlist_date DATE,
                FOREIGN KEY (song_id) REFERENCES music_library (id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_play_history_date
            ON play_history(playlist_date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_play_history_played
            ON play_history(played_at)
        """)

        conn.commit()
        conn.close()

    def add_song(self, song_data: Dict):
        """Add a song to the music library"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO music_library
                (file_path, title, artist, album, genre, duration_seconds,
                 energy_level, explicit, instrumental)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                song_data.get("file_path"),
                song_data.get("title"),
                song_data.get("artist"),
                song_data.get("album"),
                song_data.get("genre"),
                song_data.get("duration_seconds"),
                song_data.get("energy_level"),
                song_data.get("explicit", False),
                song_data.get("instrumental", False)
            ))
            conn.commit()
        finally:
            conn.close()

    def get_recent_plays(self, days=7) -> List[int]:
        """Get song IDs played in the last N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT song_id
            FROM play_history
            WHERE datetime(played_at) > datetime('now', ? || ' days')
        """, (-days,))

        recent_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        return recent_ids

    def get_available_songs(self, genre: str = None,
                          exclude_recent_days: int = 1,
                          energy_range: tuple = None,
                          avoid_explicit: bool = True,
                          prefer_instrumental: bool = False) -> List[Dict]:
        """Get songs matching criteria, excluding recently played"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        recent_ids = self.get_recent_plays(exclude_recent_days)
        recent_clause = f"AND id NOT IN ({','.join(map(str, recent_ids))})" if recent_ids else ""

        # Handle genre selection
        if genre == "Other":
            # Select songs with Unknown or empty genres
            genre_clause = "AND (genre = 'Unknown' OR genre IS NULL OR genre = '')"
        elif genre and genre != "mixed":
            genre_clause = f"AND genre = '{genre}'"
        else:
            genre_clause = ""

        energy_clause = ""
        if energy_range:
            energy_clause = f"AND energy_level BETWEEN {energy_range[0]} AND {energy_range[1]}"

        explicit_clause = "AND explicit = 0" if avoid_explicit else ""

        instrumental_clause = "AND instrumental = 1" if prefer_instrumental else ""

        query = f"""
            SELECT * FROM music_library
            WHERE 1=1
            {recent_clause}
            {genre_clause}
            {energy_clause}
            {explicit_clause}
            {instrumental_clause}
        """

        cursor.execute(query)
        songs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return songs

    def get_available_genres(self) -> List[str]:
        """Get list of all unique genres in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT genre
            FROM music_library
            WHERE genre IS NOT NULL AND genre != ''
            ORDER BY genre
        """)

        genres = [row[0] for row in cursor.fetchall()]
        conn.close()

        return genres

    def record_play(self, song_id: int, playlist_date: str = None):
        """Record that a song was added to a playlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if not playlist_date:
            playlist_date = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO play_history (song_id, playlist_date)
            VALUES (?, ?)
        """, (song_id, playlist_date))

        conn.commit()
        conn.close()

def curate_playlist(config_file: str = "playlist_config.json") -> List[Dict]:
    """
    Main function to curate a playlist based on configuration
    """
    # First try to load from dated directory if it exists in config
    with open(config_file, 'r') as f:
        config = json.load(f)

    # If playlist_dir is in config, use files from there
    if "playlist_dir" in config:
        playlist_dir = Path(config["playlist_dir"])
        config_file = playlist_dir / "playlist_config.json"
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        playlist_dir = Path(".")

    db = MusicDatabase()

    # Get available genres and validate requested genre
    available_genres = db.get_available_genres()
    requested_genre = config.get("genre", "mixed")

    # Map requested genre to available genre
    if requested_genre != "mixed":
        if requested_genre not in available_genres:
            # Check if Unknown songs exist
            has_unknown = "Unknown" in available_genres
            if has_unknown:
                print(f"Genre '{requested_genre}' not found. Using 'Other' (Unknown/untagged songs)")
                genre = "Other"
            else:
                print(f"Genre '{requested_genre}' not found. Available genres: {', '.join(available_genres)}")
                genre = None  # Will select from all genres
        else:
            genre = requested_genre
    else:
        genre = "mixed"

    energy_level = config.get("energy_level", 5)
    total_songs = config.get("total_songs", 100)
    preferences = config.get("preferences", {})

    energy_range = (max(1, energy_level - 2), min(10, energy_level + 2))

    available_songs = db.get_available_songs(
        genre=genre,
        exclude_recent_days=1,
        energy_range=energy_range,
        avoid_explicit=preferences.get("avoid_explicit", True),
        prefer_instrumental=preferences.get("prefer_instrumental", False)
    )

    if len(available_songs) < total_songs:
        print(f"Warning: Only {len(available_songs)} songs available for genre '{genre}', using all genres...")
        available_songs = db.get_available_songs(
            genre=None,
            exclude_recent_days=1,
            energy_range=energy_range,
            avoid_explicit=preferences.get("avoid_explicit", True),
            prefer_instrumental=preferences.get("prefer_instrumental", False)
        )

        if len(available_songs) < total_songs:
            print(f"Still only {len(available_songs)} songs, removing recent play restriction...")
            available_songs = db.get_available_songs(
                genre=None,
                exclude_recent_days=0,
                energy_range=(1, 10),
                avoid_explicit=preferences.get("avoid_explicit", True),
                prefer_instrumental=preferences.get("prefer_instrumental", False)
            )

    selected_songs = []
    if available_songs:
        num_to_select = min(len(available_songs), total_songs)
        selected_songs = random.sample(available_songs, num_to_select)

        for song in selected_songs:
            db.record_play(song['id'])

    playlist_data = {
        "config": config,
        "songs": selected_songs,
        "total_duration_seconds": sum(s.get("duration_seconds", 0) for s in selected_songs),
        "created_at": datetime.now().isoformat()
    }

    return playlist_data

def main():
    """
    Read config and output curated playlist
    """
    playlist = curate_playlist()

    # Determine output directory from config
    output_file = "curated_playlist.json"
    if "playlist_dir" in playlist["config"]:
        playlist_dir = Path(playlist["config"]["playlist_dir"])
        output_file = playlist_dir / "curated_playlist.json"

    # Save to the appropriate directory
    with open(output_file, "w") as f:
        json.dump(playlist, f, indent=2)

    print(f"Curated {len(playlist['songs'])} songs")
    print(f"Total duration: {playlist['total_duration_seconds'] / 3600:.1f} hours")
    print(f"Saved playlist to: {output_file}")

    # Print song list summary
    if playlist['songs']:
        print("\nFirst 10 songs in playlist:")
        for i, song in enumerate(playlist['songs'][:10], 1):
            artist = song.get('artist', 'Unknown Artist')
            title = song.get('title', 'Unknown Title')
            print(f"  {i}. {artist} - {title}")
        if len(playlist['songs']) > 10:
            print(f"  ... and {len(playlist['songs']) - 10} more songs")

    return playlist

if __name__ == "__main__":
    main()