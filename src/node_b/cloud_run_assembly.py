import os
import json
import base64
import logging
import tempfile
import subprocess
from typing import Any, Dict, List, Optional

from flask import Flask, request
from google.cloud import storage, pubsub_v1

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("node-b")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "brazil-studio-v2")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "brazil-studio-assets")
TOPIC_NAME = os.environ.get("PUBSUB_TOPIC", "pulsar-jobs")


def parse_pubsub_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    msg = envelope.get("message") or {}
    data_b64 = msg.get("data")
    if not data_b64:
        return {}
    return json.loads(base64.b64decode(data_b64).decode("utf-8"))


def gcs_list_prefix(bucket: storage.Bucket, prefix: str) -> List[storage.Blob]:
    return list(bucket.list_blobs(prefix=prefix))


def gcs_download_blobs(bucket: storage.Bucket, blobs: List[storage.Blob], local_dir: str) -> List[str]:
    paths = []
    for b in blobs:
        if b.name.endswith("/"):
            continue
        filename = os.path.basename(b.name)
        local_path = os.path.join(local_dir, filename)
        b.download_to_filename(local_path)
        paths.append(local_path)
    return sorted(paths)


def gcs_upload_file(bucket: storage.Bucket, local_path: str, blob_path: str, content_type: str) -> str:
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(local_path, content_type=content_type)
    return f"gs://{bucket.name}/{blob_path}"


def gcs_upload_json(bucket: storage.Bucket, blob_path: str, payload: Dict[str, Any]) -> str:
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json")
    return f"gs://{bucket.name}/{blob_path}"


def download_watermark_from_gcs(gcs_uri: str) -> str:
    if not gcs_uri.startswith("gs://"):
        raise ValueError("Invalid GCS URI (expected gs://bucket/path)")

    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name = parts[0]
    blob_path = parts[1]

    local_path = "/tmp/watermark.png"
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.download_to_filename(local_path)
    return local_path


def publish_stage(job_id: str, stage: str, spec_uri: str) -> None:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    message = {"job_id": job_id, "bucket": BUCKET_NAME, "stage": stage, "spec_uri": spec_uri}
    publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
    logger.info("Published stage=%s for job=%s", stage, job_id)


def ffmpeg_concat_scenes(scene_paths: List[str], music_path: Optional[str], out_path: str) -> None:
    """
    Concatenate MP4 scene fragments. Optional music. Optional watermark (PNG preferred, text fallback).
    Watermark is ENV-controlled.
    """
    watermark_enabled = os.environ.get("WATERMARK_ENABLED", "0") == "1"
    wm_png_uri = os.environ.get("WATERMARK_PNG_GCS_URI")  # gs://.../watermark.png
    wm_text = os.environ.get("WATERMARK_TEXT", "PULSAR STUDIO — DEMO")
    wm_opacity = float(os.environ.get("WATERMARK_OPACITY", "0.25"))
    wm_position = os.environ.get("WATERMARK_POSITION", "bottom")  # top|center|bottom
    wm_scale_percent = float(os.environ.get("WATERMARK_SCALE_PERCENT", "12"))

    safe_margin_enabled = os.environ.get("WATERMARK_SAFE_MARGIN", "1") == "1"
    bottom_margin = int(os.environ.get("WATERMARK_BOTTOM_MARGIN", "300"))
    top_margin = int(os.environ.get("WATERMARK_TOP_MARGIN", "200"))

    # Safe Y placement (TikTok/Reels UI safe areas)
    if wm_position == "top":
        y_expr = f"{top_margin}" if safe_margin_enabled else "20"
    elif wm_position == "center":
        y_expr = "(H-h)/2"
    else:
        y_expr = f"H-h-{bottom_margin}" if safe_margin_enabled else "H-h-40"

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        for p in scene_paths:
            f.write(f"file '{p}'\n")
        list_path = f.name

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path]

    # Input indexes:
    # 0: concatenated video
    # 1: watermark (optional)
    # 2: music (optional, depending on watermark)
    wm_local = None
    if watermark_enabled and wm_png_uri:
        wm_local = download_watermark_from_gcs(wm_png_uri)
        cmd += ["-i", wm_local]

    if music_path:
        cmd += ["-i", music_path]

    # Build filter graph
    # Always enforce final format.
    base = "[0:v]scale=1080:1920,format=yuv420p"

    filters = []
    maps = ["-map", "[v]"]

    # Watermark preference: PNG (overlay). If missing, fallback to drawtext.
    if watermark_enabled and wm_local:
        # scale watermark relative to video height by percent
        # watermark stream is [1:v]
        # scale = -1 : ih*percent/100
        filters.append(
            f"{base}[basev];"
            f"[1:v]scale=-1:ih*{wm_scale_percent}/100,format=rgba,colorchannelmixer=aa={wm_opacity}[wm];"
            f"[basev][wm]overlay=x=(W-w)/2:y={y_expr}:format=auto[v]"
        )
    elif watermark_enabled:
        safe_text = wm_text.replace(":", "\\:").replace("'", "\\'")
        # use DejaVuSans (install via fonts-dejavu-core in docker)
        filters.append(
            f"{base},drawtext="
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='{safe_text}':"
            f"fontsize=56:"
            f"fontcolor=white@{wm_opacity}:"
            f"borderw=3:bordercolor=black@{min(wm_opacity+0.15, 1.0)}:"
            f"x=(w-text_w)/2:"
            f"y={y_expr}"
            f"[v]"
        )
    else:
        filters.append(f"{base}[v]")

    # Audio mapping
    if music_path:
        # music input index depends on whether watermark exists
        music_idx = 2 if (watermark_enabled and wm_local) else 1
        filters.append(f"[{music_idx}:a]volume=0.6[a]")
        maps += ["-map", "[a]", "-shortest"]

    filter_complex = ";".join(filters)

    cmd += [
        "-filter_complex", filter_complex,
        *maps,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
    ]

    if music_path:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    cmd += [out_path]

    logger.info("Running ffmpeg concat (watermark_enabled=%s)...", watermark_enabled)
    subprocess.run(cmd, check=True)


def ffmpeg_frames_to_pseudomotion(frame_paths: List[str], music_path: Optional[str], out_path: str, fps: int = 30) -> None:
    """
    Creates short zoompan clips from each PNG, then concatenates using ffmpeg_concat_scenes().
    Watermark/music handled in concat stage.
    """
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for i, frame in enumerate(frame_paths, start=1):
            clip = os.path.join(tmp, f"clip_{i:02d}.mp4")
            d = fps * 3  # 3 seconds per frame
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", frame,
                "-filter_complex", f"zoompan=z='min(zoom+0.0015,1.2)':d={d}:s=1080x1920,format=yuv420p",
                "-t", "3",
                "-r", str(fps),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                clip,
            ]
            subprocess.run(cmd, check=True)
            clips.append(clip)

        ffmpeg_concat_scenes(clips, music_path, out_path)


@app.route("/", methods=["POST"])
def receive_message():
    envelope = request.get_json(force=True) or {}
    payload = parse_pubsub_envelope(envelope)
    if not payload:
        return "Bad Request", 400

    job_id = payload.get("job_id")
    stage = payload.get("stage")
    spec_uri = payload.get("spec_uri") or ""
    bucket_name = payload.get("bucket", BUCKET_NAME)

    logger.info("Job=%s stage=%s", job_id, stage)

    # Simple v0.1: assemble only on assets_ready
    if stage != "assets_ready":
        return "OK", 200

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    job_prefix = f"jobs/{job_id}"
    scenes_prefix = f"{job_prefix}/scenes/"
    frames_prefix = f"{job_prefix}/frames/"
    audio_prefix = f"{job_prefix}/audio/"

    scenes = gcs_list_prefix(bucket, scenes_prefix)
    frames = gcs_list_prefix(bucket, frames_prefix)
    audio = gcs_list_prefix(bucket, audio_prefix)

    music_blob = None
    for b in audio:
        name = os.path.basename(b.name).lower()
        if name.endswith((".mp3", ".wav", ".m4a")) and "music" in name:
            music_blob = b
            break

    with tempfile.TemporaryDirectory() as workdir:
        music_path = None
        if music_blob:
            music_path = os.path.join(workdir, os.path.basename(music_blob.name))
            music_blob.download_to_filename(music_path)

        out_path = os.path.join(workdir, "video.mp4")

        try:
            if scenes:
                scene_paths = gcs_download_blobs(bucket, scenes, workdir)
                ffmpeg_concat_scenes(scene_paths, music_path, out_path)
            elif frames:
                frame_paths = gcs_download_blobs(bucket, frames, workdir)
                ffmpeg_frames_to_pseudomotion(frame_paths, music_path, out_path)
            else:
                raise RuntimeError("No scenes/ or frames/ found in GCS for this job")

            final_blob_path = f"{job_prefix}/final/video.mp4"
            final_uri = gcs_upload_file(bucket, out_path, final_blob_path, content_type="video/mp4")

            result = {
                "job_id": job_id,
                "status": "success",
                "final_video_uri": final_uri,
                "artifacts": {
                    "frames_uri": f"gs://{bucket_name}/{frames_prefix}",
                    "scenes_uri": f"gs://{bucket_name}/{scenes_prefix}",
                },
                "metrics": {},
                "errors": [],
            }
            gcs_upload_json(bucket, f"{job_prefix}/final/result.json", result)

            # Optional: publish done stage
            publish_stage(job_id, "done", spec_uri)

        except Exception as e:
            logger.exception("Assembly failed")
            err = str(e)
            result = {
                "job_id": job_id,
                "status": "failed",
                "final_video_uri": None,
                "artifacts": {},
                "metrics": {},
                "errors": [err],
            }
            gcs_upload_json(bucket, f"{job_prefix}/final/result.json", result)

    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
