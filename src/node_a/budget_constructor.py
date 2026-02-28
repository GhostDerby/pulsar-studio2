import os
import json
import time
import logging
from typing import Any, Dict, List

from flask import Flask, request, jsonify
from google.cloud import pubsub_v1, storage

from shared.pricing_engine import PricingEngine
from shared.contracts import JobSpec, SceneSpec, PricingSpec

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("node-a")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "brazil-studio-v2")
REGION = os.environ.get("REGION", "us-central1")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "brazil-studio-assets")
TOPIC_NAME = os.environ.get("PUBSUB_TOPIC", "pulsar-jobs")

pricing = PricingEngine()


def gcs_job_prefix(job_id: str) -> str:
    return f"jobs/{job_id}"


def gcs_job_spec_path(job_id: str) -> str:
    return f"{gcs_job_prefix(job_id)}/job.json"


def upload_json_to_gcs(bucket_name: str, blob_path: str, payload: Dict[str, Any]) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(payload, ensure_ascii=False, indent=2), content_type="application/json")
    return f"gs://{bucket_name}/{blob_path}"


def publish_job_message(job_id: str, stage: str, spec_uri: str) -> None:
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

    job_id = f"job_{int(time.time())}"

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
    return jsonify({"status": "ok", "bucket": BUCKET_NAME, "topic": TOPIC_NAME}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
