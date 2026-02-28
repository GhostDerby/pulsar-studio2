import os
import io
import logging
import uuid
import torch
from flask import Flask, request, jsonify
from google.cloud import storage
from diffusers import StableDiffusionXLPipeline, AutoencoderKL
from rembg import remove

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("node-c")

BUCKET_NAME = os.environ.get("BUCKET_NAME")
pipe = None


def load_model():
    global pipe
    if pipe:
        return
    logger.info("🔌 Loading SDXL...")
    vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        vae=vae,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
    )
    if torch.cuda.is_available():
        pipe.to("cuda")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ready" if pipe else "loading"}), (200 if pipe else 503)


@app.route("/predict", methods=["POST"])
def predict():
    if not pipe:
        load_model()

    req = request.get_json(force=True)
    instance = req["instances"][0]
    prompt = instance.get("prompt", "Product")
    job_id = instance.get("job_id", str(uuid.uuid4()))

    image = pipe(prompt=prompt, num_inference_steps=20).images[0]
    image = remove(image)

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"outputs/{job_id}.png")

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    blob.upload_from_file(img_byte_arr, content_type="image/png")
    return jsonify({"predictions": [{"image_uri": f"gs://{BUCKET_NAME}/outputs/{job_id}.png"}]})


if __name__ == "__main__":
    load_model()
    app.run(host="0.0.0.0", port=int(os.environ.get("AIP_HTTP_PORT", 8080)))
