const haloStage = document.getElementById("halo-stage");
const haloSceneOverlay = document.getElementById("halo-scene-overlay");
const statusEl = document.getElementById("status");
const cameraSwitchButton = document.getElementById("camera-switch-button");
const cameraButton = document.getElementById("camera-button");
const cameraPreview = document.getElementById("camera-preview");
const cameraCanvas = document.getElementById("camera-canvas");
const cameraDeviceName = document.getElementById("camera-device-name");
const cameraFloatEl = document.querySelector(".camera-float");
const userSubtitleEl = document.getElementById("user-subtitle");
const agentSubtitleEl = document.getElementById("agent-subtitle");
const countdownPanelEl = document.getElementById("countdown-panel");
const countdownValueEl = document.getElementById("countdown-value");
const countdownMessageEl = document.getElementById("countdown-message");

let assistantLabel = document.body.dataset.assistantLabel || "我";
const needsNameOnboarding = document.body.dataset.needsOnboarding === "true";
const VOICE_SILENCE_MS = 1200;
const VOICE_MAX_MS = 12000;
const VOICE_THRESHOLD = 0.018;
const ASSISTANT_ECHO_WINDOW_MS = 15000;
const TABLET_STATE_KEY = "mirror-tablet-state";
const CAMERA_DEVICE_KEY = "mirror-preferred-camera-device-id";
const PREFERRED_CAMERA_LABEL = "1080P USB Camera";
const SPEECH_RECOGNITION = window.SpeechRecognition || window.webkitSpeechRecognition;
const SCENE_VARIANTS = {
  "startup": "crown-trace",
  "listening": "wand-sweep",
  "thinking": "star-spiral",
  "reply": "bow-flash",
  "idle": "ribbon-sway",
};
const STARTUP_SETTLE_MS = 2400;
const tabletChannel =
  typeof BroadcastChannel === "function" ? new BroadcastChannel("mirror-tablet-display") : null;

let mediaRecorder = null;
let recordedChunks = [];
let voiceStream = null;
let cameraStream = null;
let isRecording = false;
let autoMirrorMode = false;
let audioContext = null;
let voiceAnalyser = null;
let voiceSource = null;
let voiceData = null;
let voiceFrameId = null;
let voiceSilenceTimer = null;
let voiceMaxTimer = null;
let voiceHasSpeech = false;
let recognition = null;
let availableCameras = [];
let preferredCameraDeviceId = readStoredCameraDeviceId();
let activeCameraTrack = null;
let cameraRecoveryPromise = null;
let activeReminder = null;
let reminderInterval = null;
let activeAudioPlayer = null;
let playbackQueue = Promise.resolve();
let lastPlayedReminderId = "";
let sceneSettleTimer = null;
let dueReminderPollPromise = null;
let recentAssistantSpeech = [];
let openingGreetingRequestInFlight = false;
let openingGreetingPlayed = false;

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

function variableElements(items) {
  return items
    .map((item) => {
      const style = Object.entries(item)
        .filter(([key]) => key !== "className")
        .map(([key, value]) => `--${key}:${value}`)
        .join(";");
      return `<span class="${item.className}" style="${style}"></span>`;
    })
    .join("");
}

const stageTemplates = {
  "crown-trace": `
    <div class="scene-layer stage-crown-trace">
      <span class="scene-haze crown-haze"></span>
      ${crownSvg()}
      ${variableElements([
        { className: "jewel-dot", left: "35%", top: "26%", size: "8px", delay: "0.16s" },
        { className: "jewel-dot", left: "50%", top: "20.5%", size: "9px", delay: "0.34s" },
        { className: "jewel-dot", left: "65%", top: "26%", size: "8px", delay: "0.52s" },
      ])}
    </div>
  `,
  "wand-sweep": `
    <div class="scene-layer stage-wand-sweep">
      <span class="scene-haze listening-haze"></span>
      <span class="wand-line"></span>
      <span class="wand-echo"></span>
      <span class="wand-star"></span>
    </div>
  `,
  "star-spiral": `
    <div class="scene-layer stage-star-spiral">
      <span class="scene-haze thinking-haze"></span>
      <span class="center-glow"></span>
      ${variableElements([
        { className: "spiral-star", angle: "0deg", radius: "48px", delay: "0s", size: "10px" },
        { className: "spiral-star", angle: "72deg", radius: "62px", delay: "0.18s", size: "11px" },
        { className: "spiral-star", angle: "144deg", radius: "54px", delay: "0.36s", size: "10px" },
        { className: "spiral-star", angle: "216deg", radius: "70px", delay: "0.54s", size: "12px" },
        { className: "spiral-star", angle: "288deg", radius: "58px", delay: "0.72s", size: "10px" },
      ])}
    </div>
  `,
  "bow-flash": `
    <div class="scene-layer stage-bow-flash">
      <span class="scene-haze reply-haze"></span>
      <span class="soft-glow"></span>
      ${bowSvg()}
    </div>
  `,
  "ribbon-sway": `
    <div class="scene-layer stage-ribbon-sway">
      ${ribbonSvg("left")}
      ${ribbonSvg("right")}
      <span class="ribbon-knot"></span>
    </div>
  `,
};

function setAssistantLabel(label) {
  assistantLabel = label && label.trim() ? label.trim() : "我";
  document.body.dataset.assistantLabel = assistantLabel;
}

function setStatus(text) {
  if (!statusEl) {
    return;
  }
  statusEl.textContent = text;
}

function setControlsDisabled(disabled) {
  cameraSwitchButton.disabled = disabled;
  cameraButton.disabled = disabled;
}

async function playOpeningGreetingIfNeeded() {
  if (!needsNameOnboarding || assistantLabel !== "我" || openingGreetingPlayed || openingGreetingRequestInFlight) {
    return;
  }

  openingGreetingRequestInFlight = true;
  try {
    const response = await fetch("/api/onboarding/opening", { method: "GET" });
    const payload = await readPayload(response);
    if (!response.ok) {
      throw new Error(payload.error || "开场白这次没接住。");
    }

    openingGreetingPlayed = true;
    setAssistantLabel(payload.assistant_label);
    userSubtitleEl.textContent = "打开镜头后，直接告诉我你想怎么叫我。";
    agentSubtitleEl.textContent = payload.reply;
    rememberAssistantSpeech(payload.reply);
    setScene("reply");

    if (payload.audio_url) {
      const audioPlayer = createVoiceAudioPlayer(payload.audio_url);
      await queueAudioPlayback(
        audioPlayer,
        "我先把开场白说完，再接你下一句。",
        "自动播放被浏览器拦住了，不过字幕已经把开场白放出来了。"
      );
    }

    window.setTimeout(() => {
      if (!isRecording) {
        setScene("idle");
      }
    }, 1800);
  } catch (error) {
    userSubtitleEl.textContent = "打开镜头后，直接告诉我你想怎么叫我。";
    agentSubtitleEl.textContent = "嗨！我刚搬进你的镜子里，不过我还没有名字诶，你想叫我什么？";
    setScene("reply");
  } finally {
    openingGreetingRequestInFlight = false;
  }
}

function normalizeSpeechFingerprint(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .replace(/[\s，,。！？!?~～:：；;、"'“”‘’（）()\-]/g, "");
}

function pruneRecentAssistantSpeech() {
  const now = Date.now();
  recentAssistantSpeech = recentAssistantSpeech.filter((entry) => now - entry.timestamp <= ASSISTANT_ECHO_WINDOW_MS);
}

function rememberAssistantSpeech(text) {
  const fingerprint = normalizeSpeechFingerprint(text);
  if (fingerprint.length < 6) {
    return;
  }

  pruneRecentAssistantSpeech();
  recentAssistantSpeech.push({ fingerprint, timestamp: Date.now() });
  recentAssistantSpeech = recentAssistantSpeech.slice(-6);
}

function isLikelyAssistantEcho(text) {
  const fingerprint = normalizeSpeechFingerprint(text);
  if (fingerprint.length < 6) {
    return false;
  }

  pruneRecentAssistantSpeech();
  return recentAssistantSpeech.some(
    (entry) =>
      entry.fingerprint === fingerprint ||
      entry.fingerprint.includes(fingerprint) ||
      fingerprint.includes(entry.fingerprint)
  );
}

function normalizeScene(scene) {
  return typeof scene === "string" && scene in SCENE_VARIANTS ? scene : "idle";
}

function clearSceneSettleTimer() {
  if (!sceneSettleTimer) {
    return;
  }

  window.clearTimeout(sceneSettleTimer);
  sceneSettleTimer = null;
}

function renderScene(scene) {
  const safeScene = normalizeScene(scene);
  const variant = SCENE_VARIANTS[safeScene];
  haloStage.dataset.scene = safeScene;
  haloStage.dataset.variant = variant;

  if (haloSceneOverlay) {
    haloSceneOverlay.dataset.variant = variant;
    haloSceneOverlay.innerHTML = stageTemplates[variant] || "";
  }

  clearSceneSettleTimer();
  if (safeScene === "startup") {
    sceneSettleTimer = window.setTimeout(() => {
      if (haloStage.dataset.scene !== "startup") {
        return;
      }
      setScene("idle");
    }, STARTUP_SETTLE_MS);
  }
}

function setScene(scene) {
  const safeScene = normalizeScene(scene);
  renderScene(safeScene);
  pushTabletScene(safeScene);
}

function readStoredCameraDeviceId() {
  try {
    return localStorage.getItem(CAMERA_DEVICE_KEY) || "";
  } catch (error) {
    return "";
  }
}

function persistSelectedCameraDevice(deviceId) {
  preferredCameraDeviceId = deviceId || "";
  try {
    localStorage.setItem(CAMERA_DEVICE_KEY, preferredCameraDeviceId);
  } catch (error) {
    return;
  }
}

async function persistTabletState(nextState) {
  try {
    await fetch("/api/tablet-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nextState),
      keepalive: true,
    });
  } catch (error) {
    return;
  }
}

function readTabletState() {
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

function writeTabletState(nextState) {
  const payload = { ...nextState, timestamp: Date.now() };
  try {
    localStorage.setItem(TABLET_STATE_KEY, JSON.stringify(payload));
  } catch (error) {
    return;
  }
  if (tabletChannel) {
    tabletChannel.postMessage(payload);
  }
  void persistTabletState(payload);
}

function updateTabletState(updates = {}) {
  const currentState = readTabletState();
  writeTabletState({ ...currentState, ...updates });
}

function pushTabletScene(scene, details = {}) {
  updateTabletState({ scene, ...details });
}

function setTabletReminder(reminder) {
  if (!reminder) {
    updateTabletState({ reminder: null });
    return;
  }

  updateTabletState({
    reminder: {
      id: reminder.id,
      message: reminder.message,
      due_at: reminder.due_at,
      due_at_ms: reminder.due_at_ms,
    },
    lastTriggeredReminder: null,
  });
}

function markTabletReminderTriggered(reminder) {
  if (!reminder) {
    return;
  }

  updateTabletState({
    reminder: null,
    lastTriggeredReminder: {
      id: reminder.id || reminder.message,
      message: reminder.message,
      audio_url: reminder.audio_url || "",
      due_at: reminder.due_at || "",
      due_at_ms: reminder.due_at_ms || 0,
      triggered_at: new Date().toISOString(),
    },
  });
}

function readPayload(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text().then((text) => ({ error: text || "服务端返回了非 JSON 内容" }));
}

function waitForAudioPlayback(audioPlayer) {
  if (!audioPlayer || audioPlayer.ended || audioPlayer.paused) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const finish = () => {
      audioPlayer.removeEventListener("ended", finish);
      audioPlayer.removeEventListener("pause", finish);
      audioPlayer.removeEventListener("error", finish);
      resolve();
    };

    audioPlayer.addEventListener("ended", finish);
    audioPlayer.addEventListener("pause", finish);
    audioPlayer.addEventListener("error", finish);
  });
}

function registerManagedAudioPlayer(audioPlayer) {
  audioPlayer.addEventListener("play", () => {
    if (activeAudioPlayer && activeAudioPlayer !== audioPlayer && !activeAudioPlayer.paused) {
      activeAudioPlayer.pause();
    }
    activeAudioPlayer = audioPlayer;
  });

  const release = () => {
    if (activeAudioPlayer === audioPlayer) {
      activeAudioPlayer = null;
    }
  };

  audioPlayer.addEventListener("ended", release);
  audioPlayer.addEventListener("pause", release);
  audioPlayer.addEventListener("error", release);
}

function createVoiceAudioPlayer(audioUrl) {
  const audioPlayer = document.createElement("audio");
  audioPlayer.controls = true;
  audioPlayer.preload = "metadata";
  audioPlayer.src = audioUrl;
  audioPlayer.className = "voice-player";
  audioPlayer.hidden = true;
  registerManagedAudioPlayer(audioPlayer);
  document.body.appendChild(audioPlayer);
  return audioPlayer;
}

async function queueAudioPlayback(audioPlayer, waitingStatus, blockedStatus) {
  playbackQueue = playbackQueue.finally(async () => {
    if (activeAudioPlayer && activeAudioPlayer !== audioPlayer && !activeAudioPlayer.paused) {
      if (waitingStatus) {
        setStatus(waitingStatus);
      }
      await waitForAudioPlayback(activeAudioPlayer);
    }

    try {
      await audioPlayer.play();
      await waitForAudioPlayback(audioPlayer);
    } catch (error) {
      if (blockedStatus) {
        setStatus(blockedStatus);
      }
    }
  });

  return playbackQueue;
}

function setCameraDeviceLabel(label) {
  cameraDeviceName.textContent = `当前摄像头：${label}`;
}

function stopMediaStream(stream) {
  if (!stream) {
    return;
  }
  stream.getTracks().forEach((track) => track.stop());
}

function getVideoTrack(stream = cameraStream) {
  if (!stream) {
    return null;
  }
  return stream.getVideoTracks()[0] || null;
}

function getVideoTrackDeviceId(videoTrack) {
  if (!videoTrack || typeof videoTrack.getSettings !== "function") {
    return "";
  }
  return videoTrack.getSettings().deviceId || "";
}

async function listVideoInputs() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
    return [];
  }
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((device) => device.kind === "videoinput");
}

function normalizeCameraLabel(label = "") {
  return label.trim().toLowerCase();
}

function isLikelyBuiltInCamera(label = "") {
  const normalized = normalizeCameraLabel(label);
  if (!normalized) {
    return false;
  }
  return [
    "facetime",
    "built-in",
    "builtin",
    "integrated",
    "macbook air相机",
    "macbook pro相机",
    "内建",
    "内置",
  ].some((keyword) => normalized.includes(keyword));
}

function findPreferredVideoInput(devices) {
  const selectedDevice = preferredCameraDeviceId
    ? devices.find((device) => device.deviceId === preferredCameraDeviceId)
    : null;
  if (selectedDevice) {
    return selectedDevice;
  }

  const namedPreferred = devices.find((device) => device.label === PREFERRED_CAMERA_LABEL) || null;
  if (namedPreferred) {
    return namedPreferred;
  }

  const externalDevice = devices.find((device) => !isLikelyBuiltInCamera(device.label)) || null;
  if (externalDevice) {
    return externalDevice;
  }

  return devices[0] || null;
}

function detachActiveCameraTrack() {
  if (!activeCameraTrack) {
    return;
  }
  activeCameraTrack.removeEventListener("ended", handleCameraTrackEnded);
  activeCameraTrack = null;
}

function bindActiveCameraTrack(stream) {
  detachActiveCameraTrack();
  const videoTrack = getVideoTrack(stream);
  if (!videoTrack) {
    return;
  }
  videoTrack.addEventListener("ended", handleCameraTrackEnded);
  activeCameraTrack = videoTrack;
}

async function refreshAvailableCameras() {
  availableCameras = await listVideoInputs().catch(() => []);
  return availableCameras;
}

async function openExactCameraStream(deviceId) {
  return navigator.mediaDevices.getUserMedia({
    video: { deviceId: { exact: deviceId } },
    audio: false,
  });
}

async function openPreferredCameraStream() {
  const devices = await refreshAvailableCameras();

  if (preferredCameraDeviceId) {
    const current = devices.find((device) => device.deviceId === preferredCameraDeviceId);
    if (current) {
      try {
        return await openExactCameraStream(current.deviceId);
      } catch (error) {
        preferredCameraDeviceId = "";
      }
    }
  }

  const preferred = findPreferredVideoInput(devices);
  if (preferred && preferred.deviceId) {
    preferredCameraDeviceId = preferred.deviceId;
    try {
      return await openExactCameraStream(preferred.deviceId);
    } catch (error) {
      preferredCameraDeviceId = "";
    }
  }

  return navigator.mediaDevices.getUserMedia({ video: true, audio: false });
}

async function syncCameraDeviceName(stream) {
  const videoTrack = getVideoTrack(stream);
  if (!videoTrack) {
    setCameraDeviceLabel("未连接");
    return "未连接";
  }

  let label = videoTrack.label && videoTrack.label.trim() ? videoTrack.label.trim() : "";
  if (!label) {
    const devices = await refreshAvailableCameras();
    const matched = devices.find((device) => device.deviceId === getVideoTrackDeviceId(videoTrack));
    label = matched && matched.label ? matched.label.trim() : "";
  }

  if (!label) {
    label = "系统默认摄像头";
  }

  const deviceId = getVideoTrackDeviceId(videoTrack);
  if (deviceId) {
    persistSelectedCameraDevice(deviceId);
  }

  setCameraDeviceLabel(label);
  return label;
}

async function cycleCameraDevice() {
  availableCameras = await refreshAvailableCameras();
  if (availableCameras.length === 0) {
    setStatus("当前没有可切换的摄像头。");
    return;
  }

  const currentIndex = availableCameras.findIndex((device) => device.deviceId === preferredCameraDeviceId);
  const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % availableCameras.length : 0;
  const nextDevice = availableCameras[nextIndex];
  persistSelectedCameraDevice(nextDevice.deviceId);

  if (cameraStream) {
    await restoreCameraPreview("已经切到下一个摄像头。");
    return;
  }

  setCameraDeviceLabel(nextDevice.label || `摄像头 ${nextIndex + 1}`);
  setStatus("下次打开镜头时会使用这个摄像头。");
}

async function waitForCameraFrame() {
  if (!cameraPreview || !cameraPreview.srcObject) {
    return;
  }

  if (cameraPreview.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && cameraPreview.videoWidth > 0) {
    return;
  }

  await new Promise((resolve, reject) => {
    const cleanup = () => {
      cameraPreview.removeEventListener("loadeddata", handleLoaded);
      cameraPreview.removeEventListener("error", handleError);
    };

    const handleLoaded = () => {
      cleanup();
      resolve();
    };

    const handleError = () => {
      cleanup();
      reject(new Error("镜头画面还没准备好。"));
    };

    cameraPreview.addEventListener("loadeddata", handleLoaded, { once: true });
    cameraPreview.addEventListener("error", handleError, { once: true });
  });
}

async function captureCameraFrame() {
  if (!cameraStream || !cameraCanvas) {
    return null;
  }

  await waitForCameraFrame();
  const width = cameraPreview.videoWidth || 960;
  const height = cameraPreview.videoHeight || 540;
  cameraCanvas.width = width;
  cameraCanvas.height = height;
  const context = cameraCanvas.getContext("2d");
  if (!context) {
    return null;
  }
  context.drawImage(cameraPreview, 0, 0, width, height);
  return new Promise((resolve) => {
    cameraCanvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.92);
  });
}

function stopVoiceTracks() {
  if (!voiceStream) {
    return;
  }
  voiceStream.getTracks().forEach((track) => track.stop());
  voiceStream = null;
}

function clearVoiceTimers() {
  if (voiceSilenceTimer) {
    window.clearTimeout(voiceSilenceTimer);
    voiceSilenceTimer = null;
  }
  if (voiceMaxTimer) {
    window.clearTimeout(voiceMaxTimer);
    voiceMaxTimer = null;
  }
  if (voiceFrameId) {
    window.cancelAnimationFrame(voiceFrameId);
    voiceFrameId = null;
  }
}

async function destroyVoiceMonitor() {
  clearVoiceTimers();
  if (voiceSource) {
    voiceSource.disconnect();
    voiceSource = null;
  }
  if (voiceAnalyser) {
    voiceAnalyser.disconnect();
    voiceAnalyser = null;
  }
  voiceData = null;
  if (audioContext) {
    await audioContext.close().catch(() => {});
    audioContext = null;
  }
}

function stopSubtitleRecognition() {
  if (!recognition) {
    return;
  }
  recognition.onresult = null;
  recognition.onerror = null;
  recognition.onend = null;
  recognition.stop();
  recognition = null;
}

function startSubtitleRecognition() {
  if (!SPEECH_RECOGNITION) {
    return;
  }

  recognition = new SPEECH_RECOGNITION();
  recognition.lang = "zh-CN";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.onresult = (event) => {
    let subtitle = "";
    for (let index = 0; index < event.results.length; index += 1) {
      subtitle += event.results[index][0].transcript;
    }
    userSubtitleEl.textContent = subtitle.trim() || "我在听你说。";
  };
  recognition.onerror = () => {};
  recognition.onend = () => {
    recognition = null;
  };
  recognition.start();
}

function createVoiceAudioContext() {
  if (window.AudioContext) {
    return new AudioContext();
  }
  if (window.webkitAudioContext) {
    return new window.webkitAudioContext();
  }
  return null;
}

function stopVoiceRecording() {
  clearVoiceTimers();
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
}

function monitorVoiceLevel() {
  if (!voiceAnalyser || !voiceData || !isRecording) {
    return;
  }

  voiceAnalyser.getFloatTimeDomainData(voiceData);
  let sum = 0;
  for (const sample of voiceData) {
    sum += sample * sample;
  }

  const rms = Math.sqrt(sum / voiceData.length);
  if (rms > VOICE_THRESHOLD) {
    voiceHasSpeech = true;
    if (voiceSilenceTimer) {
      window.clearTimeout(voiceSilenceTimer);
      voiceSilenceTimer = null;
    }
  } else if (voiceHasSpeech && !voiceSilenceTimer) {
    voiceSilenceTimer = window.setTimeout(stopVoiceRecording, VOICE_SILENCE_MS);
  }

  voiceFrameId = window.requestAnimationFrame(monitorVoiceLevel);
}

async function startVoiceMonitor(stream) {
  audioContext = createVoiceAudioContext();
  if (!audioContext) {
    throw new Error("这个浏览器还不支持网页语音监听。");
  }

  if (audioContext.state === "suspended") {
    await audioContext.resume();
  }

  voiceSource = audioContext.createMediaStreamSource(stream);
  voiceAnalyser = audioContext.createAnalyser();
  voiceAnalyser.fftSize = 2048;
  voiceData = new Float32Array(voiceAnalyser.fftSize);
  voiceSource.connect(voiceAnalyser);
  voiceHasSpeech = false;
  voiceMaxTimer = window.setTimeout(stopVoiceRecording, VOICE_MAX_MS);
  voiceFrameId = window.requestAnimationFrame(monitorVoiceLevel);
}

async function streamVoice(blob, onEvent, frameBlob = null, cameraActive = false) {
  const formData = new FormData();
  formData.append("audio", blob, "mirror-agent-voice.webm");
  if (cameraActive) {
    formData.append("camera_active", "true");
  }
  if (frameBlob) {
    formData.append("frame", frameBlob, "mirror-agent-frame.jpg");
  }

  const response = await fetch("/api/voice-chat-stream", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await readPayload(response);
    throw new Error(payload.error || "语音发送失败");
  }

  if (!response.body) {
    throw new Error("服务端这次没把字幕流吐出来。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      await onEvent(JSON.parse(trimmed));
    }
  }

  const tail = buffer.trim();
  if (tail) {
    await onEvent(JSON.parse(tail));
  }
}

function normalizeReminder(reminder) {
  if (!reminder || typeof reminder !== "object") {
    return null;
  }

  const dueAt = String(reminder.due_at || reminder.dueAt || "").trim();
  const dueAtMs = Number(reminder.due_at_ms ?? reminder.dueAtMs);
  const message = String(reminder.message || "").trim();
  const id = String(reminder.id || message).trim();
  if (!message) {
    return null;
  }

  return {
    id,
    message,
    due_at: dueAt,
    due_at_ms: Number.isFinite(dueAtMs) && dueAtMs > 0 ? dueAtMs : parseReminderDueAtMs({ due_at: dueAt }),
    audio_url: String(reminder.audio_url || reminder.audioUrl || "").trim(),
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

function formatDueTime(reminder) {
  const dueAtMs = parseReminderDueAtMs(reminder);
  if (!Number.isFinite(dueAtMs) || dueAtMs <= 0) {
    return "";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(dueAtMs));
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

function stopReminderCountdown() {
  if (!reminderInterval) {
    return;
  }

  window.clearInterval(reminderInterval);
  reminderInterval = null;
}

function showDueReminder(reminder) {
  countdownPanelEl.hidden = false;
  countdownPanelEl.dataset.state = "due";
  countdownValueEl.textContent = "00:00";
  countdownMessageEl.textContent = reminder.message;
  haloStage.dataset.reminder = "due";
}

function clearReminderDisplay() {
  if (activeReminder) {
    renderReminder(activeReminder);
    return;
  }

  if (countdownPanelEl.dataset.state !== "due") {
    return;
  }

  renderReminder(null);
}

async function presentDueReminder(reminder) {
  const normalized = normalizeReminder(reminder);
  if (!normalized) {
    return false;
  }

  if (normalized.id && normalized.id === lastPlayedReminderId) {
    return true;
  }

  if (normalized.id) {
    lastPlayedReminderId = normalized.id;
  }

  activeReminder = null;
  stopReminderCountdown();
  showDueReminder(normalized);
  rememberAssistantSpeech(normalized.message);
  setAssistantLabel(reminder.assistant_label || assistantLabel);
  agentSubtitleEl.textContent = normalized.message;
  markTabletReminderTriggered(normalized);
  setScene("reply");

  if (normalized.audio_url) {
    const audioPlayer = createVoiceAudioPlayer(normalized.audio_url);
    await queueAudioPlayback(
      audioPlayer,
      "我在整理提醒，不会让它和上一条语音撞在一起。",
      "自动播放被浏览器拦住了，提醒已经到了。"
    );
  } else {
    setStatus("提醒时间到了。");
  }

  window.setTimeout(() => {
    clearReminderDisplay();
    if (!isRecording) {
      setScene("idle");
    }
  }, 1400);
  return true;
}

async function pollDueReminders(options = {}) {
  const { expectedReminderId = "" } = options;
  if (dueReminderPollPromise) {
    return dueReminderPollPromise;
  }

  dueReminderPollPromise = (async () => {
    let handledExpectedReminder = false;
    try {
      const response = await fetch("/api/reminders/due", { method: "GET" });
      const payload = await readPayload(response);
      if (!response.ok || !payload.reminders || payload.reminders.length === 0) {
        return false;
      }

      for (const reminder of payload.reminders) {
        const normalized = normalizeReminder(reminder);
        if (!normalized) {
          continue;
        }
        if (await presentDueReminder(reminder)) {
          if (expectedReminderId && normalized.id === expectedReminderId) {
            handledExpectedReminder = true;
          }
        }
      }
      return handledExpectedReminder;
    } catch (error) {
      return false;
    } finally {
      dueReminderPollPromise = null;
    }
  })();

  return dueReminderPollPromise;
}

async function triggerReminderDue(reminder, options = {}) {
  const { preferBackend = false } = options;
  const normalized = normalizeReminder(reminder);
  if (!normalized) {
    return;
  }

  if (normalized.id && normalized.id === lastPlayedReminderId) {
    return;
  }

  if (preferBackend) {
    const handledByBackend = await pollDueReminders({ expectedReminderId: normalized.id });
    if (handledByBackend) {
      return;
    }
  }

  await presentDueReminder(normalized);
}

function updateReminderCountdown() {
  renderReminder(activeReminder);
}

function setActiveReminder(reminder) {
  activeReminder = normalizeReminder(reminder);
  renderReminder(activeReminder);

  stopReminderCountdown();

  if (activeReminder) {
    reminderInterval = window.setInterval(updateReminderCountdown, 1000);
  }
}

function restoreReminderFromSharedState(state) {
  if (!state || typeof state !== "object" || !state.reminder) {
    return;
  }

  setActiveReminder(state.reminder);
}

function renderReminder(reminder) {
  const normalized = normalizeReminder(reminder);
  if (!normalized) {
    countdownPanelEl.hidden = true;
    countdownPanelEl.dataset.state = "idle";
    countdownValueEl.textContent = "00:00";
    countdownMessageEl.textContent = "";
    haloStage.dataset.reminder = "idle";
    return;
  }

  countdownPanelEl.hidden = false;
  const remainingMs = Number.isNaN(normalized.due_at_ms) ? 0 : normalized.due_at_ms - Date.now();
  if (remainingMs <= 0) {
    showDueReminder(normalized);
    void triggerReminderDue(normalized, { preferBackend: true });
    return;
  }
  const reminderState = remainingMs > 0 ? "active" : "due";
  countdownPanelEl.dataset.state = reminderState;
  haloStage.dataset.reminder = reminderState;
  countdownValueEl.textContent = formatRemainingTime(remainingMs);
  countdownMessageEl.textContent = normalized.message;
}

function scheduleAutoVoiceRound(delayMs = 450) {
  if (!autoMirrorMode || !cameraStream || isRecording) {
    return;
  }

  window.setTimeout(() => {
    if (!autoMirrorMode || !cameraStream || isRecording) {
      return;
    }
    void startVoiceRecording({ autoStarted: true });
  }, delayMs);
}

async function startVoiceRecording(options = {}) {
  const { autoStarted = false } = options;
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    setStatus("这个浏览器不支持网页录音。");
    return;
  }
  if (isRecording || !cameraStream) {
    return;
  }

  voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  await startVoiceMonitor(voiceStream);
  recordedChunks = [];
  startSubtitleRecognition();
  userSubtitleEl.textContent = "我在听你说。";
  agentSubtitleEl.textContent = `${assistantLabel} 正在听你说`;
  mediaRecorder = new MediaRecorder(voiceStream);
  mediaRecorder.addEventListener("dataavailable", (event) => {
    if (event.data && event.data.size > 0) {
      recordedChunks.push(event.data);
    }
  });
  mediaRecorder.addEventListener("stop", async () => {
    const audioBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
    let frameBlob = null;
    try {
      frameBlob = await captureCameraFrame();
    } catch (error) {
      frameBlob = null;
    }

    stopSubtitleRecognition();
    await destroyVoiceMonitor();
    stopVoiceTracks();
    isRecording = false;

    if (autoStarted && isLikelyAssistantEcho(userSubtitleEl.textContent)) {
      userSubtitleEl.textContent = "我在等你下一句。";
      agentSubtitleEl.textContent = `${assistantLabel} 先把刚才那点回声略过去了`;
      setScene("idle");
      if (autoMirrorMode && cameraStream) {
        setStatus("刚才更像是我自己的回声，我继续等你下一句。");
        scheduleAutoVoiceRound(1200);
      } else {
        setStatus("刚才更像是我自己的回声。");
      }
      return;
    }

    if (!voiceHasSpeech || audioBlob.size === 0) {
      userSubtitleEl.textContent = "这次没听清。";
      agentSubtitleEl.textContent = `${assistantLabel} 还在等你下一句`;
      setScene("idle");
      if (autoMirrorMode && cameraStream) {
        setStatus("镜头还开着，我继续等你下一句。");
        scheduleAutoVoiceRound();
      } else {
        setStatus("我刚刚没听清。");
      }
      return;
    }

    try {
      setScene("thinking");
      agentSubtitleEl.textContent = `${assistantLabel} 正在想`;
      setStatus(frameBlob ? "我在看你这张当前画面。" : "我先按语音接你。");
      let replyStarted = false;
      await streamVoice(
        audioBlob,
        async ({
          type,
          text,
          delta,
          reply,
          audio_url: audioUrl,
          error,
          assistant_label: assistantLabelFromEvent,
          scheduled_reminder: scheduledReminder,
        }) => {
          if (type === "transcript") {
            setAssistantLabel(assistantLabelFromEvent);
            userSubtitleEl.textContent = text;
            agentSubtitleEl.textContent = `${assistantLabel} 正在想`;
            setScene("thinking");
            setStatus(`${assistantLabel} 在回你，字幕开始走了。`);
            return;
          }

          if (type === "reply_delta") {
            setAssistantLabel(assistantLabelFromEvent);
            if (!replyStarted) {
              replyStarted = true;
              setScene("reply");
            }
            agentSubtitleEl.textContent = text || delta || "";
            return;
          }

          if (type === "reply_done") {
            setAssistantLabel(assistantLabelFromEvent);
            setScene("reply");
            agentSubtitleEl.textContent = reply;
            rememberAssistantSpeech(reply);
            if (scheduledReminder) {
              setActiveReminder(scheduledReminder);
              setTabletReminder(scheduledReminder);
            }
            if (audioUrl) {
              const audioPlayer = createVoiceAudioPlayer(audioUrl);
              await queueAudioPlayback(
                audioPlayer,
                "上一条语音还在说，我让它说完再接这条。",
                "自动播放被浏览器拦住了，字幕已经到了。"
              );
            }
            setStatus(autoMirrorMode ? "这一轮聊完了，我会继续听下一句。" : "这一轮聊完了。");
            window.setTimeout(() => {
              if (!isRecording) {
                setScene("idle");
              }
            }, 1400);
            return;
          }

          if (type === "error") {
            throw new Error(error || "语音流式回复失败");
          }
        },
        frameBlob,
        Boolean(cameraStream)
      );

      if (autoMirrorMode && cameraStream) {
        scheduleAutoVoiceRound();
      }
    } catch (error) {
      agentSubtitleEl.textContent = error.message;
      setScene("idle");
      if (autoMirrorMode && cameraStream) {
        setStatus("这段语音没发出去，但镜头还在，我继续帮你守着。");
        scheduleAutoVoiceRound(900);
      } else {
        setStatus("这段语音没发出去，再试一次。");
      }
    }
  });

  mediaRecorder.start();
  isRecording = true;
  setScene("listening");
  setStatus(autoStarted ? "镜头模式已经在听了，你直接说就行。" : "我已经开始听你说。");
}

function stopCameraTracks() {
  detachActiveCameraTrack();
  if (cameraStream) {
    stopMediaStream(cameraStream);
    cameraStream = null;
  }
  cameraPreview.srcObject = null;
}

async function restoreCameraPreview(reason = "镜头已切换，我继续陪你。") {
  if (!autoMirrorMode) {
    return;
  }
  if (cameraRecoveryPromise) {
    await cameraRecoveryPromise;
    return;
  }

  cameraRecoveryPromise = (async () => {
    stopCameraTracks();
    try {
      cameraStream = await openPreferredCameraStream();
      bindActiveCameraTrack(cameraStream);
      cameraPreview.srcObject = cameraStream;
      await cameraPreview.play();
      if (cameraFloatEl) {
        cameraFloatEl.dataset.active = "true";
      }
      const label = await syncCameraDeviceName(cameraStream);
      setStatus(`${reason} 当前摄像头是 ${label}。`);
    } catch (error) {
      autoMirrorMode = false;
      stopCameraTracks();
      if (cameraFloatEl) {
        cameraFloatEl.dataset.active = "false";
      }
      setCameraDeviceLabel("未连接");
      cameraButton.textContent = "打开镜头";
      setScene("idle");
      setStatus("当前没有可用摄像头了，请重新插好后再点一次。");
    } finally {
      cameraRecoveryPromise = null;
    }
  })();

  await cameraRecoveryPromise;
}

function handleCameraTrackEnded() {
  if (!autoMirrorMode) {
    return;
  }
  void restoreCameraPreview("外接镜头断开了，我已经帮你切到可用镜头。");
}

async function handleCameraDeviceChange() {
  if (cameraRecoveryPromise) {
    return;
  }

  availableCameras = await refreshAvailableCameras();
  if (!autoMirrorMode) {
    return;
  }

  const videoTrack = getVideoTrack(cameraStream);
  const currentDeviceId = getVideoTrackDeviceId(videoTrack);
  const currentStillExists = currentDeviceId
    ? availableCameras.some((device) => device.deviceId === currentDeviceId)
    : false;
  const preferredDevice = findPreferredVideoInput(availableCameras);

  if (!currentStillExists) {
    void restoreCameraPreview("镜头设备变了，我已经帮你重新接上。");
    return;
  }

  if (preferredDevice && preferredDevice.deviceId && preferredDevice.deviceId !== currentDeviceId) {
    void restoreCameraPreview("检测到外接镜头可用了，我已经切回它。");
    return;
  }

  void syncCameraDeviceName(cameraStream);
}

async function startCameraPreview() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("这个浏览器不支持网页摄像头。");
  }

  cameraStream = await openPreferredCameraStream();
  bindActiveCameraTrack(cameraStream);
  cameraPreview.srcObject = cameraStream;
  await cameraPreview.play();
  if (cameraFloatEl) {
    cameraFloatEl.dataset.active = "true";
  }
  const label = await syncCameraDeviceName(cameraStream);
  autoMirrorMode = true;
  cameraButton.textContent = "关闭镜头";
  setScene("listening");
  setStatus(`镜头已经开好了，当前摄像头是 ${label}。`);
  await startVoiceRecording({ autoStarted: true });
}

function stopCameraPreview() {
  autoMirrorMode = false;
  if (isRecording) {
    stopVoiceRecording();
  }
  stopCameraTracks();
  if (cameraFloatEl) {
    cameraFloatEl.dataset.active = "false";
  }
  setCameraDeviceLabel("未连接");
  cameraButton.textContent = "打开镜头";
  if (needsNameOnboarding && assistantLabel === "我") {
    userSubtitleEl.textContent = "打开镜头后，直接告诉我你想怎么叫我。";
    agentSubtitleEl.textContent = "我会先记住名字，再继续陪你。";
  } else {
    userSubtitleEl.textContent = "打开镜头后，我会在这里轻声复述你刚说的话。";
    agentSubtitleEl.textContent = `${assistantLabel} 会在这里用很短的字幕回应你。`;
  }
  setScene("idle");
  setStatus("镜头已经关上了。");
}

async function toggleCameraPreview() {
  if (!cameraStream) {
    await startCameraPreview();
    return;
  }
  stopCameraPreview();
}

cameraSwitchButton.addEventListener("click", async () => {
  try {
    await cycleCameraDevice();
  } catch (error) {
    setStatus("切换摄像头失败了。");
  }
});

cameraButton.addEventListener("click", async () => {
  try {
    await toggleCameraPreview();
  } catch (error) {
    stopCameraTracks();
    if (cameraFloatEl) {
      cameraFloatEl.dataset.active = "false";
    }
    setCameraDeviceLabel("未连接");
    cameraButton.textContent = "打开镜头";
    setScene("idle");
    agentSubtitleEl.textContent = error.message || "没拿到摄像头权限。";
    setStatus("先给浏览器摄像头和麦克风权限，我们再试一次。");
  }
});

if (navigator.mediaDevices && typeof navigator.mediaDevices.addEventListener === "function") {
  navigator.mediaDevices.addEventListener("devicechange", handleCameraDeviceChange);
}

void refreshAvailableCameras().then(() => {
  const preferred = findPreferredVideoInput(availableCameras);
  if (preferred) {
    persistSelectedCameraDevice(preferred.deviceId);
    setCameraDeviceLabel(preferred.label || "准备就绪");
  }
});

const initialTabletState = readTabletState();
restoreReminderFromSharedState(initialTabletState);

window.setInterval(() => {
  void pollDueReminders();
}, 5000);
void pollDueReminders();
setScene("startup");
void playOpeningGreetingIfNeeded();

window.addEventListener("beforeunload", () => {
  clearSceneSettleTimer();
  stopSubtitleRecognition();
  stopVoiceTracks();
  stopCameraTracks();
  if (reminderInterval) {
    window.clearInterval(reminderInterval);
  }
  if (navigator.mediaDevices && typeof navigator.mediaDevices.removeEventListener === "function") {
    navigator.mediaDevices.removeEventListener("devicechange", handleCameraDeviceChange);
  }
});
