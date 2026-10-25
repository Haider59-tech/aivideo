# Video Maker UI - deployable container (Render / Railway / Fly.io)
# This is what Netlify cannot do: a real Python server + ffmpeg, running all the time.
FROM python:3.12-slim

# ffmpeg is not in the Python image by default, so install it here.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY templates/ templates/

# Make sure the folders exist even on a fresh deploy.
RUN mkdir -p uploads voices outputs

# Render / Railway give you a PORT. Gunicorn must listen on it.
# Timeout is long on purpose: a long video can take minutes to render.
CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 600 --workers 1 --threads 2
