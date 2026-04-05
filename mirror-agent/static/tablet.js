const tabletStageEl = document.getElementById("tablet-stage");
const tabletSceneLabelEl = document.getElementById("tablet-scene-label");

const TABLET_STATE_KEY = "mirror-tablet-state";
const SCENE_VARIANTS = {
  "startup": "crown-trace",
  "listening": "wand-sweep",
  "thinking": "star-spiral",
  "reply": "bow-flash",
  "idle": "ribbon-sway",
};
const SCENE_LABELS = {
  startup: "启动欢迎",
  listening: "听见你了",
  thinking: "我在想",
  reply: "回应闪现",
  idle: "安静待机",
};
const TRANSIENT_SCENES = new Set(["startup", "listening", "reply"]);
const tabletChannel =
  typeof BroadcastChannel === "function" ? new BroadcastChannel("mirror-tablet-display") : null;

let settleTimer = null;

function crownSvg() {
  return `
    <svg class="crown-svg" viewBox="0 0 160 100" aria-hidden="true">
      <path class="symbol-path" d="M20 80 L38 34 L64 66 L80 20 L96 66 L122 34 L140 80"></path>
      <path class="symbol-path" d="M20 80 H140"></path>
      <path class="symbol-path" d="M42 80 L48 68"></path>
      <path class="symbol-path" d="M80 80 L80 60"></path>
      <path class="symbol-path" d="M118 80 L112 68"></path>
    </svg>
  `;
}

function bowSvg() {
  return `
    <svg class="bow-svg" viewBox="0 0 160 120" aria-hidden="true">
      <path class="symbol-path" d="M78 62 C 60 48 44 38 26 34 C 18 32 16 44 24 50 C 40 62 56 66 78 62"></path>
      <path class="symbol-path" d="M82 62 C 100 48 116 38 134 34 C 142 32 144 44 136 50 C 120 62 104 66 82 62"></path>
      <path class="symbol-path" d="M74 54 L80 60 L86 54 L80 68 Z"></path>
      <path class="symbol-path" d="M78 64 C 70 72 60 82 52 92"></path>
      <path class="symbol-path" d="M82 64 C 90 72 100 82 108 92"></path>
    </svg>
  `;
}

function ribbonSvg(side) {
  return `
    <svg class="ribbon-svg ${side}" viewBox="0 0 160 120" aria-hidden="true">
      <path class="ribbon-path" d="M18 86 C 34 40 78 28 98 62 C 110 82 124 94 142 60"></path>
      <path class="ribbon-path" d="M36 82 C 54 56 84 54 96 72"></path>
    </svg>
  `;
}

function variableStars(items) {
  return items
    .map((item) => {
      const style = Object.entries(item)
        .map(([key, value]) => `--${key}:${value}`)
        .join(";");
      return `<span class="${item.className}" style="${style}"></span>`;
    })
    .join("");
}

const stageTemplates = {
  "crown-trace": `
    <div class="stage-crown-trace">
      ${crownSvg()}
      ${variableStars([
        { className: "jewel-dot", left: "31%", top: "40%", size: "8px", delay: "0.15s" },
        { className: "jewel-dot", left: "49%", top: "28%", size: "9px", delay: "0.35s" },
        { className: "jewel-dot", left: "67%", top: "40%", size: "8px", delay: "0.55s" },
      ])}
    </div>
  `,
  "wand-sweep": `
    <div class="stage-wand-sweep">
      <span class="wand-line"></span>
      <span class="wand-star"></span>
    </div>
  `,
  "star-spiral": `
    <div class="stage-star-spiral">
      <span class="center-glow"></span>
      ${variableStars([
        { className: "spiral-star", angle: "0deg", radius: "42px", delay: "0s", size: "10px" },
        { className: "spiral-star", angle: "72deg", radius: "56px", delay: "0.18s", size: "11px" },
        { className: "spiral-star", angle: "144deg", radius: "48px", delay: "0.36s", size: "10px" },
        { className: "spiral-star", angle: "216deg", radius: "62px", delay: "0.54s", size: "12px" },
        { className: "spiral-star", angle: "288deg", radius: "52px", delay: "0.72s", size: "10px" },
      ])}
    </div>
  `,
  "bow-flash": `
    <div class="stage-bow-flash">
      <span class="soft-glow"></span>
      ${bowSvg()}
    </div>
  `,
  "ribbon-sway": `
    <div class="stage-ribbon-sway">
      ${ribbonSvg("left")}
      ${ribbonSvg("right")}
      <span class="ribbon-knot"></span>
    </div>
  `,
};

function readStoredScene() {
  try {
    const raw = localStorage.getItem(TABLET_STATE_KEY);
    if (!raw) {
      return "idle";
    }
    const payload = JSON.parse(raw);
    return payload.scene in SCENE_VARIANTS ? payload.scene : "idle";
  } catch (error) {
    return "idle";
  }
}

function settleSceneTarget() {
  const storedScene = readStoredScene();
  if (storedScene === "thinking") {
    return "thinking";
  }
  return "idle";
}

function scheduleSettle(scene) {
  if (settleTimer) {
    window.clearTimeout(settleTimer);
  }

  settleTimer = window.setTimeout(() => {
    if (tabletStageEl.dataset.scene !== scene) {
      return;
    }
    renderScene(settleSceneTarget());
  }, scene === "startup" ? 2400 : 1800);
}

function renderScene(scene) {
  const safeScene = scene in SCENE_VARIANTS ? scene : "idle";
  const variant = SCENE_VARIANTS[safeScene];
  tabletStageEl.dataset.scene = safeScene;
  tabletStageEl.innerHTML = stageTemplates[variant];
  tabletSceneLabelEl.textContent = SCENE_LABELS[safeScene];

  if (TRANSIENT_SCENES.has(safeScene)) {
    scheduleSettle(safeScene);
    return;
  }

  if (settleTimer) {
    window.clearTimeout(settleTimer);
    settleTimer = null;
  }
}

function handleIncomingScene(scene) {
  renderScene(scene);
}

if (tabletChannel) {
  tabletChannel.addEventListener("message", (event) => {
    const nextScene = event.data?.scene;
    if (typeof nextScene === "string") {
      handleIncomingScene(nextScene);
    }
  });
}

window.addEventListener("storage", (event) => {
  if (event.key !== TABLET_STATE_KEY || !event.newValue) {
    return;
  }
  try {
    const payload = JSON.parse(event.newValue);
    if (typeof payload.scene === "string") {
      handleIncomingScene(payload.scene);
    }
  } catch (error) {
    return;
  }
});

renderScene("startup");
