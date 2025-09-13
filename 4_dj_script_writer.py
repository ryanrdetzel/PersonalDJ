#!/usr/bin/env python3
"""
DJ Script Writer - Generates DJ scripts using OpenAI API
Takes spot requirements and creates engaging DJ content
"""

import json
import os
from datetime import datetime
from typing import List, Dict
from pathlib import Path
from openai import OpenAI

class DJScriptWriter:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            print("Warning: No OpenAI API key found. Using fallback scripts.")

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
        duration_target = spot_requirement["duration_target_seconds"]

        prompt = f"""
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

        Style guide:
        - Sound like a friendly radio DJ: energetic, positive, and natural.
        - Use contractions and everyday language (we're, it's, let's, gonna, gotta).
        - Keep sentences short and rhythmic (6–12 words each). Vary cadence.
        - Sprinkle light, tasteful enthusiasm (a little "let's go", "right now", "good vibes").
        - Start with a hook, end with a smooth handoff back to the music.
        - If you reference the time, say it naturally (e.g., "just after three").
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

            "general": "Thanks for listening to your personalized music stream. Let's get back to the music."
        }

        return scripts.get(spot_type, scripts["general"])

    def write_scripts_for_spots(self, spot_plan: Dict) -> List[Dict]:
        """
        Generate scripts for all planned DJ spots
        """
        scripts = []

        for spot in spot_plan["spots"]:
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
