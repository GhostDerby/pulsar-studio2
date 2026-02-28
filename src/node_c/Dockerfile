FROM python:3.11-slim

WORKDIR /app
COPY src/node_c/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/shared/ /app/shared/
ENV PYTHONPATH="${PYTHONPATH}:/app"

COPY src/node_c/sdxl_worker.py .
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 sdxl_worker:app
