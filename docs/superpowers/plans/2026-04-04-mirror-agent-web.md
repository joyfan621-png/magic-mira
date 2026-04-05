# Mirror Agent Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local interactive web page for the Mirror Agent so the user can chat, upload a skin photo, and end the session from a browser.

**Architecture:** A thin Flask web layer will wrap the existing `MirrorAgent` without changing its core memory and tool logic. The backend exposes JSON endpoints and serves a single HTML page with lightweight CSS and JavaScript for chat interactions.

**Tech Stack:** Python 3.10+, Flask, standard library, existing `zhipuai` integration

---

### Task 1: Add failing tests for web routes

**Files:**
- Create: `mirror-agent/tests/test_webapp.py`
- Modify: `mirror-agent/requirements.txt`

- [ ] **Step 1: Write failing tests for index, chat, image, and end-session routes**

```python
response = client.get("/")
self.assertEqual(200, response.status_code)

response = client.post("/api/chat", json={"message": "今天有点干"})
self.assertEqual(200, response.status_code)
```

- [ ] **Step 2: Run the test module to verify it fails**

Run: `cd mirror-agent && python3 -m unittest tests.test_webapp -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp'`

- [ ] **Step 3: Add Flask dependency**

```text
Flask>=3.0.0
```

- [ ] **Step 4: Re-run the test module**

Run: `cd mirror-agent && python3 -m unittest tests.test_webapp -v`
Expected: FAIL for missing implementation only.

### Task 2: Implement the backend web layer

**Files:**
- Create: `mirror-agent/webapp.py`
- Modify: `mirror-agent/agent.py`

- [ ] **Step 1: Implement a Flask app factory and JSON routes**

```python
def create_app(agent: MirrorAgent | None = None) -> Flask:
    app = Flask(__name__)
    ...
```

- [ ] **Step 2: Add any small agent helpers needed by the web routes**

```python
def append_local_exchange(self, user_text: str, reply: str) -> None:
    ...
```

- [ ] **Step 3: Run the web test module**

Run: `cd mirror-agent && python3 -m unittest tests.test_webapp -v`
Expected: PASS

### Task 3: Implement the page assets

**Files:**
- Create: `mirror-agent/templates/index.html`
- Create: `mirror-agent/static/style.css`
- Create: `mirror-agent/static/app.js`

- [ ] **Step 1: Build a single-page chat layout**

```html
<main class="shell">
  <section id="messages"></section>
  <form id="chat-form"></form>
</main>
```

- [ ] **Step 2: Add front-end fetch logic for chat, image upload, and end session**

```javascript
const response = await fetch("/api/chat", { ... });
```

- [ ] **Step 3: Run the full test suite**

Run: `cd mirror-agent && python3 -m unittest discover -s tests -v`
Expected: PASS

### Task 4: Verify local launch

**Files:**
- Modify: `mirror-agent/README.md`

- [ ] **Step 1: Add web launch instructions**

```markdown
python3 webapp.py
```

- [ ] **Step 2: Run a smoke check**

Run: `cd mirror-agent && python3 webapp.py`
Expected: Flask dev server starts and prints the local URL.
