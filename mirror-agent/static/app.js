const messagesEl = document.getElementById("messages");
const statusEl = document.getElementById("status");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const imageInput = document.getElementById("image-input");
const imageNoteInput = document.getElementById("image-note");
const endButton = document.getElementById("end-button");
const voiceButton = document.getElementById("voice-button");
const cameraButton = document.getElementById("camera-button");
const cameraSelect = document.getElementById("camera-select");
const cameraPreview = document.getElementById("camera-preview");
const cameraCanvas = document.getElementById("camera-canvas");
const cameraDeviceName = document.getElementById("camera-device-name");
const mirrorEffects = document.getElementById("mirror-effects");
let assistantLabel = document.body.dataset.assistantLabel || "我";
const VOICE_SILENCE_MS = 1200;
const VOICE_MAX_MS = 12000;
const VOICE_THRESHOLD = 0.018;
const TABLET_STATE_KEY = "mirror-tablet-state";
const CAMERA_DEVICE_KEY = "mirror-preferred-camera-device-id";
const PREFERRED_CAMERA_LABEL = "1080P USB Camera";
const SPEECH_RECOGNITION = window.SpeechRecognition || window.webkitSpeechRecognition;
const tabletChannel =
  typeof BroadcastChannel === "function" ? new BroadcastChannel("mirror-tablet-display") : null;
let mediaRecorder = null;
let recordedChunks = [];
let voiceStream = null;
let cameraStream = null;
let isRecording = false;
let audioContext = null;
let voiceAnalyser = null;
let voiceSource = null;
let voiceData = null;
let voiceFrameId = null;
let voiceSilenceTimer = null;
let voiceMaxTimer = null;
let voiceHasSpeech = false;
let recognition = null;
let pendingUserVoiceBody = null;
let pendingUserVoiceCard = null;
let pendingAgentVoiceBody = null;
let pendingAgentVoiceCard = null;
let pendingAgentVoiceAudio = null;
let activeAudioPlayer = null;
let playbackQueue = Promise.resolve();
let autoMirrorMode = false;
let cameraSnapshotTimer = null;
let latestCameraFrameBlob = null;
let latestCameraRegionBlobs = [];
let tabletSceneTimer = null;
let preferredCameraDeviceId = readStoredCameraDeviceId();
let activeCameraTrack = null;
let cameraRecoveryPromise = null;

async function persistTabletState(nextState) {
  try {
    await fetch("/api/tablet-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(nextState),
      keepalive: true,
    });
  } catch (error) {
    // Cross-device sync should fail soft; same-device local sync can still keep the UI moving.
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
    localStorage.setItem(CAMERA_DEVICE_KEY, deviceId);
  } catch (error) {
    // Camera selection persistence should fail soft.
  }
}

function writeTabletState(nextState) {
  const payload = { ...nextState, timestamp: Date.now() };
  try {
    localStorage.setItem("mirror-tablet-state", JSON.stringify(payload));
  } catch (error) {
    // localStorage can be disabled in some private contexts; tablet sync should fail soft.
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
      id: reminder.id,
      message: reminder.message,
      audio_url: reminder.audio_url || "",
      due_at: reminder.due_at || "",
      triggered_at: new Date().toISOString(),
    },
  });
}

function queueTabletScene(scene, delayMs = 0, details = {}) {
  if (tabletSceneTimer) {
    window.clearTimeout(tabletSceneTimer);
    tabletSceneTimer = null;
  }
  if (delayMs <= 0) {
    pushTabletScene(scene, details);
    return;
  }
  tabletSceneTimer = window.setTimeout(() => {
    pushTabletScene(scene, details);
    tabletSceneTimer = null;
  }, delayMs);
}

function setAssistantLabel(label) {
  assistantLabel = label && label.trim() ? label.trim() : "我";
  document.body.dataset.assistantLabel = assistantLabel;
}

function appendMessage(role, text) {
  const card = document.createElement("article");
  card.className = `message message-${role}`;

  const roleNode = document.createElement("p");
  roleNode.className = "message-role";
  roleNode.textContent = role === "user" ? "你" : role === "agent" ? assistantLabel : "系统";

  const bodyNode = document.createElement("p");
  bodyNode.textContent = text;

  card.append(roleNode, bodyNode);
  messagesEl.appendChild(card);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendAgentVoiceReply(text, audioUrl) {
  const card = document.createElement("article");
  card.className = "message message-agent";

  const roleNode = document.createElement("p");
  roleNode.className = "message-role";
  roleNode.textContent = assistantLabel;

  const bodyNode = document.createElement("p");
  bodyNode.textContent = text;

  const audioPlayer = createVoiceAudioPlayer(audioUrl);

  card.append(roleNode, bodyNode, audioPlayer);
  messagesEl.appendChild(card);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return audioPlayer;
}

function createVoiceAudioPlayer(audioUrl) {
  const audioPlayer = document.createElement("audio");
  audioPlayer.controls = true;
  audioPlayer.preload = "metadata";
  audioPlayer.src = audioUrl;
  audioPlayer.className = "voice-player";
  registerManagedAudioPlayer(audioPlayer);
  return audioPlayer;
}

function createLiveMessage(role, text = "") {
  const card = document.createElement("article");
  card.className = `message message-${role}`;

  const roleNode = document.createElement("p");
  roleNode.className = "message-role";
  roleNode.textContent = role === "user" ? "你" : role === "agent" ? assistantLabel : "系统";

  const bodyNode = document.createElement("p");
  bodyNode.textContent = text;

  card.append(roleNode, bodyNode);
  messagesEl.appendChild(card);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { card, bodyNode };
}

function setStatus(text) {
  statusEl.textContent = text;
}

function triggerMirrorEffect(effectName) {
  if (!mirrorEffects || !effectName) {
    return;
  }

  const burst = document.createElement("div");
  burst.className = `effect-burst effect-${effectName}`;
  mirrorEffects.appendChild(burst);
  window.setTimeout(() => {
    burst.remove();
  }, 1600);
}

function applyInteractionPayload(payload) {
  if (!payload || !payload.ui_effect) {
    return;
  }
  triggerMirrorEffect(payload.ui_effect);
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
    } catch (playError) {
      if (blockedStatus) {
        setStatus(blockedStatus);
      }
    }
  });

  return playbackQueue;
}

async function readPayload(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return { error: text || "服务端返回了非 JSON 内容" };
}

async function sendChat(message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const payload = await readPayload(response);
  if (!response.ok) {
    throw new Error(payload.error || "消息发送失败");
  }
  return payload;
}

async function sendImage(file, note) {
  const formData = new FormData();
  formData.append("image", file);
  formData.append("note", note);

  const response = await fetch("/api/image", {
    method: "POST",
    body: formData,
  });
  const payload = await readPayload(response);
  if (!response.ok) {
    throw new Error(payload.error || "图片发送失败");
  }
  return payload;
}

async function endSession() {
  const response = await fetch("/api/end", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "晚安" }),
  });
  const payload = await readPayload(response);
  if (!response.ok) {
    throw new Error(payload.error || "结束会话失败");
  }
  return payload;
}

async function sendVoice(blob, frameBlob = null, regionBlobs = [], cameraActive = false) {
  const formData = new FormData();
  formData.append("audio", blob, "mirror-agent-voice.webm");
  if (cameraActive) {
    formData.append("camera_active", "true");
  }
  if (frameBlob) {
    formData.append("frame", frameBlob, "mirror-agent-frame.jpg");
  }
  for (const region of regionBlobs) {
    formData.append("frame_regions", region.blob, `mirror-region-${region.name}.jpg`);
  }

  const response = await fetch("/api/voice-chat", {
    method: "POST",
    body: formData,
  });
  const payload = await readPayload(response);
  if (!response.ok) {
    throw new Error(payload.error || "语音发送失败");
  }
  return payload;
}

async function streamVoice(blob, onEvent, frameBlob = null, regionBlobs = [], cameraActive = false) {
  const formData = new FormData();
  formData.append("audio", blob, "mirror-agent-voice.webm");
  if (cameraActive) {
    formData.append("camera_active", "true");
  }
  if (frameBlob) {
    formData.append("frame", frameBlob, "mirror-agent-frame.jpg");
  }
  for (const region of regionBlobs) {
    formData.append("frame_regions", region.blob, `mirror-region-${region.name}.jpg`);
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

function stopVoiceTracks() {
  if (!voiceStream) {
    return;
  }
  voiceStream.getTracks().forEach((track) => track.stop());
  voiceStream = null;
}

function setCameraDeviceLabel(label) {
  if (!cameraDeviceName) {
    return;
  }
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
    ? devices.find((device) => device.kind === "videoinput" && device.deviceId === preferredCameraDeviceId)
    : null;
  if (selectedDevice) {
    return selectedDevice;
  }

  const namedPreferred =
    devices.find((device) => device.kind === "videoinput" && device.label === PREFERRED_CAMERA_LABEL) || null;
  if (namedPreferred) {
    return namedPreferred;
  }

  const externalDevice = devices.find((device) => device.kind === "videoinput" && !isLikelyBuiltInCamera(device.label));
  if (externalDevice) {
    return externalDevice;
  }

  return devices[0] || null;
}

function getCameraOptionLabel(device, index, currentLabel = "") {
  const trimmedLabel = device.label && device.label.trim() ? device.label.trim() : "";
  if (trimmedLabel) {
    return trimmedLabel;
  }
  if (currentLabel && device.deviceId && preferredCameraDeviceId && device.deviceId === preferredCameraDeviceId) {
    return currentLabel;
  }
  return `摄像头 ${index + 1}`;
}

function syncCameraSelectOptions(devices, activeDeviceId = "", activeLabel = "") {
  if (!cameraSelect) {
    return;
  }

  const fragment = document.createDocumentFragment();
  if (devices.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "未发现可用摄像头";
    fragment.appendChild(option);
    cameraSelect.replaceChildren(fragment);
    cameraSelect.disabled = true;
    return;
  }

  devices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = getCameraOptionLabel(device, index, activeLabel);
    if (
      (activeDeviceId && device.deviceId === activeDeviceId) ||
      (!activeDeviceId && preferredCameraDeviceId && device.deviceId === preferredCameraDeviceId) ||
      (!activeDeviceId && !preferredCameraDeviceId && device.label === PREFERRED_CAMERA_LABEL)
    ) {
      option.selected = true;
    }
    fragment.appendChild(option);
  });

  cameraSelect.replaceChildren(fragment);
  cameraSelect.disabled = false;
  if (!cameraSelect.value) {
    const preferredDevice = findPreferredVideoInput(devices);
    if (preferredDevice && preferredDevice.deviceId) {
      cameraSelect.value = preferredDevice.deviceId;
    }
  }
}

async function refreshCameraOptions(stream = cameraStream) {
  const devices = await listVideoInputs().catch(() => []);
  const videoTrack = getVideoTrack(stream);
  const activeDeviceId = videoTrack ? getVideoTrackDeviceId(videoTrack) : "";
  const activeLabel = videoTrack && videoTrack.label ? videoTrack.label.trim() : "";
  syncCameraSelectOptions(devices, activeDeviceId, activeLabel);
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

async function openExactCameraStream(deviceId) {
  return navigator.mediaDevices.getUserMedia({
    video: { deviceId: { exact: deviceId } },
    audio: false,
  });
}

async function openPreferredCameraStream() {
  const initialDevices = await listVideoInputs().catch(() => []);

  if (preferredCameraDeviceId) {
    const cachedDevice = initialDevices.find(
      (device) => device.kind === "videoinput" && device.deviceId === preferredCameraDeviceId
    );
    if (cachedDevice) {
      try {
        return await openExactCameraStream(cachedDevice.deviceId);
      } catch (error) {
        preferredCameraDeviceId = "";
      }
    }
  }

  const preferredDevice = findPreferredVideoInput(initialDevices);
  if (preferredDevice && preferredDevice.deviceId) {
    preferredCameraDeviceId = preferredDevice.deviceId;
    try {
      return await openExactCameraStream(preferredDevice.deviceId);
    } catch (error) {
      preferredCameraDeviceId = "";
    }
  }

  const fallbackStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  const fallbackTrack = getVideoTrack(fallbackStream);
  const fallbackLabel = fallbackTrack && fallbackTrack.label ? fallbackTrack.label.trim() : "";
  if (fallbackLabel === PREFERRED_CAMERA_LABEL) {
    const fallbackDeviceId = getVideoTrackDeviceId(fallbackTrack);
    if (fallbackDeviceId) {
      preferredCameraDeviceId = fallbackDeviceId;
    }
    return fallbackStream;
  }

  const refreshedDevices = await listVideoInputs().catch(() => []);
  const refreshedPreferredDevice = findPreferredVideoInput(refreshedDevices);
  if (!refreshedPreferredDevice || !refreshedPreferredDevice.deviceId) {
    return fallbackStream;
  }

  preferredCameraDeviceId = refreshedPreferredDevice.deviceId;
  const fallbackDeviceId = getVideoTrackDeviceId(fallbackTrack);
  if (refreshedPreferredDevice.deviceId === fallbackDeviceId) {
    return fallbackStream;
  }

  try {
    const preferredStream = await openExactCameraStream(refreshedPreferredDevice.deviceId);
    stopMediaStream(fallbackStream);
    return preferredStream;
  } catch (error) {
    return fallbackStream;
  }
}

async function syncCameraDeviceName(stream) {
  const videoTrack = getVideoTrack(stream);
  if (!videoTrack) {
    setCameraDeviceLabel("未连接");
    await refreshCameraOptions(null);
    return "未连接";
  }

  let label = videoTrack.label && videoTrack.label.trim() ? videoTrack.label.trim() : "";
  if (!label) {
    const devices = await listVideoInputs().catch(() => []);
    const matchedDevice = devices.find(
      (device) => device.kind === "videoinput" && device.deviceId === getVideoTrackDeviceId(videoTrack)
    );
    label = matchedDevice && matchedDevice.label ? matchedDevice.label.trim() : "";
  }

  if (!label) {
    label = "系统默认摄像头";
  }

  const deviceId = getVideoTrackDeviceId(videoTrack);
  if (deviceId && (!preferredCameraDeviceId || label === PREFERRED_CAMERA_LABEL)) {
    persistSelectedCameraDevice(deviceId);
  }

  setCameraDeviceLabel(label);
  await refreshCameraOptions(stream);
  return label;
}

function startCameraSnapshotPolling() {
  if (cameraSnapshotTimer) {
    window.clearInterval(cameraSnapshotTimer);
  }
  cameraSnapshotTimer = window.setInterval(() => {
    void refreshCameraSnapshotCache();
  }, 1800);
}

function stopCameraTracks() {
  detachActiveCameraTrack();
  if (cameraStream) {
    stopMediaStream(cameraStream);
    cameraStream = null;
  }
  if (cameraPreview) {
    cameraPreview.srcObject = null;
  }
}

function clearCameraSnapshotCache() {
  latestCameraFrameBlob = null;
  latestCameraRegionBlobs = [];
  if (cameraSnapshotTimer) {
    window.clearInterval(cameraSnapshotTimer);
    cameraSnapshotTimer = null;
  }
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
  if (!cameraStream || !cameraPreview || !cameraCanvas) {
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
    cameraCanvas.toBlob((blob) => {
      resolve(blob);
    }, "image/jpeg", 0.92);
  });
}

function clampRegion(rect, width, height) {
  const x = Math.max(0, Math.min(rect.x, width));
  const y = Math.max(0, Math.min(rect.y, height));
  const maxWidth = Math.max(1, width - x);
  const maxHeight = Math.max(1, height - y);
  return {
    x,
    y,
    width: Math.max(1, Math.min(rect.width, maxWidth)),
    height: Math.max(1, Math.min(rect.height, maxHeight)),
  };
}

async function detectFaceBounds(width, height) {
  if (typeof FaceDetector === "undefined" || !cameraCanvas) {
    return null;
  }

  try {
    const detector = new FaceDetector({ fastMode: true, maxDetectedFaces: 1 });
    const faces = await detector.detect(cameraCanvas);
    if (faces.length > 0 && faces[0].boundingBox) {
      return clampRegion(faces[0].boundingBox, width, height);
    }
  } catch (error) {
    return null;
  }

  return null;
}

function buildFallbackFaceBounds(width, height) {
  return {
    x: width * 0.2,
    y: height * 0.08,
    width: width * 0.6,
    height: height * 0.78,
  };
}

function buildFaceRegions(faceBox) {
  const { x, y, width, height } = faceBox;
  return [
    { name: "full-face", x, y, width, height },
    { name: "forehead", x: x + width * 0.2, y: y + height * 0.03, width: width * 0.6, height: height * 0.2 },
    { name: "left-cheek", x: x + width * 0.08, y: y + height * 0.3, width: width * 0.28, height: height * 0.26 },
    { name: "right-cheek", x: x + width * 0.64, y: y + height * 0.3, width: width * 0.28, height: height * 0.26 },
    { name: "nose", x: x + width * 0.36, y: y + height * 0.28, width: width * 0.28, height: height * 0.24 },
    { name: "chin", x: x + width * 0.25, y: y + height * 0.68, width: width * 0.5, height: height * 0.2 },
  ];
}

async function cropCanvasRegion(region) {
  if (!cameraCanvas) {
    return null;
  }

  const sourceWidth = cameraCanvas.width || 1;
  const sourceHeight = cameraCanvas.height || 1;
  const rect = clampRegion(region, sourceWidth, sourceHeight);
  const cropCanvas = document.createElement("canvas");
  cropCanvas.width = Math.round(rect.width);
  cropCanvas.height = Math.round(rect.height);
  const cropContext = cropCanvas.getContext("2d");
  if (!cropContext) {
    return null;
  }
  cropContext.drawImage(
    cameraCanvas,
    rect.x,
    rect.y,
    rect.width,
    rect.height,
    0,
    0,
    cropCanvas.width,
    cropCanvas.height
  );

  return new Promise((resolve) => {
    cropCanvas.toBlob((blob) => {
      if (!blob) {
        resolve(null);
        return;
      }
      resolve({ name: region.name, blob });
    }, "image/jpeg", 0.9);
  });
}

async function captureFaceRegionBlobs() {
  if (!cameraCanvas || !cameraCanvas.width || !cameraCanvas.height) {
    return [];
  }

  const width = cameraCanvas.width;
  const height = cameraCanvas.height;
  const faceBox = (await detectFaceBounds(width, height)) || buildFallbackFaceBounds(width, height);
  const regions = buildFaceRegions(faceBox);
  const blobs = [];
  for (const region of regions) {
    const payload = await cropCanvasRegion(region);
    if (payload) {
      blobs.push(payload);
    }
  }
  return blobs;
}

async function refreshCameraSnapshotCache() {
  if (!cameraStream) {
    return;
  }

  try {
    const frameBlob = await captureCameraFrame();
    if (!frameBlob) {
      return;
    }
    latestCameraFrameBlob = frameBlob;
    latestCameraRegionBlobs = await captureFaceRegionBlobs();
  } catch (error) {
    return;
  }
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
    clearCameraSnapshotCache();
    stopCameraTracks();
    try {
      cameraStream = await openPreferredCameraStream();
      bindActiveCameraTrack(cameraStream);
      cameraPreview.srcObject = cameraStream;
      await cameraPreview.play();
      const label = await syncCameraDeviceName(cameraStream);
      await refreshCameraSnapshotCache();
      startCameraSnapshotPolling();
      cameraButton.textContent = "关掉镜头";
      setStatus(`${reason} 当前摄像头是 ${label}。`);
    } catch (error) {
      autoMirrorMode = false;
      clearCameraSnapshotCache();
      stopCameraTracks();
      cameraButton.textContent = "打开镜头";
      setCameraDeviceLabel("未连接");
      await refreshCameraOptions(null);
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

  const devices = await listVideoInputs().catch(() => []);
  syncCameraSelectOptions(devices, getVideoTrackDeviceId(getVideoTrack(cameraStream)), getVideoTrack(cameraStream)?.label || "");
  if (!autoMirrorMode) {
    return;
  }
  const videoTrack = getVideoTrack(cameraStream);
  if (!videoTrack) {
    void restoreCameraPreview("我在重新接回镜头。");
    return;
  }

  const currentDeviceId = getVideoTrackDeviceId(videoTrack);
  const currentStillExists = currentDeviceId
    ? devices.some((device) => device.kind === "videoinput" && device.deviceId === currentDeviceId)
    : devices.some((device) => device.kind === "videoinput" && device.label === videoTrack.label);
  const preferredDevice = findPreferredVideoInput(devices);

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

async function startCameraPreview() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("这个浏览器不支持网页摄像头。");
  }

  cameraStream = await openPreferredCameraStream();
  bindActiveCameraTrack(cameraStream);
  cameraPreview.srcObject = cameraStream;
  await cameraPreview.play();
  const label = await syncCameraDeviceName(cameraStream);
  autoMirrorMode = true;
  await refreshCameraSnapshotCache();
  startCameraSnapshotPolling();
  cameraButton.textContent = "关掉镜头";
  pushTabletScene("listening", { source: "camera-start" });
  setStatus(`镜头已经开好了，当前摄像头是 ${label}。我会直接听你说，也会持续记住最近一帧画面。`);
  if (!isRecording) {
    await startVoiceRecording({ autoStarted: true });
  }
}

function stopCameraPreview() {
  autoMirrorMode = false;
  clearCameraSnapshotCache();
  if (isRecording) {
    stopVoiceRecording();
  }
  stopCameraTracks();
  cameraButton.textContent = "打开镜头";
  setCameraDeviceLabel("未连接");
  void refreshCameraOptions(null);
  queueTabletScene("idle", 0, { source: "camera-stop" });
  setStatus("镜头已经关上了；想继续做视频问答再点一次。");
}

async function toggleCameraPreview() {
  if (!cameraStream) {
    await startCameraPreview();
    return;
  }

  stopCameraPreview();
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
  if (recognition) {
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    recognition.stop();
    recognition = null;
  }
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
    if (pendingUserVoiceBody) {
      pendingUserVoiceBody.textContent = subtitle.trim() || "我在听你说。";
    }
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

async function startVoiceRecording(options = {}) {
  const { autoStarted = false } = options;
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    setStatus("这个浏览器不支持网页录音，先用命令行 `python main.py --voice` 也行。");
    return;
  }
  if (isRecording) {
    return;
  }

  voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  await startVoiceMonitor(voiceStream);
  const liveUserMessage = createLiveMessage("user", "我在听你说。");
  pendingUserVoiceCard = liveUserMessage.card;
  pendingUserVoiceBody = liveUserMessage.bodyNode;
  pendingAgentVoiceCard = null;
  pendingAgentVoiceBody = null;
  pendingAgentVoiceAudio = null;
  startSubtitleRecognition();
  recordedChunks = [];
  mediaRecorder = new MediaRecorder(voiceStream);
  mediaRecorder.addEventListener("dataavailable", (event) => {
    if (event.data && event.data.size > 0) {
      recordedChunks.push(event.data);
    }
  });
  mediaRecorder.addEventListener("stop", async () => {
    const audioBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
    let frameBlob = null;
    let regionBlobs = [];
    const cameraWasActive = Boolean(cameraStream || autoMirrorMode);
    try {
      frameBlob = await captureCameraFrame();
      regionBlobs = await captureFaceRegionBlobs();
    } catch (frameError) {
      frameBlob = null;
      regionBlobs = [];
    }
    if (!frameBlob && latestCameraFrameBlob) {
      frameBlob = latestCameraFrameBlob;
    }
    if ((!regionBlobs || regionBlobs.length === 0) && latestCameraRegionBlobs.length > 0) {
      regionBlobs = latestCameraRegionBlobs;
    }
    stopSubtitleRecognition();
    await destroyVoiceMonitor();
    stopVoiceTracks();
    isRecording = false;
    voiceButton.textContent = autoMirrorMode ? "镜头常听中" : "点一下开口";

    if (!voiceHasSpeech || audioBlob.size === 0) {
      if (pendingUserVoiceCard && autoStarted) {
        pendingUserVoiceCard.remove();
      } else if (pendingUserVoiceBody) {
        pendingUserVoiceBody.textContent = "这次没听清。";
      }
      queueTabletScene("idle", 0, { source: "voice-empty" });
      if (autoMirrorMode && cameraStream) {
        setStatus("镜头已经开着，我继续等你下一句。");
        scheduleAutoVoiceRound();
        return;
      }
      setStatus("我刚刚没听清，你再点一下说一遍。");
      return;
    }

    try {
      pushTabletScene("thinking", { source: "voice-submit" });
      setStatus(
        frameBlob
          ? "我在看你这张当前画面，字幕会边走边出来。"
          : cameraWasActive
            ? "镜头还开着，但这轮画面没抓稳，我先按语音接你。"
            : "我在整理你的话，字幕会边走边出来。"
      );
      let tabletReplyStarted = false;
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
          ui_effect: uiEffect,
          scheduled_reminder: scheduledReminder,
        }) => {
        if (type === "transcript") {
          setAssistantLabel(assistantLabelFromEvent);
          if (pendingUserVoiceBody) {
            pendingUserVoiceBody.textContent = text;
          }
          pushTabletScene("thinking", { source: "transcript" });
          const liveAgentMessage = createLiveMessage("agent", "");
          pendingAgentVoiceCard = liveAgentMessage.card;
          pendingAgentVoiceBody = liveAgentMessage.bodyNode;
          pendingAgentVoiceAudio = null;
          setStatus(`${assistantLabel}在回你，字幕已经开始走了。`);
          return;
        }

        if (type === "reply_delta") {
          setAssistantLabel(assistantLabelFromEvent);
          if (!tabletReplyStarted) {
            tabletReplyStarted = true;
            pushTabletScene("reply", { source: "reply-delta" });
          }
          if (pendingAgentVoiceBody) {
            pendingAgentVoiceBody.textContent = text || delta || "";
          }
          return;
        }

        if (type === "reply_done") {
          setAssistantLabel(assistantLabelFromEvent);
          if (!tabletReplyStarted) {
            pushTabletScene("reply", { source: "reply-done" });
            tabletReplyStarted = true;
          }
          applyInteractionPayload({ ui_effect: uiEffect });
          if (scheduledReminder) {
            setTabletReminder(scheduledReminder);
          }
          if (pendingAgentVoiceBody) {
            pendingAgentVoiceBody.textContent = reply;
          }
          if (audioUrl && pendingAgentVoiceCard) {
            const audioPlayer = createVoiceAudioPlayer(audioUrl);
            pendingAgentVoiceCard.appendChild(audioPlayer);
            pendingAgentVoiceAudio = audioPlayer;
            await queueAudioPlayback(
              audioPlayer,
              "上一条语音还在说，我让它说完再接这条。",
              "自动播放被浏览器拦住了，字幕已经到了，点播放器就行。"
            );
          }
          queueTabletScene("idle", 1400, { source: "reply-finished" });
          setStatus(autoMirrorMode ? "这一轮聊完了，镜头开着的话我会继续听下一句。" : "这一轮聊完了，再点一下我继续听。");
          return;
        }

        if (type === "error") {
          throw new Error(error || "语音流式回复失败");
        }
        },
        frameBlob,
        regionBlobs,
        cameraWasActive
      );
      if (autoMirrorMode && cameraStream) {
        setStatus("镜头还开着，我继续等你下一句。");
        scheduleAutoVoiceRound();
      }
    } catch (error) {
      appendMessage("system", error.message);
      queueTabletScene("idle", 0, { source: "voice-error" });
      if (autoMirrorMode && cameraStream) {
        setStatus("这段语音没发出去，但镜头还在，我继续帮你守着。");
        scheduleAutoVoiceRound(900);
        return;
      }
      setStatus("这段语音没发出去，再试一次。");
    }
  });

  mediaRecorder.start();
  isRecording = true;
  voiceButton.textContent = autoMirrorMode ? "镜头常听中" : "我在听";
  pushTabletScene("listening", { source: autoStarted ? "auto-start" : "manual-start" });
  setStatus(autoStarted ? "镜头模式已经在听了，你直接说就行。" : "点一下就开始听你说；你说完我会自己停，再直接开口回你。");
}

async function toggleVoiceRecording() {
  if (!isRecording) {
    await startVoiceRecording();
    return;
  }

  stopVoiceRecording();
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = imageInput.files[0];
  const draft = messageInput.value.trim() || imageNoteInput.value.trim();
  const note = [messageInput.value.trim(), imageNoteInput.value.trim()].filter(Boolean).join(" ");

  if (!file && !draft) {
    setStatus("先说一句嘛，不然我会盯着输入框发呆。");
    return;
  }

  try {
    let reply;

    if (file) {
      appendMessage("user", `[发了一张图] ${note || file.name}`);
      pushTabletScene("thinking", { source: "image-submit" });
      setStatus("我在看图，等我一下。");
      const replyPayload = await sendImage(file, note);
      reply = replyPayload.reply;
      applyInteractionPayload(replyPayload);
      if (replyPayload.scheduled_reminder) {
        setTabletReminder(replyPayload.scheduled_reminder);
      }
      if (replyPayload.audio_url) {
        setAssistantLabel(replyPayload.assistant_label);
        pushTabletScene("reply", { source: "image-reply" });
        const audioPlayer = appendAgentVoiceReply(replyPayload.reply, replyPayload.audio_url);
        await queueAudioPlayback(
          audioPlayer,
          "上一条语音还在说，我让它说完再接这张图。",
          "自动播放被浏览器拦住了，图片分析已经出来了，点播放器就行。"
        );
        queueTabletScene("idle", 1400, { source: "image-finished" });
        if (audioPlayer.paused && audioPlayer.currentTime === 0) {
          messageInput.value = "";
          imageNoteInput.value = "";
          imageInput.value = "";
          return;
        }
      } else {
        setAssistantLabel(replyPayload.assistant_label);
        appendMessage("agent", reply);
      }
    } else {
      appendMessage("user", draft);
      pushTabletScene("thinking", { source: "text-submit" });
      setStatus(`${assistantLabel}在想，等我一下。`);
      const replyPayload = await sendChat(draft);
      reply = replyPayload.reply;
      applyInteractionPayload(replyPayload);
      if (replyPayload.scheduled_reminder) {
        setTabletReminder(replyPayload.scheduled_reminder);
      }
      setAssistantLabel(replyPayload.assistant_label);
      appendMessage("agent", reply);
      pushTabletScene("reply", { source: "text-reply" });
      queueTabletScene("idle", 1400, { source: "text-finished" });
    }
    messageInput.value = "";
    imageNoteInput.value = "";
    imageInput.value = "";
    setStatus("发图也行，或者继续聊。");
  } catch (error) {
    appendMessage("system", error.message);
    queueTabletScene("idle", 0, { source: "chat-error" });
    setStatus("这条没发出去，再试一下。");
  }
});

imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  if (!file) {
    setStatus("图片选择已取消。");
    return;
  }
  setStatus(`照片已经选好：${file.name}。点“发送”就行。`);
});

endButton.addEventListener("click", async () => {
  setStatus("我在收尾写 diary。");
  try {
    const payload = await endSession();
    setAssistantLabel(payload.assistant_label);
    appendMessage("agent", payload.reply);
    appendMessage("system", `今天的记录已经写到 ${payload.diary_path}`);
    pushTabletScene("reply", { source: "end-session" });
    queueTabletScene("idle", 1400, { source: "end-finished" });
    setStatus("收工啦，明天见。");
  } catch (error) {
    appendMessage("system", error.message);
    queueTabletScene("idle", 0, { source: "end-error" });
    setStatus("收尾失败了，再点一次我试试。");
  }
});

cameraButton.addEventListener("click", async () => {
  try {
    await toggleCameraPreview();
  } catch (error) {
    stopCameraTracks();
    setCameraDeviceLabel("未连接");
    cameraButton.textContent = "打开镜头";
    appendMessage("system", error.message || "没拿到摄像头权限。");
    queueTabletScene("idle", 0, { source: "camera-error" });
    setStatus("先给浏览器摄像头权限，我们再试一次。");
  }
});

if (cameraSelect) {
  cameraSelect.addEventListener("change", async () => {
    const deviceId = cameraSelect.value;
    persistSelectedCameraDevice(deviceId);
    if (!deviceId) {
      setStatus("我先继续用当前可用镜头。");
      return;
    }

    if (autoMirrorMode) {
      await restoreCameraPreview("我已经帮你切到你选的镜头。");
      return;
    }

    const devices = await listVideoInputs().catch(() => []);
    const selectedDevice = devices.find((device) => device.kind === "videoinput" && device.deviceId === deviceId);
    const selectedLabel = selectedDevice && selectedDevice.label ? selectedDevice.label.trim() : "你选的摄像头";
    setCameraDeviceLabel(selectedLabel);
    setStatus(`下次打开镜头时，我会优先连接 ${selectedLabel}。`);
  });
}

if (navigator.mediaDevices && typeof navigator.mediaDevices.addEventListener === "function") {
  navigator.mediaDevices.addEventListener("devicechange", handleCameraDeviceChange);
}

voiceButton.addEventListener("click", async () => {
  try {
    await toggleVoiceRecording();
  } catch (error) {
    stopVoiceTracks();
    stopSubtitleRecognition();
    await destroyVoiceMonitor();
    voiceButton.textContent = "点一下开口";
    isRecording = false;
    appendMessage("system", error.message || "没拿到麦克风权限。");
    queueTabletScene("idle", 0, { source: "voice-permission-error" });
    setStatus("先给浏览器麦克风权限，我们再试一次。");
  }
});

async function pollDueReminders() {
  try {
    const response = await fetch("/api/reminders/due", { method: "GET" });
    const payload = await readPayload(response);
    if (!response.ok || !payload.reminders || payload.reminders.length === 0) {
      return;
    }

    for (const reminder of payload.reminders) {
      setAssistantLabel(reminder.assistant_label || assistantLabel);
      applyInteractionPayload(reminder);
      markTabletReminderTriggered(reminder);
      pushTabletScene("reply", { source: "reminder" });
      const audioPlayer = appendAgentVoiceReply(reminder.message, reminder.audio_url);
      await queueAudioPlayback(
        audioPlayer,
        "我在整理提醒，不会让它和上一条语音撞在一起。",
        "自动播放被浏览器拦住了，提醒已经到了，点播放器就行。"
      );
      queueTabletScene("idle", 1400, { source: "reminder-finished" });
    }
  } catch (error) {
    return;
  }
}

window.setInterval(() => {
  void pollDueReminders();
}, 5000);
void pollDueReminders();
void refreshCameraOptions();
pushTabletScene("idle", { source: "page-load" });

window.addEventListener("beforeunload", () => {
  queueTabletScene("idle", 0, { source: "page-unload" });
  stopVoiceTracks();
  clearCameraSnapshotCache();
  stopCameraTracks();
  if (navigator.mediaDevices && typeof navigator.mediaDevices.removeEventListener === "function") {
    navigator.mediaDevices.removeEventListener("devicechange", handleCameraDeviceChange);
  }
});
