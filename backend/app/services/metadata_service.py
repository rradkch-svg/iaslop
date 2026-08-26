from backend.app.models.schemas import MetadataResponse
from backend.app.services.llm_service import llm_service

class MetadataService:
    async def generate_package(self, topic: str, full_script: str) -> MetadataResponse:
        """
        Step 8: Generates High-CTR Titles, SEO Description, Tags and retention strategy.
        """
        return await llm_service.generate_youtube_metadata(topic, full_script)

metadata_service = MetadataService()
