# PersonalDJ

PersonalDJ builds daily, fully‑controlled music playlists with short, natural DJ voice spots mixed between songs. It curates songs from your local library, plans when to speak, writes scripts, generates TTS audio, and outputs M3U playlists you can stream anywhere.

## What’s Inside
- Scripts are numbered as a pipeline you can run end‑to‑end or step‑by‑step:
  - `1_playlist_selector.py` — picks a genre/mood and creates a dated output folder.
  - `2_music_curator.py` — pulls songs from a local SQLite library, avoiding recent repeats.
  - `3_dj_spot_planner.py` — decides where DJ spots go (default every ~20 minutes).
  - `4_dj_script_writer.py` — writes DJ copy (OpenAI if available, otherwise fallback text).
  - `5_tts_generator.py` — generates MP3s for DJ spots using OpenAI TTS.
  - `6_playlist_assembler.py` — assembles final `.m3u` and a streaming list.
- Utility scripts:
  - `process_music.py` — scans files, extracts metadata (Mutagen), populates `music_history.db`.
  - `complete_metadata.py` — enriches incomplete song metadata using multiple online sources.
  - `list_genres.py` — prints available genres and counts from the DB.
- Data and output:
  - `music/` — your music library directory containing all audio files.
  - `playlists/YYYY-MM-DD/` — dated outputs (JSON artifacts + final M3U).
  - `dj_spots/YYYY-MM-DD/` — generated DJ MP3s.
  - `streaming/stream.m3u` — streaming‑friendly list pointing to local files.

## How It Works (Pipeline)
1) Playlist selection
   - `1_playlist_selector.py` picks a genre + mood based on day/time (and a simple weather stub) and writes `playlists/<date>/playlist_config.json`.

2) Music curation
   - `2_music_curator.py` queries `music_history.db` for songs matching the config, avoids recent plays, and writes `curated_playlist.json`.

3) DJ spot planning
   - `3_dj_spot_planner.py` places short DJ spots roughly every 20 minutes, preserving “after_song_index” so we can insert audio in the right places.

4) Script writing
   - `4_dj_script_writer.py` generates friendly, on‑air style scripts per spot.
   - If `OPENAI_API_KEY` is set, uses OpenAI; otherwise, uses built‑in fallback copy.

5) TTS generation
   - `5_tts_generator.py` converts scripts to MP3s (OpenAI `gpt-4o-mini-tts`). Files go to `dj_spots/<date>/`.
   - Styling: voice, tone, dialect, and delivery features are controlled via presets in `style_presets.py`.
   - CLI flags: `--voice shimmer` and `--style morning_radio` (default). Add `--extra-instructions` to append guidance.
   - Voices available: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`.

6) Assemble playlists
   - `6_playlist_assembler.py` weaves songs and DJ MP3s into `.m3u`, also writes `streaming/stream.m3u` for easy playback via a simple HTTP server.

All artifacts for a run land under `playlists/<date>/`: config, curated songs, spot plan, scripts, audio metadata, playlist summary, plus a `latest_<date>.m3u` symlink.

## Setup
- Requirements
  - Python 3.10+
  - Packages: `openai`, `python-dotenv`, `requests`, `icalendar`, `python-dateutil`, `ffmpeg-python`, `mutagen`, `musicbrainzngs`
  - Optional: `fpcalc` tool for audio fingerprinting (part of Chromaprint)
  - SQLite (standard with Python)

- Install
  - `pip install -r requirements.txt`
  - For audio fingerprinting (optional): Install Chromaprint tools
    - macOS: `brew install chromaprint`
    - Ubuntu/Debian: `sudo apt install libchromaprint-tools`
    - Windows: Download from https://acoustid.org/chromaprint

- OpenAI (optional but recommended)
  - Export your key: `export OPENAI_API_KEY=sk-...`
  - Without a key, scripts are still generated (fallback text), and TTS can be skipped.

## Prepare Your Library
1) Put your music files in the `music/` directory (any of: mp3, m4a/mp4/aac, flac, wav, ogg).
2) Process and index into the library/DB:
   - `python process_music.py`
   - Options:
     - `--music-dir` path to scan (default `music`)
     - `--db` path to SQLite DB (default `music_history.db`)
3) See available genres: `./list_genres.py`

Notes
- Files are processed from their current locations and indexed into the database without moving them.
- The DB stores key metadata (title, artist, album, genre, duration, bitrate, year) and play history.
- Duplicate detection is performed using file hashes to avoid processing the same file twice.

## Complete Missing Metadata
After processing your music library, you may find some songs have incomplete metadata (missing genres, years, etc.). Use the metadata completion script to enrich this information from multiple online sources:

### Basic Usage
```bash
# Show current metadata completeness statistics
python complete_metadata.py --stats-only

# Complete metadata for all songs (uses MusicBrainz and path inference)
python complete_metadata.py

# Process only a limited number of songs (good for testing)
python complete_metadata.py --limit 10

# Update database only (don't modify file tags)
python complete_metadata.py --no-file-update
```

### With API Keys (Better Results)
For more accurate metadata completion, set up free API keys:

```bash
# Set environment variables for better results
export ACOUSTID_API_KEY="your_key"        # Audio fingerprinting
export LASTFM_API_KEY="your_key"          # Genre tags and community data
export SPOTIFY_CLIENT_ID="your_id"        # Detailed track info
export SPOTIFY_CLIENT_SECRET="your_secret"

python complete_metadata.py
```

### Available Sources
- **MusicBrainz** (free, no key needed) - Comprehensive music database
- **Path inference** (free) - Extracts metadata from file/folder names
- **AcoustID** (free API key + fpcalc tool) - Audio fingerprinting for accurate identification
- **Spotify** (free API key) - Genre, popularity, and detailed track info
- **Last.fm** (free API key) - Community tags and listening data

### Getting API Keys
- **AcoustID**: https://acoustid.org/new-application
- **Last.fm**: https://www.last.fm/api/account/create
- **Spotify**: https://developer.spotify.com/dashboard/applications

### Installing AcoustID Fingerprinting (Optional)
For the most accurate track identification, install the Chromaprint tools:

- **macOS**: `brew install chromaprint`
- **Ubuntu/Debian**: `sudo apt install libchromaprint-tools`
- **Windows**: Download from https://acoustid.org/chromaprint

This provides the `fpcalc` command-line tool needed for audio fingerprinting.

### Features
- **Smart metadata merging** from multiple sources
- **Preserves existing good data** while replacing "Unknown" values
- **Updates both database and file tags**
- **Rate limiting** to respect free API quotas
- **Progress tracking** with detailed output
- **Direct API calls** - no Python library dependencies for fingerprinting

The script automatically identifies songs with missing genres, unknown artists/albums, or missing years and attempts to complete this information using the available sources.

## Audio Normalization (LUFS)
PersonalDJ includes professional audio normalization to ensure consistent volume levels across your entire music library using the EBU R128 loudness standard (LUFS).

### Normalize Your Library
After processing files into your library, normalize them for consistent playback volume:

- **Normalize all files to -14 LUFS** (industry standard, same as Spotify/YouTube):
  ```bash
  python process_music.py --normalize
  ```

- **Use a different target LUFS** (e.g., -16 for quieter, -12 for louder):
  ```bash
  python process_music.py --normalize --target-lufs -16.0
  ```

- **Re-normalize already processed files** (force update):
  ```bash
  python process_music.py --normalize --force-normalize
  ```

- **Check normalization status**:
  ```bash
  python process_music.py --normalize-stats
  ```

### Features
- **Two-pass LUFS normalization** using FFmpeg's `loudnorm` filter for optimal quality
- **Automatic backup creation** with `_original` suffix before modifying files
- **Smart processing** - skips files already within 0.5 LUFS of target
- **Database tracking** of normalization status with before/after LUFS values
- **No quality loss** - prevents clipping and distortion while normalizing

### Requirements
- FFmpeg must be installed on your system (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Ubuntu)
- The `ffmpeg-python` package is included in requirements.txt

## Run The Whole Pipeline
Use the orchestrator to run all steps and produce playlists:

- Basic run
  - `python generate_playlist.py`

- Skip TTS (faster, text‑only)
  - `python generate_playlist.py --skip-audio`

- Choose voice
  - `python generate_playlist.py --voice shimmer`

- Choose style preset (voice/tone/dialect/features)
  - `python generate_playlist.py --style morning_radio`
  - Optional: `--extra-instructions "Keep transitions tight; no long pauses."`

- Clean intermediate JSON in project root (artifacts remain in the dated folder)
  - `python generate_playlist.py --clean`

On success you’ll see a summary with counts and where to find the final files. Everything is written under `playlists/<date>/`.

## Play The Playlist
- Start a simple local server from the project root:
  - `python -m http.server 8000`
- Open the streaming M3U in your player:
  - `streaming/stream.m3u`
- Or use the dated playlist M3U:
  - `playlists/<date>/playlist_*.m3u` (there’s also `latest_<date>.m3u` symlink)

## Customization
- Spot frequency
  - Default is every ~20 minutes in `3_dj_spot_planner.py` (`minutes_between_spots=20`). Adjust if you want more/less talk.
- Curation preferences
  - `1_playlist_selector.py` sets energy and filters; `2_music_curator.py` respects `avoid_explicit`, `prefer_instrumental`, and length bounds.
- Base URL for streaming
  - `6_playlist_assembler.py` defaults to `http://localhost:8000`. Pass `--base-url` if serving elsewhere.

## Troubleshooting
- “No OpenAI API key found”
  - Scripts fall back to text; pass `--skip-audio` to avoid TTS. Set `OPENAI_API_KEY` to enable AI + audio.
- “No music files found” / empty playlists
  - Ensure you ran `process_music.py` and your DB has songs. Check `music/` contains playable files with readable metadata.
- “Genre not found; using Other/mixed”
  - Use `./list_genres.py` to see valid genre names present in your DB.
- Mutagen not installed
  - `pip install mutagen` (used only by `process_music.py`).

## Reference
- Arylic HTTP API (for future device control): http://developer.arylic.com/httpapi/#http-api
