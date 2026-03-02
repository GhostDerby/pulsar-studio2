import os
import json
import time
import uuid
import logging
from typing import Any, Dict, List

from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from shared.pricing_engine import PricingEngine
from shared.contracts import JobSpec, SceneSpec, PricingSpec

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("node-a")

LOCAL_MOCK = os.environ.get("LOCAL_MOCK", "0") == "1"

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "pulsar-studio-prod")
REGION = os.environ.get("REGION", "us-central1")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "pulsar-studio-assets")
TOPIC_NAME = os.environ.get("PUBSUB_TOPIC", "pulsar-jobs")
LOCAL_JOBS_DIR = os.environ.get("LOCAL_JOBS_DIR", "./tmp/jobs")

if not LOCAL_MOCK:
    from google.cloud import pubsub_v1, storage

pricing = PricingEngine()


def gcs_job_prefix(job_id: str) -> str:
    return f"jobs/{job_id}"


def gcs_job_spec_path(job_id: str) -> str:
    return f"{gcs_job_prefix(job_id)}/job.json"


# ── Local mock helpers ──────────────────────────────────────────────
def save_json_locally(job_id: str, payload: Dict[str, Any]) -> str:
    job_dir = os.path.join(LOCAL_JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    path = os.path.join(job_dir, "job.json")
    with open(path, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("[MOCK] Saved job spec → %s", path)
    return f"file://{os.path.abspath(path)}"


# ── GCS helpers (real mode) ─────────────────────────────────────────
def upload_json_to_gcs(bucket_name: str, blob_path: str, payload: Dict[str, Any]) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json")
    return f"gs://{bucket_name}/{blob_path}"


def publish_job_message(job_id: str, stage: str, spec_uri: str) -> None:
    if LOCAL_MOCK:
        logger.info("[MOCK] Pub/Sub skipped — stage=%s job=%s", stage, job_id)
        return
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    message = {
        "job_id": job_id,
        "bucket": BUCKET_NAME,
        "stage": stage,
        "spec_uri": spec_uri,
    }
    publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
    logger.info("Published Pub/Sub message: %s", message)


def mock_scene_plan(product_name: str) -> List[SceneSpec]:
    prompts = [
        f"professional product photography of {product_name}, dramatic neon reflections, macro, ultra sharp, 9:16",
        f"{product_name} close-up, raindrops, rugged tech vibe, cinematic lighting, 9:16",
        f"{product_name} lifestyle shot, vibrant colors, high contrast, brazil vibe, 9:16",
    ]
    motions = ["zoom_in", "orbit", "pan"]
    scenes: List[SceneSpec] = []
    for i, (p, m) in enumerate(zip(prompts, motions), start=1):
        scenes.append(SceneSpec(id=i, hook="HOOK", prompt=p, motion=m))
    return scenes


@app.route("/create_job", methods=["POST"])
def create_job():
    data = request.get_json(force=True) or {}
    product_name = data.get("product_name", "Unknown Product")
    mode = str(data.get("mode", "engineering")).lower()
    market = str(data.get("market", "BR")).upper()

    scenes = mock_scene_plan(product_name)
    target_margin = 0.60 if mode == "hollywood" else 0.50
    financials = pricing.calculate_job_budget(mode, len(scenes), target_margin)

    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    job_spec = JobSpec(
        job_id=job_id,
        product_name=product_name,
        market=market,
        mode=mode,
        scenes=scenes,
        pricing=PricingSpec(
            currency=financials.currency,
            estimated_cogs=financials.total_cogs,
            suggested_price=financials.suggested_price,
            margin_target=target_margin,
        ),
    )

    # ── Persist job spec ────────────────────────────────────────────
    if LOCAL_MOCK:
        spec_uri = save_json_locally(job_id, job_spec.to_dict())
    else:
        spec_uri = upload_json_to_gcs(BUCKET_NAME, gcs_job_spec_path(job_id), job_spec.to_dict())

    publish_job_message(job_id=job_id, stage="job_created", spec_uri=spec_uri)

    return jsonify(
        {
            "status": "dispatched",
            "job_id": job_id,
            "spec_uri": spec_uri,
            "price": financials.suggested_price,
            "currency": financials.currency,
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bucket": BUCKET_NAME, "topic": TOPIC_NAME, "local_mock": LOCAL_MOCK}), 200


if __name__ == "__main__":
    logger.info("Starting Node A (LOCAL_MOCK=%s)", LOCAL_MOCK)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
