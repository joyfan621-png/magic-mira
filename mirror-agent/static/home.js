const haloStage = document.getElementById("halo-stage");
const statusEl = document.getElementById("status");
const cameraSwitchButton = document.getElementById("camera-switch-button");
const cameraButton = document.getElementById("camera-button");
const cameraPreview = document.getElementById("camera-preview");
const cameraCanvas = document.getElementById("camera-canvas");
const cameraDeviceName = document.getElementById("camera-device-name");
const userSubtitleEl = document.getElementById("user-subtitle");
const agentSubtitleEl = document.getElementById("agent-subtitle");
const countdownPanelEl = document.getElementById("countdown-panel");
const countdownValueEl = document.getElementById("countdown-value");
const countdownMessageEl = document.getElementById("countdown-message");

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

function setAssistantLabel(label) {
  assistantLabel = label && label.trim() ? label.trim() : "我";
  document.body.dataset.assistantLabel = assistantLabel;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function setScene(scene) {
  haloStage.dataset.scene = scene;
  pushTabletScene(scene);
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
  const message = String(reminder.message || "").trim();
  const id = String(reminder.id || message).trim();
  if (!message) {
    return null;
  }

  return {
    id,
    message,
    due_at: dueAt,
    audio_url: String(reminder.audio_url || reminder.audioUrl || "").trim(),
  };
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

function updateReminderCountdown() {
  renderReminder(activeReminder);
}

function setActiveReminder(reminder) {
  activeReminder = normalizeReminder(reminder);
  renderReminder(activeReminder);

  if (reminderInterval) {
    window.clearInterval(reminderInterval);
    reminderInterval = null;
  }

  if (activeReminder) {
    reminderInterval = window.setInterval(updateReminderCountdown, 1000);
  }
}

function renderReminder(reminder) {
  const normalized = normalizeReminder(reminder);
  if (!normalized) {
    countdownPanelEl.hidden = true;
    countdownValueEl.textContent = "00:00";
    countdownMessageEl.textContent = "";
    return;
  }

  countdownPanelEl.hidden = false;
  const dueAtMs = normalized.due_at ? new Date(normalized.due_at).getTime() : Number.NaN;
  const remainingMs = Number.isNaN(dueAtMs) ? 0 : dueAtMs - Date.now();
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
      const label = await syncCameraDeviceName(cameraStream);
      setStatus(`${reason} 当前摄像头是 ${label}。`);
    } catch (error) {
      autoMirrorMode = false;
      stopCameraTracks();
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
  setCameraDeviceLabel("未连接");
  cameraButton.textContent = "打开镜头";
  userSubtitleEl.textContent = "打开镜头后，我会在这里轻声复述你刚说的话。";
  agentSubtitleEl.textContent = `${assistantLabel} 会在这里用很短的字幕回应你。`;
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

async function pollDueReminders() {
  try {
    const response = await fetch("/api/reminders/due", { method: "GET" });
    const payload = await readPayload(response);
    if (!response.ok || !payload.reminders || payload.reminders.length === 0) {
      return;
    }

    for (const reminder of payload.reminders) {
      const normalized = normalizeReminder(reminder);
      if (!normalized) {
        continue;
      }
      if (normalized.id && normalized.id === lastPlayedReminderId) {
        continue;
      }
      lastPlayedReminderId = normalized.id;
      setAssistantLabel(reminder.assistant_label || assistantLabel);
      agentSubtitleEl.textContent = normalized.message;
      renderReminder(normalized);
      markTabletReminderTriggered(reminder);
      setScene("reply");
      if (normalized.audio_url) {
        const audioPlayer = createVoiceAudioPlayer(normalized.audio_url);
        await queueAudioPlayback(
          audioPlayer,
          "我在整理提醒，不会让它和上一条语音撞在一起。",
          "自动播放被浏览器拦住了，提醒已经到了。"
        );
      }
      window.setTimeout(() => {
        if (!isRecording) {
          setScene("idle");
        }
      }, 1400);
    }
  } catch (error) {
    return;
  }
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

window.setInterval(() => {
  void pollDueReminders();
}, 5000);
void pollDueReminders();
setScene("idle");

window.addEventListener("beforeunload", () => {
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
