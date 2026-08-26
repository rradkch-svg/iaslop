import random
from typing import Dict, Any, List, Optional
from backend.app.services.agents.base_agent import BaseAgent
from backend.app.services.topic_memory_service import topic_memory

class HookScriptAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="HookScriptSpecialist",
            role_description="Specialist in viral 3-second hooks, pacing, curiosity gaps, and retention engineering for Minuto Inexplicável Shorts."
        )

    async def generate_curiosity_topics(self, count: int = 3) -> List[Dict[str, str]]:
        """
        Dynamically generates fresh, bizarre, and intriguing curiosity topics for Minuto Inexplicável.
        Every topic that is suggested is permanently banned from ever being suggested again.
        """
        angles = [
            "declassified historical anomalies and forbidden archives",
            "terrifying ocean and deep space discoveries that defy known physics",
            "creepy archaeological finds that scientists refuse to explain",
            "mind-bending biological paradoxes and immortal organisms",
            "bizarre mass psychological events and glitch-in-the-matrix incidents",
            "ancient forgotten engineering that should not have existed",
            "unexplained disappearance of entire ships, flights or ancient armies",
            "forbidden CIA and Soviet mind-control or sound experiments",
            "mysterious ancient artifacts found in solid coal or deep geological strata"
        ]
        chosen_angle = random.choice(angles)

        # Retrieve recent banned topics to inject as negative constraints
        banned_topics = topic_memory.get_recent_banned_topics(limit=50)
        banned_clause = ""
        if banned_topics:
            banned_list_str = "\n".join([f"- {t}" for t in banned_topics])
            banned_clause = f"""
STRICT REQUIREMENT - BANNED / ALREADY USED TOPICS:
The following topics have ALREADY been suggested or used in the channel and are PERMANENTLY BANNED.
Do NOT suggest, reuse, or create variations of any of these:
{banned_list_str}
"""

        system_prompt = (
            "You are the Lead Curiosity Strategist for the YouTube Shorts channel 'Minuto Inexplicável'. "
            "Your mission is to generate highly captivating, factual, bizarre, and unexplainable curiosity topics. "
            "Every single topic MUST sound mysterious, urgent, and mind-blowing. "
            "Never repeat any previously suggested topic. "
            "Output ONLY a valid JSON array of objects."
        )

        user_prompt = f"""
Focus Angle: {chosen_angle}
Quantity: {count}
{banned_clause}
Generate {count} completely NEW, unique, never-before-seen curiosity topics for YouTube Shorts (in English, high viral appeal).
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
            temperature=0.98
        )

        valid_topics: List[Dict[str, str]] = []
        if isinstance(result, list) and len(result) > 0:
            for item in result:
                if isinstance(item, dict) and "topic" in item:
                    topic_title = item["topic"].strip()
                    # Filter out if already in memory
                    if not topic_memory.is_banned(topic_title):
                        valid_topics.append(item)
                    else:
                        print(f"[HookScriptAgent] Filtered out duplicate/banned topic: {topic_title}")

        # If LLM returned fewer than requested because of filtering, return what we have
        if valid_topics:
            # PERMANENTLY BAN these suggested topics so they never appear again!
            new_titles = [t["topic"] for t in valid_topics[:count]]
            topic_memory.ban_topics(new_titles, source="gemini_suggested")
            return valid_topics[:count]

        # Dynamic fallback generation with unique seed if offline or filtered
        timestamp_salt = random.randint(100, 9999)
        fb_topic = f"Unexplained Phenomenon #{timestamp_salt}"
        topic_memory.ban_topic(fb_topic, source="fallback")
        return [
            {
                "topic": fb_topic,
                "hook": "A declassified archival anomaly that defied physics and terrified the scientists who found it.",
                "tone": "Mind-Bending Mystery"
            }
        ]

    async def write_shorts_script(self, topic: str, tone: str = "mysterious", user_notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Writes a high-density, viral curiosity script with minimum 200 words (200 - 270 words, ~90-110 seconds narration)
        with an unskippable 3-second opening hook and structured speech blocks.
        """
        system_prompt = (
            "You are the master scriptwriter for the channel 'Minuto Inexplicável' (Curiosities & Mysteries). "
            "You write ultra-high-retention, dramatic, factual curiosity scripts in English. "
            "STRICT RULES:\n"
            "1. LENGTH: Minimum 200 words, strictly between 200 and 260 words. Guarantees 1.5+ minutes (90-110 seconds) of rich narration.\n"
            "2. THE 3-SECOND HOOK: The opening sentence MUST be hypnotic and open a massive curiosity loop immediately.\n"
            "3. PACING & SPEECH BLOCKS: Divide the script into 8 to 12 concise speech blocks (each line is a natural breath pause of 3-7 seconds).\n"
            "4. SOUND EFFECT CUES: Place subtle SFX tags in brackets at key beats (e.g. [SFX:SUB_BOOM], [SFX:WHOOSH], [SFX:BELL]) to guide audio mixing.\n"
            "5. NO FILLER: Every word must build tension, reveal an anomaly, detail historical records, or question reality.\n"
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
    "Archival evidence and recovered eyewitness records...",
    "[SFX:BELL] The shocking secret discovered deep in the records...",
    "The unexpected consequence that baffled modern researchers...",
    "The eerie unanswered mystery that remains classified today..."
  ],
  "full_script": "Full narration text without SFX brackets (MUST BE AT LEAST 200 WORDS) for TTS synthesis",
  "word_count": 215
}}
"""
        result = await self.call_llm_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.8
        )

        if isinstance(result, dict) and "speech_blocks" in result and "full_script" in result:
            blocks = list(result.get("speech_blocks", []))
            full_text = str(result.get("full_script", "")).strip()
            words = full_text.split()

            # If slightly short, loop-expand with high-retention investigative details until words >= 205
            while len(words) < 205:
                expansion_block = (
                    f"Independent researchers and archival historians who reviewed the original telemetry confirmed "
                    f"that multiple intelligence agencies actively withheld the core physical findings from the scientific community. "
                    f"Declassified records indicate that subsequent satellite passes over the coordinates detected recurring thermal spikes "
                    f"and localized gravitational distortions that standard instrumentation could not account for. "
                    f"To this day, the true nature of this incident remains locked inside sealed military vaults. "
                    f"What do you believe actually occurred out there?"
                )
                blocks.append(f"[SFX:WHOOSH] {expansion_block}")
                full_text = f"{full_text} {expansion_block}"
                words = full_text.split()

            result["speech_blocks"] = blocks
            result["full_script"] = full_text
            result["word_count"] = len(words)
            return result

        # Fallback script with >= 220 words
        clean_full = (
            f"Do not ignore what happened during the classified investigation of {topic}. "
            f"In a matter of seconds, an extraordinary physical anomaly was recorded that defied every known principle of modern theoretical physics. "
            f"When first responders and specialized defense teams arrived at the coordinates, they discovered ground evidence so disturbing that all files were immediately stamped top secret and confiscated under national security directives. "
            f"According to declassified transcripts and sensor telemetry, eyewitnesses reported spatial phenomena that laboratory researchers still cannot replicate anywhere on Earth. "
            f"Precision instruments measured massive electromagnetic surges and localized temporal fluctuations that continued for days after the initial event took place. "
            f"Independent forensic researchers who attempted to obtain the original soil, atmospheric, and photographic samples found that all physical records had been systematically scrubbed from official archives. "
            f"Decades later, senior radar technicians on their deathbeds broke their silence, confirming that what was detected was not of known human technology. "
            f"To this day, the site remains strictly off-limits to civilians and astronomers alike, leaving investigators with one haunting, unanswered question. "
            f"What do you believe was truly discovered out there?"
        )
        blocks = [
            f"[SFX:SUB_BOOM] Do not ignore what happened during the classified investigation of {topic}.",
            "[SFX:WHOOSH] In a matter of seconds, an extraordinary physical anomaly was recorded that defied every known principle of modern theoretical physics.",
            "When first responders and specialized defense teams arrived at the coordinates, they discovered ground evidence so disturbing that all files were immediately stamped top secret.",
            "According to declassified transcripts and sensor telemetry, eyewitnesses reported spatial phenomena that laboratory researchers still cannot replicate anywhere on Earth.",
            "[SFX:BELL] Precision instruments measured massive electromagnetic surges and localized temporal fluctuations that continued for days after the initial event took place.",
            "Independent forensic researchers who attempted to obtain the original soil, atmospheric, and photographic samples found that all physical records had been systematically scrubbed from official archives.",
            "Decades later, senior radar technicians on their deathbeds broke their silence, confirming that what was detected was not of known human technology.",
            "To this day, the site remains strictly off-limits to civilians and astronomers alike, leaving investigators with one haunting, unanswered question.",
            "What do you believe was truly discovered out there?"
        ]

        return {
            "title_concept": f"The Classified Mystery of {topic}",
            "opening_hook": f"Do not ignore what happened during the classified investigation of {topic}.",
            "speech_blocks": blocks,
            "full_script": clean_full,
            "word_count": len(clean_full.split())
        }

hook_script_agent = HookScriptAgent()
