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
import ffmpeg
import tempfile
import subprocess

class MusicProcessor:
    def __init__(self, music_dir="music", db_path="music_history.db"):
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
                year INTEGER,
                normalized BOOLEAN DEFAULT FALSE,
                lufs_before REAL,
                lufs_after REAL,
                normalized_date TIMESTAMP
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

        # Add normalization columns to existing tables if they don't exist
        try:
            cursor.execute("ALTER TABLE music_library ADD COLUMN normalized BOOLEAN DEFAULT FALSE")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE music_library ADD COLUMN lufs_before REAL")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE music_library ADD COLUMN lufs_after REAL")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE music_library ADD COLUMN normalized_date TIMESTAMP")
        except sqlite3.OperationalError:
            pass

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

    def get_unprocessed_files(self, all_files: list) -> list:
        """Return list of files that are not yet in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all file paths and hashes from database
        cursor.execute("SELECT file_path, file_hash FROM music_library")
        db_files = cursor.fetchall()
        conn.close()

        # Create sets for faster lookup
        db_paths = {Path(file_path) for file_path, _ in db_files}
        db_hashes = {file_hash for _, file_hash in db_files if file_hash}

        unprocessed_files = []
        for file_path in all_files:
            # Check if file path is already in database
            if file_path in db_paths:
                continue

            # Check if file hash is already in database (duplicate detection)
            try:
                file_hash = self.calculate_file_hash(file_path)
                if file_hash in db_hashes:
                    print(f"Skipping {file_path.name} - duplicate already in database")
                    continue
            except Exception as e:
                print(f"Warning: Could not hash {file_path}: {e}")

            unprocessed_files.append(file_path)

        return unprocessed_files


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
        """Process a single music file (no file moving, just add to database)"""
        print(f"\nProcessing: {filepath.name}")

        # Extract metadata
        metadata = self.extract_metadata(filepath)
        if not metadata:
            print(f"  Failed to extract metadata")
            return False

        # Set file path to current location (no moving)
        metadata["file_path"] = str(filepath)

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
            return False

    def process_all(self):
        """Process all files in music directory that aren't in database yet"""
        if not self.music_dir.exists():
            print(f"Music directory does not exist: {self.music_dir}")
            return

        # Get all music files in the directory
        all_files = []
        for ext in self.supported_extensions:
            all_files.extend(self.music_dir.glob(f"*{ext}"))
            all_files.extend(self.music_dir.glob(f"*{ext.upper()}"))

        if not all_files:
            print(f"No music files found in {self.music_dir}")
            print(f"Supported formats: {', '.join(self.supported_extensions)}")
            return

        # Filter out files already in database
        files_to_process = self.get_unprocessed_files(all_files)

        if not files_to_process:
            print(f"No new music files to process in {self.music_dir}")
            print(f"All {len(all_files)} files are already in the database")
            return

        print(f"Found {len(files_to_process)} new files to process out of {len(all_files)} total files")
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

    def measure_lufs(self, filepath: Path) -> Optional[float]:
        """Measure LUFS loudness of audio file using ffmpeg"""
        try:
            # Use ffmpeg to analyze loudness
            result = subprocess.run([
                'ffmpeg', '-i', str(filepath), '-af', 'loudnorm=print_format=json',
                '-f', 'null', '-'
            ], capture_output=True, text=True)

            # Parse JSON output from stderr (ffmpeg outputs to stderr)
            output = result.stderr
            if 'input_i' in output:
                # Extract LUFS value from JSON output
                import re
                lufs_match = re.search(r'"input_i"\s*:\s*"([^"]+)"', output)
                if lufs_match:
                    return float(lufs_match.group(1))
        except Exception as e:
            print(f"  Error measuring LUFS: {e}")
            return None

        return None

    def normalize_audio_file(self, filepath: Path, target_lufs: float = -14.0, backup: bool = True) -> bool:
        """Normalize audio file to target LUFS using FFmpeg loudnorm filter"""
        try:
            print(f"  Normalizing audio to {target_lufs} LUFS...")

            # Measure current LUFS
            current_lufs = self.measure_lufs(filepath)
            if current_lufs is None:
                print(f"  Failed to measure current LUFS")
                return False

            print(f"  Current LUFS: {current_lufs:.1f}")

            # Skip if already close to target (within 0.5 LUFS)
            if abs(current_lufs - target_lufs) < 0.5:
                print(f"  Already normalized (within 0.5 LUFS of target)")
                return True

            # Create backup if requested
            if backup:
                backup_path = filepath.parent / f"{filepath.stem}_original{filepath.suffix}"
                if not backup_path.exists():
                    shutil.copy2(filepath, backup_path)
                    print(f"  Created backup: {backup_path}")

            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=filepath.suffix, delete=False) as temp_file:
                temp_path = Path(temp_file.name)

            try:
                # First pass: analyze
                analyze_result = subprocess.run([
                    'ffmpeg', '-i', str(filepath), '-af',
                    f'loudnorm=I={target_lufs}:dual_mono=true:TP=-1.5:LRA=11:print_format=json',
                    '-f', 'null', '-'
                ], capture_output=True, text=True)

                # Extract first pass measurements
                analyze_output = analyze_result.stderr
                import re

                input_i = re.search(r'"input_i"\s*:\s*"([^"]+)"', analyze_output)
                input_tp = re.search(r'"input_tp"\s*:\s*"([^"]+)"', analyze_output)
                input_lra = re.search(r'"input_lra"\s*:\s*"([^"]+)"', analyze_output)
                input_thresh = re.search(r'"input_thresh"\s*:\s*"([^"]+)"', analyze_output)

                if not all([input_i, input_tp, input_lra, input_thresh]):
                    print(f"  Failed to analyze audio for normalization")
                    temp_path.unlink()
                    return False

                # Second pass: normalize with measured values
                normalize_cmd = [
                    'ffmpeg', '-i', str(filepath), '-af',
                    f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11:' +
                    f'measured_I={input_i.group(1)}:' +
                    f'measured_TP={input_tp.group(1)}:' +
                    f'measured_LRA={input_lra.group(1)}:' +
                    f'measured_thresh={input_thresh.group(1)}:' +
                    'linear=true:print_format=json',
                    '-y', str(temp_path)
                ]

                result = subprocess.run(normalize_cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    print(f"  FFmpeg normalization failed: {result.stderr}")
                    temp_path.unlink()
                    return False

                # Replace original with normalized version
                shutil.move(str(temp_path), str(filepath))

                # Measure final LUFS
                final_lufs = self.measure_lufs(filepath)
                if final_lufs:
                    print(f"  Normalized LUFS: {final_lufs:.1f}")

                    # Update database
                    self.update_normalization_status(filepath, current_lufs, final_lufs)

                return True

            except Exception as e:
                print(f"  Normalization failed: {e}")
                if temp_path.exists():
                    temp_path.unlink()
                return False

        except Exception as e:
            print(f"  Error normalizing {filepath}: {e}")
            return False

    def update_normalization_status(self, filepath: Path, lufs_before: float, lufs_after: float):
        """Update database with normalization status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE music_library
                SET normalized = TRUE, lufs_before = ?, lufs_after = ?, normalized_date = ?
                WHERE file_path = ?
            """, (lufs_before, lufs_after, datetime.now(), str(filepath)))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"  Failed to update normalization status: {e}")

    def normalize_all_files(self, target_lufs: float = -14.0, force: bool = False):
        """Normalize all files in the music library"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if force:
            # Normalize all files
            cursor.execute("SELECT file_path FROM music_library")
        else:
            # Only normalize files that haven't been normalized yet
            cursor.execute("SELECT file_path FROM music_library WHERE normalized != 1 OR normalized IS NULL")

        files_to_normalize = cursor.fetchall()
        conn.close()

        if not files_to_normalize:
            print("No files need normalization")
            return

        total_files = len(files_to_normalize)
        print(f"\nNormalizing {total_files} files to {target_lufs} LUFS...")
        print("=" * 60)

        success_count = 0
        error_count = 0

        for idx, (file_path,) in enumerate(files_to_normalize, 1):
            filepath = Path(file_path)

            if not filepath.exists():
                print(f"[{idx}/{total_files}] File not found: {filepath}")
                error_count += 1
                continue

            print(f"\n[{idx}/{total_files}] Processing: {filepath.name}")

            if self.normalize_audio_file(filepath, target_lufs):
                success_count += 1
                print(f"  ✓ Normalized successfully")
            else:
                error_count += 1
                print(f"  ✗ Normalization failed")

        print("\n" + "=" * 60)
        print(f"Normalization complete!")
        print(f"  Successfully normalized: {success_count}")
        print(f"  Errors: {error_count}")

    def show_normalization_stats(self):
        """Display normalization statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM music_library WHERE normalized = 1")
        normalized_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM music_library")
        total_count = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(lufs_before), AVG(lufs_after) FROM music_library WHERE normalized = 1")
        result = cursor.fetchone()
        avg_before, avg_after = result if result[0] else (None, None)

        conn.close()

        print(f"\nNormalization Statistics:")
        print(f"  Normalized files: {normalized_count}/{total_count}")
        if avg_before and avg_after:
            print(f"  Average LUFS before: {avg_before:.1f}")
            print(f"  Average LUFS after: {avg_after:.1f}")

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Process music files and add to library")
    parser.add_argument("--music-dir", default="music",
                       help="Target music library directory")
    parser.add_argument("--db", default="music_history.db",
                       help="Database file path")

    # Normalization options
    parser.add_argument("--normalize", action="store_true",
                       help="Normalize all audio files to consistent LUFS level")
    parser.add_argument("--target-lufs", type=float, default=-14.0,
                       help="Target LUFS level for normalization (default: -14.0)")
    parser.add_argument("--force-normalize", action="store_true",
                       help="Re-normalize files that were already normalized")
    parser.add_argument("--normalize-stats", action="store_true",
                       help="Show normalization statistics only")

    args = parser.parse_args()

    processor = MusicProcessor(
        music_dir=args.music_dir,
        db_path=args.db
    )

    # Handle different modes
    if args.normalize_stats:
        processor.show_normalization_stats()
    elif args.normalize:
        processor.normalize_all_files(args.target_lufs, args.force_normalize)
        processor.show_normalization_stats()
    else:
        processor.process_all()
        # Show normalization stats after processing
        processor.show_normalization_stats()

if __name__ == "__main__":
    main()