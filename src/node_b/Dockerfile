FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY src/node_b/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/shared/ /app/shared/
ENV PYTHONPATH="${PYTHONPATH}:/app"

COPY src/node_b/cloud_run_assembly.py .
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 cloud_run_assembly:app
