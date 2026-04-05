# Mirror Animation Playground Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone local playground page that shows 15 looping black-and-pink magic animations in a responsive grid so the user can compare and pick favorites.

**Architecture:** Keep the work isolated under `playgrounds/` as a static HTML/CSS/JS page. Use a small Python `unittest` contract test to verify file existence, required containers, animation metadata count, and selection behavior hooks before serving the page via a local HTTP server.

**Tech Stack:** Static HTML, CSS animations, vanilla JavaScript, Python `unittest`, `python3 -m http.server`

---

### Task 1: Add Contract Test

**Files:**
- Create: `playgrounds/tests/test_mirror_animation_playground.py`
- Test: `playgrounds/tests/test_mirror_animation_playground.py`

- [ ] **Step 1: Write the failing test**

```python
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYGROUND_DIR = PROJECT_ROOT / "playgrounds" / "mirror-animation-playground"


class MirrorAnimationPlaygroundTests(unittest.TestCase):
    def test_playground_files_exist(self) -> None:
        self.assertTrue((PLAYGROUND_DIR / "index.html").exists())
        self.assertTrue((PLAYGROUND_DIR / "style.css").exists())
        self.assertTrue((PLAYGROUND_DIR / "app.js").exists())

    def test_html_contains_gallery_and_selection_summary(self) -> None:
        html = (PLAYGROUND_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="gallery"', html)
        self.assertIn('id="selection-summary"', html)

    def test_script_defines_fifteen_animations_and_selection_state(self) -> None:
        script = (PLAYGROUND_DIR / "app.js").read_text(encoding="utf-8")
        self.assertEqual(15, len(re.findall(r'id:\\s*"', script)))
        self.assertIn("selectedAnimationIds", script)
        self.assertIn("renderSelectionSummary()", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s playgrounds/tests -p 'test_*.py' -v`
Expected: FAIL because the new playground files do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create the new playground directory and the three page files so the test can find them, then fill in the required containers and animation metadata.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s playgrounds/tests -p 'test_*.py' -v`
Expected: PASS with all tests green.

### Task 2: Build the Playground Page

**Files:**
- Create: `playgrounds/mirror-animation-playground/index.html`
- Create: `playgrounds/mirror-animation-playground/style.css`
- Create: `playgrounds/mirror-animation-playground/app.js`

- [ ] **Step 1: Add the HTML shell**

Create a page with:
- header copy
- selected-result bar
- gallery container
- script/style references

- [ ] **Step 2: Add responsive card layout and animation keyframes**

Implement:
- full-page black background
- responsive 15-card grid
- stage styling shared across cards
- keyframes for 15 animation variants
- selected-card highlight state

- [ ] **Step 3: Add the animation metadata and rendering logic**

Implement:
- 15 animation records with names, vibe copy, scene tags, and variant classes
- DOM rendering into `#gallery`
- selection toggle behavior
- live update of `#selection-summary`

- [ ] **Step 4: Run a local smoke check**

Run:
- `python3 -m http.server 8010`
- Open `/playgrounds/mirror-animation-playground/`

Expected:
- page loads
- all 15 cards loop automatically
- card selection updates the summary

### Task 3: Verify and Hand Off

**Files:**
- Verify: `playgrounds/mirror-animation-playground/index.html`
- Verify: `playgrounds/mirror-animation-playground/style.css`
- Verify: `playgrounds/mirror-animation-playground/app.js`
- Verify: `playgrounds/tests/test_mirror_animation_playground.py`

- [ ] **Step 1: Re-run the contract test**

Run: `python3 -m unittest discover -s playgrounds/tests -p 'test_*.py' -v`
Expected: PASS

- [ ] **Step 2: Re-run the local HTTP smoke check**

Run: `python3 -m http.server 8010`
Expected: server starts successfully and serves the new playground.

- [ ] **Step 3: Share the local URL**

Report:
- `http://127.0.0.1:8010/playgrounds/mirror-animation-playground/`
- brief note that the page is for comparing and selecting candidate animations
