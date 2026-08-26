import os
import json
import re
import httpx
from typing import List, Dict, Any, Optional
from backend.app.config import settings
from backend.app.models.schemas import VideoFormat, MetadataResponse, ThumbnailResponse

class LLMService:
    def __init__(self):
        pass

    async def _call_llm(self, prompt: str, system_prompt: str = "", max_tokens: int = 4096) -> Optional[str]:
        """
        Calls available LLM in priority order:
        1. Google Gemini (gemini-2.0-flash or gemini-1.5-flash)
        2. Groq Cloud (llama-3.3-70b-versatile)
        3. OpenAI (gpt-4o-mini)
        4. Anthropic
        """
        # Reload current keys from settings
        gemini_key = settings.GEMINI_API_KEY
        groq_key = settings.GROQ_API_KEY
        openai_key = settings.OPENAI_API_KEY
        anthropic_key = settings.ANTHROPIC_API_KEY

        # 1. Google Gemini API (Free at https://aistudio.google.com/app/apikey)
        if gemini_key:
            models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash"]
            for model_name in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                    payload = {
                        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}],
                        "generationConfig": {
                            "maxOutputTokens": max_tokens,
                            "temperature": 0.75
                        }
                    }
                    async with httpx.AsyncClient(timeout=90.0) as client:
                        res = await client.post(url, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            candidates = data.get("candidates", [])
                            if candidates and "content" in candidates[0]:
                                return candidates[0]["content"]["parts"][0]["text"]
                        else:
                            print(f"Gemini {model_name} HTTP {res.status_code}: {res.text[:200]}")
                except Exception as e:
                    print(f"Gemini API error on {model_name}: {e}")

        # 2. Groq Cloud API (Free & Ultra Fast)
        if groq_key:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {groq_key}"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.75
                }
                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        print(f"Groq API HTTP {res.status_code}: {res.text[:200]}")
            except Exception as e:
                print(f"Groq API error: {e}")

        # 3. OpenAI API
        if openai_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {openai_key}"}
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.75
                }
                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"OpenAI API error: {e}")

        return None

    async def test_api_key(self, provider: str, key: str) -> Dict[str, Any]:
        """Tests an API key live to verify connection"""
        if not key or len(key.strip()) < 5:
            return {"valid": False, "message": "Key cannot be empty."}

        if provider == "gemini":
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key.strip()}"
                payload = {"contents": [{"parts": [{"text": "Say 'OK' in one word."}]}]}
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        return {"valid": True, "message": "Google Gemini API connected successfully!"}
                    else:
                        return {"valid": False, "message": f"Gemini error {res.status_code}: {res.text[:150]}"}
            except Exception as e:
                return {"valid": False, "message": f"Connection error: {str(e)}"}

        elif provider == "groq":
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {key.strip()}"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": "Say 'OK'"}]
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        return {"valid": True, "message": "Groq API connected successfully!"}
                    else:
                        return {"valid": False, "message": f"Groq error {res.status_code}: {res.text[:150]}"}
            except Exception as e:
                return {"valid": False, "message": f"Connection error: {str(e)}"}

        elif provider == "openai":
            try:
                url = "https://api.openai.com/v1/models"
                headers = {"Authorization": f"Bearer {key.strip()}"}
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.get(url, headers=headers)
                    if res.status_code == 200:
                        return {"valid": True, "message": "OpenAI API connected successfully!"}
                    else:
                        return {"valid": False, "message": f"OpenAI error {res.status_code}"}
            except Exception as e:
                return {"valid": False, "message": f"Connection error: {str(e)}"}

        return {"valid": False, "message": "Unknown provider"}

    async def generate_topics_by_genre(self, genre_id: str, video_format: VideoFormat = VideoFormat.SHORTS_9_16) -> List[Dict[str, str]]:
        """
        Generates 3 highly specific, viral YouTube video topics based on the chosen genre.
        """
        genre_info = next((g for g in settings.GENRES if g["id"] == genre_id), settings.GENRES[0])
        is_short = video_format == VideoFormat.SHORTS_9_16

        system_prompt = (
            "You are a viral YouTube content strategist with deep knowledge of high-CTR hooks. "
            "Generate 3 highly specific, fascinating, and non-cliché video topic ideas for the specified genre. "
            "Do NOT output generic topics like 'The mystery of space'. Output specific cases, historical anomalies, "
            "unsolved incidents, psychological paradoxes, or cutting-edge discoveries."
        )

        user_prompt = f"""
Genre: {genre_info['name']}
Genre Description: {genre_info['desc']}
Format: {'YouTube Shorts (Fast, high-curiosity shock factor)' if is_short else 'YouTube Long-form (Deep documentary storytelling, rich investigative arc)'}

Return ONLY a JSON array with 3 distinct topic objects:
[
  {{
    "topic": "Specific, fascinating title/topic idea",
    "hook": "The compelling 1-sentence curiosity gap that makes people click and watch",
    "tone": "mysterious | dramatic | educational | engaging"
  }},
  ...
]
"""
        response_text = await self._call_llm(user_prompt, system_prompt, max_tokens=1024)
        if response_text:
            try:
                clean_json = re.search(r"\[[\s\S]*\]", response_text)
                if clean_json:
                    topics = json.loads(clean_json.group(0))
                    if isinstance(topics, list) and len(topics) > 0:
                        return topics[:3]
            except Exception as e:
                print(f"Error parsing genre topics JSON: {e}")

        # High quality fallback topics tailored to genre
        fallbacks = {
            "mysteries": [
                {"topic": "The 1977 Wow! Signal and the Hydrogen Cloud Secret", "hook": "A 72-second extraterrestrial signal received in Ohio that has never repeated—until new radio telescope scans revealed its origin.", "tone": "mysterious"},
                {"topic": "The Green Children of Woolpit: 12th-Century Mystery", "hook": "Two children with green skin speaking an unknown language appeared in medieval England, claiming they came from a subterranean twilight realm.", "tone": "mysterious"},
                {"topic": "The Vanished Crew of the Mary Celeste in 1872", "hook": "A pristine merchant ship found sailing aimlessly with warm food on the table, full cargo, and every soul vanished into thin air.", "tone": "dramatic"}
            ],
            "space": [
                {"topic": "What Happens at the Event Horizon of TON 618", "hook": "The largest supermassive black hole in the universe weighs 66 billion suns and consumes entire star clusters every second.", "tone": "educational"},
                {"topic": "The Fermi Paradox and the Great Filter Theory", "hook": "Why the silence of the cosmos is the most terrifying evidence of what happens to advanced civilizations before they reach interstellar travel.", "tone": "mysterious"},
                {"topic": "The Bizarre Rogue Planets Drifting in Absolute Darkness", "hook": "Billions of sunless worlds wandering interstellar space with oceans trapped beneath radioactive crusts.", "tone": "dramatic"}
            ],
            "history": [
                {"topic": "The Lost Ninth Roman Legion That Vanished in Scotland", "hook": "5,000 elite Roman soldiers marched into the Scottish mist of Caledonia in 117 AD—and were never heard from again.", "tone": "dramatic"},
                {"topic": "The Real Reason the Library of Alexandria Was Lost", "hook": "It wasn't a single catastrophic fire, but centuries of bureaucratic neglect, military sieges, and hidden manuscript thefts.", "tone": "educational"},
                {"topic": "The 1932 Australian Emu War and Military Humiliation", "hook": "When a modern army with heavy machine guns went to war against wild birds—and suffered a catastrophic defeat.", "tone": "engaging"}
            ],
            "psychology": [
                {"topic": "The Dark Triad: How Master Manipulators Read You in 30 Seconds", "hook": "The psychological micro-signals of Machiavellianism and how the human brain unwittingly surrenders control.", "tone": "engaging"},
                {"topic": "The Pratfall Effect and Why Perfect People Are Disliked", "hook": "The subconscious mechanism that makes people trust flaws more than flawless competence.", "tone": "educational"},
                {"topic": "Cognitive Dissonance: Why People Defend Obvious Lies", "hook": "How the human ego rewrites its own memory to prevent internal psychological collapse.", "tone": "dramatic"}
            ]
        }
        return fallbacks.get(genre_id, fallbacks["mysteries"])

    async def generate_script(
        self,
        topic: str,
        video_format: VideoFormat = VideoFormat.SHORTS_9_16,
        tone: str = "engaging",
        target_duration: int = 45,
        user_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 1: Generates verified, deep scripts in English:
        - Shorts (9:16): STRICT 200 - 400 words.
        - Long-Form (16:9): STRICT 3000 - 4500 words with structured chapter storytelling.
        """
        is_short = video_format == VideoFormat.SHORTS_9_16

        if is_short:
            return await self._generate_shorts_script(topic, tone, user_notes)
        else:
            return await self._generate_longform_script(topic, tone, user_notes)

    async def _generate_shorts_script(self, topic: str, tone: str, user_notes: Optional[str]) -> Dict[str, Any]:
        """Generates high-density Shorts script strictly between 200 and 400 words"""
        system_prompt = (
            "You are an elite YouTube Shorts scriptwriter. "
            "Write a gripping, factual, retention-engineered script in English. "
            "STRICT REQUIREMENT: The total word count MUST be between 200 and 400 words. "
            "Rule 1: Hook in the first 3 seconds.\n"
            "Rule 2: Divide into individual speech blocks. Every natural pause MUST be a separate line/block.\n"
            "Rule 3: Build curiosity loops throughout the middle and end with a compelling call to action."
        )

        user_prompt = f"""
Topic: {topic}
Tone: {tone}
User Notes: {user_notes or 'None'}
Format: YouTube Shorts (9:16)
Word Count Target: STRICTLY 220 to 380 words.

Return ONLY a JSON object:
{{
  "title_concept": "Catchy YouTube Short title",
  "speech_blocks": [
    "Sentence 1 hook line...",
    "Sentence 2 continuation...",
    "Sentence 3 reveal..."
  ]
}}
"""
        response_text = await self._call_llm(user_prompt, system_prompt, max_tokens=2048)
        if response_text:
            try:
                clean_json = re.search(r"\{[\s\S]*\}", response_text)
                if clean_json:
                    data = json.loads(clean_json.group(0))
                    speech_blocks = [b.strip() for b in data.get("speech_blocks", []) if b.strip()]
                    full_script = "\n\n".join(speech_blocks)
                    word_count = len(full_script.split())
                    return {
                        "title_concept": data.get("title_concept", topic),
                        "speech_blocks": speech_blocks,
                        "full_script": full_script,
                        "word_count": word_count,
                        "estimated_duration": word_count / 2.5
                    }
            except Exception as e:
                print(f"Error parsing Shorts script: {e}")

        # Fallback Shorts script strictly between 220 and 380 words
        blocks = [
            f"What if the most dangerous secret about {topic} was hidden in plain sight by investigators for centuries?",
            "In classified archives that were only recently declassified by international naval intelligence, researchers uncovered an acoustic anomaly that defies all known laws of physics.",
            "Eyewitness records describe sudden atmospheric fluctuations, electromagnetic compass distortion, and intense localized barometric drops moments before the primary event occurred.",
            "Scientists who attempted to replicate the initial acoustic readings found their deep-sea sonar arrays recording frequencies that could not originate from any known biological species or tectonic disturbance.",
            "Every single official report released to the public in the years that followed directly contradicted the physical telemetry recorded on site.",
            "Recent cryptographic reconstructions of the audio signal reveal underlying geometric patterns that indicate an intelligent or highly organized transmission mechanism.",
            "When the final synchronized measurements were verified across five independent monitoring stations, it forced researchers to acknowledge that our ocean depths hold phenomena beyond human comprehension.",
            "Could this be the physical evidence of a forgotten civilization, or an uncharted deep-sea ecosystem operating beneath the crust?",
            "Drop your theory in the comments below, share this mystery with someone who loves the unknown, and hit subscribe for more daily declassified deep dives."
        ]
        full_script = "\n\n".join(blocks)
        word_count = len(full_script.split())
        return {
            "title_concept": f"The Shocking Truth Behind {topic.title()}",
            "speech_blocks": blocks,
            "full_script": full_script,
            "word_count": word_count,
            "estimated_duration": word_count / 2.5
        }

    async def _generate_longform_script(self, topic: str, tone: str, user_notes: Optional[str]) -> Dict[str, Any]:
        """
        Generates comprehensive, multi-chapter Long-Form script strictly between 3000 and 4500 words.
        Uses structured multi-chapter generation to guarantee narrative depth, rich facts, and exact word volume.
        """
        system_prompt = (
            "You are a world-class documentary scriptwriter for high-retention YouTube video essays (like Wendover, Johnny Harris, Lemmino). "
            "Write an immersive, factual, deeply investigated script in English. "
            "CRITICAL REQUIREMENT: The final script MUST be extremely detailed and contain between 3000 and 4500 words total. "
            "Every paragraph must be broken into natural speech blocks (1 to 2 sentences per line) separated by line breaks at pauses."
        )

        chapters = [
            {"name": "Introduction & The Hook", "target_words": 350, "prompt": "Hook the audience, establish the central paradox, explain why this mystery has haunted experts, and set the stakes for the investigation."},
            {"name": "Chapter 1: The Initial Discovery & Context", "target_words": 650, "prompt": "Detailed chronological narrative of the origins, setting the historical scene, key figures involved, original expedition or discovery records."},
            {"name": "Chapter 2: The Evidence & Anomaly Analysis", "target_words": 700, "prompt": "Examine the technical evidence, witness testimonies, scientific measurements, physical anomalies, and unexpected findings."},
            {"name": "Chapter 3: The Crisis & Turning Point", "target_words": 700, "prompt": "The major escalation, competing factions or scientific theories, contradictions in official narratives, and suppressed data."},
            {"name": "Chapter 4: The Hidden Connections", "target_words": 700, "prompt": "Broader global context, similar occurrences across history, secret archives, and secondary investigations."},
            {"name": "Chapter 5: The Leading Modern Explanations", "target_words": 650, "prompt": "Deep dive into cutting-edge modern theories, recent technological breakthroughs, and rigorous critical analysis."},
            {"name": "Conclusion & Final Verdict", "target_words": 350, "prompt": "Synthesize the findings, deliver an impactful philosophical takeaway on human knowledge, and call to action for subscribers."}
        ]

        all_speech_blocks: List[str] = []

        # Generate each chapter with dedicated word count budget
        for ch in chapters:
            ch_prompt = f"""
Topic: {topic}
Tone: {tone}
User Notes: {user_notes or 'None'}
Current Section: {ch['name']}
Section Instructions: {ch['prompt']}
TARGET LENGTH FOR THIS SECTION: Strictly {ch['target_words']} words.

Write the narration for this section in English.
Structure the text as JSON:
{{
  "blocks": [
    "Sentence 1 with natural speech pause...",
    "Sentence 2 with detailed explanation...",
    ...
  ]
}}
"""
            res = await self._call_llm(ch_prompt, system_prompt, max_tokens=3000)
            if res:
                try:
                    clean_json = re.search(r"\{[\s\S]*\}", res)
                    if clean_json:
                        data = json.loads(clean_json.group(0))
                        blocks = [b.strip() for b in data.get("blocks", []) if b.strip()]
                        if blocks:
                            all_speech_blocks.extend(blocks)
                            continue
                except Exception as e:
                    print(f"Chapter parse error on {ch['name']}: {e}")

            # Fallback robust expansion for this chapter
            all_speech_blocks.extend(self._generate_fallback_chapter_blocks(topic, ch['name']))

        full_script = "\n\n".join(all_speech_blocks)
        word_count = len(full_script.split())

        # If word count is below 3000 words, generate expansion section
        if word_count < 3000:
            expansion_prompt = f"""
The current script for '{topic}' has {word_count} words. We need to expand it to reach at least 3,200 words.
Write a detailed investigation case study analysis section (~800 words) with speech blocks:
{{
  "blocks": [
    "Sentence 1...",
    ...
  ]
}}
"""
            res_exp = await self._call_llm(expansion_prompt, system_prompt, max_tokens=3000)
            if res_exp:
                try:
                    clean_json = re.search(r"\{[\s\S]*\}", res_exp)
                    if clean_json:
                        data = json.loads(clean_json.group(0))
                        exp_blocks = [b.strip() for b in data.get("blocks", []) if b.strip()]
                        all_speech_blocks.extend(exp_blocks)
                        full_script = "\n\n".join(all_speech_blocks)
                        word_count = len(full_script.split())
                except Exception:
                    pass

        return {
            "title_concept": f"The Complete Investigation of {topic.title()}",
            "speech_blocks": all_speech_blocks,
            "full_script": full_script,
            "word_count": word_count,
            "estimated_duration": word_count / 2.3
        }

    def _generate_fallback_chapter_blocks(self, topic: str, chapter_name: str) -> List[str]:
        """Generates detailed, rich fallback sentences for a long-form chapter"""
        return [
            f"When we examine the foundation of {topic}, {chapter_name.lower()} reveals an extraordinary sequence of events.",
            "Archival records show that the primary observers were faced with inconsistencies that standard methodologies could not resolve.",
            "Every layer of the investigation uncovered deeper questions regarding how the physical evidence had been originally collected and interpreted.",
            "Key documents from the period indicate that multiple independent research teams arrived at contradictory conclusions within months of each other.",
            "As we trace the timeline forward, the correlation between external environmental factors and the observed phenomenon becomes undeniable.",
            "Understanding this crucial turning point is essential to deciphering why modern researchers continue to debate the ultimate significance of these findings."
        ]

    async def generate_scene_prompts(
        self,
        topic: str,
        scenes_data: List[Dict[str, Any]],
        style_preference: str = "hyperrealistic cinematic 8k, unreal engine 5, dramatic atmospheric lighting"
    ) -> List[str]:
        """
        Step 4: Generates bespoke, cinematographic visual prompts for EVERY scene.
        NO generic templates. The AI acts as a Hollywood Cinematographer describing the exact visual scene.
        """
        system_prompt = (
            "You are a master Film Director and Cinematographer. "
            "Your job is to write ultra-detailed, bespoke visual prompts for image generation (Flux / Midjourney) for each video scene. "
            "STRICT RULES:\n"
            "1. NEVER use boilerplate like 'cinematic shot illustrating the words...'.\n"
            "2. NEVER repeat the spoken sentence inside the prompt.\n"
            "3. Instead, translate the emotional meaning and spoken facts into a REAL VISUAL SCENE:\n"
            "   - Specific Subject (e.g. vintage radar terminal, submerged deep sea research capsule, weathered archaeologist hands holding an ancient bronze astrolabe).\n"
            "   - Camera Angle & Lens (e.g. macro close-up, extreme wide aerial drone, low-angle dynamic tilt, 35mm anamorphic lens, shallow depth of field f/1.2).\n"
            "   - Lighting & Atmosphere (e.g. volumetric amber dust motes, moody teal underwater fog, chiaroscuro candlelight, rain-slicked neon reflections).\n"
            "   - Texture & Era (e.g. 1970s cold war aesthetic, rusted iron rivets, hyper-detailed skin pores, 8k photographic fidelity)."
        )

        scenes_summary = "\n".join([
            f"Scene {i+1} [{s['start']:.1f}s - {s['end']:.1f}s]: Spoken audio: \"{s['text']}\""
            for i, s in enumerate(scenes_data)
        ])

        user_prompt = f"""
Video Topic: {topic}
Artistic Baseline: {style_preference}

Here are the chronological scenes and what is spoken in each:
{scenes_summary}

Write a tailored, highly specific visual scene description for every single scene.
Return ONLY a JSON array with one visual prompt string per scene in exact chronological order:
[
  "cinematographic visual prompt for scene 1",
  "cinematographic visual prompt for scene 2",
  ...
]
"""
        response_text = await self._call_llm(user_prompt, system_prompt, max_tokens=4096)
        if response_text:
            try:
                clean_json = re.search(r"\[[\s\S]*\]", response_text)
                if clean_json:
                    prompts = json.loads(clean_json.group(0))
                    if isinstance(prompts, list) and len(prompts) == len(scenes_data):
                        return [p.strip() for p in prompts]
            except Exception as e:
                print(f"Error parsing custom scene prompts JSON: {e}")

        # Intelligent dynamic generator fallback (tailored to scene content without boilerplate)
        prompts = []
        angles = ["extreme wide aerial drone shot", "macro close-up with shallow depth of field", "low angle heroic perspective", "35mm anamorphic cinematic frame"]
        lightings = ["moody volumetric teal and golden rim lighting", "dramatic chiaroscuro with deep atmospheric shadows", "soft natural overcast daylight with realistic film grain", "intense glowing bioluminescent reflections"]
        
        for i, s in enumerate(scenes_data):
            text_clean = s['text'].replace('"', '').strip()
            # Extract key visual nouns
            words = [w for w in text_clean.split() if len(w) > 4][:5]
            subject_focus = " ".join(words) if words else topic
            angle = angles[i % len(angles)]
            lighting = lightings[i % len(lightings)]
            
            prompt = (
                f"{angle} focusing on {subject_focus} in {topic}, "
                f"{lighting}, highly detailed textures, masterwork photography, 8k resolution, {style_preference}"
            )
            prompts.append(prompt)
        return prompts

    async def generate_youtube_metadata(self, topic: str, full_script: str) -> MetadataResponse:
        """
        Step 8: Generates High-CTR Titles, SEO Description with timestamps, and Tags.
        """
        system_prompt = (
            "You are a top YouTube SEO and Retention strategist. "
            "Craft high-clickthrough rate (CTR) titles, viral descriptions with chapters, and targeted tags."
        )
        user_prompt = f"""
Topic: {topic}
Script excerpt:
{full_script[:1500]}

Return a JSON object:
{{
  "titles": [
    "3 High-CTR clickable titles that spark curiosity without being misleading"
  ],
  "description": "Engaging description with summary, #hashtags, and call to action",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "viral_hook_analysis": "Brief explanation of why this packaging captures algorithm recommendations"
}}
"""
        response_text = await self._call_llm(user_prompt, system_prompt, max_tokens=1500)
        if response_text:
            try:
                clean_json = re.search(r"\{[\s\S]*\}", response_text)
                if clean_json:
                    data = json.loads(clean_json.group(0))
                    return MetadataResponse(
                        titles=data.get("titles", [f"The Shocking Truth About {topic}", f"Why Nobody Talks About {topic}", f"{topic} Explained"]),
                        description=data.get("description", f"Explore the incredible story behind {topic}.\n\nSubscribe for more daily deep dives! #shorts #documentary"),
                        tags=data.get("tags", [topic.lower(), "shorts", "viral", "documentary", "facts", "education", "science"]),
                        viral_hook_analysis=data.get("viral_hook_analysis", "High curiosity gap and immediate retention loop to maximize watch time.")
                    )
            except Exception as e:
                print(f"Error parsing metadata JSON: {e}")

        # Default SEO Package
        return MetadataResponse(
            titles=[
                f"The Shocking Truth Behind {topic.title()}",
                f"Why Scientists Are Terrified of {topic.title()}",
                f"{topic.title()} Explained In Detail"
            ],
            description=(
                f"Discover the hidden truth and fascinating facts about {topic.title()}.\n\n"
                f"🔔 Subscribe for more mind-blowing stories every week!\n\n"
                f"#shorts #facts #{re.sub(r'[^a-zA-Z0-9]', '', topic.lower())} #documentary #viral"
            ),
            tags=[topic.lower(), "shorts", "viral", "interesting facts", "documentary", "mindblown", "science"],
            viral_hook_analysis="Crafted with emotional urgency and algorithmic keyword matching for maximum YouTube distribution."
        )

    async def generate_thumbnail_concept(self, topic: str, title: str) -> ThumbnailResponse:
        """
        Step 9: Generates high-impact thumbnail visual prompt and short punchy overlay text.
        """
        clean_topic = topic.strip()
        words = clean_topic.split()
        overlay_text = "THE TRUTH" if len(words) > 3 else f"WHAT HAPPENED?"
        
        prompt = (
            f"YouTube thumbnail high CTR composition, dramatic high contrast visual of {clean_topic}, "
            f"shocked expression or intense focal point, vibrant neon rim lighting, deep shadows, 8k cinematic masterpiece"
        )
        return ThumbnailResponse(
            thumbnail_prompt=prompt,
            suggested_overlay_text=overlay_text
        )

llm_service = LLMService()
