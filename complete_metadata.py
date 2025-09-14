#!/usr/bin/env python3
"""
Complete Music Metadata - Enriches song metadata using multiple sources
"""

import os
import sqlite3
import requests
import json
import time
import re
from pathlib import Path
from typing import Dict, Optional, List
from mutagen import File
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TDRC, TPE2, TPOS, TRCK, TPUB, TBPM, TKEY, COMM
from mutagen.mp4 import MP4
from datetime import datetime
import hashlib
import subprocess

import musicbrainzngs

class MetadataCompleter:
    def __init__(self, db_path="music_history.db", music_dir="music"):
        self.db_path = db_path
        self.music_dir = Path(music_dir)
        self.updated_count = 0
        self.error_count = 0

        # Initialize MusicBrainz
        musicbrainzngs.set_useragent(
            "PersonalDJ",
            "1.0",
            "https://github.com/yourname/personaldj"
        )

        # API Keys (you'll need to set these)
        self.acoustid_api_key = os.environ.get('ACOUSTID_API_KEY', '')
        self.lastfm_api_key = os.environ.get('LASTFM_API_KEY', '')
        self.spotify_client_id = os.environ.get('SPOTIFY_CLIENT_ID', '')
        self.spotify_client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
        self.spotify_access_token = None

    def get_incomplete_songs(self, limit: Optional[int] = None) -> List[Dict]:
        """Get songs with incomplete metadata from database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT id, file_path, title, artist, album, genre, year, duration_seconds
            FROM music_library
            WHERE genre = 'Unknown'
               OR genre IS NULL
               OR year IS NULL
               OR album = 'Unknown Album'
               OR artist = 'Unknown Artist'
            ORDER BY id
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_spotify_token(self) -> Optional[str]:
        """Get Spotify access token using client credentials"""
        if not self.spotify_client_id or not self.spotify_client_secret:
            return None

        try:
            import base64

            auth_str = f"{self.spotify_client_id}:{self.spotify_client_secret}"
            auth_bytes = auth_str.encode("ascii")
            auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            response = requests.post(
                "https://accounts.spotify.com/api/token",
                headers=headers,
                data={"grant_type": "client_credentials"},
                timeout=10
            )

            if response.status_code == 200:
                self.spotify_access_token = response.json()["access_token"]
                return self.spotify_access_token
        except Exception as e:
            print(f"  Failed to get Spotify token: {e}")

        return None

    def search_spotify(self, title: str, artist: str) -> Optional[Dict]:
        """Search Spotify for track metadata"""
        if not self.spotify_access_token:
            self.spotify_access_token = self.get_spotify_token()

        if not self.spotify_access_token:
            return None

        try:
            # Clean up search query
            search_query = f"track:{title}"
            if artist and artist != "Unknown Artist":
                search_query += f" artist:{artist}"

            headers = {"Authorization": f"Bearer {self.spotify_access_token}"}
            params = {
                "q": search_query,
                "type": "track",
                "limit": 1
            }

            response = requests.get(
                "https://api.spotify.com/v1/search",
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("tracks", {}).get("items"):
                    track = data["tracks"]["items"][0]

                    # Extract genre from artist (Spotify doesn't provide genre per track)
                    artist_id = track["artists"][0]["id"] if track.get("artists") else None
                    genres = []

                    if artist_id:
                        artist_response = requests.get(
                            f"https://api.spotify.com/v1/artists/{artist_id}",
                            headers=headers,
                            timeout=10
                        )
                        if artist_response.status_code == 200:
                            artist_data = artist_response.json()
                            genres = artist_data.get("genres", [])

                    return {
                        "title": track.get("name"),
                        "artist": ", ".join([a["name"] for a in track.get("artists", [])]),
                        "album": track.get("album", {}).get("name"),
                        "year": track.get("album", {}).get("release_date", "")[:4] if track.get("album", {}).get("release_date") else None,
                        "genre": genres[0].title() if genres else None,
                        "popularity": track.get("popularity"),
                        "explicit": track.get("explicit", False),
                        "track_number": track.get("track_number"),
                        "disc_number": track.get("disc_number"),
                        "duration_ms": track.get("duration_ms")
                    }

        except Exception as e:
            print(f"  Spotify search error: {e}")

        return None

    def search_lastfm(self, title: str, artist: str) -> Optional[Dict]:
        """Search Last.fm for track metadata"""
        if not self.lastfm_api_key:
            return None

        try:
            params = {
                "method": "track.getInfo",
                "api_key": self.lastfm_api_key,
                "artist": artist,
                "track": title,
                "format": "json"
            }

            response = requests.get(
                "https://ws.audioscrobbler.com/2.0/",
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if "track" in data:
                    track = data["track"]

                    # Extract top tags as genres
                    tags = track.get("toptags", {}).get("tag", [])
                    genre = tags[0]["name"].title() if tags else None

                    return {
                        "title": track.get("name"),
                        "artist": track.get("artist", {}).get("name"),
                        "album": track.get("album", {}).get("title") if track.get("album") else None,
                        "genre": genre,
                        "playcount": track.get("playcount"),
                        "listeners": track.get("listeners")
                    }

        except Exception as e:
            print(f"  Last.fm search error: {e}")

        return None

    def search_lastfm_artist(self, artist: str) -> Optional[Dict]:
        """Search Last.fm for artist-level genre information when track has no genre"""
        if not self.lastfm_api_key:
            return None

        try:
            params = {
                "method": "artist.getInfo",
                "api_key": self.lastfm_api_key,
                "artist": artist,
                "format": "json"
            }

            response = requests.get(
                "https://ws.audioscrobbler.com/2.0/",
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if "artist" in data:
                    artist_data = data["artist"]

                    # Extract top tags as genres
                    tags = artist_data.get("tags", {}).get("tag", [])
                    genre = tags[0]["name"].title() if tags else None

                    return {
                        "genre": genre,
                        "artist": artist_data.get("name")
                    }

        except Exception as e:
            print(f"  Last.fm artist search error: {e}")

        return None

    def search_musicbrainz(self, title: str, artist: str) -> Optional[Dict]:
        """Search MusicBrainz for track metadata"""
        try:
            # Search for recordings
            result = musicbrainzngs.search_recordings(
                recording=title,
                artist=artist,
                limit=1
            )

            if result.get("recording-list"):
                recording = result["recording-list"][0]

                # Extract basic info
                metadata = {
                    "title": recording.get("title"),
                    "duration_ms": recording.get("length")
                }

                # Get artist info
                if recording.get("artist-credit"):
                    artists = []
                    for artist_credit in recording["artist-credit"]:
                        if isinstance(artist_credit, dict) and "artist" in artist_credit:
                            artists.append(artist_credit["artist"]["name"])
                    metadata["artist"] = ", ".join(artists)

                # Get release info (album, year)
                if recording.get("release-list"):
                    release = recording["release-list"][0]
                    metadata["album"] = release.get("title")

                    if release.get("date"):
                        metadata["year"] = release["date"][:4]

                    # Get more detailed release info
                    if release.get("id"):
                        try:
                            release_detail = musicbrainzngs.get_release_by_id(
                                release["id"],
                                includes=["labels", "recordings", "release-groups"]
                            )

                            if release_detail.get("release"):
                                rel = release_detail["release"]

                                # Get label
                                if rel.get("label-info-list"):
                                    label = rel["label-info-list"][0].get("label", {}).get("name")
                                    if label:
                                        metadata["label"] = label

                                # Get release group for genre/type
                                if rel.get("release-group"):
                                    metadata["release_type"] = rel["release-group"].get("type")

                        except Exception:
                            pass

                return metadata

        except Exception as e:
            print(f"  MusicBrainz search error: {e}")

        return None

    def generate_fingerprint(self, file_path: str) -> Optional[Dict]:
        """Generate audio fingerprint using fpcalc command"""
        try:
            # Run fpcalc to generate fingerprint
            result = subprocess.run([
                'fpcalc', '-json', str(file_path)
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                # Parse JSON output
                fingerprint_data = json.loads(result.stdout)
                return {
                    'fingerprint': fingerprint_data.get('fingerprint'),
                    'duration': fingerprint_data.get('duration')
                }
            else:
                print(f"    fpcalc failed: {result.stderr}")
                return None

        except FileNotFoundError:
            print(f"    fpcalc not found. Install Chromaprint tools.")
            return None
        except subprocess.TimeoutExpired:
            print(f"    fpcalc timeout")
            return None
        except Exception as e:
            print(f"    Fingerprint generation error: {e}")
            return None

    def lookup_acoustid(self, fingerprint: str, duration: int) -> Optional[Dict]:
        """Lookup track using AcoustID web service"""
        try:
            url = "https://api.acoustid.org/v2/lookup"
            params = {
                'client': self.acoustid_api_key,
                'meta': 'recordings+releasegroups+releases+compress',
                'duration': duration,
                'fingerprint': fingerprint,
                'format': 'json'
            }

            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()

                if data.get('status') == 'ok' and data.get('results'):
                    # Find the best match
                    best_result = None
                    best_score = 0

                    for result in data['results']:
                        score = result.get('score', 0)
                        if score > best_score and score > 0.5:  # Confidence threshold
                            best_result = result
                            best_score = score

                    if best_result and best_result.get('recordings'):
                        recording = best_result['recordings'][0]

                        # Extract metadata
                        metadata = {
                            'title': recording.get('title'),
                            'duration_ms': recording.get('length')
                        }

                        # Extract artist info
                        if recording.get('artists'):
                            artists = []
                            for artist in recording['artists']:
                                artists.append(artist.get('name', ''))
                            metadata['artist'] = ', '.join(filter(None, artists))

                        # Extract release info (album, year)
                        if recording.get('releases'):
                            release = recording['releases'][0]
                            metadata['album'] = release.get('title')

                            # Extract year from date
                            if release.get('date'):
                                date_str = release['date']
                                if len(date_str) >= 4:
                                    try:
                                        metadata['year'] = int(date_str[:4])
                                    except ValueError:
                                        pass

                        return metadata

            else:
                print(f"    AcoustID API error: {response.status_code}")

        except Exception as e:
            print(f"    AcoustID lookup error: {e}")

        return None

    def identify_with_acoustid(self, file_path: str) -> Optional[Dict]:
        """Use AcoustID to fingerprint and identify track"""
        if not self.acoustid_api_key:
            return None

        # Generate fingerprint
        fingerprint_data = self.generate_fingerprint(file_path)
        if not fingerprint_data:
            return None

        # Lookup track
        return self.lookup_acoustid(
            fingerprint_data['fingerprint'],
            fingerprint_data['duration']
        )

    def infer_metadata_from_path(self, file_path: str) -> Dict:
        """Try to infer metadata from file path structure"""
        path = Path(file_path)
        metadata = {}

        # Common patterns: Artist/Album/Track.mp3 or Artist - Album/Track.mp3
        parts = path.parts

        if len(parts) >= 3:
            # Possible artist folder
            possible_artist = parts[-3]
            if possible_artist != "music" and not possible_artist.startswith("."):
                metadata["artist"] = possible_artist.replace("_", " ").replace("-", " ")

            # Possible album folder
            possible_album = parts[-2]
            if not possible_album.startswith("."):
                # Check for "Artist - Album" pattern
                if " - " in possible_album:
                    artist_album = possible_album.split(" - ", 1)
                    if len(artist_album) == 2:
                        metadata["artist"] = artist_album[0]
                        metadata["album"] = artist_album[1]
                else:
                    metadata["album"] = possible_album.replace("_", " ")

        # Parse filename for track info
        filename = path.stem

        # Common patterns: "01 - Track Name", "01. Track Name", "Track Name"
        track_patterns = [
            r"^(\d+)[\s\-\.]+(.+)$",  # Track number prefix
            r"^(.+?)[\s\-]+(.+?)$",    # Artist - Title
        ]

        for pattern in track_patterns:
            match = re.match(pattern, filename)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    if groups[0].isdigit():
                        metadata["track_number"] = int(groups[0])
                        metadata["title"] = groups[1]
                    else:
                        # Might be Artist - Title
                        if not metadata.get("artist"):
                            metadata["artist"] = groups[0]
                        metadata["title"] = groups[1]
                break

        if not metadata.get("title"):
            metadata["title"] = filename.replace("_", " ")

        # Clean up metadata
        for key in ["title", "artist", "album"]:
            if key in metadata:
                # Remove common junk
                metadata[key] = re.sub(r"\[.*?\]", "", metadata[key])  # Remove [tags]
                metadata[key] = re.sub(r"\(.*?\)", "", metadata[key])  # Remove (tags)
                metadata[key] = metadata[key].strip()

        return metadata

    def merge_metadata(self, original: Dict, *sources: Dict) -> Dict:
        """Intelligently merge metadata from multiple sources"""
        merged = original.copy()

        # Priority fields (prefer non-Unknown values)
        for source in sources:
            if not source:
                continue

            for field in ["title", "artist", "album", "genre", "year"]:
                if source.get(field):
                    # Replace if original is Unknown or missing
                    if not merged.get(field) or "Unknown" in str(merged.get(field, "")):
                        merged[field] = source[field]
                    # For genre, prefer more specific
                    elif field == "genre" and merged.get(field) == "Unknown":
                        merged[field] = source[field]

        # Additional metadata
        for source in sources:
            if not source:
                continue

            # Add new fields that don't exist
            for field in ["track_number", "disc_number", "label", "explicit", "bpm", "key"]:
                if field in source and field not in merged:
                    merged[field] = source[field]

        # Clean up year field
        if merged.get("year"):
            year_str = str(merged["year"])
            if len(year_str) >= 4:
                try:
                    merged["year"] = int(year_str[:4])
                except ValueError:
                    pass

        return merged

    def update_file_tags(self, file_path: str, metadata: Dict) -> bool:
        """Update the actual file tags with new metadata"""
        try:
            audio_file = File(file_path)
            if audio_file is None:
                return False

            if isinstance(audio_file, MP4):
                # MP4/M4A tags
                if metadata.get("title"):
                    audio_file["\xa9nam"] = metadata["title"]
                if metadata.get("artist"):
                    audio_file["\xa9ART"] = metadata["artist"]
                if metadata.get("album"):
                    audio_file["\xa9alb"] = metadata["album"]
                if metadata.get("genre"):
                    audio_file["\xa9gen"] = metadata["genre"]
                if metadata.get("year"):
                    audio_file["\xa9day"] = str(metadata["year"])

            else:
                # ID3 tags (MP3, etc.)
                if not hasattr(audio_file, "tags") or audio_file.tags is None:
                    audio_file.add_tags()

                tags = audio_file.tags

                if metadata.get("title"):
                    tags["TIT2"] = TIT2(encoding=3, text=metadata["title"])
                if metadata.get("artist"):
                    tags["TPE1"] = TPE1(encoding=3, text=metadata["artist"])
                if metadata.get("album"):
                    tags["TALB"] = TALB(encoding=3, text=metadata["album"])
                if metadata.get("genre"):
                    tags["TCON"] = TCON(encoding=3, text=metadata["genre"])
                if metadata.get("year"):
                    tags["TDRC"] = TDRC(encoding=3, text=str(metadata["year"]))

            audio_file.save()
            return True

        except Exception as e:
            print(f"  Failed to update file tags: {e}")
            return False

    def update_database(self, song_id: int, metadata: Dict) -> bool:
        """Update database with new metadata"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build update query dynamically
            updates = []
            values = []

            for field in ["title", "artist", "album", "genre", "year"]:
                if field in metadata and metadata[field]:
                    updates.append(f"{field} = ?")
                    values.append(metadata[field])

            if metadata.get("explicit") is not None:
                updates.append("explicit = ?")
                values.append(metadata["explicit"])

            if not updates:
                return False

            values.append(song_id)
            query = f"UPDATE music_library SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(query, values)
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()

            return success

        except Exception as e:
            print(f"  Database update error: {e}")
            return False

    def process_song(self, song: Dict, update_files: bool = True) -> bool:
        """Process a single song to complete its metadata"""
        print(f"\nProcessing: {song['title']} by {song['artist']}")
        print(f"  File: {song['file_path']}")

        file_path = song['file_path']
        if not Path(file_path).exists():
            print(f"  File not found!")
            return False

        # Collect metadata from various sources
        metadata_sources = []

        # 1. Try acoustic fingerprinting first (most accurate)
        if self.acoustid_api_key:
            print("  Trying AcoustID fingerprinting...")
            acoustid_data = self.identify_with_acoustid(file_path)
            if acoustid_data:
                print(f"    Found: {acoustid_data.get('title')} by {acoustid_data.get('artist')}")
                metadata_sources.append(acoustid_data)

        # 2. Search online databases
        title = song['title'] if song['title'] else Path(file_path).stem
        artist = song['artist'] if song['artist'] != 'Unknown Artist' else ''

        # Spotify
        if self.spotify_client_id:
            print("  Searching Spotify...")
            spotify_data = self.search_spotify(title, artist)
            if spotify_data:
                print(f"    Found: {spotify_data.get('genre')} genre")
                metadata_sources.append(spotify_data)

        # Last.fm
        if self.lastfm_api_key:
            print("  Searching Last.fm...")
            lastfm_data = self.search_lastfm(title, artist)
            if lastfm_data and lastfm_data.get('genre'):
                print(f"    Found: {lastfm_data.get('genre')} genre")
                metadata_sources.append(lastfm_data)
            else:
                # If track search found no genre, try artist-level search
                if artist and artist != 'Unknown Artist':
                    print("  Trying Last.fm artist fallback...")
                    artist_data = self.search_lastfm_artist(artist)
                    if artist_data and artist_data.get('genre'):
                        print(f"    Found artist genre: {artist_data.get('genre')}")
                        metadata_sources.append(artist_data)

        # MusicBrainz
        print("  Searching MusicBrainz...")
        mb_data = self.search_musicbrainz(title, artist)
        if mb_data:
            print(f"    Found: {mb_data.get('album')} album")
            metadata_sources.append(mb_data)

        # 3. Infer from file path
        path_data = self.infer_metadata_from_path(file_path)
        if path_data:
            print(f"  Inferred from path: {path_data}")
            metadata_sources.append(path_data)

        # Merge all metadata
        merged_metadata = self.merge_metadata(song, *metadata_sources)

        # Check if we have improvements
        improvements = []
        for field in ["title", "artist", "album", "genre", "year"]:
            old_val = song.get(field)
            new_val = merged_metadata.get(field)

            if new_val and old_val != new_val:
                if not old_val or "Unknown" in str(old_val):
                    improvements.append(f"{field}: '{old_val}' → '{new_val}'")

        if not improvements:
            print("  No improvements found")
            return False

        print(f"  Improvements:")
        for imp in improvements:
            print(f"    {imp}")

        # Update file tags if requested
        if update_files:
            print("  Updating file tags...")
            if not self.update_file_tags(file_path, merged_metadata):
                print("    Failed to update file tags")

        # Update database
        print("  Updating database...")
        if self.update_database(song['id'], merged_metadata):
            print("  ✓ Successfully updated")
            self.updated_count += 1
            return True
        else:
            print("  ✗ Failed to update database")
            self.error_count += 1
            return False

    def complete_all(self, limit: Optional[int] = None, update_files: bool = True):
        """Process all songs with incomplete metadata"""
        incomplete_songs = self.get_incomplete_songs(limit)

        if not incomplete_songs:
            print("No songs with incomplete metadata found!")
            return

        total = len(incomplete_songs)
        print(f"Found {total} songs with incomplete metadata")
        print("=" * 60)

        for idx, song in enumerate(incomplete_songs, 1):
            print(f"\n[{idx}/{total}]", end="")
            self.process_song(song, update_files)

            # Rate limiting for APIs
            if idx < total:
                time.sleep(0.5)  # Be nice to free APIs

        print("\n" + "=" * 60)
        print("Metadata completion finished!")
        print(f"  Successfully updated: {self.updated_count}")
        print(f"  Errors: {self.error_count}")

        # Show updated statistics
        self.show_statistics()

    def show_statistics(self):
        """Show current metadata completeness statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN artist != 'Unknown Artist' THEN 1 END) as has_artist,
                COUNT(CASE WHEN album != 'Unknown Album' THEN 1 END) as has_album,
                COUNT(CASE WHEN genre != 'Unknown' AND genre IS NOT NULL THEN 1 END) as has_genre,
                COUNT(CASE WHEN year IS NOT NULL THEN 1 END) as has_year
            FROM music_library
        """)

        stats = cursor.fetchone()
        total = stats[0]

        print(f"\nMetadata Completeness:")
        print(f"  Total songs: {total}")
        print(f"  With artist: {stats[1]} ({stats[1]*100/total:.1f}%)")
        print(f"  With album: {stats[2]} ({stats[2]*100/total:.1f}%)")
        print(f"  With genre: {stats[3]} ({stats[3]*100/total:.1f}%)")
        print(f"  With year: {stats[4]} ({stats[4]*100/total:.1f}%)")

        # Show genre distribution
        cursor.execute("""
            SELECT genre, COUNT(*) as count
            FROM music_library
            WHERE genre != 'Unknown' AND genre IS NOT NULL
            GROUP BY genre
            ORDER BY count DESC
            LIMIT 10
        """)

        genres = cursor.fetchall()
        if genres:
            print(f"\nTop Genres:")
            for genre, count in genres:
                print(f"  {genre}: {count}")

        conn.close()

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Complete missing music metadata")
    parser.add_argument("--db", default="music_history.db", help="Database file path")
    parser.add_argument("--music-dir", default="music", help="Music library directory")
    parser.add_argument("--limit", type=int, help="Limit number of songs to process")
    parser.add_argument("--no-file-update", action="store_true",
                       help="Don't update file tags, only database")
    parser.add_argument("--stats-only", action="store_true",
                       help="Show statistics only")

    # API key options
    parser.add_argument("--acoustid-key", help="AcoustID API key")
    parser.add_argument("--lastfm-key", help="Last.fm API key")
    parser.add_argument("--spotify-id", help="Spotify client ID")
    parser.add_argument("--spotify-secret", help="Spotify client secret")

    args = parser.parse_args()

    # Set API keys from arguments if provided
    if args.acoustid_key:
        os.environ['ACOUSTID_API_KEY'] = args.acoustid_key
    if args.lastfm_key:
        os.environ['LASTFM_API_KEY'] = args.lastfm_key
    if args.spotify_id:
        os.environ['SPOTIFY_CLIENT_ID'] = args.spotify_id
    if args.spotify_secret:
        os.environ['SPOTIFY_CLIENT_SECRET'] = args.spotify_secret

    completer = MetadataCompleter(
        db_path=args.db,
        music_dir=args.music_dir
    )

    if args.stats_only:
        completer.show_statistics()
    else:
        # Show available APIs
        print("Available metadata sources:")
        if completer.acoustid_api_key:
            print("  ✓ AcoustID (fingerprinting)")
        else:
            print("  ✗ AcoustID (set ACOUSTID_API_KEY, requires fpcalc tool)")

        if completer.spotify_client_id:
            print("  ✓ Spotify")
        else:
            print("  ✗ Spotify (set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)")

        if completer.lastfm_api_key:
            print("  ✓ Last.fm")
        else:
            print("  ✗ Last.fm (set LASTFM_API_KEY)")

        print("  ✓ MusicBrainz (no API key needed)")
        print("  ✓ Path inference\n")

        completer.complete_all(
            limit=args.limit,
            update_files=not args.no_file_update
        )

if __name__ == "__main__":
    main()