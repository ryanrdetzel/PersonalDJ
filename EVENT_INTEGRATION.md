# Event Integration for PersonalDJ 🎉

Your PersonalDJ system now supports event integration using iCal feeds! The DJ will mention relevant events from your calendars at appropriate times.

## Quick Setup

### 1. Install Dependencies
```bash
pip install icalendar python-dateutil
```

### 2. Configure iCal URLs
Set your iCal URLs as an environment variable:

```bash
# Single calendar
export ICAL_URLS="https://calendar.google.com/calendar/ical/your-calendar-id/public/basic.ics"

# Multiple calendars (comma-separated)
export ICAL_URLS="https://calendar.google.com/calendar/ical/cal1/public/basic.ics,https://calendar.google.com/calendar/ical/cal2/public/basic.ics"
```

### 3. Run Your Playlist
```bash
python generate_playlist.py
```

That's it! The DJ will now mention relevant events from your calendars.

## Getting iCal URLs

### Google Calendar
1. Open Google Calendar
2. Click the three dots next to your calendar name
3. Select "Settings and sharing"
4. Scroll to "Integrate calendar"
5. Copy the "Public URL to this calendar" (the .ics link)

### Outlook Calendar
1. Go to Outlook.com
2. Select your calendar
3. Click "Share" → "Publish calendar"
4. Copy the ICS link

### Apple Calendar
1. Open Calendar app
2. Right-click your calendar
3. Select "Share Calendar"
4. Choose "Public Calendar" and copy the link

## How It Works

### Event Types the DJ Will Mention
- **Happening Now**: Events currently in progress
- **Today**: All-day or timed events today
- **Tonight**: Events from 5 PM today to 2 AM tomorrow
- **Tomorrow**: Events happening tomorrow
- **This Week**: Events in the next 7 days

### When Events Are Mentioned
- **Morning (7-9 AM)**: Today's events, tonight's events
- **Afternoon (3-4 PM)**: Tonight's events, tomorrow's events, event mentions
- **Evening (6 PM)**: Tonight's events
- **Top of Hour**: 30% chance of event mention

### DJ Spot Types Created
- `event_mention`: General event references
- `today_events`: Focus on today's schedule
- `tonight_events`: Evening event previews
- `tonight_preview`: Looking ahead to evening plans

## Examples

With events in your calendar, the DJ might say:

> "Good morning! Just after eight, rolling with bright beats. Don't forget about tonight's concert at the venue starting at 8 PM. Take a breath, smile—let's cruise into your day."

> "Quick evening check-in! Hope you're ready for tonight's dinner with friends at 7. Same here, good vibes. Stay with me—more music right now."

## Fallback Behavior

If no events are found or the service is unavailable, the DJ will use generic event-related content:

> "Hope you've got something fun planned for this Saturday! Whether you're out and about or staying in, you've got the perfect soundtrack right here."

## Configuration Options

The system automatically configures reasonable defaults:

- **Event mention frequency**: Moderate (not too overwhelming)
- **Include all-day events**: Yes
- **Max events per mention**: 3
- **Cache duration**: 60 minutes (reduces API calls)

## Privacy & Caching

- Events are cached locally for 60 minutes to reduce network calls
- Only event titles, times, and locations are used
- No personal data is stored permanently
- Cache files are stored in the `cache/` directory

## Troubleshooting

### "Warning: icalendar library not installed"
```bash
pip install icalendar python-dateutil
```

### No events mentioned despite having a calendar URL
- Check that your iCal URL is public and accessible
- Verify events exist in the relevant timeframes (today, tonight, etc.)
- The system only mentions upcoming events, not past ones

### DJ creates generic event content instead of real events
This is normal! The AI will creatively mention generic events when no real events are available, maintaining natural conversation flow.

## Testing Your Setup

Test with the US Holidays calendar:
```bash
export ICAL_URLS="https://calendar.google.com/calendar/ical/en.usa%23holiday%40group.v.calendar.google.com/public/basic.ics"
python test_events.py
```

## Advanced Usage

### Multiple Calendar Support
```bash
export ICAL_URLS="https://work-calendar.ics,https://personal-calendar.ics,https://holidays.ics"
```

### Custom Event Service
```python
from event_service import EventService

service = EventService(cache_duration_minutes=30)  # 30-minute cache
events = service.get_relevant_events_summary(['your-calendar-url'])
```

## What's New

✨ **Event-aware DJ spots**: New spot types specifically for event mentions
✨ **Smart timing**: Events mentioned at contextually appropriate times
✨ **Intelligent fallbacks**: Generic event content when no real events available
✨ **Multi-calendar support**: Combine multiple calendars seamlessly
✨ **Efficient caching**: Reduces API calls while keeping events fresh

---

Enjoy your event-aware PersonalDJ experience! 🎵