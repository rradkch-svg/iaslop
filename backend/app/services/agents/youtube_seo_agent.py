from typing import Dict, Any, List
from backend.app.models.schemas import MetadataResponse
from backend.app.services.agents.base_agent import BaseAgent

class YoutubeSEOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="YoutubeSEOStrategist",
            role_description="YouTube Shorts SEO & Algorithm strategist for Minuto Inexplicável. Maximizes CTR, algorithmic recommendations, and search indexing."
        )

    async def generate_seo_package(self, topic: str, full_script: str) -> MetadataResponse:
        """
        Generates 3 High-CTR titles (under 60 characters, curiosity gap),
        YouTube Shorts description with hashtags, and search tags.
        """
        system_prompt = (
            "You are the Lead Growth & SEO Strategist for the YouTube Shorts channel 'Minuto Inexplicável'. "
            "You generate viral titles that get 80%+ swipe-to-watch ratio, structured descriptions with relevant hashtags, "
            "and targeted algorithmic search tags."
        )

        user_prompt = f"""
Topic: {topic}
Script Context: {full_script[:400]}

Return JSON format:
{{
  "titles": [
    "Short viral title 1 (under 55 chars, intense mystery)",
    "Short viral title 2 (forbidden secret / anomaly)",
    "Short viral title 3 (question curiosity gap)"
  ],
  "description": "Engaging 2-paragraph YouTube Shorts description with search keywords and #Shorts #Curiosidades #MinutoInexplicavel #Misterio #FatosCuriosos",
  "tags": ["shorts", "minuto inexplicavel", "curiosidades", "misterios", "fatos bizarros", "unexplained mysteries", "viral shorts"],
  "viral_hook_analysis": "Strategic breakdown of why this video topic will trigger high algorithm recommendation"
}}
"""
        result = await self.call_llm_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.8
        )

        if isinstance(result, dict) and "titles" in result and isinstance(result["titles"], list):
            return MetadataResponse(
                titles=result["titles"][:3],
                description=result.get("description", f"O mistério inexplicável sobre {topic}. Inscreva-se no Minuto Inexplicável para mais fatos bizarros e curiosidades inacreditáveis todos os dias!\n\n#Shorts #MinutoInexplicavel #Curiosidades #Misterio"),
                tags=result.get("tags", ["shorts", "minuto inexplicavel", "curiosidades", "misterio"]),
                viral_hook_analysis=result.get("viral_hook_analysis", "Curiosity gap engineered for high retention.")
            )

        # Fallback SEO package
        clean_topic = topic.replace('"', '')
        return MetadataResponse(
            titles=[
                f"The Truth Behind {clean_topic} 😱",
                f"Scientists Can't Explain {clean_topic}...",
                f"The Forbidden Mystery of {clean_topic}"
            ],
            description=f"Descubra o segredo fascinante sobre {topic}. Fatos bizarros, mistérios inexplicáveis e anomalias científicas que ninguém te contou!\n\n🔔 Inscreva-se no Minuto Inexplicável para vídeos diários!\n\n#Shorts #MinutoInexplicavel #Curiosidades #Misterio #FatosBizarros",
            tags=["shorts", "minuto inexplicavel", "curiosidades", "misterio", "fatos bizarros", "ciencia", "historia"],
            viral_hook_analysis="High emotional shock factor and fast question-driven curiosity gap."
        )

youtube_seo_agent = YoutubeSEOAgent()
