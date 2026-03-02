#!/usr/bin/env python3
"""
Утиліта для ініціалізації структури GCS bucket.
Запуск: python tools/init_gcs_structure.py

Створює необхідні "папки" (пусті blob-и) в GCS bucket.
"""
import os
import sys

try:
    from google.cloud import storage
except ImportError:
    print("ERROR: google-cloud-storage not installed. Run: pip install google-cloud-storage")
    sys.exit(1)

BUCKET_NAME = os.environ.get("BUCKET_NAME", "pulsar-studio-assets")

FOLDERS = [
    "jobs/",
    "outputs/",
    "watermarks/",
    "frames/",
    "scenes/",
]


def main():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    if not bucket.exists():
        print(f"ERROR: Bucket '{BUCKET_NAME}' does not exist. Create it first.")
        sys.exit(1)

    for folder in FOLDERS:
        blob = bucket.blob(folder)
        if not blob.exists():
            blob.upload_from_string("", content_type="application/x-directory")
            print(f"  ✅ Created: gs://{BUCKET_NAME}/{folder}")
        else:
            print(f"  ⏭️  Exists:  gs://{BUCKET_NAME}/{folder}")

    print(f"\n✅ GCS structure ready in gs://{BUCKET_NAME}/")


if __name__ == "__main__":
    main()
