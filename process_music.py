#!/usr/bin/env python3
"""
Music File Processor - Extracts metadata and moves files from unprocessed to library
"""

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from mutagen import File
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
import json
import hashlib

class MusicProcessor:
    def __init__(self, unprocessed_dir="music/unprocessed", music_dir="music", db_path="music_history.db"):
        self.unprocessed_dir = Path(unprocessed_dir)
        self.music_dir = Path(music_dir)
        self.db_path = db_path
        self.supported_extensions = ['.mp3', '.m4a', '.mp4', '.aac', '.flac', '.wav', '.ogg']
        self.processed_count = 0
        self.error_count = 0
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
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_hash TEXT,
                bitrate INTEGER,
                year INTEGER
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
            CREATE INDEX IF NOT EXISTS idx_file_hash
            ON music_library(file_hash)
        """)

        conn.commit()
        conn.close()

    def calculate_file_hash(self, filepath: Path) -> str:
        """Calculate MD5 hash of file for duplicate detection"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def extract_metadata(self, filepath: Path) -> Optional[Dict]:
        """Extract metadata from audio file using mutagen"""
        try:
            audio_file = File(filepath)
            if audio_file is None:
                print(f"Warning: Could not read audio file: {filepath}")
                return None

            metadata = {
                "file_path": "",  # Will be set after moving
                "title": None,
                "artist": None,
                "album": None,
                "genre": None,
                "duration_seconds": None,
                "bitrate": None,
                "year": None,
                "energy_level": 5,  # Default middle energy
                "explicit": False,
                "instrumental": False,
                "file_hash": self.calculate_file_hash(filepath)
            }

            # Extract duration
            if hasattr(audio_file.info, 'length'):
                metadata["duration_seconds"] = int(audio_file.info.length)

            # Extract bitrate
            if hasattr(audio_file.info, 'bitrate'):
                metadata["bitrate"] = audio_file.info.bitrate

            # Extract tags based on file type
            if isinstance(audio_file, MP4):
                # MP4/M4A files
                metadata["title"] = str(audio_file.get('\xa9nam', [None])[0]) if '\xa9nam' in audio_file else None
                metadata["artist"] = str(audio_file.get('\xa9ART', [None])[0]) if '\xa9ART' in audio_file else None
                metadata["album"] = str(audio_file.get('\xa9alb', [None])[0]) if '\xa9alb' in audio_file else None
                metadata["genre"] = str(audio_file.get('\xa9gen', [None])[0]) if '\xa9gen' in audio_file else None

                # Year
                if '\xa9day' in audio_file:
                    year_str = str(audio_file['\xa9day'][0])
                    if year_str and len(year_str) >= 4:
                        metadata["year"] = int(year_str[:4])

            elif hasattr(audio_file, 'tags'):
                # MP3, FLAC, OGG files
                tags = audio_file.tags
                if tags:
                    metadata["title"] = str(tags.get('TIT2', tags.get('TITLE', [None]))[0]) if 'TIT2' in tags or 'TITLE' in tags else None
                    metadata["artist"] = str(tags.get('TPE1', tags.get('ARTIST', [None]))[0]) if 'TPE1' in tags or 'ARTIST' in tags else None
                    metadata["album"] = str(tags.get('TALB', tags.get('ALBUM', [None]))[0]) if 'TALB' in tags or 'ALBUM' in tags else None
                    metadata["genre"] = str(tags.get('TCON', tags.get('GENRE', [None]))[0]) if 'TCON' in tags or 'GENRE' in tags else None

                    # Year
                    year_tag = tags.get('TDRC', tags.get('TYER', tags.get('DATE', None)))
                    if year_tag:
                        year_str = str(year_tag[0]) if hasattr(year_tag, '__getitem__') else str(year_tag)
                        if year_str and len(year_str) >= 4:
                            try:
                                metadata["year"] = int(year_str[:4])
                            except ValueError:
                                pass

            # Fallback to filename if title is missing
            if not metadata["title"]:
                metadata["title"] = filepath.stem

            # Set unknown for missing fields
            if not metadata["artist"]:
                metadata["artist"] = "Unknown Artist"
            if not metadata["album"]:
                metadata["album"] = "Unknown Album"
            if not metadata["genre"]:
                metadata["genre"] = "Unknown"

            return metadata

        except Exception as e:
            print(f"Error extracting metadata from {filepath}: {e}")
            return None

    def check_duplicate(self, file_hash: str) -> bool:
        """Check if file already exists in database by hash"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, file_path FROM music_library WHERE file_hash = ?", (file_hash,))
        result = cursor.fetchone()
        conn.close()

        if result:
            print(f"  Duplicate detected (already in library as {result[1]})")
            return True
        return False

    def organize_file_path(self, metadata: Dict, original_path: Path) -> Path:
        """Generate organized file path based on metadata"""
        artist = metadata.get("artist", "Unknown Artist").replace("/", "-").replace("\\", "-")
        album = metadata.get("album", "Unknown Album").replace("/", "-").replace("\\", "-")

        # Create artist/album directory structure
        target_dir = self.music_dir / artist / album
        target_dir.mkdir(parents=True, exist_ok=True)

        # Use original filename
        target_path = target_dir / original_path.name

        # Handle filename conflicts
        if target_path.exists():
            counter = 1
            while target_path.exists():
                stem = original_path.stem
                suffix = original_path.suffix
                target_path = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        return target_path

    def add_to_database(self, metadata: Dict) -> bool:
        """Add song metadata to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO music_library
                (file_path, title, artist, album, genre, duration_seconds,
                 energy_level, explicit, instrumental, file_hash, bitrate, year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata["file_path"],
                metadata["title"],
                metadata["artist"],
                metadata["album"],
                metadata["genre"],
                metadata["duration_seconds"],
                metadata["energy_level"],
                metadata["explicit"],
                metadata["instrumental"],
                metadata["file_hash"],
                metadata["bitrate"],
                metadata["year"]
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def process_file(self, filepath: Path) -> bool:
        """Process a single music file"""
        print(f"\nProcessing: {filepath.name}")

        # Extract metadata
        metadata = self.extract_metadata(filepath)
        if not metadata:
            print(f"  Failed to extract metadata")
            return False

        # Check for duplicates
        if self.check_duplicate(metadata["file_hash"]):
            return False

        # Determine target path
        target_path = self.organize_file_path(metadata, filepath)
        metadata["file_path"] = str(target_path)

        # Move file
        try:
            shutil.move(str(filepath), str(target_path))
            print(f"  Moved to: {target_path}")
        except Exception as e:
            print(f"  Failed to move file: {e}")
            return False

        # Add to database
        if self.add_to_database(metadata):
            print(f"  Added to database:")
            print(f"    Title: {metadata['title']}")
            print(f"    Artist: {metadata['artist']}")
            print(f"    Album: {metadata['album']}")
            print(f"    Genre: {metadata['genre']}")
            if metadata['duration_seconds']:
                print(f"    Duration: {metadata['duration_seconds']}s")
            return True
        else:
            print(f"  Failed to add to database")
            # Move file back if database insert failed
            try:
                shutil.move(str(target_path), str(filepath))
            except:
                pass
            return False

    def process_all(self):
        """Process all files in unprocessed directory"""
        if not self.unprocessed_dir.exists():
            print(f"Unprocessed directory does not exist: {self.unprocessed_dir}")
            return

        files_to_process = []
        for ext in self.supported_extensions:
            files_to_process.extend(self.unprocessed_dir.glob(f"*{ext}"))
            files_to_process.extend(self.unprocessed_dir.glob(f"*{ext.upper()}"))

        if not files_to_process:
            print(f"No music files found in {self.unprocessed_dir}")
            print(f"Supported formats: {', '.join(self.supported_extensions)}")
            return

        print(f"Found {len(files_to_process)} files to process")
        print("=" * 50)

        for filepath in files_to_process:
            if self.process_file(filepath):
                self.processed_count += 1
            else:
                self.error_count += 1

        print("\n" + "=" * 50)
        print(f"Processing complete!")
        print(f"  Successfully processed: {self.processed_count}")
        print(f"  Errors/Skipped: {self.error_count}")

        # Show database stats
        self.show_library_stats()

    def show_library_stats(self):
        """Display statistics about the music library"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM music_library")
        total_songs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT artist) FROM music_library")
        total_artists = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT album) FROM music_library")
        total_albums = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT genre) FROM music_library")
        total_genres = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(duration_seconds) FROM music_library")
        total_duration = cursor.fetchone()[0] or 0

        conn.close()

        print(f"\nLibrary Statistics:")
        print(f"  Total songs: {total_songs}")
        print(f"  Total artists: {total_artists}")
        print(f"  Total albums: {total_albums}")
        print(f"  Total genres: {total_genres}")
        print(f"  Total duration: {total_duration // 3600:.1f} hours")

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Process music files and add to library")
    parser.add_argument("--unprocessed", default="music/unprocessed",
                       help="Directory containing unprocessed music files")
    parser.add_argument("--music-dir", default="music",
                       help="Target music library directory")
    parser.add_argument("--db", default="music_history.db",
                       help="Database file path")

    args = parser.parse_args()

    processor = MusicProcessor(
        unprocessed_dir=args.unprocessed,
        music_dir=args.music_dir,
        db_path=args.db
    )

    processor.process_all()

if __name__ == "__main__":
    main()