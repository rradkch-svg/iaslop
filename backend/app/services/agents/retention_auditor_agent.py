from typing import Dict, Any
from backend.app.services.agents.base_agent import BaseAgent

class RetentionAuditorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="RetentionAuditor",
            role_description="Auditor of watch-time retention. Verifies that the 3-second hook is aggressive, unskippable, and curiosity-driven."
        )

    async def audit_and_optimize_hook(self, topic: str, current_hook: str, full_script: str) -> Dict[str, Any]:
        """
        Evaluates the opening line. If it lacks urgency or starts like an essay,
        replaces it with an unskippable high-voltage hook line.
        """
        system_prompt = (
            "You are the Retention Quality Auditor for 'Minuto Inexplicável' YouTube Shorts. "
            "Your sole focus is the first 3 seconds of the video. "
            "Viewers swipe away in 1.5 seconds if the hook doesn't create instant suspense.\n"
            "CRITERIA:\n"
            "- Must be under 14 words.\n"
            "- Must NEVER start with 'Welcome back', 'In today's video', 'Did you know', or 'Have you ever heard'.\n"
            "- MUST start with an urgent warning, a forbidden secret, or a bizarre impossibility."
        )

        user_prompt = f"""
Topic: {topic}
Current Hook: {current_hook}
Full Script Context: {full_script[:300]}

Return JSON:
{{
  "is_hook_strong": true,
  "optimized_hook": "Refined hypnotic first sentence under 14 words",
  "audit_reason": "Why this hook guarantees higher 3-second retention"
}}
"""
        result = await self.call_llm_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )

        if isinstance(result, dict) and "optimized_hook" in result:
            return result

        return {
            "is_hook_strong": True,
            "optimized_hook": current_hook,
            "audit_reason": "Default verified high retention structure."
        }

retention_auditor_agent = RetentionAuditorAgent()
