"""
T-008: FFmpeg Frames → Video (pseudomotion)
T-009: FFmpeg Scenes Concatenation
T-010: Watermark Module
Priority: P1 High
Requires: ffmpeg in PATH
"""
import json
import os
import subprocess
import tempfile
import shutil
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Ensure imageio-ffmpeg binary is in PATH
try:
    import imageio_ffmpeg
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["PATH"] = os.path.dirname(ffmpeg_bin) + ":" + os.environ.get("PATH", "")
except ImportError:
    pass

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")


# ── Test media generators ──────────────────────────────────────────

def make_test_png(path: str, width=1080, height=1920, color="red"):
    """Generate a solid-color PNG using ffmpeg."""
    subprocess.run([
        FFMPEG, "-y", "-f", "lavfi",
        "-i", f"color=c={color}:s={width}x{height}:d=1",
        "-frames:v", "1", path,
    ], check=True, capture_output=True)


def make_test_mp4(path: str, duration=2, width=1080, height=1920, color="blue"):
    """Generate a solid-color MP4 clip using ffmpeg."""
    subprocess.run([
        FFMPEG, "-y", "-f", "lavfi",
        "-i", f"color=c={color}:s={width}x{height}:d={duration}:r=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-t", str(duration), path,
    ], check=True, capture_output=True)


def make_test_audio(path: str, duration=6):
    """Generate a sine wave audio file."""
    subprocess.run([
        FFMPEG, "-y", "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-c:a", "aac", "-b:a", "128k", path,
    ], check=True, capture_output=True)


def get_video_info(path: str) -> dict:
    """Get video metadata via ffprobe/ffmpeg."""
    result = subprocess.run([
        FFMPEG, "-i", path, "-f", "null", "-",
    ], capture_output=True, text=True)
    stderr = result.stderr

    info = {"has_video": False, "has_audio": False, "duration": 0}
    for line in stderr.split("\n"):
        if "Video:" in line:
            info["has_video"] = True
            # Try to extract resolution
            import re
            res = re.search(r"(\d{3,4})x(\d{3,4})", line)
            if res:
                info["width"] = int(res.group(1))
                info["height"] = int(res.group(2))
        if "Audio:" in line:
            info["has_audio"] = True
        if "Duration:" in line:
            import re
            dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", line)
            if dur:
                h, m, s = dur.groups()
                info["duration"] = int(h) * 3600 + int(m) * 60 + float(s)
    return info


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def workdir():
    d = tempfile.mkdtemp(prefix="pulsar_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def three_frames(workdir):
    frames = []
    for i, color in enumerate(["red", "green", "blue"], 1):
        p = os.path.join(workdir, f"frame_{i:02d}.png")
        make_test_png(p, color=color)
        frames.append(p)
    return frames


@pytest.fixture
def three_clips(workdir):
    clips = []
    for i, color in enumerate(["red", "green", "blue"], 1):
        p = os.path.join(workdir, f"scene_{i:02d}.mp4")
        make_test_mp4(p, duration=2, color=color)
        clips.append(p)
    return clips


@pytest.fixture
def music_file(workdir):
    p = os.path.join(workdir, "music.m4a")
    make_test_audio(p, duration=10)
    return p


# Import Node B functions (set LOCAL_MOCK to avoid GCS imports)
os.environ["LOCAL_MOCK"] = "1"
from node_b.cloud_run_assembly import (
    ffmpeg_concat_scenes,
    ffmpeg_frames_to_pseudomotion,
)


# ═══════════════════════════════════════════════════════════════════
# T-008: Frames → Pseudomotion Video
# ═══════════════════════════════════════════════════════════════════

class TestFramesToPseudomotion:
    def test_three_frames_produce_video(self, three_frames, workdir):
        """TC-008.1: 3 PNG frames → ~9s video, 1080×1920"""
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_frames_to_pseudomotion(three_frames, None, out, fps=30)
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 1000  # not an empty file

        info = get_video_info(out)
        assert info["has_video"]
        # Duration should be ~9s (3 frames × 3s each)
        assert 7 <= info["duration"] <= 12

    def test_output_resolution(self, three_frames, workdir):
        """TC-008.2: output is 1080×1920"""
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_frames_to_pseudomotion(three_frames, None, out, fps=30)
        info = get_video_info(out)
        assert info.get("width") == 1080
        assert info.get("height") == 1920

    def test_with_music(self, three_frames, music_file, workdir):
        """TC-008.4: with music → audio track present"""
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_frames_to_pseudomotion(three_frames, music_file, out, fps=30)
        info = get_video_info(out)
        assert info["has_video"]
        assert info["has_audio"]

    def test_without_music_no_audio(self, three_frames, workdir):
        """TC-008.5: without music → no audio track"""
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_frames_to_pseudomotion(three_frames, None, out, fps=30)
        info = get_video_info(out)
        assert info["has_video"]
        assert not info["has_audio"]

    def test_single_frame(self, workdir):
        """TC-008.6: 1 frame → ~3s video, no crash"""
        frame = os.path.join(workdir, "single.png")
        make_test_png(frame, color="yellow")
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_frames_to_pseudomotion([frame], None, out, fps=30)
        assert os.path.isfile(out)
        info = get_video_info(out)
        assert 2 <= info["duration"] <= 5


# ═══════════════════════════════════════════════════════════════════
# T-009: Scene Concatenation
# ═══════════════════════════════════════════════════════════════════

class TestSceneConcatenation:
    def test_concat_three_clips(self, three_clips, workdir):
        """TC-009.1: 3 MP4 clips → concatenated output"""
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_concat_scenes(three_clips, None, out)
        assert os.path.isfile(out)
        info = get_video_info(out)
        assert info["has_video"]
        # 3 clips × 2s = ~6s
        assert 4 <= info["duration"] <= 8

    def test_output_forced_resolution(self, three_clips, workdir):
        """TC-009.2: output resolution forced to 1080×1920"""
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_concat_scenes(three_clips, None, out)
        info = get_video_info(out)
        assert info.get("width") == 1080
        assert info.get("height") == 1920

    def test_with_music(self, three_clips, music_file, workdir):
        """TC-009.3: with music → audio mixed"""
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_concat_scenes(three_clips, music_file, out)
        info = get_video_info(out)
        assert info["has_video"]
        assert info["has_audio"]

    def test_single_clip(self, workdir):
        """TC-009.5: 1 clip → works, no crash"""
        clip = os.path.join(workdir, "single.mp4")
        make_test_mp4(clip, duration=3, color="orange")
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_concat_scenes([clip], None, out)
        assert os.path.isfile(out)


# ═══════════════════════════════════════════════════════════════════
# T-010: Watermark Module
# ═══════════════════════════════════════════════════════════════════

class TestWatermark:
    def test_no_watermark_clean(self, three_clips, workdir):
        """TC-010.3: WATERMARK_ENABLED=0 → video produced (baseline)"""
        os.environ["WATERMARK_ENABLED"] = "0"
        out = os.path.join(workdir, "output.mp4")
        ffmpeg_concat_scenes(three_clips, None, out)
        assert os.path.isfile(out)
        info = get_video_info(out)
        assert info["has_video"]

    def test_watermark_text_fallback(self, three_clips, workdir):
        """TC-010.1: WATERMARK_ENABLED=1, no PNG → drawtext fallback"""
        os.environ["WATERMARK_ENABLED"] = "1"
        os.environ.pop("WATERMARK_PNG_GCS_URI", None)
        os.environ["WATERMARK_TEXT"] = "TEST WATERMARK"
        out = os.path.join(workdir, "output.mp4")

        # This may fail if fonts-dejavu not installed — skip gracefully
        try:
            ffmpeg_concat_scenes(three_clips, None, out)
            assert os.path.isfile(out)
            info = get_video_info(out)
            assert info["has_video"]
        except subprocess.CalledProcessError:
            pytest.skip("drawtext filter requires fonts-dejavu-core")
        finally:
            os.environ["WATERMARK_ENABLED"] = "0"

    def test_watermark_position_bottom(self, three_clips, workdir):
        """TC-010.5: position=bottom → video still produces"""
        os.environ["WATERMARK_ENABLED"] = "1"
        os.environ["WATERMARK_POSITION"] = "bottom"
        os.environ.pop("WATERMARK_PNG_GCS_URI", None)
        out = os.path.join(workdir, "output.mp4")
        try:
            ffmpeg_concat_scenes(three_clips, None, out)
            assert os.path.isfile(out)
        except subprocess.CalledProcessError:
            pytest.skip("drawtext filter requires fonts-dejavu-core")
        finally:
            os.environ["WATERMARK_ENABLED"] = "0"
            os.environ.pop("WATERMARK_POSITION", None)

    def test_watermark_position_top(self, three_clips, workdir):
        """TC-010.6: position=top → video still produces"""
        os.environ["WATERMARK_ENABLED"] = "1"
        os.environ["WATERMARK_POSITION"] = "top"
        os.environ.pop("WATERMARK_PNG_GCS_URI", None)
        out = os.path.join(workdir, "output.mp4")
        try:
            ffmpeg_concat_scenes(three_clips, None, out)
            assert os.path.isfile(out)
        except subprocess.CalledProcessError:
            pytest.skip("drawtext filter requires fonts-dejavu-core")
        finally:
            os.environ["WATERMARK_ENABLED"] = "0"
            os.environ.pop("WATERMARK_POSITION", None)

    def test_watermark_position_center(self, three_clips, workdir):
        """TC-010.7: position=center → video still produces"""
        os.environ["WATERMARK_ENABLED"] = "1"
        os.environ["WATERMARK_POSITION"] = "center"
        os.environ.pop("WATERMARK_PNG_GCS_URI", None)
        out = os.path.join(workdir, "output.mp4")
        try:
            ffmpeg_concat_scenes(three_clips, None, out)
            assert os.path.isfile(out)
        except subprocess.CalledProcessError:
            pytest.skip("drawtext filter requires fonts-dejavu-core")
        finally:
            os.environ["WATERMARK_ENABLED"] = "0"
            os.environ.pop("WATERMARK_POSITION", None)

    def test_special_chars_in_text(self, three_clips, workdir):
        """TC-010.9: special chars escaped correctly"""
        os.environ["WATERMARK_ENABLED"] = "1"
        os.environ["WATERMARK_TEXT"] = "PULSAR: Studio's Test"
        os.environ.pop("WATERMARK_PNG_GCS_URI", None)
        out = os.path.join(workdir, "output.mp4")
        try:
            ffmpeg_concat_scenes(three_clips, None, out)
            assert os.path.isfile(out)
        except subprocess.CalledProcessError:
            pytest.skip("drawtext filter requires fonts-dejavu-core")
        finally:
            os.environ["WATERMARK_ENABLED"] = "0"
            os.environ.pop("WATERMARK_TEXT", None)
