# Mirror Princess Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone static HTML prototype for a mirror-first princess-style conversation surface without changing the existing `mirror-agent` app.

**Architecture:** Create a small self-contained frontend prototype under `playgrounds/`. Keep the center of the viewport visually empty for mirror use, anchor the chat UI to the bottom, and use local keyword-triggered overlays to demonstrate princess ornaments, acne maps, and TCM face-reading hints.

**Tech Stack:** Static HTML, CSS, vanilla JavaScript

---

### Task 1: Scaffold the standalone prototype shell

**Files:**
- Create: `playgrounds/mirror-princess-demo/index.html`
- Create: `playgrounds/mirror-princess-demo/style.css`
- Create: `playgrounds/mirror-princess-demo/app.js`

- [ ] **Step 1: Add the HTML structure for mirror stage, overlay layers, demo chips, messages, and composer**

```html
<main class="mirror-app">
  <section class="mirror-stage"></section>
  <section class="chat-dock"></section>
</main>
```

- [ ] **Step 2: Add the black mirror visual system and bottom-docked layout**

```css
body {
  background: #050505;
}

.chat-dock {
  position: fixed;
  bottom: 20px;
}
```

- [ ] **Step 3: Add minimal startup behavior and static demo state**

```javascript
appendMessage("agent", "我在，你照你的镜子，我轻轻陪着你。");
```

- [ ] **Step 4: Open the static file in a browser and confirm the page reads as mirror-first**

Run: open the HTML file locally in a browser
Expected: the center of the page stays mostly empty and the chat UI sits near the bottom

### Task 2: Implement keyword-triggered visual overlays

**Files:**
- Modify: `playgrounds/mirror-princess-demo/index.html`
- Modify: `playgrounds/mirror-princess-demo/style.css`
- Modify: `playgrounds/mirror-princess-demo/app.js`

- [ ] **Step 1: Add dedicated overlay containers for sparkle, princess, acne-map, and tcm-map states**

```html
<aside class="overlay overlay-princess" data-scene="princess"></aside>
<aside class="overlay overlay-face" data-scene="acne-map"></aside>
```

- [ ] **Step 2: Add CSS transitions so overlays fade and float in without blocking the mirror center**

```css
.overlay.is-active {
  opacity: 1;
  transform: translateY(0) scale(1);
}
```

- [ ] **Step 3: Add local keyword matching and scene switching in JavaScript**

```javascript
if (/(痘|爆痘|额头|下巴|鼻翼)/.test(text)) {
  activateScene("acne-map");
}
```

- [ ] **Step 4: Verify each quick-demo chip triggers the expected scene**

Run: click the demo chips in the browser
Expected: princess ornaments appear for emotion prompts, acne highlights appear for breakout prompts, and the TCM chart appears for face-reading prompts

### Task 3: Polish the prototype for readability and demo usefulness

**Files:**
- Modify: `playgrounds/mirror-princess-demo/style.css`
- Modify: `playgrounds/mirror-princess-demo/app.js`

- [ ] **Step 1: Tune spacing and opacity so the dock remains readable but does not dominate the screen**

```css
.chat-dock {
  width: min(720px, calc(100vw - 24px));
  background: rgba(10, 10, 16, 0.72);
}
```

- [ ] **Step 2: Add short canned replies so each demo scene feels intentional**

```javascript
return "先别急，我给你轻轻看一下这个位置。";
```

- [ ] **Step 3: Add a small empty-state hint describing how to try the demo**

```javascript
setStatus("试试输入：下巴爆痘 / 想哭 / 中医面诊");
```

- [ ] **Step 4: Re-open on desktop and a narrow mobile width and verify the overlay and dock still fit**

Run: resize the browser window and refresh
Expected: the dock stays anchored and overlays remain on the edges without covering the center
