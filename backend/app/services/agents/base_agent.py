import re
import json
import base64
import asyncio
import httpx
from typing import Optional, Dict, Any, List, Union
from backend.app.config import settings
from backend.app.services.rate_limiter import gemini_rate_limiter

class BaseAgent:
    def __init__(self, agent_name: str, role_description: str):
        self.agent_name = agent_name
        self.role_description = role_description

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        json_mode: bool = False,
        temperature: float = 0.85,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """
        Executes an LLM call via Google Gemini API (primary) with Rate Limiting and Groq/OpenAI fallbacks.
        When json_mode is True, enables strict JSON output format.
        """
        gemini_key = settings.GEMINI_API_KEY
        groq_key = settings.GROQ_API_KEY
        openai_key = settings.OPENAI_API_KEY

        # 1. Primary: Google Gemini 3.6 / Flash
        if gemini_key:
            models_to_try = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-2.0-flash"]
            for model_name in models_to_try:
                try:
                    await gemini_rate_limiter.acquire()
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                    combined_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                    
                    gen_config: Dict[str, Any] = {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperature
                    }
                    if json_mode:
                        gen_config["responseMimeType"] = "application/json"

                    payload = {
                        "contents": [{"parts": [{"text": combined_prompt}]}],
                        "generationConfig": gen_config
                    }

                    async with httpx.AsyncClient(timeout=30.0) as client:
                        res = await client.post(url, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            candidates = data.get("candidates", [])
                            if candidates and "content" in candidates[0]:
                                return candidates[0]["content"]["parts"][0]["text"]
                        elif res.status_code == 429:
                            print(f"[{self.agent_name}] 429 Too Many Requests on {model_name}, applying 4s backoff...")
                            await asyncio.sleep(4.0)
                        else:
                            print(f"[{self.agent_name}] Gemini {model_name} HTTP {res.status_code}: {res.text[:140]}")
                except Exception as e:
                    print(f"[{self.agent_name}] Gemini API error ({model_name}): {e}")

        # 2. Backup: Groq Cloud API
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
                    "temperature": temperature
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[{self.agent_name}] Groq API error: {e}")

        # 3. Backup: OpenAI API
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
                    "temperature": temperature
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[{self.agent_name}] OpenAI API error: {e}")

        return None

    async def call_llm_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.85
    ) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """Calls LLM in JSON mode and parses the structured response automatically."""
        raw_text = await self.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=True,
            temperature=temperature
        )
        if not raw_text:
            return None

        try:
            return json.loads(raw_text)
        except Exception:
            # Fallback regex search for { ... } or [ ... ]
            try:
                array_match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", raw_text)
                if array_match:
                    return json.loads(array_match.group(0))
                
                obj_match = re.search(r"\{[\s\S]*\}", raw_text)
                if obj_match:
                    return json.loads(obj_match.group(0))
            except Exception as parse_err:
                print(f"[{self.agent_name}] JSON parse error: {parse_err}")
        return None

    async def call_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        json_mode: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Multimodal Gemini Vision Inspection:
        Sends an image frame together with an inspection prompt to verify B-Roll clips.
        """
        gemini_key = settings.GEMINI_API_KEY
        if not gemini_key:
            return None

        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        models_to_try = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-2.0-flash"]

        for model_name in models_to_try:
            try:
                await gemini_rate_limiter.acquire()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                
                parts: List[Dict[str, Any]] = [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": b64_data
                        }
                    }
                ]

                gen_config: Dict[str, Any] = {
                    "maxOutputTokens": 1024,
                    "temperature": 0.2
                }
                if json_mode:
                    gen_config["responseMimeType"] = "application/json"

                payload = {
                    "contents": [{"parts": parts}],
                    "generationConfig": gen_config
                }

                async with httpx.AsyncClient(timeout=25.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            text = candidates[0]["content"]["parts"][0]["text"]
                            try:
                                return json.loads(text)
                            except Exception:
                                match = re.search(r"\{[\s\S]*\}", text)
                                if match:
                                    return json.loads(match.group(0))
                    elif res.status_code == 429:
                        print(f"[{self.agent_name}] Vision 429 on {model_name}, waiting 4s...")
                        await asyncio.sleep(4.0)
            except Exception as e:
                print(f"[{self.agent_name}] Vision error on {model_name}: {e}")

        return None
