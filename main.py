# main.py
# FastAPI backend entrypoint for EchoEase

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
import threading
import time

# import your mode modules (they should NOT start recording on import)
import safe_mode
import group_mode

app = FastAPI(title="EchoEase API")

# Allow React dev server (http://localhost:3000) to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory censor word list (shared with safe_mode)
censor_words = []  # safe_mode will read from this list reference

# API models
class WordItem(BaseModel):
    word: str

class ModeParams(BaseModel):
    pitch: float = -2.0
    volume: float = 1.0
    speed: float = 1.0

# Simple run-lock state
state = {
    "safe_mode_running": False,
    "group_mode_running": False
}

#############
# SAFE MODE #
#############
@app.post("/safe_mode/start")
def start_safe_mode():
    if state["safe_mode_running"]:
        print("Safe Mode start requested but already running.")
        return {"status": "already_running"}
    # pass a reference of the censor_words list so module reads live updates
    safe_mode.set_censor_list_reference(censor_words)
    safe_mode.start_recording()
    state["safe_mode_running"] = True
    print("Recording Started (Safe Mode)")
    return {"status": "started"}

@app.post("/safe_mode/stop")
def stop_safe_mode():
    if not state["safe_mode_running"]:
        print("Safe Mode stop requested but not running.")
        return {"status": "not_running"}
    safe_mode.stop_recording()
    state["safe_mode_running"] = False
    print("Recording Stopped (Safe Mode)")
    return {"status": "stopped"}

@app.get("/safe_mode/words", response_model=List[str])
def get_safe_mode_words():
    return censor_words

@app.post("/safe_mode/words")
def add_safe_word(item: WordItem):
    w = item.word.strip()
    if not w:
        raise HTTPException(status_code=400, detail="Empty word")
    if w in censor_words:
        raise HTTPException(status_code=400, detail="Word already exists")
    censor_words.append(w)
    print(f"Word Added to Censor List: {w}")
    return {"status": "added", "word": w}

@app.delete("/safe_mode/words/{word}")
def delete_safe_word(word: str):
    if word not in censor_words:
        raise HTTPException(status_code=404, detail="Word not found")
    censor_words.remove(word)
    print(f"Word Removed from Censor List: {word}")
    return {"status": "removed", "word": word}

##############
# GROUP MODE #
##############
@app.post("/group_mode/start")
def start_group_mode(params: ModeParams):
    if state["group_mode_running"]:
        print("Group Mode start requested but already running.")
        return {"status": "already_running"}
    group_mode.set_parameters(pitch=params.pitch, volume=params.volume, speed=params.speed)
    group_mode.start_recording()
    state["group_mode_running"] = True
    print("Recording Started (Group Mode)")
    return {"status": "started"}

@app.post("/group_mode/stop")
def stop_group_mode():
    if not state["group_mode_running"]:
        print("Group Mode stop requested but not running.")
        return {"status": "not_running"}
    group_mode.stop_recording()
    state["group_mode_running"] = False
    print("Recording Stopped (Group Mode)")
    return {"status": "stopped"}

@app.get("/status")
def status():
    return {
        "safe_mode_running": state["safe_mode_running"],
        "group_mode_running": state["group_mode_running"],
        "censor_words": censor_words
    }

@app.get("/")
def root():
    return {"message": "EchoEase backend is up. Use API endpoints to control modes."}
