import os
import json
import sys
from google.cloud import pubsub_v1

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "brazil-studio-v2")
TOPIC_NAME = os.environ.get("PUBSUB_TOPIC", "pulsar-jobs")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "brazil-studio-assets")


def publish_stage(job_id: str, stage: str):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)

    message = {
        "job_id": job_id,
        "bucket": BUCKET_NAME,
        "stage": stage,
        "spec_uri": f"gs://{BUCKET_NAME}/jobs/{job_id}/job.json",
    }

    future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
    print(f"Published stage='{stage}' for job='{job_id}'")
    print(f"Message ID: {future.result()}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tools/publish_stage.py <job_id> <stage>")
        sys.exit(1)

    publish_stage(sys.argv[1], sys.argv[2])
