const messagesEl = document.getElementById("messages");
const statusEl = document.getElementById("status");
const composerEl = document.getElementById("composer");
const messageInput = document.getElementById("message-input");
const promptChips = Array.from(document.querySelectorAll(".prompt-chip"));
const scenes = Array.from(document.querySelectorAll(".scene"));
const acneMapEl = document.querySelector(".face-map");
const acneCaptionEl = document.getElementById("acne-caption");
const tcmCaptionEl = document.getElementById("tcm-caption");
const SCENE_RESET_MS = 5600;

let sceneTimer = null;

const zoneMeta = {
  forehead: {
    label: "额头",
    caption: "这版 demo 会把额头区域提亮，模拟你在讲这个位置反复长痘时的视觉反馈。",
  },
  nose: {
    label: "鼻翼",
    caption: "这版 demo 会先把鼻部和鼻翼附近提亮，表达油脂和泛红位置被看见了。",
  },
  chin: {
    label: "下巴",
    caption: "这版 demo 会把下巴区域提亮，方便模拟经期前后或作息波动时的观察提示。",
  },
  "cheek-left": {
    label: "左脸颊",
    caption: "这版 demo 会先把脸颊这一块点亮，表现局部泛红、痘痘或闭口提示。",
  },
  "cheek-right": {
    label: "右脸颊",
    caption: "这版 demo 会先把脸颊这一块点亮，表现局部泛红、痘痘或闭口提示。",
  },
};

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message message-${role}`;

  const roleNode = document.createElement("p");
  roleNode.className = "message-role";
  roleNode.textContent = role === "user" ? "你" : "镜子虾";

  const bodyNode = document.createElement("p");
  bodyNode.textContent = text;

  article.append(roleNode, bodyNode);
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function activateScene(sceneName, options = {}) {
  scenes.forEach((scene) => {
    scene.classList.toggle("is-active", scene.dataset.scene === sceneName);
  });

  if (sceneName === "acne-map" && acneMapEl) {
    const zone = options.zone || "chin";
    acneMapEl.dataset.zone = zone;
    acneCaptionEl.textContent = zoneMeta[zone]?.caption || "聊到痘痘位置时，这里会高亮对应区域。";
  }

  if (sceneName === "tcm-map" && tcmCaptionEl) {
    tcmCaptionEl.textContent = options.caption || "这是一张简化面诊图，只用来演示讲到中医时的轻量视觉反馈。";
  }

  window.clearTimeout(sceneTimer);
  if (sceneName !== "sparkle") {
    sceneTimer = window.setTimeout(() => {
      activateScene("sparkle");
      setStatus("镜面又安静下来了，等你下一句。");
    }, SCENE_RESET_MS);
  }
}

function detectAcneZone(text) {
  if (/(额头|抬头纹)/.test(text)) {
    return "forehead";
  }
  if (/(鼻翼|鼻头|鼻子)/.test(text)) {
    return "nose";
  }
  if (/(左脸|左边脸|左脸颊)/.test(text)) {
    return "cheek-left";
  }
  if (/(右脸|右边脸|右脸颊)/.test(text)) {
    return "cheek-right";
  }
  return "chin";
}

function composeReply(text) {
  if (/(中医|面诊|气血|上火|湿气|脾胃)/.test(text)) {
    activateScene("tcm-map", {
      caption: "讲到中医面诊时，我会把图解收在边角，既能解释，又尽量不挡住你的脸。",
    });
    setStatus("已触发中医面诊图层，这一层会待几秒再退回镜面。");
    return "如果走中医面诊的讲法，我会把图解轻轻放到边上，不让它压住你的镜面空间。";
  }

  if (/(痘|爆痘|闭口|红肿|粉刺|额头|下巴|鼻翼|脸颊)/.test(text)) {
    const zone = detectAcneZone(text);
    activateScene("acne-map", { zone });
    setStatus(`已触发${zoneMeta[zone].label}示意图，这一层会短暂停留。`);
    return `我先把${zoneMeta[zone].label}的位置提亮给你看，这样更像对着镜子边聊边指出来。`;
  }

  if (/(委屈|想哭|开心|公主|可爱|漂亮|不开心|难过)/.test(text)) {
    activateScene("princess");
    setStatus("已触发小公主装饰层，边缘会轻轻亮一下。");
    return "这句更适合温柔陪伴模式，所以我把小皇冠、蝴蝶结和星点从边缘请出来陪你。";
  }

  activateScene("sparkle");
  setStatus("这句没有命中特殊图层，我先保持镜面安静。");
  return "这版 demo 会优先把镜面让给你，所以没触发特定话题时，我只留一点很轻的星点。";
}

function sendPrompt(text) {
  const prompt = text.trim();
  if (!prompt) {
    setStatus("先输一句话试试，我再给你看图层怎么冒出来。");
    return;
  }

  appendMessage("user", prompt);
  const reply = composeReply(prompt);
  window.setTimeout(() => {
    appendMessage("agent", reply);
  }, 160);
}

composerEl.addEventListener("submit", (event) => {
  event.preventDefault();
  sendPrompt(messageInput.value);
  messageInput.value = "";
  messageInput.focus();
});

promptChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const prompt = chip.dataset.prompt || "";
    messageInput.value = prompt;
    sendPrompt(prompt);
    messageInput.value = "";
    messageInput.focus();
  });
});
