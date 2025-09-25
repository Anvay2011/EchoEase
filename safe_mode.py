# safe_mode.py
# EchoEase Safe Mode — faster-whisper + VAD + Gemini punctuation + ElevenLabs replay
# Fixed: better end-of-speech detection + flush on stop

import os
import threading
import re
import numpy as np
import sounddevice as sd
import webrtcvad
import collections
from faster_whisper import WhisperModel

# === 🔑 API KEY PLACEHOLDERS ===
GEMINI_API_KEY = ""
ELEVEN_API_KEY = ""
ELEVEN_VOICE_ID = ""   # your ElevenLabs voice ID
# ===============================

try:
    import google.generativeai as ai
except ImportError:
    ai = None

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import play
except ImportError:
    ElevenLabs = None
    play = None

# -------------------------
# Globals
# -------------------------
censor_list_ref = []
is_listening = False
_stop_event = threading.Event()
_thread = None
captured_texts = []
voiced_frames = []  # keep globally for flush

# Mic settings
samplerate = 16000
frame_ms = 30
frame_len = int(samplerate * frame_ms / 1000)

# Load Whisper model (tiny for speed)
print("Loading Whisper model (tiny)...")
model = WhisperModel("tiny", device="cpu", compute_type="int8")

# -------------------------
# Helpers
# -------------------------
eleven_client = None
def get_eleven_client():
    global eleven_client
    if eleven_client:
        return eleven_client
    api_key = ELEVEN_API_KEY or os.environ.get("ELEVEN_API_KEY")
    if not api_key:
        print("⚠️ ELEVEN_API_KEY not set. TTS disabled.")
        return None
    eleven_client = ElevenLabs(api_key=api_key)
    return eleven_client

gemini_model = None
def get_gemini_model():
    global gemini_model, ai
    if gemini_model:
        return gemini_model
    gemini_key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("⚠️ GEMINI_API_KEY not set. Punctuation disabled.")
        return None
    if ai is None:
        print("⚠️ google.generativeai not installed.")
        return None
    ai.configure(api_key=gemini_key)
    gemini_model = ai.GenerativeModel("gemini-2.0-flash-lite")
    return gemini_model

def set_censor_list_reference(ref):
    global censor_list_ref
    censor_list_ref = ref

def censor_text(text, banned_list):
    if not banned_list:
        return text
    pattern = r"\b(" + "|".join(map(re.escape, banned_list)) + r")\b"
    return re.sub(pattern, "beep", text, flags=re.IGNORECASE)

def transcribe_audio(samples: np.ndarray):
    """Helper: run Whisper + Gemini + Censor"""
    samples = np.ascontiguousarray(samples, dtype=np.float32)

    # Pad short samples (min 2s)
    min_len = samplerate * 2
    if len(samples) < min_len:
        pad = np.zeros(min_len - len(samples), dtype=np.float32)
        samples = np.concatenate([samples, pad])
        print(f"🔈 Padded audio to {len(samples)/samplerate:.2f}s for Whisper")

    # --- Whisper ---
    segments, _ = model.transcribe(samples, beam_size=1)
    raw_text = " ".join([seg.text for seg in segments]).strip()
    if not raw_text:
        print("❌ Whisper returned empty text")
        return None

    print(f"Speech-to-Text Output: {raw_text}")

    # --- Gemini punctuation ---
    punctuated = raw_text
    gem = get_gemini_model()
    if gem:
        try:
            response = gem.generate_content(
                f"DO NOT CHANGE THE WORDS. ONLY ADD PUNCTUATION. If the sentence is more than 5 words add one commas in between the sentence. :\n\n{raw_text}"
            )
            if hasattr(response, "text") and response.text:
                punctuated = response.text.strip()
            elif hasattr(response, "candidates") and response.candidates:
                parts = response.candidates[0].content.parts
                punctuated = "".join(
                    [p.text for p in parts if hasattr(p, "text")]
                ).strip()
            print(f"✨ Punctuated Text: {punctuated}")
        except Exception as e:
            print(f"❌ Gemini punctuation failed: {e}")
    else:
        print("⚠️ Gemini not configured — using unpunctuated text")

            

    # --- Censor ---
    censored = censor_text(punctuated, censor_list_ref)
    print(f"Censored Text: {censored}")
    return censored

# -------------------------
# Listen Loop (with VAD)
# -------------------------
def _listen_loop():
    global captured_texts, voiced_frames
    captured_texts = []
    voiced_frames = []

    vad = webrtcvad.Vad(1)  # less strict
    ring_buffer = collections.deque(maxlen=10)  # ~300ms
    buffer = []
    triggered = False

    def callback(indata, frames, time, status):
        if status:
            print("⚠️", status)
        frame = (indata[:, 0] * 32768).astype("int16").tobytes()
        buffer.append(frame)

    print("🎤 Listening with VAD (Safe Mode with faster-whisper)")
    with sd.InputStream(samplerate=samplerate, channels=1,
                        blocksize=frame_len, dtype="float32", callback=callback):
        while not _stop_event.is_set():
            if not buffer:
                continue

            frame = buffer.pop(0)
            is_speech = vad.is_speech(frame, samplerate)
            #print(f"[DEBUG] Speech detected: {is_speech}")
            ring_buffer.append((frame, is_speech))

            if not triggered:
                num_voiced = len([f for f, speech in ring_buffer if speech])
                if num_voiced > 0.6 * ring_buffer.maxlen:
                    triggered = True
                    voiced_frames = list(ring_buffer)
                    ring_buffer.clear()
                    print("🎙️ Speech started")
            else:
                voiced_frames.append((frame, is_speech))
                num_unvoiced = len([f for f, speech in ring_buffer if not speech])
                if num_unvoiced > 0.3 * ring_buffer.maxlen:  # more sensitive
                    triggered = False
                    print("⏹️ Speech ended")

                    # Convert speech frames to numpy audio
                    pcm_data = b"".join([f for f, s in voiced_frames])
                    samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
                    voiced_frames = []

                    result = transcribe_audio(samples)
                    if result:
                        captured_texts.append(result)

    print("🛑 Listening stopped (Safe Mode)")

# -------------------------
# Public API
# -------------------------
def start_recording():
    global is_listening, _thread, _stop_event
    if is_listening:
        print("⚠️ Safe Mode already running.")
        return
    _stop_event.clear()
    is_listening = True
    _thread = threading.Thread(target=_listen_loop, daemon=True)
    _thread.start()
    print("✅ Recording Started (Safe Mode)")

def stop_recording():
    global is_listening, _thread, _stop_event, captured_texts, voiced_frames
    if not is_listening:
        print("⚠️ Safe Mode not running.")
        return
    _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
    is_listening = False

    # --- Safety flush ---
    if voiced_frames:
        print("🚨 Flushing leftover speech segment...")
        pcm_data = b"".join([f for f, s in voiced_frames])
        samples = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        result = transcribe_audio(samples)
        if result:
            captured_texts.append(result)
        voiced_frames = []

    print("✅ Recording Stopped (Safe Mode)")

    # Replay combined text
    if captured_texts:
        final_text = " ".join(captured_texts)
        print(f"📝 Final Combined Text: {final_text}")

        client = get_eleven_client()
        voice_id = ELEVEN_VOICE_ID or os.environ.get("ELEVEN_VOICE_ID")
        if client and voice_id:
            try:
                audio = client.text_to_speech.convert(
                    text=final_text,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                print("🔊 Replaying full session in cloned voice...")
                if play:
                    play(audio)
            except Exception as e:
                print(f"ElevenLabs TTS error: {e}")
        else:
            print("Skipping TTS: not configured.")
    else:
        print("ℹ️ No text captured, nothing to replay.")
