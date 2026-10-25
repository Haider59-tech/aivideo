"""
Chand aur Jugnu - Video Maker UI
==================================
A small local website for making a video from clips + text.

What it does:
  1. You upload clips, one per scene. The website renames them
     automatically to Scene 1, Scene 2, Scene 3... in the order shown.
     You never have to rename files yourself.
  2. For each scene you type Urdu or English text and pick a voice.
  3. Press "Generate Video". The website:
       - makes a voice mp3 for each scene with Edge TTS (free, no key)
       - trims / holds each clip to match its voice length
       - adds a short pause between scenes
       - joins all scenes into one final mp4
  4. You preview it in the browser and download it.

Run it (first time only: create venv + install):
    python3 -m venv video-venv
    source video-venv/bin/activate
    pip install -r requirements.txt

Run it (every time after that):
    source video-venv/bin/activate
    python3 app.py
    # then open http://127.0.0.1:5000 in your browser
    # stop it with Ctrl+C in the terminal

Your clips, texts and final video stay in this folder
(uploads/, voices/, outputs/, scenes.json) after you shut down,
so you can close the browser, restart the app later, and continue.
"""

import asyncio
import json
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, render_template

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"
VOICES = BASE / "voices"
OUTPUTS = BASE / "outputs"
SCENES_FILE = BASE / "scenes.json"
for d in (UPLOADS, VOICES, OUTPUTS):
    d.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB per upload

VOICES_MAP = {
    "ur-PK-AsadNeural": "-8%",   # Urdu, male, calm storyteller
    "ur-PK-UzmaNeural": "-8%",   # Urdu, female, formal
    "en-US-AriaNeural": "+0%",   # English, female
    "en-US-GuyNeural": "+0%",    # English, male
}

job = {"state": "idle", "step": "", "message": "", "output": None}


def load_scenes():
    if SCENES_FILE.exists():
        try:
            data = json.loads(SCENES_FILE.read_text())
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return [{"id": str(uuid.uuid4()), "clip": None, "text": "", "voice": "ur-PK-AsadNeural"}]


def save_scenes(scenes):
    SCENES_FILE.write_text(json.dumps(scenes, ensure_ascii=False, indent=2))


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{result.stderr[-2000:]}")
    return result


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,r_frame_rate",
               "-show_entries", "format=duration", "-of", "json", str(path)])
    data = json.loads(out.stdout)
    stream = data["streams"][0] if data.get("streams") else {}
    # audio check
    out2 = run(["ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index", "-of", "json", str(path)])
    has_audio = bool(json.loads(out2.stdout).get("streams"))
    return {
        "duration": float(data["format"]["duration"]),
        "width": int(stream.get("width", 1280)),
        "height": int(stream.get("height", 720)),
        "has_audio": has_audio,
    }


def make_voice(text, voice_name, out_path):
    import edge_tts
    rate = VOICES_MAP.get(voice_name, "+0%")

    async def _go():
        communicate = edge_tts.Communicate(text, voice_name, rate=rate)
        await communicate.save(str(out_path))

    asyncio.run(_go())


def generate_video(scenes, pause_seconds, output_name):
    """Runs in a background thread. Updates the global `job` dict."""
    global job
    try:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("ffmpeg is not found. Install it first: brew install ffmpeg")
        usable = [s for s in scenes if s.get("clip")]
        if not usable:
            raise RuntimeError("No clips uploaded yet. Add a scene and upload a clip first.")
        if not output_name.lower().endswith(".mp4"):
            output_name += ".mp4"
        output_name = Path(output_name).name  # no folders in the name

        job.update({"state": "running", "step": "Preparing", "message": f"{len(usable)} scenes", "output": None})
        matched = []
        for i, scene in enumerate(usable, start=1):
            clip_path = UPLOADS / scene["clip"]
            if not clip_path.exists():
                raise RuntimeError(f"Scene {i}: clip file is missing. Upload it again.")
            job.update({"step": f"Scene {i} of {len(usable)}", "message": "Making voice and matching video length"})
            text = (scene.get("text") or "").strip()
            info = probe(clip_path)
            matched_path = OUTPUTS / f"matched{i}.mp4"

            # Video filter: same size + same fps for every scene, so concat works.
            vfilter = ("scale=1280:720:force_original_aspect_ratio=decrease,"
                       "pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30")

            if text:
                voice_name = scene.get("voice", "ur-PK-AsadNeural")
                voice_path = VOICES / f"scene{i}.mp3"
                try:
                    make_voice(text, voice_name, voice_path)
                except Exception as e:
                    raise RuntimeError(f"Scene {i}: voice failed ({voice_name}). "
                                       f"Check your internet and voice choice. Error: {e}")
                voice_len = probe(voice_path)["duration"]
                target = voice_len + (pause_seconds if i != len(usable) else 0)
                run(["ffmpeg", "-y", "-i", str(clip_path), "-i", str(voice_path),
                     "-filter_complex",
                     f"[0:v]{vfilter},tpad=stop_mode=clone:stop_duration={target:.2f}[v];"
                     f"[1:a]apad=whole_dur={target:.2f}[a]",
                     "-map", "[v]", "-map", "[a]", "-t", f"{target:.2f}",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                     str(matched_path)])
            else:
                # No text: keep the clip as it is (with its own sound if it has one).
                if info["has_audio"]:
                    run(["ffmpeg", "-y", "-i", str(clip_path),
                         "-vf", vfilter, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                         "-c:a", "aac", str(matched_path)])
                else:
                    run(["ffmpeg", "-y", "-i", str(clip_path),
                         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                         "-vf", vfilter, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                         "-c:a", "aac", "-shortest", str(matched_path)])
            matched.append(matched_path)

        job.update({"step": "Joining scenes", "message": "Making the final video"})
        concat_path = OUTPUTS / "concat.txt"
        concat_path.write_text("".join(f"file '{p.name}'\n" for p in matched))
        final_path = OUTPUTS / output_name
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path),
             "-c", "copy", str(final_path)])
        total = probe(final_path)["duration"]
        job.update({"state": "done", "step": "Done",
                    "message": f"Final video is {total:.1f} seconds long.",
                    "output": output_name})
    except Exception as e:
        job.update({"state": "error", "step": "Error", "message": str(e), "output": None})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scenes", methods=["GET"])
def api_get_scenes():
    return jsonify(load_scenes())


@app.route("/api/scenes", methods=["POST"])
def api_save_scenes():
    scenes = request.get_json(force=True)
    if not isinstance(scenes, list):
        return jsonify({"error": "scenes must be a list"}), 400
    # Keep only safe fields, and keep clip filenames that really exist.
    clean = []
    for s in scenes:
        clip = s.get("clip")
        if clip and not (UPLOADS / Path(clip).name).exists():
            clip = None
        clean.append({
            "id": str(s.get("id") or uuid.uuid4()),
            "clip": Path(clip).name if clip else None,
            "text": str(s.get("text") or ""),
            "voice": str(s.get("voice") or "ur-PK-AsadNeural"),
        })
    save_scenes(clean)
    return jsonify(clean)


@app.route("/api/upload/<scene_id>", methods=["POST"])
def api_upload(scene_id):
    if "clip" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["clip"]
    if not f.filename:
        return jsonify({"error": "Empty file"}), 400
    ext = Path(f.filename).suffix.lower() or ".mp4"
    if ext not in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
        return jsonify({"error": f"Video type {ext} is not supported. Use mp4 if possible."}), 400
    filename = f"{uuid.uuid4()}{ext}"
    f.save(UPLOADS / filename)
    scenes = load_scenes()
    for s in scenes:
        if s["id"] == scene_id:
            # Delete the old clip for this scene, so uploads stay tidy.
            if s.get("clip") and (UPLOADS / s["clip"]).exists():
                (UPLOADS / s["clip"]).unlink()
            s["clip"] = filename
    save_scenes(scenes)
    return jsonify({"clip": filename})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    if job["state"] == "running":
        return jsonify({"error": "Generation is already running"}), 400
    data = request.get_json(force=True) or {}
    scenes = load_scenes()
    pause = float(data.get("pause", 0.5))
    output_name = str(data.get("output_name") or "final_video.mp4")
    job.update({"state": "running", "step": "Starting", "message": "", "output": None})
    threading.Thread(target=generate_video, args=(scenes, pause, output_name), daemon=True).start()
    return jsonify({"started": True})


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(job)


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOADS, filename)


@app.route("/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUTS, filename, as_attachment=False)


@app.route("/download/<path:filename>")
def download_output(filename):
    return send_from_directory(OUTPUTS, filename, as_attachment=True)


if __name__ == "__main__":
    # Locally: http://127.0.0.1:5000
    # On a host like Render: host 0.0.0.0 and the PORT they give you.
    port = int(os.environ.get("PORT", 5000))
    print(f"Open in your browser: http://127.0.0.1:{port}")
    print("Stop with Ctrl+C")
    app.run(host="0.0.0.0", port=port, debug=False)
