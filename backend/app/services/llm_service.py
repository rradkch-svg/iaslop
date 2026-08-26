import os
import json
import re
import httpx
from typing import List, Dict, Any, Optional
from backend.app.config import settings
from backend.app.models.schemas import VideoFormat, MetadataResponse, ThumbnailResponse

class LLMService:
    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.gemini_key = settings.GEMINI_API_KEY
        self.anthropic_key = settings.ANTHROPIC_API_KEY

    async def _call_llm(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Calls available LLM API (Gemini, OpenAI) or returns None to use built-in engine"""
        # 1. Try Gemini if configured
        if self.gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}]
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                print(f"Gemini API error: {e}")

        # 2. Try OpenAI if configured
        if self.openai_key:
            try:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.openai_key}"}
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"OpenAI API error: {e}")

        return None

    async def generate_script(
        self,
        topic: str,
        video_format: VideoFormat = VideoFormat.SHORTS_9_16,
        tone: str = "engaging",
        target_duration: int = 45,
        user_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 1: Generates speech script in English, broken into speech blocks at each pause.
        """
        is_short = video_format == VideoFormat.SHORTS_9_16
        word_count = int((target_duration / 60) * 140)  # ~140 words per minute for punchy narration
        
        system_prompt = (
            "You are a master YouTube retention scriptwriter. "
            "Write high-retention, viral scripts in clear, engaging English. "
            "Rule 1: Hook the viewer in the first 3 seconds with a shocking statement or open loop.\n"
            "Rule 2: Divide the script into speech blocks separated by line breaks at EVERY natural pause or scene change.\n"
            "Rule 3: Keep sentences concise and impactful. No filler words."
        )

        user_prompt = f"""
Topic: {topic}
Format: {'YouTube Shorts (9:16 vertical)' if is_short else 'YouTube Long-form (16:9 horizontal)'}
Target Duration: ~{target_duration} seconds (~{word_count} words)
Tone: {tone}
User Notes: {user_notes or 'None'}

Return ONLY a valid JSON object with this exact structure:
{{
  "title_concept": "Catchy working title",
  "speech_blocks": [
    "Did you know that the deepest ocean sound ever recorded remains unexplained?",
    "In 1997, NOAA detected an ultra-low frequency sound nicknamed The Bloop.",
    "It was louder than any known animal and traveled over 5,000 kilometers.",
    "Scientists initially thought it was a giant squid or an unknown sea monster.",
    "Years later, they found it matched the acoustic signature of icequakes in Antarctica.",
    "Follow for more unexplained mysteries of our planet."
  ]
}}
"""
        response_text = await self._call_llm(user_prompt, system_prompt)
        
        if response_text:
            try:
                # Extract JSON from markdown blocks if present
                clean_json = re.search(r"\{[\s\S]*\}", response_text)
                if clean_json:
                    data = json.loads(clean_json.group(0))
                    full_script = "\n\n".join(data.get("speech_blocks", []))
                    return {
                        "title_concept": data.get("title_concept", topic),
                        "speech_blocks": data.get("speech_blocks", []),
                        "full_script": full_script,
                        "estimated_duration": len(full_script.split()) / 2.3
                    }
            except Exception as e:
                print(f"Error parsing LLM script JSON: {e}")

        # Built-in High-Retention Generator Fallback
        return self._generate_builtin_script(topic, is_short, target_duration, tone)

    def _generate_builtin_script(self, topic: str, is_short: bool, target_duration: int, tone: str) -> Dict[str, Any]:
        """Built-in heuristic generator for reliable offline/keyless script generation"""
        clean_topic = topic.strip().capitalize()
        
        if is_short:
            speech_blocks = [
                f"Most people have no idea this secret about {clean_topic} actually exists.",
                f"For decades, researchers noticed something strange happening beneath the surface.",
                f"Every single test revealed patterns that defied modern scientific logic.",
                f"When the final results were unveiled, it changed our entire perspective forever.",
                f"Drop a comment if you believe this is real, and subscribe for more daily breakthroughs."
            ]
        else:
            speech_blocks = [
                f"What if everything you thought you knew about {clean_topic} was completely wrong?",
                f"Today, we dive deep into one of the most intriguing phenomena of our modern world.",
                f"For years, experts have debated the true origins and mechanisms behind this mystery.",
                f"Recent discoveries have finally shed light on what actually happens behind the scenes.",
                f"The evidence points to a hidden pattern that connects technology, nature, and human perception.",
                f"As we examine the latest data, the implications for our future become unmistakably clear.",
                f"If you enjoyed this breakdown, make sure to hit like and subscribe for more deep dives."
            ]

        full_script = "\n\n".join(speech_blocks)
        return {
            "title_concept": f"The Hidden Truth Behind {clean_topic}",
            "speech_blocks": speech_blocks,
            "full_script": full_script,
            "estimated_duration": len(full_script.split()) / 2.3
        }

    async def generate_scene_prompts(
        self,
        topic: str,
        scenes_data: List[Dict[str, Any]],
        style_preference: str = "cinematic realistic 8k, unreal engine 5 render, dramatic lighting"
    ) -> List[str]:
        """
        Step 4: Generates rich visual illustration prompts for each scene [0:07] based on speech content.
        """
        system_prompt = (
            "You are a master Midjourney/Flux prompt engineer for YouTube visual storytelling. "
            "Generate descriptive, cinematographic image prompts that visually match the spoken narration for each scene. "
            "Avoid text in images. Focus on lighting, focal depth, subject, and atmosphere."
        )

        scenes_summary = "\n".join([
            f"Scene {i+1} [{s['start']:.1f}s - {s['end']:.1f}s]: \"{s['text']}\""
            for i, s in enumerate(scenes_data)
        ])

        user_prompt = f"""
Topic: {topic}
Visual Style: {style_preference}

Scenes:
{scenes_summary}

Return ONLY a JSON array with one visual prompt string per scene in exact chronological order:
[
  "cinematic wide shot of mysterious dark ocean trench with glowing blue bioluminescent particles, volumetric lighting, 8k, hyperrealistic",
  "dramatic close-up of underwater acoustic sonar equipment submerged in deep water, moody blue atmosphere, Unreal Engine 5 render",
  ...
]
"""
        response_text = await self._call_llm(user_prompt, system_prompt)
        if response_text:
            try:
                clean_json = re.search(r"\[[\s\S]*\]", response_text)
                if clean_json:
                    prompts = json.loads(clean_json.group(0))
                    if len(prompts) == len(scenes_data):
                        return prompts
            except Exception as e:
                print(f"Error parsing scene prompts JSON: {e}")

        # Fallback scene prompts generator
        prompts = []
        for i, s in enumerate(scenes_data):
            text_snippet = s['text'].replace('"', '').strip()
            prompt = (
                f"cinematic shot illustrating '{text_snippet}', "
                f"dramatic volumetric lighting, high detail, photorealistic, 8k resolution, {style_preference}"
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
Script:
{full_script}

Return a JSON object:
{{
  "titles": [
    "3 High-CTR clickable titles that spark curiosity without being misleading"
  ],
  "description": "Engaging description with summary, #hashtags, and call to action",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "viral_hook_analysis": "Brief 2-sentence explanation of why this packaging captures algorithm recommendations"
}}
"""
        response_text = await self._call_llm(user_prompt, system_prompt)
        if response_text:
            try:
                clean_json = re.search(r"\{[\s\S]*\}", response_text)
                if clean_json:
                    data = json.loads(clean_json.group(0))
                    return MetadataResponse(
                        titles=data.get("titles", [f"The Shocking Truth About {topic}", f"Why Nobody Talks About {topic}", f"{topic} Explained In 60 Seconds"]),
                        description=data.get("description", f"Explore the incredible story behind {topic}.\n\nSubscribe for more daily stories! #shorts #mystery"),
                        tags=data.get("tags", [topic.lower(), "shorts", "viral", "documentary", "facts", "education", "science"]),
                        viral_hook_analysis=data.get("viral_hook_analysis", "High curiosity gap and immediate retention loop to maximize YouTube Shorts feed watch time.")
                    )
            except Exception as e:
                print(f"Error parsing metadata JSON: {e}")

        # Default SEO Package
        return MetadataResponse(
            titles=[
                f"The Shocking Truth Behind {topic.title()}",
                f"Why Scientists Are Terrified of {topic.title()}",
                f"{topic.title()} Explained In 60 Seconds!"
            ],
            description=(
                f"Discover the hidden truth and fascinating facts about {topic.title()}.\n\n"
                f"🔔 Subscribe for more mind-blowing stories every day!\n\n"
                f"#shorts #facts #{re.sub(r'[^a-zA-Z0-9]', '', topic.lower())} #documentary #viral"
            ),
            tags=[topic.lower(), "shorts", "viral", "interesting facts", "documentary", "mindblown", "science"],
            viral_hook_analysis="Crafted with emotional urgency and algorithmic keyword matching for maximum YouTube search and suggested feed distribution."
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
