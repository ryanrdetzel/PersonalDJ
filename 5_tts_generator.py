#!/usr/bin/env python3
"""
TTS Generator - Converts DJ scripts to MP3 files using OpenAI TTS
Saves audio files organized by date
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from openai import OpenAI
from style_presets import get_style, build_instructions, list_styles

# Import DJ personality functions (define them here too for independence)
def load_dj_personalities():
    """Load DJ personality configuration"""
    try:
        with open('dj_personalities.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: dj_personalities.json not found, using default personality")
        return None

def get_dj_personality_for_time(hour: int):
    """Get the appropriate DJ personality for a given hour"""
    personalities = load_dj_personalities()
    if not personalities:
        return None

    # Find which time slot this hour belongs to
    for slot_name, slot_data in personalities["time_slots"].items():
        if hour in slot_data["hours"]:
            return slot_data["personality"]

    # Fallback to default
    return personalities.get("fallback_personality")


class TTSGenerator:
    def __init__(
        self,
        api_key: str = None,
        voice: str = "shimmer",
        model: str = "gpt-4o-mini-tts",
        speed: float = 1.08,
        style_name: str = "morning_radio",
        extra_instructions: str = None,
        dryrun: bool = False,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.voice = voice
        self.model = model
        self.speed = speed
        self.style_name = style_name
        self.style = None
        self.extra_instructions = extra_instructions
        self.output_dir = Path("dj_spots")
        self.dryrun = dryrun

        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            print("Warning: No OpenAI API key found. Cannot generate audio.")

        self.setup_directories()
        # Load style preset if available
        try:
            self.style = get_style(self.style_name)
        except Exception:
            self.style = None

    def setup_directories(self):
        """Create directory structure for DJ spots"""
        today = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = self.output_dir / today
        self.today_dir.mkdir(parents=True, exist_ok=True)

    def generate_audio(self, script: Dict) -> str:
        """
        Generate MP3 audio from script text
        """
        if self.dryrun:
            return self._simulate_audio_generation(script)

        if not self.client:
            print(
                f"Skipping audio generation for spot {script['spot_number']} - No API key"
            )
            return None

        spot_number = script["spot_number"]
        script_text = script["script"]
        spot_type = script.get("type")
        spot_tone = script.get("tone")
        approximate_time = script.get("approximate_time", "")

        # Determine voice based on DJ personality for this time
        voice_to_use = self.voice  # Default fallback
        try:
            if approximate_time and ":" in approximate_time:
                hour = int(approximate_time.split(":")[0])
                dj_personality = get_dj_personality_for_time(hour)
                if dj_personality and "voice" in dj_personality:
                    voice_to_use = dj_personality["voice"]
                    print(f"Using {dj_personality['name']}'s voice: {voice_to_use}")
        except Exception as e:
            print(f"Could not determine personality voice, using default: {e}")

        filename = f"dj_spot_{spot_number:03d}_{spot_type}.mp3"
        file_path = self.today_dir / filename

        # Build style-driven instructions (voice, tone, dialect, features)
        instructions = None
        if self.style is not None:
            instructions = build_instructions(
                self.style,
                spot_type=spot_type,
                spot_tone=spot_tone,
                extra_notes=self.extra_instructions,
            )

        # Use classic speech API with gpt-4o-mini-tts
        try:
            response = self.client.audio.speech.create(
                model=self.model,
                voice=voice_to_use,
                input=script_text,
                instructions=instructions,
                speed=self.speed,
            )

            response.stream_to_file(str(file_path))
            print(f"Generated audio: {filename}")

            return str(file_path)

        except Exception as e:
            print(f"Error generating audio for spot {spot_number}: {e}")
            return None

    def _simulate_audio_generation(self, script: Dict) -> str:
        """
        Simulate audio generation for dryrun mode
        """
        spot_number = script["spot_number"]
        spot_type = script.get("type")
        approximate_time = script.get("approximate_time", "")
        script_text = script["script"]

        # Determine voice based on DJ personality for this time
        voice_to_use = self.voice  # Default fallback
        personality_name = "Default"
        try:
            if approximate_time and ":" in approximate_time:
                hour = int(approximate_time.split(":")[0])
                dj_personality = get_dj_personality_for_time(hour)
                if dj_personality and "voice" in dj_personality:
                    voice_to_use = dj_personality["voice"]
                    personality_name = dj_personality["name"]
        except Exception:
            pass

        filename = f"dj_spot_{spot_number:03d}_{spot_type}.mp3"
        file_path = self.today_dir / filename

        # Simulate the file creation (just create empty file for dryrun)
        file_path.touch()

        print(f"[DRYRUN] Would generate audio: {filename}")
        print(f"         Voice: {voice_to_use} ({personality_name})")
        print(f"         Script: {script_text[:60]}{'...' if len(script_text) > 60 else ''}")

        return str(file_path)

    def generate_all_audio(self, scripts_data: Dict) -> List[Dict]:
        """
        Generate audio for all DJ scripts
        """
        audio_files = []

        cnt = 0
        max = 2
        for script in scripts_data["scripts"]:
            audio_path = self.generate_audio(script)

            audio_info = {
                "spot_number": script["spot_number"],
                "type": script["type"],
                "approximate_time": script["approximate_time"],
                "script": script["script"],
                "audio_file": audio_path,
                "created_at": datetime.now().isoformat(),
            }

            audio_files.append(audio_info)

            time.sleep(0.5)
            cnt += 1
            # if cnt >= max:
            #     return audio_files

        return audio_files

    def get_voice_options(self) -> List[str]:
        """
        Return available TTS voices
        """
        return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

    def create_silence_file(self, duration_seconds: float = 1.0) -> str:
        """
        Create a silent MP3 file for spacing
        This is a placeholder - would need actual audio library
        """
        filename = f"silence_{int(duration_seconds * 1000)}ms.mp3"
        file_path = self.output_dir / filename

        print(f"Would create silence file: {filename}")
        return str(file_path)


def generate_tts_audio(
    scripts_file: str = "dj_scripts.json",
    voice: str = "alloy",
    model: str = "gpt-4o-mini-tts",
    speed: float = 1.08,
    style_name: str = "morning_radio",
    extra_instructions: str = None,
    dryrun: bool = False,
) -> Dict:
    """
    Main function to generate TTS audio from scripts
    """
    # Try to read from dated directory first
    playlist_dir = None
    try:
        # Check if we have a config with playlist_dir
        with open("playlist_config.json", "r") as f:
            config = json.load(f)
            if "playlist_dir" in config:
                playlist_dir = Path(config["playlist_dir"])
                scripts_file = playlist_dir / "dj_scripts.json"
    except:
        pass

    with open(scripts_file, "r") as f:
        scripts_data = json.load(f)

    generator = TTSGenerator(
        voice=voice,
        model=model,
        speed=speed,
        style_name=style_name,
        extra_instructions=extra_instructions,
        dryrun=dryrun,
    )
    audio_files = generator.generate_all_audio(scripts_data)

    output = {
        "total_audio_files": len(audio_files),
        "audio_files": audio_files,
        "output_directory": str(generator.today_dir),
        "voice_used": voice,
        "model_used": model,
        "speed_used": speed,
        "created_at": datetime.now().isoformat(),
        "playlist_date": datetime.now().strftime("%Y-%m-%d"),
    }

    # Add playlist_dir if we have it
    if playlist_dir:
        output["playlist_dir"] = str(playlist_dir)

    return output


def main():
    """
    Read scripts and generate audio files
    """
    import argparse

    parser = argparse.ArgumentParser(description="Generate TTS audio for DJ spots")
    parser.add_argument(
        "--voice",
        default="alloy",
        choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        help="TTS voice to use",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini-tts",
        help="TTS model to use (default: gpt-4o-mini-tts)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.08,
        help="Playback speed multiplier (e.g., 1.0 normal, 1.08 brighter)",
    )
    parser.add_argument(
        "--style",
        default="morning_radio",
        choices=list_styles(),
        help="Named style preset for voice/tone/dialect/features",
    )
    parser.add_argument(
        "--extra-instructions",
        default=None,
        help="Optional extra guidance to append to the style instructions",
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Simulate audio generation without making API calls (for debugging)",
    )
    args = parser.parse_args()

    audio_data = generate_tts_audio(
        voice=args.voice,
        model=args.model,
        speed=args.speed,
        style_name=args.style,
        extra_instructions=args.extra_instructions,
        dryrun=args.dryrun,
    )

    # Get playlist directory from audio data or config
    if "playlist_dir" in audio_data:
        playlist_dir = Path(audio_data["playlist_dir"])
    else:
        try:
            with open("playlist_config.json", "r") as f:
                config = json.load(f)
                if "playlist_dir" in config:
                    playlist_dir = Path(config["playlist_dir"])
                else:
                    playlist_dir = Path(".")
        except:
            playlist_dir = Path(".")

    # Save to dated directory
    output_file = playlist_dir / "dj_audio.json"
    with open(output_file, "w") as f:
        json.dump(audio_data, f, indent=2)

    dryrun_prefix = "[DRYRUN] " if args.dryrun else ""
    print(f"\n{dryrun_prefix}Generated {audio_data['total_audio_files']} audio files")
    print(f"{dryrun_prefix}Audio saved to: {audio_data['output_directory']}")
    print(f"Voice used: {audio_data['voice_used']}")
    print(f"Model used: {audio_data.get('model_used')}")
    print(f"Speed used: {audio_data.get('speed_used')}")
    print(f"Metadata saved to: {output_file}")
    if args.dryrun:
        print("\\n💡 This was a dry run - no actual API calls were made.")

    return audio_data


if __name__ == "__main__":
    main()
