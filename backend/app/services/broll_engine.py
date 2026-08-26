import os
import re
import json
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Set
import httpx
from backend.app.config import settings
from backend.app.models.schemas import SceneModel, VideoFormat
from backend.app.services.agents.reviewer_agent import reviewer_agent
from backend.app.services.image_service import image_service
from backend.app.utils.ffmpeg_helper import run_ffmpeg, generate_ken_burns_clip, get_media_duration

class BRollEngine:
    """
    B-Roll Scraping, Temporal Segment Scanning & Multimodal Auditing Engine:
    1. Searches authentic HD video footage via YouTube (yt-dlp) and Pexels.
    2. Executes 4-point temporal segment scanning (0.25D, 0.50D, 0.70D, 0.85D).
    3. Crops and formats to 1080x1920 vertical (9:16) with Lanczos interpolation.
    4. Audits frames with ReviewerAgent (Gemini Vision) to enforce Anti-Vlog policy.
    5. Seamlessly falls back to Hyper-Realistic AI Images + Ken Burns motion if needed.
    """
    def __init__(self, max_search_results: int = 5):
        self.max_search_results = max_search_results

    def _clean_query(self, query: str) -> str:
        clean = re.sub(r'[^\w\s-]', '', query).strip()
        words = clean.split()
        return " ".join(words[:6])

    def search_youtube_candidates(self, query: str, max_results: int = 4) -> List[Dict[str, Any]]:
        """Searches YouTube using yt-dlp metadata extraction without downloading full videos"""
        clean_q = self._clean_query(query)
        search_query = f"ytsearch{max_results}:{clean_q} 4k hd footage -vlog -gameplay"
        
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--default-search", "ytsearch",
            "--max-downloads", str(max_results),
            "--no-playlist",
            "--skip-download",
            "--no-warnings",
            "--quiet",
            search_query
        ]
        candidates = []
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        video_id = item.get("id")
                        duration = float(item.get("duration", 0))
                        title = item.get("title", "")
                        # Accept videos between 15s and 1200s (20 mins)
                        if video_id and 15 <= duration <= 1200:
                            candidates.append({
                                "id": video_id,
                                "title": title,
                                "duration": duration,
                                "url": f"https://www.youtube.com/watch?v={video_id}"
                            })
                    except Exception:
                        pass
        except Exception as e:
            print(f"[BRollEngine] yt-dlp search error on '{clean_q}': {e}")

        return candidates

    def download_raw_video(self, video_url: str, output_path: Path) -> bool:
        """Downloads 720p/1080p MP4 video stream via yt-dlp"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and output_path.stat().st_size > 100000:
            return True

        cmd = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(output_path),
            "--no-playlist",
            "--no-warnings",
            "--quiet",
            video_url
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
            return res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 100000
        except Exception as e:
            print(f"[BRollEngine] Download error on {video_url}: {e}")
            return False

    def extract_lanczos_segment(
        self,
        raw_video_path: Path,
        output_clip_path: Path,
        start_time: float,
        duration: float
    ) -> bool:
        """
        Extracts temporal segment and converts 16:9 horizontal to 1080x1920 vertical (9:16)
        using Pan & Scan with 3-lobe Lanczos interpolation.
        """
        output_clip_path.parent.mkdir(parents=True, exist_ok=True)
        # Pan & Scan Lanczos filter
        filter_expr = "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1,fps=30"

        args = [
            "-ss", f"{start_time:.2f}",
            "-i", str(raw_video_path),
            "-t", f"{duration:.2f}",
            "-vf", filter_expr,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-an",
            str(output_clip_path)
        ]
        ok, _ = run_ffmpeg(args)
        return ok and output_clip_path.exists() and output_clip_path.stat().st_size > 20000

    async def search_and_process_broll(
        self,
        query: str,
        target_duration: float,
        seen_ids: Set[str],
        output_clip_path: Path,
        global_topic: str,
        scene_fala: str,
        temp_dir: Path
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Searches YouTube, applies 4-point segment scanning, and validates with ReviewerAgent.
        """
        candidates = self.search_youtube_candidates(query, max_results=4)
        if not candidates:
            return False, None, None

        sample_ratios = [0.25, 0.50, 0.70, 0.85]

        for cand in candidates:
            video_id = cand["id"]
            if video_id in seen_ids:
                continue

            title = cand["title"]
            # 1. Pre-filter title heuristically
            approved_title, reason = reviewer_agent.pre_filter_title(title, global_topic)
            if not approved_title:
                continue

            # 2. Download raw video
            raw_vid_path = temp_dir / f"raw_{video_id}.mp4"
            ok_down = self.download_raw_video(cand["url"], raw_vid_path)
            if not ok_down:
                continue

            seen_ids.add(video_id)
            total_d = cand["duration"] or get_media_duration(raw_vid_path)
            if total_d <= 0:
                continue

            # 3. 4-point Smart Segment Scanning
            for ratio in sample_ratios:
                start_t = ratio * total_d
                if start_t + target_duration > total_d:
                    start_t = max(0.0, total_d - target_duration - 1.0)

                temp_clip = temp_dir / f"scan_{video_id}_{int(start_t)}.mp4"
                extracted = self.extract_lanczos_segment(
                    raw_video_path=raw_vid_path,
                    output_clip_path=temp_clip,
                    start_time=start_t,
                    duration=target_duration
                )
                if not extracted:
                    continue

                # 4. Gemini Vision Multimodal Review
                verdict = await reviewer_agent.inspect_clip(
                    clip_path=temp_clip,
                    global_topic=global_topic,
                    scene_fala=scene_fala,
                    video_title=title
                )

                if verdict.get("aprovado", False) and verdict.get("score", 0) >= 6.5:
                    # Approved! Copy to output_clip_path
                    if output_clip_path.exists():
                        output_clip_path.unlink()
                    temp_clip.rename(output_clip_path)
                    return True, video_id, verdict

        return False, None, None

    async def render_scene_clip_hybrid(
        self,
        scene: SceneModel,
        global_topic: str,
        output_clip_path: Path,
        temp_dir: Path,
        seen_ids: Set[str]
    ) -> bool:
        """
        Hybrid Scene Processing:
        1. Tries B-Roll scraping from YouTube with Gemini Vision inspection.
        2. If unapproved or offline, generates hyper-realistic 9:16 AI image + Ken Burns clip.
        """
        target_dur = max(scene.duration, 1.0)
        query = scene.visual_prompt or f"{global_topic} {scene.speech_text}"
        
        # 1. Try B-Roll Video Scraping
        try:
            ok, vid_id, verdict = await self.search_and_process_broll(
                query=query,
                target_duration=target_dur,
                seen_ids=seen_ids,
                output_clip_path=output_clip_path,
                global_topic=global_topic,
                scene_fala=scene.speech_text,
                temp_dir=temp_dir
            )
            if ok and output_clip_path.exists():
                print(f"[BRollEngine] Scene {scene.id}: B-Roll Approved ({vid_id}) - Score: {verdict.get('score')}")
                return True
        except Exception as e:
            print(f"[BRollEngine] B-Roll processing error on scene {scene.id}: {e}")

        # 2. Fallback: AI Image Generation + Ken Burns Animation
        print(f"[BRollEngine] Scene {scene.id}: Falling back to Ken Burns AI image illustration...")
        images_dir = temp_dir.parent / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        img_path = await image_service.generate_scene_image(
            scene=scene,
            output_dir=images_dir,
            video_format=VideoFormat.SHORTS_9_16
        )

        if img_path and Path(img_path).exists():
            success = generate_ken_burns_clip(
                image_path=Path(img_path),
                output_path=output_clip_path,
                duration=target_dur,
                width=1080,
                height=1920,
                motion_type=scene.motion_type,
                fps=30
            )
            return success

        return False

    async def process_all_scenes_hybrid(
        self,
        scenes: List[SceneModel],
        global_topic: str,
        project_dir: Path
    ) -> List[Path]:
        """
        Processes all scenes in parallel with rate-limited concurrency.
        Returns ordered list of final 1080x1920 scene clip paths.
        """
        temp_dir = project_dir / "video" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        seen_ids: Set[str] = set()
        semaphore = asyncio.Semaphore(2)  # 2 concurrent download/vision streams
        rendered_clips: List[Optional[Path]] = [None] * len(scenes)

        async def worker(idx: int, sc: SceneModel):
            clip_path = temp_dir / f"final_{sc.id}_clip.mp4"
            async with semaphore:
                ok = await self.render_scene_clip_hybrid(
                    scene=sc,
                    global_topic=global_topic,
                    output_clip_path=clip_path,
                    temp_dir=temp_dir,
                    seen_ids=seen_ids
                )
                if ok and clip_path.exists():
                    rendered_clips[idx] = clip_path

        tasks = [worker(i, scene) for i, scene in enumerate(scenes)]
        await asyncio.gather(*tasks)

        # Filter and return existing clips
        return [c for c in rendered_clips if c is not None and c.exists()]

broll_engine = BRollEngine()
