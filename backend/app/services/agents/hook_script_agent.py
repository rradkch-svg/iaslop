import random
from typing import Dict, Any, List, Optional
from backend.app.services.agents.base_agent import BaseAgent

class HookScriptAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="HookScriptSpecialist",
            role_description="Specialist in viral 3-second hooks, pacing, curiosity gaps, and retention engineering for Minuto Inexplicável Shorts."
        )

    async def generate_curiosity_topics(self, count: int = 3) -> List[Dict[str, str]]:
        """
        Dynamically generates fresh, bizarre, and intriguing curiosity topics for Minuto Inexplicável.
        Uses random seed/temperature to ensure dynamic topics are always fresh and unrepeatable.
        """
        angles = [
            "declassified historical anomalies and forbidden archives",
            "terrifying ocean and deep space discoveries that defy known physics",
            "creepy archaeological finds that scientists refuse to explain",
            "mind-bending biological paradoxes and immortal organisms",
            "bizarre mass psychological events and glitch-in-the-matrix incidents",
            "ancient forgotten engineering that should not have existed",
            "unexplained disappearance of entire ships, flights or ancient armies"
        ]
        chosen_angle = random.choice(angles)

        system_prompt = (
            "You are the Lead Curiosity Strategist for the YouTube Shorts channel 'Minuto Inexplicável'. "
            "Your mission is to generate highly captivating, factual, bizarre, and unexplainable curiosity topics. "
            "Every single topic MUST sound mysterious, urgent, and mind-blowing. "
            "Output ONLY a valid JSON array of objects."
        )

        user_prompt = f"""
Focus Angle: {chosen_angle}
Quantity: {count}

Generate {count} unique, high-retention video topics specifically for YouTube Shorts (in English, high viral appeal).
Return JSON format:
[
  {{
    "topic": "Compelling Title/Subject (e.g. The 1994 Oakville Gelatin Rain Mystery)",
    "hook": "The irresistible 1-sentence curiosity gap that forces the viewer to keep watching (0:00-0:03 hook)",
    "tone": "Eerie & Fast-Paced | Bizarre & Shocking | Mind-Bending Mystery"
  }}
]
"""
        result = await self.call_llm_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.95
        )

        if isinstance(result, list) and len(result) > 0:
            return result[:count]

        # Fallback if offline
        return [
            {
                "topic": "The 1994 Oakville Blob Incident",
                "hook": "In August 1994, a mysterious toxic gelatin rained from the clouds over Washington, making an entire town violently ill.",
                "tone": "Bizarre & Shocking"
            },
            {
                "topic": "The Immortal Turritopsis Jellyfish",
                "hook": "There is a creature living in our oceans right now that can literally reverse its aging process and live forever.",
                "tone": "Mind-Bending Mystery"
            },
            {
                "topic": "The 1518 Dancing Plague of Strasbourg",
                "hook": "In July 1518, hundreds of people in Europe began dancing uncontrollably in the streets until their hearts literally burst.",
                "tone": "Eerie & Fast-Paced"
            }
        ]

    async def write_shorts_script(self, topic: str, tone: str = "mysterious", user_notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Writes a high-density, viral YouTube Shorts script (130 - 180 words, ~45-50 seconds narration)
        with an unskippable 3-second opening hook and structured speech blocks.
        """
        system_prompt = (
            "You are the master scriptwriter for the YouTube Shorts channel 'Minuto Inexplicável'. "
            "You write ultra-high-retention, dramatic, factual curiosity scripts in English. "
            "STRICT RULES:\n"
            "1. LENGTH: Exactly 130 to 180 words. Never exceed 190 words. Perfect for a 45-50 second rapid-fire Short.\n"
            "2. THE 3-SECOND HOOK: The opening sentence MUST be hypnotic and open a massive curiosity loop immediately.\n"
            "3. PACING & SPEECH BLOCKS: Divide the script into 6 to 9 concise speech blocks (each line is a natural breath pause of 3-6 seconds).\n"
            "4. SOUND EFFECT CUES: Place subtle SFX tags in brackets at key beats (e.g. [SFX:SUB_BOOM], [SFX:WHOOSH], [SFX:BELL]) to guide audio mixing.\n"
            "5. NO FILLER: Every word must build tension, reveal an anomaly, or question reality.\n"
            "6. LOOP ENDING: The final sentence must seamlessly connect back or leave a shocking unanswered question."
        )

        user_prompt = f"""
Topic: {topic}
Tone: {tone}
Extra Notes: {user_notes or 'Focus on the unexplainable facts and dark mysteries.'}

Return JSON format:
{{
  "title_concept": "High-CTR Title Concept",
  "opening_hook": "The shocking first sentence (under 14 words)",
  "speech_blocks": [
    "[SFX:SUB_BOOM] Opening hypnotic hook line...",
    "[SFX:WHOOSH] Rapid buildup of the bizarre incident...",
    "The scientific anomaly that baffled investigators...",
    "[SFX:BELL] The shocking secret discovered in the records...",
    "The eerie unanswered mystery that remains today..."
  ],
  "full_script": "Full narration text without SFX brackets for TTS synthesis",
  "word_count": 150
}}
"""
        result = await self.call_llm_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.8
        )

        if isinstance(result, dict) and "speech_blocks" in result and "full_script" in result:
            return result

        # Fallback script
        clean_full = (
            f"Do not ignore what happened during the incident of {topic}. "
            f"In a matter of seconds, an anomaly was recorded that defied every known law of physics. "
            f"Witnesses reported seeing something so bizarre that government officials immediately classified the reports. "
            f"When researchers analyzed the evidence, they found patterns that should not exist in nature. "
            f"To this day, the true explanation remains completely hidden in sealed archives. "
            f"What do you think really happened?"
        )
        blocks = [
            f"[SFX:SUB_BOOM] Do not ignore what happened during the incident of {topic}.",
            "[SFX:WHOOSH] In a matter of seconds, an anomaly was recorded that defied every known law of physics.",
            "Witnesses reported seeing something so bizarre that government officials immediately classified the reports.",
            "[SFX:BELL] When researchers analyzed the evidence, they found patterns that should not exist in nature.",
            "To this day, the true explanation remains completely hidden in sealed archives.",
            "What do you think really happened?"
        ]

        return {
            "title_concept": f"The Unexplained Mystery of {topic}",
            "opening_hook": f"Do not ignore what happened during the incident of {topic}.",
            "speech_blocks": blocks,
            "full_script": clean_full,
            "word_count": len(clean_full.split())
        }

hook_script_agent = HookScriptAgent()
