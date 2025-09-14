#!/usr/bin/env python3
"""
Test Server for Dynamic Playlist System
Simple web server to test the dynamic playlist concept with fake MP3 filenames
"""

import glob
import json
import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, Response, abort, jsonify, request, send_file

app = Flask(__name__)


class TestPlaylistDB:
    def __init__(self, db_path: str = "test_playlist.db"):
        self.db_path = db_path
        self.music_dir = Path("music")
        self.init_db()
        self.populate_sample_data()

    def init_db(self):
        """Initialize test database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS playlist_mapping (
                fake_filename TEXT PRIMARY KEY,
                real_file_path TEXT,
                title TEXT,
                artist TEXT,
                duration INTEGER,
                created_at TIMESTAMP,
                play_count INTEGER DEFAULT 0
            )
        """
        )

        conn.commit()
        conn.close()

    def populate_sample_data(self):
        """Add some sample mappings for testing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if we already have data
        cursor.execute("SELECT COUNT(*) FROM playlist_mapping")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return

        # Get some real music files for mapping
        music_files = self.get_music_files()

        if music_files:
            sample_mappings = [
                (
                    "20250913-1.mp3",
                    music_files[0] if len(music_files) > 0 else None,
                    "Morning Opener",
                    "Test Artist",
                    180,
                ),
                (
                    "20250913-2.mp3",
                    music_files[1] if len(music_files) > 1 else None,
                    "Second Track",
                    "Another Artist",
                    210,
                ),
                (
                    "20250913-3.mp3",
                    music_files[2] if len(music_files) > 2 else None,
                    "Third Song",
                    "Band Name",
                    195,
                ),
            ]

            for fake_name, real_path, title, artist, duration in sample_mappings:
                if real_path and Path(real_path).exists():
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO playlist_mapping
                        (fake_filename, real_file_path, title, artist, duration, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            fake_name,
                            real_path,
                            title,
                            artist,
                            duration,
                            datetime.now().isoformat(),
                        ),
                    )

        conn.commit()
        conn.close()

    def get_music_files(self) -> List[str]:
        """Get list of available music files"""
        music_files = []
        if self.music_dir.exists():
            for ext in ["*.mp3", "*.wav", "*.flac"]:
                music_files.extend(
                    glob.glob(str(self.music_dir / "**" / ext), recursive=True)
                )
        return music_files[:50]  # Limit for testing

    def get_mapping(self, fake_filename: str) -> Optional[Dict]:
        """Get real file mapping for fake filename"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT real_file_path, title, artist, duration, play_count
            FROM playlist_mapping WHERE fake_filename = ?
        """,
            (fake_filename,),
        )

        result = cursor.fetchone()

        if result:
            # Increment play count
            cursor.execute(
                """
                UPDATE playlist_mapping SET play_count = play_count + 1
                WHERE fake_filename = ?
            """,
                (fake_filename,),
            )
            conn.commit()

            conn.close()
            return {
                "real_file_path": result[0],
                "title": result[1],
                "artist": result[2],
                "duration": result[3],
                "play_count": result[4] + 1,
            }

        conn.close()
        return None

    def add_mapping(
        self,
        fake_filename: str,
        real_file_path: str,
        title: str = None,
        artist: str = None,
    ):
        """Add new mapping to database"""
        if not title:
            title = Path(real_file_path).stem
        if not artist:
            # Try to extract artist from path structure
            parts = Path(real_file_path).parts
            artist = parts[-3] if len(parts) >= 3 else "Unknown Artist"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO playlist_mapping
            (fake_filename, real_file_path, title, artist, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                fake_filename,
                real_file_path,
                title,
                artist,
                180,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def get_random_music_file(self) -> Optional[str]:
        """Get a random music file from the catalog"""
        music_files = self.get_music_files()
        if music_files:
            return random.choice(music_files)
        return None


# Global database instance
db = TestPlaylistDB()


@app.route("/playlist/<date>")
def generate_playlist(date: str):
    """Generate M3U playlist with fake filenames"""
    try:
        # Validate date format
        datetime.strptime(date, "%Y%m%d")
    except ValueError:
        abort(400, "Invalid date format. Use YYYYMMDD")

    track_count = int(request.args.get("count", 200))
    base_url = request.args.get("base_url", "http://localhost:5004")

    playlist_lines = ["#EXTM3U", f"#PLAYLIST:Test Dynamic Playlist - {date}"]

    for i in range(1, track_count + 1):
        fake_filename = f"{date}-{i}.mp3"
        playlist_lines.append(f"#EXTINF:-1,Track {i:03d}")
        playlist_lines.append(f"{base_url}/music/{fake_filename}")

    playlist_content = "\n".join(playlist_lines)

    return Response(
        playlist_content,
        mimetype="audio/x-mpegurl",
        headers={"Content-Disposition": f'attachment; filename="playlist-{date}.m3u"'},
    )


@app.route("/music/<filename>")
def serve_music(filename: str):
    """Serve music file - either from database mapping or random fallback"""
    if not filename.endswith(".mp3"):
        abort(400, "Only MP3 files supported")

    print(f"Request for: {filename}")

    # Try to get mapping from database
    mapping = db.get_mapping(filename)

    if mapping and Path(mapping["real_file_path"]).exists():
        print(f"Found mapping: {mapping['title']} by {mapping['artist']}")
        print(f"Serving: {mapping['real_file_path']}")
        return send_file(
            mapping["real_file_path"], as_attachment=False, mimetype="audio/mpeg"
        )

    # No mapping found, try to create one with random file
    print("No mapping found, selecting random file...")
    random_file = db.get_random_music_file()

    if random_file and Path(random_file).exists():
        # Add this mapping to database for future requests
        db.add_mapping(filename, random_file)
        print(f"Created new mapping: {filename} -> {random_file}")

        return send_file(random_file, as_attachment=False, mimetype="audio/mpeg")

    abort(404, f"No music file available for {filename}")


@app.route("/info/<filename>")
def get_music_info(filename: str):
    """Get information about a music file"""
    mapping = db.get_mapping(filename)

    if mapping:
        return jsonify(
            {
                "filename": filename,
                "title": mapping["title"],
                "artist": mapping["artist"],
                "duration": mapping["duration"],
                "play_count": mapping["play_count"],
                "real_file": mapping["real_file_path"],
                "exists": Path(mapping["real_file_path"]).exists(),
            }
        )

    return jsonify(
        {
            "filename": filename,
            "mapped": False,
            "message": "No mapping found - would serve random file",
        }
    )


@app.route("/admin/mappings")
def list_mappings():
    """List all current mappings"""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT fake_filename, real_file_path, title, artist, play_count, created_at
        FROM playlist_mapping
        ORDER BY fake_filename
    """
    )

    mappings = []
    for row in cursor.fetchall():
        mappings.append(
            {
                "fake_filename": row[0],
                "real_file_path": row[1],
                "title": row[2],
                "artist": row[3],
                "play_count": row[4],
                "created_at": row[5],
                "file_exists": Path(row[1]).exists() if row[1] else False,
            }
        )

    conn.close()

    return jsonify({"total_mappings": len(mappings), "mappings": mappings})


@app.route("/admin/add_mapping", methods=["POST"])
def add_mapping():
    """Add a new mapping via API"""
    data = request.get_json()

    if not data or "fake_filename" not in data or "real_file_path" not in data:
        abort(400, "Missing required fields: fake_filename, real_file_path")

    fake_filename = data["fake_filename"]
    real_file_path = data["real_file_path"]
    title = data.get("title")
    artist = data.get("artist")

    if not Path(real_file_path).exists():
        abort(400, f"Real file does not exist: {real_file_path}")

    db.add_mapping(fake_filename, real_file_path, title, artist)

    return jsonify(
        {
            "success": True,
            "message": f"Added mapping: {fake_filename} -> {real_file_path}",
        }
    )


@app.route("/admin/music_files")
def list_music_files():
    """List available music files"""
    music_files = db.get_music_files()

    return jsonify(
        {
            "total_files": len(music_files),
            "files": music_files[:50],  # Limit for display
        }
    )


@app.route("/test")
def test_page():
    """Simple test page"""
    return f"""
    <h1>Dynamic Playlist Test Server</h1>
    <h2>Endpoints:</h2>
    <ul>
        <li><a href="/playlist/20250913">Generate Playlist</a> - M3U with fake filenames</li>
        <li><a href="/music/20250913-1.mp3">Test Music File</a> - Serve dynamic content</li>
        <li><a href="/info/20250913-1.mp3">File Info</a> - Get metadata</li>
        <li><a href="/admin/mappings">View Mappings</a> - See current database</li>
        <li><a href="/admin/music_files">List Music Files</a> - Available real files</li>
    </ul>

    <h2>Usage:</h2>
    <ol>
        <li>Generate playlist: <code>GET /playlist/20250913</code></li>
        <li>Load playlist in media player</li>
        <li>Player requests tracks like <code>/music/20250913-1.mp3</code></li>
        <li>Server either serves mapped file or random fallback</li>
    </ol>

    <p>Music directory: {db.music_dir}</p>
    <p>Available files: {len(db.get_music_files())}</p>
    """


@app.route("/")
def home():
    return test_page()


if __name__ == "__main__":
    print("Starting Dynamic Playlist Test Server...")
    print(f"Music directory: {db.music_dir}")
    print(f"Available music files: {len(db.get_music_files())}")

    if not db.music_dir.exists():
        print(f"⚠️  Warning: Music directory '{db.music_dir}' not found")
        print("   Create the directory and add some MP3 files to test")

    app.run(host="0.0.0.0", port=5004, debug=True)

