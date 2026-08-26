import os
import random
import urllib.parse
import asyncio
from pathlib import Path
from typing import Optional, List
import httpx
from PIL import Image, ImageDraw, ImageFont
from backend.app.config import settings
from backend.app.models.schemas import SceneModel, VideoFormat

class ImageService:
    def __init__(self):
        self.fal_key = settings.FAL_KEY
        self.openai_key = settings.OPENAI_API_KEY

    async def generate_scene_image(
        self,
        scene: SceneModel,
        output_dir: Path,
        video_format: VideoFormat = VideoFormat.SHORTS_9_16,
        force_regenerate: bool = False
    ) -> str:
        """
        Step 5: Generates illustration image for a specific scene and saves locally.
        Returns local file path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        img_filename = f"{scene.id}.jpg"
        local_path = output_dir / img_filename

        if local_path.exists() and not force_regenerate and local_path.stat().st_size > 1000:
            scene.local_image_path = str(local_path)
            return str(local_path)

        # Dimensions based on format
        if video_format == VideoFormat.SHORTS_9_16:
            width, height = 720, 1280
        else:
            width, height = 1280, 720

        prompt = scene.visual_prompt or f"cinematic high quality visual for {scene.speech_text}"
        seed = random.randint(1000, 999999)

        # 1. Try Pollinations.ai (Flux)
        try:
            clean_prompt = prompt.replace("\n", " ").strip()
            encoded_prompt = urllib.parse.quote(clean_prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"
            
            async with httpx.AsyncClient(timeout=40.0) as client:
                res = await client.get(url)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(local_path, "wb") as f:
                        f.write(res.content)
                    scene.local_image_path = str(local_path)
                    scene.image_url = url
                    return str(local_path)
        except Exception as e:
            print(f"Pollinations generation failed for scene {scene.id}: {e}")

        # 2. Local Fallback Procedural Generator (Ensures pipeline never fails)
        self._generate_fallback_image(local_path, width, height, scene.index, scene.speech_text)
        scene.local_image_path = str(local_path)
        return str(local_path)

    def _generate_fallback_image(self, path: Path, width: int, height: int, index: int, text: str):
        """Creates an aesthetic cinematic gradient image with subtle atmospheric lighting"""
        # Palette gradients
        colors = [
            ((15, 23, 42), (30, 58, 138)),    # Deep ocean blue
            ((24, 24, 27), (88, 28, 135)),    # Cyberpunk purple
            ((12, 10, 9), (124, 45, 18)),     # Ember dark gold
            ((6, 78, 59), (15, 23, 42)),      # Dark emerald
        ]
        c1, c2 = colors[(index - 1) % len(colors)]
        
        img = Image.new("RGB", (width, height), color=c1)
        draw = ImageDraw.Draw(img)
        
        # Draw vertical gradient
        for y in range(height):
            ratio = y / height
            r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
            g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
            b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
            
        # Draw soft glowing center vignette
        center_x, center_y = width // 2, height // 2
        for r_offset in range(120, 0, -10):
            alpha = int(40 * (1 - r_offset / 120))
            draw.ellipse(
                [center_x - r_offset * 3, center_y - r_offset * 3, center_x + r_offset * 3, center_y + r_offset * 3],
                outline=(255, 255, 255, alpha)
            )

        img.save(path, quality=92)

    async def generate_all_scene_images(
        self,
        scenes: List[SceneModel],
        output_dir: Path,
        video_format: VideoFormat = VideoFormat.SHORTS_9_16
    ) -> List[SceneModel]:
        """Generates images for all scenes concurrently with a rate limiter"""
        semaphore = asyncio.Semaphore(3)  # 3 concurrent downloads

        async def worker(scene: SceneModel):
            async with semaphore:
                await self.generate_scene_image(scene, output_dir, video_format)

        await asyncio.gather(*[worker(s) for s in scenes])
        return scenes

image_service = ImageService()
