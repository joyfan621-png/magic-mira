# Mirror Agent External Camera Preference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web camera flow prefer `1080P USB Camera`, show the active device name in the page, and automatically fall back to the built-in camera if the external camera disappears.

**Architecture:** Keep all logic in the existing single-page frontend. Extend the current camera lifecycle in `app.js` to enumerate video inputs, prefer the named external device when available, surface the active device label in the UI, and recover on `devicechange` or track end without changing the existing voice/frame upload pipeline.

**Tech Stack:** Browser `navigator.mediaDevices`, `MediaStreamTrack`, existing HTML/CSS/vanilla JS frontend, Python `unittest`

---

### Task 1: Add failing contract tests for preferred camera selection and UI state

**Files:**
- Modify: `mirror-agent/tests/test_frontend_contract.py`
- Test: `mirror-agent/tests/test_frontend_contract.py`

- [ ] **Step 1: Add a template assertion for the active camera label**

```python
def test_camera_controls_show_active_device_name(self) -> None:
    template = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    self.assertIn('id="camera-device-name"', template)
    self.assertIn("当前摄像头：未连接", template)
```

- [ ] **Step 2: Add a script assertion for preferred external camera selection**

```python
def test_frontend_prefers_named_external_camera_when_available(self) -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    self.assertIn('const PREFERRED_CAMERA_LABEL = "1080P USB Camera";', script)
    self.assertIn("navigator.mediaDevices.enumerateDevices()", script)
    self.assertIn('device.kind === "videoinput"', script)
    self.assertIn("device.label === PREFERRED_CAMERA_LABEL", script)
```

- [ ] **Step 3: Add a script assertion for fallback and automatic recovery**

```python
def test_frontend_falls_back_and_recovers_when_camera_changes(self) -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    self.assertIn('navigator.mediaDevices.getUserMedia({ video: true, audio: false })', script)
    self.assertIn('navigator.mediaDevices.addEventListener("devicechange"', script)
    self.assertIn('videoTrack.addEventListener("ended"', script)
    self.assertIn('setStatus(`当前摄像头：${label}`);', script)
```

- [ ] **Step 4: Run the targeted contract suite and confirm failure**

Run: `python3 -m unittest mirror-agent.tests.test_frontend_contract -v`
Expected: FAIL because the template does not yet expose `camera-device-name` and the current frontend does not enumerate devices or recover on camera changes.

### Task 2: Implement the camera label UI and preferred-device lifecycle

**Files:**
- Modify: `mirror-agent/templates/index.html`
- Modify: `mirror-agent/static/style.css`
- Modify: `mirror-agent/static/app.js`

- [ ] **Step 1: Add the active device label to the camera panel**

```html
<p id="camera-device-name" class="camera-device-name">当前摄像头：未连接</p>
```

- [ ] **Step 2: Style the device label to match the existing camera panel**

```css
.camera-device-name {
  margin: 0.65rem 1rem 0;
  color: var(--accent-deep);
  font-size: 0.88rem;
}
```

- [ ] **Step 3: Add preferred camera selection helpers**

```javascript
const PREFERRED_CAMERA_LABEL = "1080P USB Camera";

async function listVideoInputs() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((device) => device.kind === "videoinput");
}
```

- [ ] **Step 4: Add active-device label updates and recovery hooks**

```javascript
function setCameraDeviceName(label) {
  cameraDeviceName.textContent = `当前摄像头：${label}`;
}

videoTrack.addEventListener("ended", handleCameraDeviceLoss);
navigator.mediaDevices.addEventListener("devicechange", handleCameraDeviceChange);
```

- [ ] **Step 5: Update `startCameraPreview()` to prefer the external camera, then fall back**

```javascript
cameraStream = await openPreferredCameraStream();
cameraPreview.srcObject = cameraStream;
await syncCameraDeviceLabelFromStream(cameraStream);
```

- [ ] **Step 6: Re-run the targeted contract suite**

Run: `python3 -m unittest mirror-agent.tests.test_frontend_contract -v`
Expected: PASS

### Task 3: Verify camera behavior did not regress

**Files:**
- Modify: `mirror-agent/static/app.js` (only if verification uncovers issues)

- [ ] **Step 1: Run the broader web-facing tests**

Run: `python3 -m unittest mirror-agent.tests.test_frontend_contract mirror-agent.tests.test_webapp -v`
Expected: PASS

- [ ] **Step 2: Review the diff to ensure only the intended camera files changed**

Run: `git diff -- mirror-agent/templates/index.html mirror-agent/static/style.css mirror-agent/static/app.js mirror-agent/tests/test_frontend_contract.py`
Expected: Diff only shows the active camera label, preferred camera selection helpers, recovery hooks, and the matching contract tests.
