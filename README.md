# Video Maker UI — simple commands

Copy this whole `video-maker` folder into your project folder on your Mac,
for example into `~/Documents/chand-aur-jugnu-test/video-maker`.

## First time only (one-time setup)

```bash
cd ~/Documents/chand-aur-jugnu-test/video-maker
python3 -m venv video-venv
source video-venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
```

`brew install ffmpeg` is only needed if ffmpeg is not already installed.
You already installed it once in your main project, so it should already be there.

## Every time after that (after shutdown, restart, new day)

These are the only commands you need, every time:

```bash
cd ~/Documents/chand-aur-jugnu-test/video-maker
source video-venv/bin/activate
python3 app.py
```

Then open this in your browser:

```
http://127.0.0.1:5000
```

To stop the website, go back to the terminal and press `Ctrl+C`.

You do NOT need to reinstall anything after shutdown. The venv,
Flask, edge-tts and ffmpeg stay installed.

## Making a video, step by step

1. Start the app with the 3 commands above, open the website.
2. Click **+ Add Scene** for each part of your story.
3. Upload a clip for each scene. It is renamed automatically to
   Scene 1, Scene 2, Scene 3… in the order shown. Use Move up / Move down
   to change the order.
4. Type Urdu or English narration for each scene, pick a voice.
   Leave the text empty if you want to keep the clip's own sound.
5. Set pause between scenes (0.5 seconds is the default) and the final
   file name (default: `final_video.mp4`).
6. Press **Generate Video** and wait. Do not close the terminal while
   it is working. Voice + ffmpeg takes a few minutes for a long video.
7. When it says Done, preview the video on the page and press
   **Download Final Video**.

## After shutdown — what is saved?

- `uploads/` — your uploaded clips
- `scenes.json` — your scene order, texts and voice choices
- `voices/` — voice mp3s made for each scene
- `outputs/` — matched scenes and your final video

So after a shutdown, start the app again with the 3 commands above,
and your last scenes and clips will still be there. Upload new clips
or edit the texts to make a new video, then Generate again.

## If something goes wrong

- "ffmpeg is not found" → run `brew install ffmpeg` in a terminal.
- "voice failed" → check your internet, and that the text is not empty
  for that scene. Edge TTS needs internet.
- Browser says "can't reach this site" → check the terminal: is
  `python3 app.py` still running? If not, run the 3 every-time commands again.
- A scene looks wrong → remove or replace just that scene's clip/text,
  then Generate again. You do not have to redo the whole video.
