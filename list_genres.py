#!/usr/bin/env python3
"""
List all available genres in the music database
"""

import sqlite3
from collections import Counter

def list_genres(db_path="music_history.db"):
    """List all genres and their song counts"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT genre, COUNT(*) as count
        FROM music_library
        GROUP BY genre
        ORDER BY count DESC, genre
    """)

    genres = cursor.fetchall()
    conn.close()

    total_songs = sum(count for _, count in genres)

    print(f"\nAvailable genres in database ({total_songs} total songs):")
    print("-" * 40)

    for genre, count in genres:
        if genre is None or genre == '':
            genre = "Unknown/Other"
        percentage = (count / total_songs) * 100
        print(f"{genre:25} {count:3} songs ({percentage:5.1f}%)")

    print("-" * 40)
    print("\nNote: 'Unknown' songs can be selected using genre='Other'")

    # Also list just the valid genre names
    print("\nValid genre names for configuration:")
    valid_genres = []
    for genre, _ in genres:
        if genre and genre != "Unknown":
            valid_genres.append(genre)
    valid_genres.append("Other")  # For Unknown/untagged songs
    valid_genres.append("mixed")  # For all genres

    print(", ".join(sorted(valid_genres)))

if __name__ == "__main__":
    list_genres()