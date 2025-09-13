#!/usr/bin/env python3
"""
DJ Script Writer - Generates DJ scripts using OpenAI API
Takes spot requirements and creates engaging DJ content
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path
from openai import OpenAI
from event_service import EventService

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

def load_recent_dj_scripts(days_back: int = 3) -> List[str]:
    """Load recent DJ scripts to avoid repetition"""
    recent_scripts = []

    # Look back through recent playlist directories
    for i in range(1, days_back + 1):  # Start from yesterday
        past_date = datetime.now() - timedelta(days=i)
        date_str = past_date.strftime("%Y-%m-%d")
        script_file = Path(f"playlists/{date_str}/dj_scripts.json")

        if script_file.exists():
            try:
                with open(script_file, 'r') as f:
                    data = json.load(f)
                    for script_data in data.get('scripts', []):
                        if 'script' in script_data:
                            recent_scripts.append(script_data['script'])
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                continue

    return recent_scripts

class DJScriptWriter:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            print("Warning: No OpenAI API key found. Using fallback scripts.")

        # Initialize event service
        self.event_service = EventService()

    def generate_script(self, spot_requirement: Dict) -> str:
        """
        Generate a DJ script based on requirements
        """
        if self.client:
            return self.generate_with_ai(spot_requirement)
        else:
            return self.generate_fallback_script(spot_requirement)

    def generate_with_ai(self, spot_requirement: Dict) -> str:
        """
        Use OpenAI to generate creative DJ scripts
        """
        spot_type = spot_requirement["type"]
        tone = spot_requirement["tone"]
        elements = spot_requirement["include_elements"]
        context = spot_requirement["context"]
        song_context = spot_requirement.get("song_context", {})
        duration_target = spot_requirement["duration_target_seconds"]
        approximate_time = spot_requirement.get("approximate_time", "")

        # Load recent DJ scripts to avoid repetition
        recent_scripts = load_recent_dj_scripts()

        # Get DJ personality for this time
        try:
            # Parse the approximate time to get hour
            if approximate_time and ":" in approximate_time:
                hour = int(approximate_time.split(":")[0])
            else:
                hour = datetime.now().hour
        except:
            hour = datetime.now().hour

        dj_personality = get_dj_personality_for_time(hour)

        # Format song context for the prompt
        song_info = ""
        if song_context.get("recent_songs"):
            recent = song_context["recent_songs"]
            song_info += f"\nSongs just played:\n"
            for song in recent:
                song_info += f"- \"{song['title']}\" by {song['artist']}\n"

        if song_context.get("upcoming_songs"):
            upcoming = song_context["upcoming_songs"]
            song_info += f"\nSongs coming up:\n"
            for song in upcoming:
                song_info += f"- \"{song['title']}\" by {song['artist']}\n"

        # Get event context
        event_info = ""
        event_context = spot_requirement.get("event_context", {})
        if event_context and event_context.get("available"):
            relevant_events = event_context.get("mentions", {})

            # Add events based on spot type or general relevance
            if spot_type in ["event_mention", "today_events"] or any(relevant_events.values()):
                event_info += f"\n\nUpcoming Events (mention naturally if relevant to the vibe):\n"

                # Prioritize events based on timeframe
                for timeframe in ["happening_now", "today", "tonight", "tomorrow", "this_week"]:
                    events = relevant_events.get(timeframe, [])
                    if events and len(events) > 0:
                        timeframe_name = timeframe.replace("_", " ").title()
                        if timeframe == "happening_now":
                            timeframe_name = "Right Now"
                        event_info += f"{timeframe_name}:\n"
                        for event in events[:2]:  # Limit to 2 per timeframe
                            event_info += f"- {event}\n"
                        event_info += "\n"

        # Format recent scripts info for the prompt
        previous_content = ""
        if recent_scripts:
            previous_content = f"""

        Previous DJ messages from recent shows (avoid repeating these themes/content):
        {chr(10).join(f"- {script[:100]}..." if len(script) > 100 else f"- {script}" for script in recent_scripts[-10:])}

        IMPORTANT: Create fresh, original content that doesn't repeat themes, jokes, facts, or phrasing from the previous messages above."""

        # Build personality-specific prompt
        base_prompt = f"""
        You are an experienced on‑air radio DJ writing a very short link.
        Your delivery is warm, upbeat, and conversational — never like reading text.
        Speak like you're live on the mic with a smile in your voice.

        Spot type: {spot_type}
        Target spoken length: ~{duration_target} seconds
        Must include: {', '.join(elements)}

        Context:
        - Day: {context['day_name']}
        - Weather: {context['weather']}
        - Mood: {context['mood']}
        - Genre playing: {context['genre']}
        {"- Special occasion: " + context['special_occasion'] if context.get('special_occasion') else ""}
        {song_info}{event_info}{previous_content}"""

        # Define common style guide
        style_guide = f"""

        Style guide:
        - Sound like a friendly radio DJ: energetic, positive, and natural.
        - Use contractions and everyday language (we're, it's, let's, gonna, gotta).
        - Keep sentences short and rhythmic (6–12 words each). Vary cadence.
        - Sprinkle light, tasteful enthusiasm (a little "let's go", "right now", "good vibes").
        - Start with a hook, end with a smooth handoff back to the music.
        - If you reference the time, say it naturally (e.g., "just after three").
        - Feel free to reference songs that just played or are coming up, but keep it natural.
        - You can drop artist facts, tease upcoming tracks, or comment on what just played.
        - Avoid overusing exclamation points; energy should come from wording and rhythm.

        Tone examples (for feel only, do not copy verbatim):
        - "Good morning! Just after eight, rolling with bright beats. Take a breath, smile—let's cruise into your day."
        - "Quick check-in: feeling that Friday lift? Same here. Stay with me—more good vibes right now."

        Do NOT:
        - Do not mention being an AI or automated.
        - Do not use station call letters, show names, hashtags, emojis, SFX, or brackets.
        - Do not include stage directions or cues.

        Output format:
        - One tight paragraph (1–3 sentences) that fits ~{duration_target} seconds when spoken.
        - Only the script text, no titles, labels, or formatting.
        """

        # Add personality-specific guidance
        if dj_personality:
            personality_prompt = f"""

        DJ Personality: {dj_personality['name']}
        {dj_personality['style_prompt']}

        Your personality traits:
        {chr(10).join(f"- {trait}" for trait in dj_personality['personality_traits'])}

        Speaking style: {dj_personality['speaking_style']}
        Energy level: {dj_personality['energy_level']}"""

            prompt = base_prompt + personality_prompt + style_guide
        else:
            prompt = base_prompt + style_guide

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a seasoned, on‑air radio DJ. You write short, upbeat,"
                            " natural scripts that sound spoken, not read. You keep energy"
                            " friendly and warm, end cleanly into music, and avoid all"
                            " station identifiers or AI mentions."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=1.0,
                max_tokens=240,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating AI script: {e}")
            return self.generate_fallback_script(spot_requirement)

    def generate_fallback_script(self, spot_requirement: Dict) -> str:
        """
        Generate fallback scripts when API is unavailable
        """
        spot_type = spot_requirement["type"]
        context = spot_requirement["context"]
        time = spot_requirement["approximate_time"]

        scripts = {
            "morning_greeting": f"Good morning! It's a beautiful {context['day_name']}. Hope you're ready for a great day ahead. Let's keep the music flowing.",

            "weather": f"Looking outside, we've got {context['weather']} weather today. Perfect for whatever you've got planned. Here's more music to keep you company.",

            "daily_schedule": f"It's {time} on this {context['day_name']}. Whatever's on your schedule today, you've got the perfect soundtrack right here.",

            "time_check": f"Just a quick time check - it's {time}. You're listening to your personalized music mix.",

            "motivation": "Remember, every moment is a chance to make today better than yesterday. Let's keep that positive energy going with more great music.",

            "fun_fact": "Here's something interesting - did you know that listening to music releases dopamine in your brain? No wonder we feel so good right now. Back to the tunes.",

            "lunch_reminder": f"It's about that time - {time}. If you haven't already, might be a good moment for a lunch break. Let the music play on.",

            "afternoon_boost": "Afternoon check-in! Hope you're staying energized. Let's keep the momentum going with more of your favorite tracks.",

            "trivia": "Quick music trivia - the most covered song in history is 'Yesterday' by The Beatles, with over 1,600 recorded versions. Speaking of great music, here's more.",

            "joke": "Why did the musician bring a ladder to the gig? They wanted to reach the high notes! Let's get back to the real music.",

            "evening_greeting": f"Good evening! As we move into the evening hours on this {context['day_name']}, let's keep the perfect vibe going.",

            "dinner_suggestion": "Evening time often means dinner time. Whatever's on your menu tonight, here's the perfect dinner soundtrack.",

            "evening_wind_down": "As the day winds down, take a moment to relax and enjoy. Here's more music to help you unwind.",

            "tomorrow_preview": "Looking ahead to tomorrow, make sure to tune in for another great day of personalized music. But for now, let's enjoy what's left of today.",

            "hour_announcement": f"It's the top of the hour - {time}. You're listening to your custom music stream.",

            "music_info": f"You're enjoying a specially curated {context['genre']} mix today. Each track chosen just for you.",

            "random_thought": "Music has a way of touching our souls and connecting us to moments in time. Let's create more of those moments right now.",

            # New daily content types
            "dad_joke": "Here's your daily dad joke - Why don't scientists trust atoms? Because they make up everything! Speaking of making up good vibes, here's more music.",

            "kid_fact": "Fun fact for the day - a group of flamingos is called a 'flamboyance!' How cool is that? Just like this music is pretty cool too.",

            "history_fact": "Did you know that the first music recording was made in 1860? That's over 160 years of recorded music history! Here's to adding more great moments to that timeline.",

            "animal_fact": "Amazing animal fact - dolphins have names for each other! They use unique whistle signatures to identify themselves. Pretty incredible, right? Here's more incredible music.",

            "global_fact": "Here's something fascinating from around the world - in Japan, there are more vending machines per capita than anywhere else on Earth. About one for every 23 people! Now that's convenience. Speaking of convenient, here's more great music.",

            "country_comparison": "Interesting cultural difference - while Americans typically eat dinner around 6 PM, Spaniards often don't eat until 9 or 10 PM! Different cultures, same love for good food and music.",

            "weird_fact": "Bizarre but true - honey never spoils! Archaeologists have found edible honey in ancient Egyptian tombs. Unlike honey, this next song is fresh and new.",

            "gross_fact": "Icky but fascinating - your body produces about 1.5 liters of saliva every day! That's enough to fill a large water bottle. Thankfully, this next song will wash that thought away.",

            # Event-related fallback content
            "event_mention": f"Hope you've got something fun planned for this {context['day_name']}! Whether you're out and about or staying in, you've got the perfect soundtrack right here.",

            "today_events": f"Whatever's on your schedule today, make sure to take some time to enjoy the moment. Speaking of enjoying the moment, here's more great music.",

            "tonight_events": f"Evening plans coming up? Whether you're heading out or staying cozy at home, let the music set the perfect mood.",

            "tonight_preview": f"As we head into tonight, hope you've got something special planned. Either way, we'll keep the perfect vibe going with more music.",

            "general": "Thanks for listening to your personalized music stream. Let's get back to the music."
        }

        return scripts.get(spot_type, scripts["general"])

    def write_scripts_for_spots(self, spot_plan: Dict) -> List[Dict]:
        """
        Generate scripts for all planned DJ spots
        """
        scripts = []

        # Get event configuration and context
        config = spot_plan.get("config", {})
        event_config = config.get("events", {})
        event_mentions = {}

        if event_config.get("mention_events", False) and event_config.get("ical_urls"):
            try:
                # Get event mentions once for all spots
                event_mentions = self.event_service.get_dj_event_mentions(
                    event_config["ical_urls"]
                )
                print(f"Loaded events: {sum(len(events) for events in event_mentions.values())} total")
            except Exception as e:
                print(f"Warning: Could not load events: {e}")
                event_mentions = {}

        for spot in spot_plan["spots"]:
            # Add event context to spot if events are available
            if event_mentions:
                spot["event_context"] = {
                    "available": True,
                    "mentions": event_mentions,
                    "config": event_config
                }
            else:
                spot["event_context"] = {"available": False}

            script_text = self.generate_script(spot)

            script_data = {
                "spot_number": spot["spot_number"],
                "type": spot["type"],
                "approximate_time": spot["approximate_time"],
                "script": script_text,
                "tone": spot["tone"],
                "duration_target_seconds": spot["duration_target_seconds"],
                "created_at": datetime.now().isoformat()
            }

            scripts.append(script_data)

            print(f"Generated script {spot['spot_number']}/{len(spot_plan['spots'])}: {spot['type']}")

        return scripts

def generate_dj_scripts(spot_plan_file: str = "dj_spot_plan.json") -> Dict:
    """
    Main function to generate all DJ scripts
    """
    # Try to read from dated directory first
    playlist_dir = None
    try:
        # Check if we have a config with playlist_dir
        with open("playlist_config.json", 'r') as f:
            config = json.load(f)
            if "playlist_dir" in config:
                playlist_dir = Path(config["playlist_dir"])
                spot_plan_file = playlist_dir / "dj_spot_plan.json"
    except:
        pass

    with open(spot_plan_file, 'r') as f:
        spot_plan = json.load(f)

    writer = DJScriptWriter()
    scripts = writer.write_scripts_for_spots(spot_plan)

    output = {
        "total_scripts": len(scripts),
        "scripts": scripts,
        "created_at": datetime.now().isoformat(),
        "playlist_date": datetime.now().strftime("%Y-%m-%d")
    }

    # Add playlist_dir if we have it
    if playlist_dir:
        output["playlist_dir"] = str(playlist_dir)

    return output

def main():
    """
    Read spot plan and output DJ scripts
    """
    scripts_data = generate_dj_scripts()

    # Get playlist directory from scripts data or config
    if "playlist_dir" in scripts_data:
        playlist_dir = Path(scripts_data["playlist_dir"])
    else:
        try:
            with open("playlist_config.json", 'r') as f:
                config = json.load(f)
                if "playlist_dir" in config:
                    playlist_dir = Path(config["playlist_dir"])
                else:
                    playlist_dir = Path(".")
        except:
            playlist_dir = Path(".")

    # Save to dated directory
    output_file = playlist_dir / "dj_scripts.json"
    with open(output_file, "w") as f:
        json.dump(scripts_data, f, indent=2)

    print(f"\nGenerated {scripts_data['total_scripts']} DJ scripts")
    print(f"Scripts saved to: {output_file}")

    return scripts_data

if __name__ == "__main__":
    main()
