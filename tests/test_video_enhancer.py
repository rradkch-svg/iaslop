import os
import sys
import unittest
import tempfile
import shutil
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from video_enhancer import VideoResolutionEnhancer, DEFAULT_VIDEO_ENHANCER, find_ffmpeg_binary

class TestVideoResolutionEnhancer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ffmpeg_bin = find_ffmpeg_binary()
        self.enhancer = VideoResolutionEnhancer(target_width=1080, target_height=1920)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_dummy_video(self, width: int = 640, height: int = 360, duration: float = 1.5) -> str:
        out_p = os.path.join(self.test_dir, f"dummy_{width}x{height}.mp4")
        cmd = [
            self.ffmpeg_bin, "-y",
            "-f", "lavfi",
            "-i", f"color=c=red:s={width}x{height}:d={duration}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            out_p
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_p

    def test_dimensions_detection(self):
        """Verifica a leitura precisa das dimensões do vídeo com ffprobe."""
        vid = self._create_dummy_video(width=640, height=480)
        w, h = self.enhancer.get_video_dimensions(vid)
        self.assertEqual(w, 640)
        self.assertEqual(h, 480)

    def test_enhance_to_full_hd_916(self):
        """Verifica se um vídeo de qualquer resolução (ex: 640x360) é convertido para 1080x1920 Full HD."""
        vid_in = self._create_dummy_video(width=640, height=360, duration=1.0)
        vid_hd = os.path.join(self.test_dir, "output_hd.mp4")

        success, msg = self.enhancer.enhance_clip(vid_in, vid_hd, sharpen_strength=0.85, denoise=True)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(vid_hd))

        final_w, final_h = self.enhancer.get_video_dimensions(vid_hd)
        self.assertEqual(final_w, 1080)
        self.assertEqual(final_h, 1920)

    def test_filter_graph_construction(self):
        """Verifica a montagem correta da string de filtros Lanczos + Unsharp + Contrast."""
        graph = self.enhancer.build_enhancement_filter_graph(sharpen_strength=0.9, denoise=True, contrast_boost=1.06)
        self.assertIn("scale=1080*16/9:1920", graph)
        self.assertIn("crop=1080:1920", graph)
        self.assertIn("unsharp=", graph)
        self.assertIn("eq=contrast=1.06", graph)
        self.assertIn("fps=30", graph)

if __name__ == "__main__":
    unittest.main()
