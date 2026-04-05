# Mirror Agent Halo Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the root web page with a user-facing halo-style display screen while keeping the existing full testing console available at `/lab`.

**Architecture:** Keep the current lab console isolated by leaving `templates/index.html` and `static/app.js` in place for `/lab`. Add a new root-only stack with `templates/home.html`, `static/home.css`, and `static/home.js` that reuses the existing Flask APIs for camera voice rounds, reminder polling, and tablet-state syncing, but presents them through a minimal display-first UI.

**Tech Stack:** Flask templates and routes, vanilla JavaScript, CSS, Python `unittest`, existing browser media APIs

---

### Task 1: Add failing tests for the new route split and display homepage contract

**Files:**
- Modify: `mirror-agent/tests/test_webapp.py`
- Modify: `mirror-agent/tests/test_frontend_contract.py`
- Test: `mirror-agent/tests/test_webapp.py`
- Test: `mirror-agent/tests/test_frontend_contract.py`

- [ ] **Step 1: Add a failing route test for the new root homepage**

```python
def test_index_page_renders_halo_home(self) -> None:
    response = self.client.get("/")

    self.assertEqual(200, response.status_code)
    html = response.get_data(as_text=True)
    self.assertIn("镜中闺蜜", html)
    self.assertIn('id="halo-stage"', html)
    self.assertIn('id="camera-switch-button"', html)
    self.assertIn('id="camera-button"', html)
    self.assertIn('id="subtitle-panel"', html)
    self.assertIn('id="countdown-panel"', html)
    self.assertIn('id="camera-preview"', html)
    self.assertNotIn('id="voice-button"', html)
```

- [ ] **Step 2: Add a failing route test for the preserved lab console**

```python
def test_lab_page_renders_existing_console(self) -> None:
    response = self.client.get("/lab")

    self.assertEqual(200, response.status_code)
    html = response.get_data(as_text=True)
    self.assertIn('data-assistant-label="我"', html)
    self.assertIn('id="voice-button"', html)
    self.assertIn('id="camera-select"', html)
    self.assertIn("打开平板页", html)
```

- [ ] **Step 3: Add failing homepage contract tests for the new display template and script**

```python
def test_halo_home_template_exposes_display_only_controls(self) -> None:
    template = (PROJECT_ROOT / "templates" / "home.html").read_text(encoding="utf-8")

    self.assertIn('id="camera-switch-button"', template)
    self.assertIn('id="camera-button"', template)
    self.assertIn('id="halo-stage"', template)
    self.assertIn('id="subtitle-panel"', template)
    self.assertIn('id="countdown-panel"', template)
    self.assertNotIn('id="voice-button"', template)
    self.assertNotIn('id="camera-select"', template)

def test_halo_home_script_cycles_camera_devices_without_dropdown(self) -> None:
    script = (PROJECT_ROOT / "static" / "home.js").read_text(encoding="utf-8")

    self.assertIn('const cameraSwitchButton = document.getElementById("camera-switch-button");', script)
    self.assertIn("async function cycleCameraDevice()", script)
    self.assertNotIn('document.getElementById("camera-select")', script)

def test_halo_home_script_streams_voice_into_compact_subtitles(self) -> None:
    script = (PROJECT_ROOT / "static" / "home.js").read_text(encoding="utf-8")

    self.assertIn('fetch("/api/voice-chat-stream"', script)
    self.assertIn('const userSubtitleEl = document.getElementById("user-subtitle");', script)
    self.assertIn('const agentSubtitleEl = document.getElementById("agent-subtitle");', script)
    self.assertIn("function renderReminder(reminder)", script)
```

- [ ] **Step 4: Run the targeted suite and verify it fails for the missing homepage files and `/lab` route**

Run: `/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest tests.test_webapp tests.test_frontend_contract -v`

Expected: FAIL because `home.html` and `home.js` do not exist yet and `GET /lab` is not implemented.

### Task 2: Add the root display route and preserve the old lab console

**Files:**
- Modify: `mirror-agent/webapp.py`
- Create: `mirror-agent/templates/home.html`
- Modify: `mirror-agent/tests/test_webapp.py` (from Task 1)

- [ ] **Step 1: Point `/` at the new homepage and add `/lab` for the old console**

```python
@app.get("/")
def index() -> str:
    return render_template("home.html", assistant_label=current_assistant_label())

@app.get("/lab")
def lab() -> str:
    return render_template("index.html", assistant_label=current_assistant_label())
```

- [ ] **Step 2: Create the new display-first root template**

```html
<main class="home-shell" data-assistant-label="{{ assistant_label }}">
  <section class="halo-screen">
    <div id="halo-stage" class="halo-stage" data-scene="idle"></div>
    <section id="subtitle-panel" class="subtitle-panel" aria-live="polite">
      <p class="subtitle-label">Live Mirror</p>
      <p id="user-subtitle" class="subtitle-line subtitle-user">等待你开镜头</p>
      <p id="agent-subtitle" class="subtitle-line subtitle-agent">{{ assistant_label }} 会在这里轻声回应</p>
    </section>
    <section id="countdown-panel" class="countdown-panel" hidden>
      <p id="countdown-value" class="countdown-value">00:00</p>
      <p id="countdown-message" class="countdown-message"></p>
    </section>
    <section class="camera-float">
      <video id="camera-preview" class="camera-preview" autoplay muted playsinline></video>
      <canvas id="camera-canvas" class="camera-canvas" aria-hidden="true"></canvas>
      <p id="camera-device-name" class="camera-device-name">当前摄像头：未连接</p>
    </section>
    <div class="home-controls">
      <button id="camera-switch-button" class="ghost-button" type="button">切换摄像头</button>
      <button id="camera-button" class="ghost-button" type="button">打开镜头</button>
    </div>
    <p id="status" class="status-line">打开镜头后，我会自动听你说，也会在这里显示很短的字幕。</p>
  </section>
</main>
```

- [ ] **Step 3: Run the targeted suite again**

Run: `/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest tests.test_webapp tests.test_frontend_contract -v`

Expected: FAIL only on the new homepage contract assertions for `static/home.js` and any still-missing homepage ids/strings.

### Task 3: Implement the halo-home CSS and minimal display JavaScript

**Files:**
- Create: `mirror-agent/static/home.css`
- Create: `mirror-agent/static/home.js`
- Modify: `mirror-agent/templates/home.html` (only if Task 2 missed required hooks)
- Test: `mirror-agent/tests/test_frontend_contract.py`

- [ ] **Step 1: Add the dark portrait halo layout and compact information zones**

```css
:root {
  --bg: #020304;
  --ink: rgba(255, 255, 255, 0.92);
  --muted: rgba(255, 255, 255, 0.58);
  --line: rgba(255, 255, 255, 0.1);
  --glow: rgba(122, 202, 255, 0.32);
}

body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 50% 16%, rgba(153, 218, 255, 0.08), transparent 24%),
    linear-gradient(180deg, #090b0e 0%, #020304 62%, #000 100%);
  color: var(--ink);
}

.halo-stage[data-scene="listening"] .halo-ring {
  opacity: 0.95;
  transform: scale(1.03);
}
```

- [ ] **Step 2: Add the root-page script skeleton with display-only DOM bindings**

```javascript
const cameraSwitchButton = document.getElementById("camera-switch-button");
const cameraButton = document.getElementById("camera-button");
const cameraPreview = document.getElementById("camera-preview");
const cameraCanvas = document.getElementById("camera-canvas");
const userSubtitleEl = document.getElementById("user-subtitle");
const agentSubtitleEl = document.getElementById("agent-subtitle");
const countdownPanelEl = document.getElementById("countdown-panel");
const countdownValueEl = document.getElementById("countdown-value");
const countdownMessageEl = document.getElementById("countdown-message");
```

- [ ] **Step 3: Implement camera selection by cycling devices instead of using a dropdown**

```javascript
let availableCameras = [];
let preferredCameraDeviceId = "";

async function cycleCameraDevice() {
  availableCameras = await listVideoInputs();
  if (availableCameras.length === 0) {
    setStatus("当前没有可切换的摄像头。");
    return;
  }

  const currentIndex = availableCameras.findIndex((device) => device.deviceId === preferredCameraDeviceId);
  const nextDevice = availableCameras[(currentIndex + 1 + availableCameras.length) % availableCameras.length];
  preferredCameraDeviceId = nextDevice.deviceId;

  if (cameraStream) {
    await restoreCameraPreview("已经切到下一个摄像头。");
    return;
  }

  setCameraDeviceLabel(nextDevice.label || "下一个摄像头");
  setStatus("下次打开镜头时会使用这个摄像头。");
}
```

- [ ] **Step 4: Implement compact subtitle rendering, reminder countdown, and streamed voice reply handling**

```javascript
function renderReminder(reminder) {
  if (!reminder) {
    countdownPanelEl.hidden = true;
    countdownValueEl.textContent = "00:00";
    countdownMessageEl.textContent = "";
    return;
  }

  countdownPanelEl.hidden = false;
  countdownValueEl.textContent = formatRemainingTime(new Date(reminder.due_at).getTime() - Date.now());
  countdownMessageEl.textContent = reminder.message;
}

async function startVoiceRound() {
  const liveUserText = "我在听你说。";
  userSubtitleEl.textContent = liveUserText;
  agentSubtitleEl.textContent = `${assistantLabel} 正在听你说`;
  await streamVoice(audioBlob, async ({ type, text, reply, audio_url: audioUrl, scheduled_reminder: scheduledReminder }) => {
    if (type === "transcript") userSubtitleEl.textContent = text;
    if (type === "reply_delta") agentSubtitleEl.textContent = text;
    if (type === "reply_done") {
      agentSubtitleEl.textContent = reply;
      if (scheduledReminder) renderReminder(scheduledReminder);
      if (audioUrl) await queueAudioPlayback(createVoiceAudioPlayer(audioUrl));
    }
  }, frameBlob, regionBlobs, Boolean(cameraStream));
}
```

- [ ] **Step 5: Keep the existing tablet-state sync and due-reminder polling in the new homepage**

```javascript
function pushTabletScene(scene, details = {}) {
  updateTabletState({ scene, ...details });
  haloStage.dataset.scene = scene;
}

async function pollDueReminders() {
  const response = await fetch("/api/reminders/due", { method: "GET" });
  const payload = await readPayload(response);
  for (const reminder of payload.reminders || []) {
    renderReminder(reminder);
  }
}
```

- [ ] **Step 6: Run the targeted suite and verify it passes**

Run: `/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest tests.test_webapp tests.test_frontend_contract -v`

Expected: PASS

### Task 4: Verify the feature with the broader web-facing suite and review the final diff

**Files:**
- Modify: `mirror-agent/webapp.py` (only if verification finds a route issue)
- Modify: `mirror-agent/templates/home.html` (only if verification finds a markup issue)
- Modify: `mirror-agent/static/home.css` (only if verification finds a style-hook issue)
- Modify: `mirror-agent/static/home.js` (only if verification finds a behavior issue)

- [ ] **Step 1: Run the broader web-focused tests from the worktree**

Run: `/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest tests.test_webapp tests.test_frontend_contract tests.test_reminders -v`

Expected: PASS

- [ ] **Step 2: Review the final diff for route isolation and homepage scope**

Run: `git diff -- mirror-agent/webapp.py mirror-agent/templates/home.html mirror-agent/templates/index.html mirror-agent/static/home.css mirror-agent/static/home.js mirror-agent/tests/test_webapp.py mirror-agent/tests/test_frontend_contract.py`

Expected: Diff shows `/` moved to `home.html`, `/lab` preserved for the old console, and the new display page only introduces the camera-only halo UI plus matching tests.
