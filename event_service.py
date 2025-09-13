import os
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import hashlib
from dateutil import tz
try:
    from icalendar import Calendar, Event as ICalEvent
    ICALENDAR_AVAILABLE = True
except ImportError:
    ICALENDAR_AVAILABLE = False

class EventService:
    def __init__(self, cache_duration_minutes: int = 60):
        self.cache_duration_minutes = cache_duration_minutes
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)

        if not ICALENDAR_AVAILABLE:
            print("Warning: icalendar library not installed. Event integration will be disabled.")
            print("Install with: pip install icalendar python-dateutil")

    def get_cache_key(self, ical_url: str) -> str:
        """Generate a cache key for an iCal URL"""
        return hashlib.md5(ical_url.encode()).hexdigest()

    def is_cache_valid(self, cache_file: Path) -> bool:
        """Check if cache file is still valid"""
        if not cache_file.exists():
            return False

        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        return cache_age < timedelta(minutes=self.cache_duration_minutes)

    def fetch_ical_content(self, ical_url: str) -> Optional[str]:
        """Fetch iCal content from URL with caching"""
        cache_key = self.get_cache_key(ical_url)
        cache_file = self.cache_dir / f"ical_{cache_key}.ics"

        # Use cache if valid
        if self.is_cache_valid(cache_file):
            try:
                return cache_file.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Error reading cache file {cache_file}: {e}")

        # Fetch from URL
        try:
            response = requests.get(ical_url, timeout=30)
            response.raise_for_status()
            content = response.text

            # Cache the content
            try:
                cache_file.write_text(content, encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not cache iCal content: {e}")

            return content

        except requests.exceptions.RequestException as e:
            print(f"Error fetching iCal from {ical_url}: {e}")

            # Try to use stale cache as fallback
            if cache_file.exists():
                try:
                    print(f"Using stale cache for {ical_url}")
                    return cache_file.read_text(encoding='utf-8')
                except Exception:
                    pass

            return None

    def parse_ical_events(self, ical_content: str) -> List[Dict[str, Any]]:
        """Parse iCal content and extract events"""
        if not ICALENDAR_AVAILABLE:
            return []

        try:
            calendar = Calendar.from_ical(ical_content)
            events = []

            for component in calendar.walk():
                if component.name == "VEVENT":
                    event_data = self.extract_event_data(component)
                    if event_data:
                        events.append(event_data)

            return events

        except Exception as e:
            print(f"Error parsing iCal content: {e}")
            return []

    def extract_event_data(self, event_component) -> Optional[Dict[str, Any]]:
        """Extract relevant data from an iCal event component"""
        try:
            # Get basic event data
            title = str(event_component.get('SUMMARY', 'Untitled Event'))
            description = str(event_component.get('DESCRIPTION', ''))
            location = str(event_component.get('LOCATION', ''))

            # Handle start time
            dtstart = event_component.get('DTSTART')
            if not dtstart:
                return None

            # Convert to datetime with timezone awareness
            start_dt = self.normalize_datetime(dtstart.dt)
            if not start_dt:
                return None

            # Handle end time
            dtend = event_component.get('DTEND')
            end_dt = None
            if dtend:
                end_dt = self.normalize_datetime(dtend.dt)

            # Check for all-day events
            is_all_day = not isinstance(dtstart.dt, datetime)

            return {
                'title': title,
                'description': description,
                'location': location,
                'start': start_dt.isoformat(),
                'end': end_dt.isoformat() if end_dt else None,
                'is_all_day': is_all_day,
                'raw_start': start_dt,
                'raw_end': end_dt
            }

        except Exception as e:
            print(f"Error extracting event data: {e}")
            return None

    def normalize_datetime(self, dt) -> Optional[datetime]:
        """Normalize various datetime formats to timezone-aware datetime"""
        try:
            from datetime import date

            if isinstance(dt, datetime):
                # If datetime has no timezone, assume local timezone
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tz.tzlocal())
                return dt
            elif isinstance(dt, date):
                # Handle date objects (all-day events) - datetime is also a date, so check datetime first
                return datetime.combine(dt, datetime.min.time()).replace(tzinfo=tz.tzlocal())
            else:
                return None
        except Exception:
            return None

    def get_events_from_urls(self, ical_urls: List[str]) -> List[Dict[str, Any]]:
        """Fetch and parse events from multiple iCal URLs"""
        all_events = []

        for url in ical_urls:
            print(f"Fetching events from: {url}")
            ical_content = self.fetch_ical_content(url)
            if ical_content:
                events = self.parse_ical_events(ical_content)
                print(f"Found {len(events)} events from {url}")
                all_events.extend(events)
            else:
                print(f"No content retrieved from {url}")

        # Sort events by start time
        all_events.sort(key=lambda x: x['raw_start'] if x['raw_start'] else datetime.min.replace(tzinfo=tz.tzlocal()))

        return all_events

    def filter_events_by_timeframe(self, events: List[Dict[str, Any]],
                                  reference_time: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Filter events into relevant timeframes"""
        if reference_time is None:
            reference_time = datetime.now(tz.tzlocal())

        # Define timeframes
        today_start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        tonight_start = reference_time.replace(hour=17, minute=0, second=0, microsecond=0)
        tonight_end = today_end.replace(hour=2, minute=0, second=0, microsecond=0)  # Until 2 AM next day
        tomorrow_start = today_end
        tomorrow_end = tomorrow_start + timedelta(days=1)
        next_week_start = today_start
        next_week_end = today_start + timedelta(days=7)

        filtered = {
            'happening_now': [],
            'today': [],
            'tonight': [],
            'tomorrow': [],
            'this_week': [],
            'upcoming': []
        }

        for event in events:
            if not event['raw_start']:
                continue

            start_time = event['raw_start']
            end_time = event['raw_end'] or start_time

            # Skip past events (unless they're still happening)
            if end_time < reference_time:
                continue

            # Happening now
            if start_time <= reference_time <= end_time:
                filtered['happening_now'].append(event)

            # Today's events
            if today_start <= start_time < today_end:
                filtered['today'].append(event)

            # Tonight's events (5 PM today to 2 AM tomorrow)
            if tonight_start <= start_time < tonight_end:
                filtered['tonight'].append(event)

            # Tomorrow's events
            elif tomorrow_start <= start_time < tomorrow_end:
                filtered['tomorrow'].append(event)

            # This week's events
            elif next_week_start <= start_time < next_week_end:
                filtered['this_week'].append(event)

            # All upcoming events (next 30 days)
            elif start_time < reference_time + timedelta(days=30):
                filtered['upcoming'].append(event)

        return filtered

    def get_relevant_events_summary(self, ical_urls: List[str],
                                   reference_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get a summary of relevant events for DJ mentions"""
        if not ical_urls or not ICALENDAR_AVAILABLE:
            return {
                'available': False,
                'events_by_timeframe': {},
                'total_events': 0,
                'summary_text': ''
            }

        try:
            # Get all events
            all_events = self.get_events_from_urls(ical_urls)

            # Filter by timeframe
            filtered_events = self.filter_events_by_timeframe(all_events, reference_time)

            # Generate summary text
            summary_parts = []

            if filtered_events['happening_now']:
                summary_parts.append(f"{len(filtered_events['happening_now'])} event(s) happening now")

            if filtered_events['today']:
                summary_parts.append(f"{len(filtered_events['today'])} event(s) today")

            if filtered_events['tonight']:
                summary_parts.append(f"{len(filtered_events['tonight'])} event(s) tonight")

            if filtered_events['tomorrow']:
                summary_parts.append(f"{len(filtered_events['tomorrow'])} event(s) tomorrow")

            summary_text = ', '.join(summary_parts) if summary_parts else 'No upcoming events'

            return {
                'available': True,
                'events_by_timeframe': filtered_events,
                'total_events': len(all_events),
                'summary_text': summary_text,
                'reference_time': reference_time.isoformat() if reference_time else None
            }

        except Exception as e:
            print(f"Error getting events summary: {e}")
            return {
                'available': False,
                'events_by_timeframe': {},
                'total_events': 0,
                'summary_text': 'Error loading events',
                'error': str(e)
            }

    def format_event_for_dj(self, event: Dict[str, Any]) -> str:
        """Format a single event for DJ mention"""
        title = event['title']
        location = event['location']

        # Format time
        start_time = event['raw_start']
        if event['is_all_day']:
            time_str = "all day"
        else:
            time_str = f"at {start_time.strftime('%I:%M %p').lstrip('0').lower()}"

        # Build formatted string
        parts = [title]
        if location:
            parts.append(f"at {location}")
        parts.append(time_str)

        return ' '.join(parts)

    def get_dj_event_mentions(self, ical_urls: List[str],
                             reference_time: Optional[datetime] = None) -> Dict[str, List[str]]:
        """Get formatted event mentions for DJ scripts"""
        events_summary = self.get_relevant_events_summary(ical_urls, reference_time)

        if not events_summary['available']:
            return {'timeframes': [], 'mentions': []}

        mentions = {
            'happening_now': [],
            'today': [],
            'tonight': [],
            'tomorrow': [],
            'this_week': []
        }

        events_by_timeframe = events_summary['events_by_timeframe']

        for timeframe, events in events_by_timeframe.items():
            if timeframe in mentions:
                for event in events[:3]:  # Limit to 3 events per timeframe
                    formatted = self.format_event_for_dj(event)
                    mentions[timeframe].append(formatted)

        return mentions


def test_event_service():
    """Test the event service with sample data"""
    service = EventService()

    # Test with a sample Google Calendar URL (you'll need a real one)
    test_urls = [
        # "https://calendar.google.com/calendar/ical/your-calendar-id/public/basic.ics"
    ]

    if test_urls and test_urls[0]:  # Only run if real URL provided
        events_summary = service.get_relevant_events_summary(test_urls)
        print("\nEvents Summary:")
        print(json.dumps(events_summary, indent=2, default=str))

        mentions = service.get_dj_event_mentions(test_urls)
        print("\nDJ Mentions:")
        print(json.dumps(mentions, indent=2))
    else:
        print("Event service loaded successfully. Add iCal URLs to test.")


if __name__ == "__main__":
    test_event_service()