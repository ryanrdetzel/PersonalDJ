#!/usr/bin/env python3
"""
Playlist Assembler - Combines music tracks and DJ spots into M3U playlist
Creates the final playlist file for streaming
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import urllib.parse

class PlaylistAssembler:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("PLAYLIST_BASE_URL", "http://localhost:8000")
        self.output_dir = Path("playlists")
        self.output_dir.mkdir(exist_ok=True)

    def create_m3u_entry(self, file_path: str, title: str = None,
                         duration: int = -1) -> str:
        """
        Create M3U playlist entry
        """
        if title is None:
            title = Path(file_path).stem

        url = self.make_url(file_path)

        entry = f"#EXTINF:{duration},{title}\n{url}"
        return entry

    def make_url(self, file_path: str) -> str:
        """
        Convert local file path to streaming URL
        """
        if file_path and (file_path.startswith("http://") or file_path.startswith("https://")):
            return file_path

        path = Path(file_path)
        relative_path = path.as_posix()

        encoded_path = urllib.parse.quote(relative_path)
        return f"{self.base_url}/{encoded_path}"

    def assemble_playlist(self, music_data: Dict, audio_data: Dict,
                         spot_plan: Dict) -> List[str]:
        """
        Assemble the complete playlist with music and DJ spots
        """
        playlist_entries = []
        playlist_entries.append("#EXTM3U")
        playlist_entries.append(f"#PLAYLIST:PersonalDJ - {datetime.now().strftime('%Y-%m-%d')}")

        songs = music_data.get("songs", [])
        audio_files = audio_data.get("audio_files", [])
        spots = spot_plan.get("spots", [])

        audio_by_spot_number = {
            audio["spot_number"]: audio
            for audio in audio_files
        }

        spot_by_index = {}
        for spot in spots:
            after_index = spot.get("after_song_index", 0)
            spot_by_index[after_index] = spot["spot_number"]

        for i, song in enumerate(songs):
            title = song.get("title", f"Track {i+1}")
            artist = song.get("artist", "Unknown Artist")
            duration = song.get("duration_seconds", -1)
            file_path = song.get("file_path", "")

            full_title = f"{artist} - {title}"
            entry = self.create_m3u_entry(file_path, full_title, duration)
            playlist_entries.append(entry)

            if i + 1 in spot_by_index:
                spot_number = spot_by_index[i + 1]
                if spot_number in audio_by_spot_number:
                    audio = audio_by_spot_number[spot_number]
                    if audio.get("audio_file"):
                        dj_title = f"DJ Spot - {audio['type']}"
                        dj_entry = self.create_m3u_entry(
                            audio["audio_file"],
                            dj_title,
                            30
                        )
                        playlist_entries.append(dj_entry)

        return playlist_entries

    def save_playlist(self, playlist_entries: List[str], output_dir: Path = None) -> str:
        """
        Save playlist to file
        """
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Use provided output_dir or default
        if output_dir:
            output_path = output_dir
        else:
            output_path = self.output_dir

        filename = f"playlist_{timestamp}.m3u"
        file_path = output_path / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(playlist_entries))

        latest_link = output_path / f"latest_{today}.m3u"
        if latest_link.exists():
            latest_link.unlink()
        try:
            latest_link.symlink_to(file_path.name)
        except:
            # Symlinks might not work on all systems
            pass

        return str(file_path)

    def create_streaming_playlist(self, playlist_entries: List[str]) -> str:
        """
        Create a streaming-ready version of the playlist
        """
        streaming_dir = Path("streaming")
        streaming_dir.mkdir(exist_ok=True)

        filename = "stream.m3u"
        file_path = streaming_dir / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(playlist_entries))

        return str(file_path)

def assemble_final_playlist(music_file: str = "curated_playlist.json",
                          audio_file: str = "dj_audio.json",
                          spot_plan_file: str = "dj_spot_plan.json",
                          base_url: str = None) -> Dict:
    """
    Main function to assemble the final playlist
    """
    # Try to read from dated directory first
    playlist_dir = None
    try:
        # Check if we have a config with playlist_dir
        with open("playlist_config.json", 'r') as f:
            config = json.load(f)
            if "playlist_dir" in config:
                playlist_dir = Path(config["playlist_dir"])
                music_file = playlist_dir / "curated_playlist.json"
                audio_file = playlist_dir / "dj_audio.json"
                spot_plan_file = playlist_dir / "dj_spot_plan.json"
    except:
        pass

    with open(music_file, 'r') as f:
        music_data = json.load(f)

    with open(audio_file, 'r') as f:
        audio_data = json.load(f)

    with open(spot_plan_file, 'r') as f:
        spot_plan = json.load(f)

    assembler = PlaylistAssembler(base_url=base_url)

    playlist_entries = assembler.assemble_playlist(
        music_data, audio_data, spot_plan
    )

    # Save to dated directory if available
    if playlist_dir:
        playlist_file = assembler.save_playlist(playlist_entries, output_dir=playlist_dir)
    else:
        playlist_file = assembler.save_playlist(playlist_entries)

    streaming_file = assembler.create_streaming_playlist(playlist_entries)

    total_songs = len(music_data.get("songs", []))
    total_dj_spots = len([e for e in playlist_entries if "DJ Spot" in e])

    output = {
        "playlist_file": playlist_file,
        "streaming_file": streaming_file,
        "total_entries": len(playlist_entries) - 2,
        "total_songs": total_songs,
        "total_dj_spots": total_dj_spots,
        "created_at": datetime.now().isoformat(),
        "playlist_date": datetime.now().strftime("%Y-%m-%d"),
        "base_url": base_url
    }

    return output

def main():
    """
    Assemble and save the final playlist
    """
    import argparse
    parser = argparse.ArgumentParser(description="Assemble final M3U playlist")
    parser.add_argument("--base-url", default=os.getenv("PLAYLIST_BASE_URL", "http://localhost:8000"),
                       help="Base URL for streaming files (defaults to PLAYLIST_BASE_URL env var)")
    args = parser.parse_args()

    playlist_data = assemble_final_playlist(base_url=args.base_url)

    # Get playlist directory from config
    playlist_dir = None
    try:
        with open("playlist_config.json", 'r') as f:
            config = json.load(f)
            if "playlist_dir" in config:
                playlist_dir = Path(config["playlist_dir"])
    except:
        pass

    # Save final summary to dated directory if available
    if playlist_dir:
        output_file = playlist_dir / "playlist_final.json"
    else:
        output_file = Path("playlist_final.json")

    with open(output_file, "w") as f:
        json.dump(playlist_data, f, indent=2)

    print(f"\nPlaylist assembled successfully!")
    print(f"Total songs: {playlist_data['total_songs']}")
    print(f"Total DJ spots: {playlist_data['total_dj_spots']}")
    print(f"Playlist file: {playlist_data['playlist_file']}")
    print(f"Streaming file: {playlist_data['streaming_file']}")

    return playlist_data

if __name__ == "__main__":
    main()