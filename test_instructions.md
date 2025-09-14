# Dynamic Playlist Test Instructions

## Quick Start

1. **Start the test server:**
   ```bash
   python test_server.py
   ```

2. **Generate a playlist:**
   ```
   http://localhost:5000/playlist/20250913
   ```
   This creates an M3U with 200 fake MP3 filenames.

3. **Test dynamic serving:**
   ```
   http://localhost:5000/music/20250913-1.mp3
   ```
   Server will either serve a mapped file or pick random from catalog.

## Test Workflow

### Step 1: Generate Playlist
```bash
curl "http://localhost:5000/playlist/20250913" > test-playlist.m3u
```

### Step 2: Load in Media Player
- Open `test-playlist.m3u` in VLC, iTunes, or any M3U player
- Player will start requesting tracks: `/music/20250913-1.mp3`, etc.

### Step 3: Monitor Dynamic Behavior
- Check `/admin/mappings` to see database entries being created
- Each new filename gets mapped to a random real file
- Subsequent requests for same filename serve the same mapped file

## API Examples

### Get playlist with custom count:
```
GET /playlist/20250913?count=50&base_url=http://mydomain.com
```

### Check what file would be served:
```
GET /info/20250913-42.mp3
```

### View all current mappings:
```
GET /admin/mappings
```

### Manually add a mapping:
```bash
curl -X POST http://localhost:5000/admin/add_mapping \
  -H "Content-Type: application/json" \
  -d '{
    "fake_filename": "20250913-1.mp3",
    "real_file_path": "/path/to/my/song.mp3",
    "title": "My Favorite Song",
    "artist": "Best Artist"
  }'
```

## Expected Behavior

1. **First request** for `20250913-1.mp3` → Server picks random real file
2. **Database mapping created** → `20250913-1.mp3` now always serves that same file
3. **Consistent playback** → Same fake filename always returns same real file
4. **Infinite scalability** → Can handle `20250913-999.mp3` with random fallbacks

## Database Structure

The test server creates `test_playlist.db` with mappings:
- `fake_filename` → Real file path
- Metadata: title, artist, duration, play count
- Timestamp tracking for analytics

This proves your dynamic playlist concept works perfectly!