#!/usr/bin/env python3
"""
Main Orchestrator - Runs the complete PersonalDJ pipeline
Coordinates all scripts to generate a complete playlist with DJ spots
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
import argparse
import subprocess

def run_step(script_name: str, description: str, extra_args=None) -> bool:
    """
    Run a pipeline step and handle errors
    """
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"Running: {script_name}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            [sys.executable, script_name] + (extra_args or []),
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}:")
        print(f"Exit code: {e.returncode}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def check_dependencies():
    """
    Check if required files and directories exist
    """
    required_dirs = ["music", "dj_spots", "playlists", "streaming"]
    for dir_name in required_dirs:
        Path(dir_name).mkdir(exist_ok=True)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  Warning: OPENAI_API_KEY not set.")
        print("   DJ scripts will use fallback content.")
        print("   Audio generation will be skipped.")
        print("   Set the environment variable to enable AI features.")
        print()

def run_pipeline(
    skip_audio: bool = False,
    voice: str = "alloy",
    style: str = "morning_radio",
    extra_instructions: str | None = None,
    start_time: str | None = None,
    start_date: str | None = None,
    dryrun: bool = False,
):
    """
    Run the complete PersonalDJ pipeline
    """
    print("\n" + "="*60)
    pipeline_mode = "🎵 PersonalDJ Pipeline Starting"
    if dryrun:
        pipeline_mode += " (DRY RUN MODE)"
    print(pipeline_mode)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if dryrun:
        print("💡 Dry run mode: Audio generation will be simulated")
    print("="*60)

    check_dependencies()

    # Prepare start time arguments for playlist selector
    playlist_args = []
    if start_time:
        playlist_args += ["--start-time", start_time]
    if start_date:
        playlist_args += ["--start-date", start_date]

    steps = [
        ("1_playlist_selector.py", "Selecting playlist genre/mood for today", playlist_args),
        ("2_music_curator.py", "Curating music based on preferences and history", None),
        ("3_dj_spot_planner.py", "Planning DJ spot placement and timing", None),
        ("4_dj_script_writer.py", "Writing creative DJ scripts", None),
    ]

    if not skip_audio:
        tts_args = [
            "--voice", voice,
            "--style", style,
        ]
        if extra_instructions:
            tts_args += ["--extra-instructions", extra_instructions]
        if dryrun:
            tts_args += ["--dryrun"]
        steps.append(("5_tts_generator.py", "Generating DJ audio with TTS" + (" (dry run)" if dryrun else ""), tts_args))

    steps.append(("6_playlist_assembler.py", "Assembling final M3U playlist", None))

    success = True
    for script, description, extra_args in steps:
        if not run_step(script, description, extra_args):
            success = False
            print(f"\n❌ Pipeline failed at: {script}")
            break

    if success:
        print("\n" + "="*60)
        print("✅ PersonalDJ Pipeline Complete!")
        print("="*60)

        # Try to read final data from dated directory or root
        final_data = None
        try:
            # First try to get playlist directory from config
            with open("playlist_config.json", 'r') as f:
                config = json.load(f)
                if "playlist_dir" in config:
                    playlist_dir = Path(config["playlist_dir"])
                    final_file = playlist_dir / "playlist_final.json"
                    if final_file.exists():
                        with open(final_file, 'r') as f:
                            final_data = json.load(f)
        except:
            pass

        # Fall back to root directory
        if not final_data:
            try:
                with open("playlist_final.json", 'r') as f:
                    final_data = json.load(f)
            except:
                pass

        if final_data:
            try:
                print(f"\n📊 Playlist Statistics:")
                print(f"   • Total songs: {final_data['total_songs']}")
                print(f"   • DJ spots: {final_data['total_dj_spots']}")
                print(f"   • Playlist file: {final_data['playlist_file']}")
                print(f"   • Streaming URL: {final_data['base_url']}/{final_data['streaming_file']}")

                print(f"\n🎧 To play your playlist:")
                print(f"   1. Start a local server: python -m http.server 8000")
                print(f"   2. Stream from: {final_data['base_url']}/{final_data['streaming_file']}")
                print(f"   3. Or use the M3U file: {final_data['playlist_file']}")

            except (KeyError, TypeError):
                print("\nPlaylist generated but summary data incomplete.")
        else:
            print("\nPlaylist generated but summary not available.")

    return success

def main():
    """
    Main entry point with CLI arguments
    """
    parser = argparse.ArgumentParser(
        description="Generate a PersonalDJ playlist with custom DJ segments"
    )
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="Skip TTS audio generation entirely"
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Simulate audio generation without making API calls (faster for debugging)"
    )
    parser.add_argument(
        "--voice",
        default="alloy",
        choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        help="TTS voice to use for DJ spots"
    )
    parser.add_argument(
        "--style",
        default="morning_radio",
        help="Global style preset for TTS (see style_presets.py)",
    )
    parser.add_argument(
        "--extra-instructions",
        default=None,
        help="Append extra guidance to the style instructions",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean intermediate files after completion"
    )
    parser.add_argument(
        "--start-time",
        default=None,
        help="When the playlist will start playing (HH:MM format, e.g. 08:00)"
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Date when playlist will start (YYYY-MM-DD format, defaults to today)"
    )

    args = parser.parse_args()

    success = run_pipeline(
        skip_audio=args.skip_audio,
        voice=args.voice,
        style=args.style,
        extra_instructions=args.extra_instructions,
        start_time=getattr(args, 'start_time'),
        start_date=getattr(args, 'start_date'),
        dryrun=args.dryrun,
    )

    if success and args.clean:
        print("\n🧹 Cleaning intermediate files...")
        # Clean up any root-level JSON files (backward compatibility)
        intermediate_files = [
            "playlist_config.json",
            "curated_playlist.json",
            "dj_spot_plan.json",
            "dj_scripts.json",
            "dj_audio.json"
        ]
        for file in intermediate_files:
            if Path(file).exists():
                Path(file).unlink()
                print(f"   Removed: {file}")

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
