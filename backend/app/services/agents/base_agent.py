import re
import json
import httpx
from typing import Optional, Dict, Any, List
from backend.app.config import settings

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
        Executes an LLM call via Google Gemini API (primary) with Groq and OpenAI fallback.
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

                    async with httpx.AsyncClient(timeout=45.0) as client:
                        res = await client.post(url, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            candidates = data.get("candidates", [])
                            if candidates and "content" in candidates[0]:
                                return candidates[0]["content"]["parts"][0]["text"]
                        else:
                            print(f"[{self.agent_name}] Gemini {model_name} HTTP {res.status_code}: {res.text[:160]}")
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

                async with httpx.AsyncClient(timeout=45.0) as client:
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

                async with httpx.AsyncClient(timeout=45.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        return data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[{self.agent_name}] OpenAI error: {e}")

        return None

    async def call_llm_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.85
    ) -> Optional[Any]:
        """Calls LLM in JSON mode and parses the result into Python dict or list"""
        raw = await self.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=True,
            temperature=temperature
        )
        if not raw:
            return None
        
        # Parse JSON directly or extract from markdown
        try:
            return json.loads(raw)
        except Exception:
            try:
                clean_json = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", raw)
                if clean_json:
                    return json.loads(clean_json.group(0))
            except Exception as e:
                print(f"[{self.agent_name}] JSON parse error: {e}\nRaw output: {raw[:200]}")
        return None
