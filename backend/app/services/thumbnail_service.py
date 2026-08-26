import os
import random
import urllib.parse
from pathlib import Path
from typing import Optional
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from backend.app.models.schemas import ThumbnailResponse
from backend.app.services.llm_service import llm_service

class ThumbnailService:
    async def generate_thumbnail(
        self,
        topic: str,
        title: str,
        output_dir: Path,
        custom_overlay_text: Optional[str] = None
    ) -> ThumbnailResponse:
        """
        Step 9: Generates high-impact thumbnail image and adds punchy text overlay.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        local_thumb_path = output_dir / "thumbnail.jpg"

        concept = await llm_service.generate_thumbnail_concept(topic, title)
        overlay_text = custom_overlay_text or concept.suggested_overlay_text

        width, height = 1280, 720
        seed = random.randint(1000, 999999)
        encoded_prompt = urllib.parse.quote(concept.thumbnail_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=turbo&nologo=true&seed={seed}"

        # Download or create base image
        base_img_path = output_dir / "thumb_base.jpg"
        downloaded = False
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(url)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(base_img_path, "wb") as f:
                        f.write(res.content)
                    downloaded = True
        except Exception as e:
            print(f"Thumbnail download failed: {e}")

        # Open image or fallback
        if downloaded and base_img_path.exists():
            img = Image.open(base_img_path).convert("RGB")
            if img.size != (width, height):
                img = img.resize((width, height), Image.Resampling.LANCZOS)
        else:
            img = Image.new("RGB", (width, height), color=(15, 23, 42))
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, width, height], fill=(20, 24, 40))

        # Enhance contrast for high CTR
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.25)
        color_enhancer = ImageEnhance.Color(img)
        img = color_enhancer.enhance(1.20)

        # Composite punchy text overlay
        draw = ImageDraw.Draw(img)
        
        # Draw dark gradient banner on the left/top for text readability
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        for x in range(width // 2):
            alpha = int(180 * (1 - (x / (width // 2))))
            overlay_draw.line([(x, 0), (x, height)], fill=(0, 0, 0, alpha))
        
        img.paste(overlay, (0, 0), overlay)
        draw = ImageDraw.Draw(img)

        # Draw overlay text
        display_text = overlay_text.upper()
        font_size = 76
        
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("Arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        # Text position
        pos_x = 60
        pos_y = height // 2 - 40

        # Draw heavy black shadow / border
        shadow_offsets = [(-4, -4), (4, -4), (-4, 4), (4, 4), (0, 5), (5, 0), (-5, 0), (0, -5)]
        for ox, oy in shadow_offsets:
            draw.text((pos_x + ox, pos_y + oy), display_text, font=font, fill=(0, 0, 0))

        # Draw vibrant yellow foreground text
        draw.text((pos_x, pos_y), display_text, font=font, fill=(255, 230, 0))

        # Save final thumbnail
        img.save(local_thumb_path, quality=95)

        concept.thumbnail_url = url
        concept.local_thumbnail_path = str(local_thumb_path)
        return concept

thumbnail_service = ThumbnailService()
