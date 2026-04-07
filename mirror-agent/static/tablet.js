const tabletStageEl = document.getElementById("tablet-stage");
const tabletSceneLabelEl = document.getElementById("tablet-scene-label");
const tabletReminderEl = document.getElementById("tablet-reminder");
const tabletCountdownLabelEl = document.getElementById("tablet-countdown-label");
const tabletCountdownValueEl = document.getElementById("tablet-countdown-value");
const tabletReminderMetaEl = document.getElementById("tablet-reminder-meta");
const tabletReminderMessageEl = document.getElementById("tablet-reminder-message");

const TABLET_STATE_KEY = "mirror-tablet-state";
const TABLET_TRIGGERED_REMINDER_WINDOW_MS = 15000;
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
let reminderRenderTimer = null;
let lastPlayedReminderId = "";
let tabletStatePollInFlight = false;
let latestTabletState = readStoredState();

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

function readStoredState() {
  try {
    const raw = localStorage.getItem(TABLET_STATE_KEY);
    if (!raw) {
      return {};
    }
    const payload = JSON.parse(raw);
    return payload && typeof payload === "object" ? payload : {};
  } catch (error) {
    return {};
  }
}

function rememberTabletState(state) {
  if (!state || typeof state !== "object") {
    return latestTabletState;
  }

  latestTabletState = { ...latestTabletState, ...state };
  try {
    localStorage.setItem(TABLET_STATE_KEY, JSON.stringify(latestTabletState));
  } catch (error) {
    // localStorage can be unavailable in private contexts; rendering should still continue in memory.
  }
  return latestTabletState;
}

function normalizeScene(state) {
  const scene = state?.scene;
  return typeof scene === "string" && scene in SCENE_VARIANTS ? scene : "idle";
}

function normalizeReminder(reminder) {
  if (!reminder || typeof reminder !== "object") {
    return null;
  }

  const dueAt = String(reminder.due_at || reminder.dueAt || "").trim();
  const dueAtMs = Number(reminder.due_at_ms ?? reminder.dueAtMs);
  const message = String(reminder.message || "").trim();
  const id = String(reminder.id || "").trim();

  if (!dueAt || !message) {
    return null;
  }

  return {
    id,
    message,
    dueAt,
    dueAtMs: Number.isFinite(dueAtMs) && dueAtMs > 0 ? dueAtMs : parseReminderDueAtMs({ dueAt }),
  };
}

function normalizeTriggeredReminder(reminder) {
  if (!reminder || typeof reminder !== "object") {
    return null;
  }

  const message = String(reminder.message || "").trim();
  if (!message) {
    return null;
  }

  const rawTriggeredAt = reminder.triggered_at || reminder.triggeredAt || reminder.timestamp;
  const parsedTriggeredAt =
    typeof rawTriggeredAt === "number" ? rawTriggeredAt : Date.parse(String(rawTriggeredAt || "").trim());

  return {
    id: String(reminder.id || message).trim(),
    message,
    dueAt: String(reminder.due_at || reminder.dueAt || "").trim(),
    dueAtMs: parseReminderDueAtMs(reminder),
    audioUrl: String(reminder.audio_url || reminder.audioUrl || "").trim(),
    triggeredAt: Number.isFinite(parsedTriggeredAt) ? parsedTriggeredAt : Date.now(),
  };
}

function parseReminderDueAtMs(reminder) {
  if (!reminder || typeof reminder !== "object") {
    return Number.NaN;
  }

  const directDueAtMs = Number(reminder.due_at_ms ?? reminder.dueAtMs);
  if (Number.isFinite(directDueAtMs) && directDueAtMs > 0) {
    return directDueAtMs;
  }

  const dueAt = String(reminder.due_at || reminder.dueAt || "").trim();
  if (!dueAt) {
    return Number.NaN;
  }

  return new Date(dueAt).getTime();
}

function readStoredScene() {
  return normalizeScene(latestTabletState);
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

function formatRemainingTime(remainingMs) {
  const totalSeconds = Math.max(0, Math.ceil(remainingMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function formatDueTime(dueAt) {
  const dueAtMs = parseReminderDueAtMs(dueAt);
  const dueDate = Number.isFinite(dueAtMs) && dueAtMs > 0 ? new Date(dueAtMs) : new Date(String(dueAt || "").trim());
  if (Number.isNaN(dueDate.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(dueDate);
}

function playReminderAudio(reminder) {
  if (!reminder || !reminder.audioUrl || !reminder.id || reminder.id === lastPlayedReminderId) {
    return;
  }

  lastPlayedReminderId = reminder.id;
  const audio = new Audio(reminder.audioUrl);
  audio.preload = "auto";
  void audio.play().catch(() => {});
}

function renderReminder(reminder, lastTriggeredReminder) {
  const activeReminder = normalizeReminder(reminder);
  const triggeredReminder = normalizeTriggeredReminder(lastTriggeredReminder);
  const hasFreshTriggeredReminder =
    triggeredReminder && Date.now() - triggeredReminder.triggeredAt <= TABLET_TRIGGERED_REMINDER_WINDOW_MS;

  if (!tabletReminderEl || !tabletCountdownLabelEl || !tabletCountdownValueEl || !tabletReminderMetaEl || !tabletReminderMessageEl) {
    return;
  }

  if (hasFreshTriggeredReminder) {
    tabletReminderEl.hidden = false;
    tabletReminderEl.dataset.state = "due";
    tabletCountdownLabelEl.textContent = "提醒到了";
    tabletCountdownValueEl.textContent = "00:00";
    tabletReminderMetaEl.textContent = triggeredReminder.dueAt ? `${formatDueTime(triggeredReminder)} 已到` : "现在提醒你";
    tabletReminderMessageEl.textContent = triggeredReminder.message;
    playReminderAudio(triggeredReminder);
    return;
  }

  if (!activeReminder) {
    tabletReminderEl.hidden = true;
    tabletReminderEl.dataset.state = "";
    tabletCountdownLabelEl.textContent = "倒计时";
    tabletCountdownValueEl.textContent = "00:00";
    tabletReminderMetaEl.textContent = "";
    tabletReminderMessageEl.textContent = "";
    return;
  }

  const remainingMs = Number.isNaN(activeReminder.dueAtMs) ? 0 : activeReminder.dueAtMs - Date.now();
  const dueTimeLabel = formatDueTime(activeReminder);

  tabletReminderEl.hidden = false;
  tabletReminderEl.dataset.state = remainingMs <= 0 ? "due" : "counting";
  tabletCountdownLabelEl.textContent = remainingMs <= 0 ? "马上提醒" : "倒计时";
  tabletCountdownValueEl.textContent = formatRemainingTime(remainingMs);
  tabletReminderMetaEl.textContent = dueTimeLabel ? `${dueTimeLabel} 提醒你` : "提醒已设置";
  tabletReminderMessageEl.textContent = activeReminder.message;
}

function renderFromState(state) {
  const safeState = rememberTabletState(state);
  renderScene(normalizeScene(safeState));
  renderReminder(safeState.reminder, safeState.lastTriggeredReminder);
}

function handleIncomingState(state) {
  renderFromState(state);
}

async function pollTabletStateFromServer() {
  if (tabletStatePollInFlight) {
    return;
  }

  tabletStatePollInFlight = true;
  try {
    const response = await fetch("/api/tablet-state", {
      method: "GET",
      cache: "no-store",
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    handleIncomingState(payload);
  } catch (error) {
    return;
  } finally {
    tabletStatePollInFlight = false;
  }
}

if (tabletChannel) {
  tabletChannel.addEventListener("message", (event) => {
    if (event.data && typeof event.data === "object") {
      handleIncomingState(event.data);
    }
  });
}

window.addEventListener("storage", (event) => {
  if (event.key !== TABLET_STATE_KEY || !event.newValue) {
    return;
  }
  try {
    const payload = JSON.parse(event.newValue);
    handleIncomingState(payload);
  } catch (error) {
    return;
  }
});

renderScene("startup");
renderReminder(latestTabletState.reminder, latestTabletState.lastTriggeredReminder);
reminderRenderTimer = window.setInterval(() => {
  renderReminder(latestTabletState.reminder, latestTabletState.lastTriggeredReminder);
}, 1000);
void pollTabletStateFromServer();
window.setInterval(() => {
  void pollTabletStateFromServer();
}, 1000);
