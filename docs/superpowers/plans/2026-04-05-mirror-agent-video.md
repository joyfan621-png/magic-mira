# Mirror Agent Video Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add camera preview and quasi-real-time video conversation so each spoken round can include the current camera frame in the model response.

**Architecture:** Keep the existing Flask + single-page UI. Extend the voice roundtrip so the browser can capture one frame from the live camera preview and send it alongside the recorded audio. The backend saves the frame, then asks `MirrorAgent` for a multimodal reply while preserving existing streaming subtitles and single-channel TTS.

**Tech Stack:** Flask, browser `getUserMedia`, `canvas`, existing Ollama multimodal chat, existing Edge-TTS, Python unittest

---

### Task 1: Add failing tests for camera UI and frame-aware routes

**Files:**
- Modify: `mirror-agent/tests/test_frontend_contract.py`
- Modify: `mirror-agent/tests/test_webapp.py`

- [ ] **Step 1: Add frontend assertions for camera preview and frame capture hooks**

```python
self.assertIn('id="camera-button"', template)
self.assertIn("canvas.toBlob", script)
```

- [ ] **Step 2: Add backend assertions for voice routes accepting a `frame` upload**

```python
response = client.post("/api/voice-chat-stream", data=data, content_type="multipart/form-data")
self.assertEqual(200, response.status_code)
```

- [ ] **Step 3: Run the targeted suite and confirm failures**

Run: `cd /Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent && .venv/bin/python -m unittest tests.test_frontend_contract tests.test_webapp -v`
Expected: FAIL on missing camera UI and missing frame-aware behavior.

### Task 2: Implement frame-aware agent and backend plumbing

**Files:**
- Modify: `mirror-agent/agent.py`
- Modify: `mirror-agent/webapp.py`

- [ ] **Step 1: Extend agent streaming path to accept optional image paths**

```python
def stream_respond(self, user_text: str, image_paths: list[str] | None = None) -> Iterator[str]:
    ...
```

- [ ] **Step 2: Update voice routes to persist optional frame uploads and pass them into the agent**

```python
frame = request.files.get("frame")
frame_path = _save_optional_upload(frame)
```

- [ ] **Step 3: Re-run targeted tests**

Run: `cd /Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent && .venv/bin/python -m unittest tests.test_webapp -v`
Expected: PASS

### Task 3: Add camera preview and client-side frame capture

**Files:**
- Modify: `mirror-agent/templates/index.html`
- Modify: `mirror-agent/static/style.css`
- Modify: `mirror-agent/static/app.js`

- [ ] **Step 1: Add camera controls and preview markup**

```html
<button id="camera-button" type="button">打开镜头</button>
<video id="camera-preview" playsinline autoplay muted></video>
<canvas id="camera-canvas" hidden></canvas>
```

- [ ] **Step 2: Implement browser camera lifecycle and frame capture**

```javascript
const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
canvas.toBlob((blob) => { ... }, "image/jpeg", 0.9);
```

- [ ] **Step 3: Attach captured frame to the existing voice-stream upload**

```javascript
formData.append("frame", frameBlob, "camera-frame.jpg");
```

- [ ] **Step 4: Run targeted frontend tests**

Run: `cd /Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent && .venv/bin/python -m unittest tests.test_frontend_contract -v`
Expected: PASS

### Task 4: Verify end-to-end behavior and docs

**Files:**
- Modify: `mirror-agent/README.md`

- [ ] **Step 1: Document camera usage**

```markdown
先点“打开镜头”，再点“点一下开口”进行视频回合。
```

- [ ] **Step 2: Run the full suite**

Run: `cd /Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent && .venv/bin/python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 3: Restart the Flask server and smoke-check**

Run: `cd /Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent && .venv/bin/python webapp.py`
Expected: server starts on `http://127.0.0.1:8000`
