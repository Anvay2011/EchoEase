# group_mode.py
# EchoEase Group Mode — record + apply pitch/volume/speed with SoundStretch

import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import subprocess
import os

# Globals
is_recording = False
_stop_event = threading.Event()
_thread = None
frames = []
samplerate = 16000
temp_file = "recorded.wav"
processed_file = "processed.wav"
final_file = "processed_final.wav"

# Parameters (set from frontend)
params = {"pitch": -2, "volume": 1.0, "speed": 1.0}

def set_parameters(pitch=-2, volume=1.0, speed=1.0):
    global params
    params = {"pitch": pitch, "volume": volume, "speed": speed}
    print(f"🎚️ Parameters set: {params}")

def adjust_volume(y, volume=1.0):
    return np.clip(y * volume, -1.0, 1.0)

def play_audio(y, sr):
    print("🔊 Playing processed audio...")
    sd.play(y, sr)
    sd.wait()

def process_with_soundstretch(input_file, output_file, semitones=0, speed=1.0):
    cmd = ["soundstretch", input_file, output_file, "-speech"]
    if semitones != 0:
        cmd.append(f"-pitch={semitones}")
    if speed != 1.0:
        tempo_percent = int((speed - 1.0) * 100)
        cmd.append(f"-tempo={tempo_percent}")
    subprocess.run(cmd, check=True)

# -------------------------
# Recording loop
# -------------------------
def _record_loop():
    global frames
    frames = []

    def callback(indata, frames_count, time, status):
        if status:
            print("⚠️", status)
        if not _stop_event.is_set():
            frames.append(indata.copy())

    print("🎤 Listening... (Group Mode)")
    with sd.InputStream(samplerate=samplerate, channels=1, dtype="float32", callback=callback):
        while not _stop_event.is_set():
            sd.sleep(100)

    # Save raw audio
    audio = np.concatenate(frames, axis=0)
    sf.write(temp_file, audio, samplerate)
    print(f"✅ Saved raw recording as {temp_file}")

    # Apply pitch/speed with soundstretch
    process_with_soundstretch(temp_file, processed_file, params["pitch"], params["speed"])

    # Adjust volume
    y, sr = sf.read(processed_file, dtype="float32")
    y = adjust_volume(y, params["volume"])
    sf.write(final_file, y, sr)
    print(f"💾 Saved final output as {final_file}")

    # Playback
    play_audio(y, sr)

# -------------------------
# Public API
# -------------------------
def start_recording():
    global is_recording, _thread, _stop_event
    if is_recording:
        print("⚠️ Group Mode already running.")
        return
    _stop_event.clear()
    is_recording = True
    _thread = threading.Thread(target=_record_loop, daemon=True)
    _thread.start()
    print("✅ Recording Started (Group Mode)")

def stop_recording():
    global is_recording, _stop_event, _thread
    if not is_recording:
        print("⚠️ Group Mode not running.")
        return
    _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
    is_recording = False
    print("✅ Recording Stopped (Group Mode)")
