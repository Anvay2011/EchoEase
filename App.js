import React, { useEffect, useState } from "react";
import "./App.css";
import logo from "./logo.png"; // 👈 Add your image file here


const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

export default function App() {
  const [mode, setMode] = useState("safe"); // 'safe' or 'group'
  const [isRecording, setIsRecording] = useState(false);
  const [words, setWords] = useState([]);
  const [newWord, setNewWord] = useState("");
  const [pitch, setPitch] = useState(-2);
  const [volume, setVolume] = useState(1);
  const [speed, setSpeed] = useState(1);
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetchWords();
    // poll status (optional)
    const iv = setInterval(() => {
      fetch(`${API_BASE}/status`).then(r => r.json()).then(j => {
        setIsRecording((mode === "safe" && j.safe_mode_running) || (mode === "group" && j.group_mode_running));
      }).catch(()=>{});
    }, 2000);
    return () => clearInterval(iv);
  }, [mode]);

  function fetchWords() {
    fetch(`${API_BASE}/safe_mode/words`).then(r => r.json()).then(j => setWords(j)).catch(()=>setWords([]));
  }

  async function addWord() {
    const w = newWord.trim();
    if (!w) return;
    const res = await fetch(`${API_BASE}/safe_mode/words`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({word: w})
    });
    if (res.ok) {
      setNewWord("");
      fetchWords();
    } else {
      const err = await res.json();
      alert(err.detail || "Could not add");
    }
  }

  async function removeWord(word) {
    const res = await fetch(`${API_BASE}/safe_mode/words/${encodeURIComponent(word)}`, {
      method: "DELETE"
    });
    if (res.ok) fetchWords();
  }

  async function start() {
    setStatus("Starting...");
    try {
      if (mode === "safe") {
        const res = await fetch(`${API_BASE}/safe_mode/start`, { method: "POST" });
        if (!res.ok) throw new Error("Failed to start safe mode");
      } else {
        const res = await fetch(`${API_BASE}/group_mode/start`, {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({pitch, volume, speed})
        });
        if (!res.ok) throw new Error("Failed to start group mode");
      }
      setIsRecording(true);
      setStatus("Recording...");
    } catch (e) {
      setStatus("Error starting: " + e.message);
    }
  }

  async function stop() {
    setStatus("Stopping...");
    try {
      if (mode === "safe") {
        await fetch(`${API_BASE}/safe_mode/stop`, { method: "POST" });
      } else {
        await fetch(`${API_BASE}/group_mode/stop`, { method: "POST" });
      }
      setIsRecording(false);
      setStatus("Stopped");
    } catch (e) {
      setStatus("Error stopping: " + e.message);
    }
  }

  return (
    <div className="container">
      <h1 className="title">
  <img src={logo} alt="EchoEase Logo" className="logo" />
  EchoEase
</h1>

      <div className="content">
        <div className="left-panel">
          <div className="mode-row">
            <button className={`mode-btn ${mode === "group" ? "active" : ""}`} onClick={() => setMode("group")}>Group Mode</button>
            <button className={`mode-btn ${mode === "safe" ? "active" : ""}`} onClick={() => setMode("safe")}>Safe Mode</button>
          </div>

          {mode === "group" && (
            <div className="sliders">
              <label>Pitch: {pitch}</label>
              <input type="range" min="-12" max="12" value={pitch} disabled={isRecording} onChange={e => setPitch(Number(e.target.value))} />
              <label>Volume: {volume}</label>
              <input type="range" min="0.5" max="1.5" step="0.1" value={volume} disabled={isRecording} onChange={e => setVolume(Number(e.target.value))} />
              <label>Speed: {speed}</label>
              <input type="range" min="0.5" max="1.5" step="0.1" value={speed} disabled={isRecording} onChange={e => setSpeed(Number(e.target.value))} />
            </div>
          )}

          <div className="controls">
            <button className="big" onClick={start} disabled={isRecording}>START</button>
            <button className="big" onClick={stop} disabled={!isRecording}>STOP</button>
            <div className="status">{status}</div>
          </div>
        </div>

        <div className="right-panel">
          <h3>WORDS TO CENSOR</h3>
          <div className="word-list">
            {words.map((w, i) => (
              <div className="word-item" key={w}>
                <span>{i+1}. {w}</span>
                <button className="x" onClick={() => removeWord(w)}>✕</button>
              </div>
            ))}
          </div>
          <div className="add-row">
            <input placeholder="Input Box" value={newWord} onChange={e=>setNewWord(e.target.value)} />
            <button onClick={addWord}>Send</button>
          </div>
        </div>
      </div>
    </div>
  );
}
