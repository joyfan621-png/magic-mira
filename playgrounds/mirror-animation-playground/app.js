const galleryEl = document.getElementById("gallery");
const selectionCountEl = document.getElementById("selection-count");
const selectionSummaryEl = document.getElementById("selection-summary");
const clearSelectionButton = document.getElementById("clear-selection");

const HEART_PATH =
  "M60 100 C 20 74 8 42 22 24 C 34 10 54 14 60 28 C 66 14 86 10 98 24 C 112 42 100 74 60 100 Z";

const selectedAnimationIds = new Set();

const animations = [
  {
    id: "heart-bloom",
    name: "细线桃心绽放",
    vibe: "最像温柔开机欢迎的一版，细线先勾心，再轻轻亮一下。",
    scenes: ["首次启动", "温柔欢迎"],
    group: "桃心线稿",
    variant: "heart-bloom",
  },
  {
    id: "heart-echo",
    name: "双线桃心回声",
    vibe: "更像一句话落下之后还有余韵，适合做轻回响感。",
    scenes: ["启动余韵", "回应回声"],
    group: "桃心线稿",
    variant: "heart-echo",
  },
  {
    id: "heart-script",
    name: "单笔勾心",
    vibe: "带一点施法笔触的感觉，像魔法棒顺手画出一个心。",
    scenes: ["启动欢迎", "点亮瞬间"],
    group: "桃心线稿",
    variant: "heart-script",
  },
  {
    id: "heart-breath",
    name: "桃心呼吸光",
    vibe: "最安静的一版，几乎像待机态，只保留轻轻呼吸的粉光。",
    scenes: ["安静待机", "柔和陪伴"],
    group: "桃心线稿",
    variant: "heart-breath",
  },
  {
    id: "heart-fragments",
    name: "桃心碎光散落",
    vibe: "桃心成形后带一点小碎光，比较适合轻收尾和祝福感。",
    scenes: ["收尾点亮", "轻祝福"],
    group: "桃心线稿",
    variant: "heart-fragments",
  },
  {
    id: "spark-gather",
    name: "星点聚拢成心",
    vibe: "先散后聚，能量从周围向中心聚焦，仪式感比较强。",
    scenes: ["启动聚焦", "召唤出现"],
    group: "星屑魔法",
    variant: "spark-gather",
  },
  {
    id: "wand-sweep",
    name: "魔法棒扫光",
    vibe: "更明显的施法瞬间，故事感比纯桃心更强。",
    scenes: ["启动欢迎", "戏剧登场"],
    group: "星屑魔法",
    variant: "wand-sweep",
  },
  {
    id: "comet-orbit",
    name: "彗尾绕心",
    vibe: "一颗亮点围着中心轻轻绕圈，适合思考中或回环感场景。",
    scenes: ["思考中", "回环魔法"],
    group: "星屑魔法",
    variant: "comet-orbit",
  },
  {
    id: "halo-ripple",
    name: "光环涟漪",
    vibe: "中心亮一下，再往外扩散，很适合做温柔反馈。",
    scenes: ["听见回应", "轻反馈"],
    group: "星屑魔法",
    variant: "halo-ripple",
  },
  {
    id: "star-spiral",
    name: "星屑旋涡",
    vibe: "小星点围绕中心绕动，最有变身前奏和能量集结感。",
    scenes: ["能量集结", "变身前奏"],
    group: "星屑魔法",
    variant: "star-spiral",
  },
  {
    id: "bow-flash",
    name: "蝴蝶结闪现",
    vibe: "公主感更直白，但还是偏细线稿，不会太像贴纸。",
    scenes: ["俏皮出现", "公主提示"],
    group: "公主符号",
    variant: "bow-flash",
  },
  {
    id: "crown-trace",
    name: "皇冠描边",
    vibe: "更高贵、更像正式登场，适合作为仪式性的开场动画。",
    scenes: ["正式开场", "贵气登场"],
    group: "公主符号",
    variant: "crown-trace",
  },
  {
    id: "pearl-arc",
    name: "珍珠轨迹",
    vibe: "像几颗小珠子在空气里串起一道弧线，礼物感很强。",
    scenes: ["礼物提示", "温柔提示"],
    group: "公主符号",
    variant: "pearl-arc",
  },
  {
    id: "ribbon-sway",
    name: "丝带回旋",
    vibe: "更适合作转场，动势比前几种强，但没有那么高调。",
    scenes: ["转场", "柔和收尾"],
    group: "公主符号",
    variant: "ribbon-sway",
  },
  {
    id: "wish-aura",
    name: "许愿光晕",
    vibe: "没有明确符号，只有祝福般的柔光和升起的小尘点。",
    scenes: ["祝福收尾", "许愿时刻"],
    group: "公主符号",
    variant: "wish-aura",
  },
];

function heartOutlineSvg(svgClass = "", pathClass = "") {
  return `
    <svg class="heart-svg ${svgClass}" viewBox="0 0 120 120" aria-hidden="true">
      <path class="heart-path ${pathClass}" d="${HEART_PATH}" pathLength="300"></path>
    </svg>
  `;
}

function heartFillSvg(svgClass = "", pathClass = "") {
  return `
    <svg class="heart-svg ${svgClass}" viewBox="0 0 120 120" aria-hidden="true">
      <path class="heart-fill-path ${pathClass}" d="${HEART_PATH}"></path>
    </svg>
  `;
}

function bowSvg(svgClass = "") {
  return `
    <svg class="bow-svg ${svgClass}" viewBox="0 0 160 120" aria-hidden="true">
      <path class="symbol-path" d="M78 62 C 60 48 44 38 26 34 C 18 32 16 44 24 50 C 40 62 56 66 78 62"></path>
      <path class="symbol-path" d="M82 62 C 100 48 116 38 134 34 C 142 32 144 44 136 50 C 120 62 104 66 82 62"></path>
      <path class="symbol-path" d="M74 54 L80 60 L86 54 L80 68 Z"></path>
      <path class="symbol-path" d="M78 64 C 70 72 60 82 52 92"></path>
      <path class="symbol-path" d="M82 64 C 90 72 100 82 108 92"></path>
    </svg>
  `;
}

function crownSvg(svgClass = "") {
  return `
    <svg class="crown-svg ${svgClass}" viewBox="0 0 160 100" aria-hidden="true">
      <path class="symbol-path" d="M20 80 L38 34 L64 66 L80 20 L96 66 L122 34 L140 80"></path>
      <path class="symbol-path" d="M20 80 H140"></path>
      <path class="symbol-path" d="M42 80 L48 68"></path>
      <path class="symbol-path" d="M80 80 L80 60"></path>
      <path class="symbol-path" d="M118 80 L112 68"></path>
    </svg>
  `;
}

function ribbonSvg(svgClass = "") {
  return `
    <svg class="ribbon-svg ${svgClass}" viewBox="0 0 160 120" aria-hidden="true">
      <path class="ribbon-path" d="M18 86 C 34 40 78 28 98 62 C 110 82 124 94 142 60"></path>
      <path class="ribbon-path" d="M36 82 C 54 56 84 54 96 72"></path>
    </svg>
  `;
}

function variableElements(className, items) {
  return items
    .map((item) => {
      const style = Object.entries(item)
        .map(([key, value]) => `--${key}:${value}`)
        .join(";");
      return `<span class="${className}" style="${style}"></span>`;
    })
    .join("");
}

const stageTemplates = {
  "heart-bloom": `
    <div class="card-stage stage-heart-bloom">
      <span class="soft-glow"></span>
      ${heartOutlineSvg("main")}
      ${variableElements("magic-spark", [
        { left: "22%", top: "32%", size: "9px", delay: "0.2s" },
        { left: "28%", top: "66%", size: "6px", delay: "0.8s" },
        { left: "72%", top: "30%", size: "8px", delay: "1.1s" },
        { left: "76%", top: "62%", size: "5px", delay: "1.5s" },
      ])}
    </div>
  `,
  "heart-echo": `
    <div class="card-stage stage-heart-echo">
      ${heartOutlineSvg("main")}
      ${heartOutlineSvg("echo echo-one")}
      ${heartOutlineSvg("echo echo-two")}
    </div>
  `,
  "heart-script": `
    <div class="card-stage stage-heart-script">
      <span class="wand-line"></span>
      <span class="wand-star"></span>
      ${heartOutlineSvg("main")}
    </div>
  `,
  "heart-breath": `
    <div class="card-stage stage-heart-breath">
      ${heartFillSvg("fill-layer")}
      ${heartOutlineSvg("main")}
    </div>
  `,
  "heart-fragments": `
    <div class="card-stage stage-heart-fragments">
      ${heartOutlineSvg("main")}
      ${variableElements("fragment-dot", [
        { size: "5px", delay: "0.3s", "offset-x": "-30px", "offset-y": "-4px", "drift-x": "-18px", "fall-y": "34px" },
        { size: "6px", delay: "0.5s", "offset-x": "-8px", "offset-y": "2px", "drift-x": "-10px", "fall-y": "40px" },
        { size: "5px", delay: "0.8s", "offset-x": "14px", "offset-y": "0px", "drift-x": "16px", "fall-y": "34px" },
        { size: "4px", delay: "1.1s", "offset-x": "30px", "offset-y": "-6px", "drift-x": "20px", "fall-y": "42px" },
      ])}
    </div>
  `,
  "spark-gather": `
    <div class="card-stage stage-spark-gather">
      <span class="center-glow"></span>
      ${heartOutlineSvg("small")}
      ${variableElements("gather-dot", [
        { size: "6px", delay: "0s", "start-x": "-92px", "start-y": "-62px", "end-x": "-8px", "end-y": "-12px" },
        { size: "5px", delay: "0.18s", "start-x": "-78px", "start-y": "40px", "end-x": "-12px", "end-y": "6px" },
        { size: "5px", delay: "0.35s", "start-x": "-24px", "start-y": "-74px", "end-x": "0px", "end-y": "-12px" },
        { size: "6px", delay: "0.52s", "start-x": "26px", "start-y": "72px", "end-x": "8px", "end-y": "10px" },
        { size: "7px", delay: "0.72s", "start-x": "76px", "start-y": "-48px", "end-x": "16px", "end-y": "-8px" },
        { size: "5px", delay: "0.94s", "start-x": "88px", "start-y": "30px", "end-x": "12px", "end-y": "4px" },
      ])}
    </div>
  `,
  "wand-sweep": `
    <div class="card-stage stage-wand-sweep">
      <span class="wand-line"></span>
      <span class="wand-star"></span>
      ${heartOutlineSvg("main")}
    </div>
  `,
  "comet-orbit": `
    <div class="card-stage stage-comet-orbit">
      ${heartOutlineSvg("small")}
      <span class="orbit-track"></span>
      <span class="orbit-wrap"><span class="orbit-comet"></span></span>
    </div>
  `,
  "halo-ripple": `
    <div class="card-stage stage-halo-ripple">
      ${heartOutlineSvg("small")}
      ${variableElements("halo", [
        { size: "68px", delay: "0s" },
        { size: "92px", delay: "0.45s" },
        { size: "118px", delay: "0.9s" },
      ])}
    </div>
  `,
  "star-spiral": `
    <div class="card-stage stage-star-spiral">
      <span class="center-glow"></span>
      ${variableElements("spiral-star", [
        { size: "8px", delay: "0s", angle: "0deg", radius: "30px" },
        { size: "9px", delay: "0.16s", angle: "60deg", radius: "40px" },
        { size: "8px", delay: "0.32s", angle: "120deg", radius: "48px" },
        { size: "10px", delay: "0.48s", angle: "180deg", radius: "52px" },
        { size: "8px", delay: "0.64s", angle: "240deg", radius: "42px" },
        { size: "9px", delay: "0.8s", angle: "300deg", radius: "34px" },
      ])}
    </div>
  `,
  "bow-flash": `
    <div class="card-stage stage-bow-flash">
      ${bowSvg()}
      ${variableElements("magic-spark", [
        { left: "28%", top: "36%", size: "6px", delay: "0.1s" },
        { left: "72%", top: "38%", size: "5px", delay: "0.5s" },
        { left: "50%", top: "68%", size: "7px", delay: "0.9s" },
      ])}
    </div>
  `,
  "crown-trace": `
    <div class="card-stage stage-crown-trace">
      ${crownSvg()}
      ${variableElements("jewel-dot", [
        { left: "31%", top: "38%", size: "6px", delay: "0.2s" },
        { left: "49%", top: "26%", size: "7px", delay: "0.5s" },
        { left: "67%", top: "38%", size: "6px", delay: "0.8s" },
      ])}
    </div>
  `,
  "pearl-arc": `
    <div class="card-stage stage-pearl-arc">
      ${heartOutlineSvg("small")}
      ${variableElements("pearl-orb", [
        { size: "7px", delay: "0s", "start-x": "-54px", "start-y": "28px", "mid-x": "-22px", "mid-y": "-16px", "end-x": "0px", "end-y": "-38px", "fade-x": "18px", "fade-y": "-52px" },
        { size: "8px", delay: "0.2s", "start-x": "-42px", "start-y": "36px", "mid-x": "-8px", "mid-y": "-22px", "end-x": "12px", "end-y": "-42px", "fade-x": "28px", "fade-y": "-54px" },
        { size: "7px", delay: "0.4s", "start-x": "-20px", "start-y": "40px", "mid-x": "10px", "mid-y": "-14px", "end-x": "26px", "end-y": "-34px", "fade-x": "44px", "fade-y": "-46px" },
        { size: "6px", delay: "0.6s", "start-x": "2px", "start-y": "42px", "mid-x": "22px", "mid-y": "-8px", "end-x": "38px", "end-y": "-24px", "fade-x": "54px", "fade-y": "-32px" },
      ])}
    </div>
  `,
  "ribbon-sway": `
    <div class="card-stage stage-ribbon-sway">
      ${ribbonSvg("left")}
      ${ribbonSvg("right")}
      <span class="ribbon-knot"></span>
    </div>
  `,
  "wish-aura": `
    <div class="card-stage stage-wish-aura">
      <span class="wish-glow"></span>
      ${variableElements("halo", [
        { size: "64px", delay: "0.08s" },
        { size: "96px", delay: "0.46s" },
        { size: "128px", delay: "0.86s" },
      ])}
      ${variableElements("wish-dust", [
        { size: "6px", delay: "0s", "start-x": "-18px", "start-y": "24px", "mid-x": "-10px", "mid-y": "-8px", "end-x": "-6px", "end-y": "-42px", "fade-x": "-2px", "fade-y": "-66px" },
        { size: "5px", delay: "0.22s", "start-x": "4px", "start-y": "32px", "mid-x": "10px", "mid-y": "-4px", "end-x": "16px", "end-y": "-46px", "fade-x": "20px", "fade-y": "-72px" },
        { size: "7px", delay: "0.42s", "start-x": "22px", "start-y": "26px", "mid-x": "6px", "mid-y": "-10px", "end-x": "-4px", "end-y": "-38px", "fade-x": "-10px", "fade-y": "-58px" },
        { size: "5px", delay: "0.64s", "start-x": "-30px", "start-y": "18px", "mid-x": "-18px", "mid-y": "-12px", "end-x": "-14px", "end-y": "-48px", "fade-x": "-8px", "fade-y": "-70px" },
      ])}
    </div>
  `,
};

function renderCard(animation) {
  const tags = animation.scenes.map((scene) => `<span class="tag">${scene}</span>`).join("");

  return `
    <article
      class="animation-card"
      role="button"
      tabindex="0"
      data-animation-id="${animation.id}"
      aria-pressed="false"
    >
      ${stageTemplates[animation.variant]}
      <div class="card-copy">
        <p class="group-label">${animation.group}</p>
        <p class="card-title">${animation.name}</p>
        <p class="card-vibe">${animation.vibe}</p>
        <div class="tag-row">${tags}</div>
      </div>
    </article>
  `;
}

function renderGallery() {
  galleryEl.innerHTML = animations.map(renderCard).join("");
}

function renderSelectionSummary() {
  const selectedAnimations = animations.filter((animation) => selectedAnimationIds.has(animation.id));
  selectionCountEl.textContent = `${selectedAnimations.length} 个`;

  if (selectedAnimations.length === 0) {
    selectionSummaryEl.innerHTML = '<span class="selection-empty">还没选，先点几个喜欢的看看。</span>';
    return;
  }

  selectionSummaryEl.innerHTML = selectedAnimations
    .map((animation) => `<span class="selection-pill">${animation.name}</span>`)
    .join("");
}

function syncCardState(animationId) {
  const button = galleryEl.querySelector(`[data-animation-id="${animationId}"]`);
  if (!button) {
    return;
  }

  const isSelected = selectedAnimationIds.has(animationId);
  button.classList.toggle("is-selected", isSelected);
  button.setAttribute("aria-pressed", isSelected ? "true" : "false");
}

function toggleSelection(animationId) {
  if (selectedAnimationIds.has(animationId)) {
    selectedAnimationIds.delete(animationId);
  } else {
    selectedAnimationIds.add(animationId);
  }

  syncCardState(animationId);
  renderSelectionSummary();
}

function handleGalleryClick(event) {
  const card = event.target.closest(".animation-card");
  if (!card) {
    return;
  }

  toggleSelection(card.dataset.animationId);
}

function handleGalleryKeydown(event) {
  const card = event.target.closest(".animation-card");
  if (!card) {
    return;
  }

  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }

  event.preventDefault();
  toggleSelection(card.dataset.animationId);
}

function clearSelections() {
  for (const animationId of selectedAnimationIds) {
    syncCardState(animationId);
  }
  selectedAnimationIds.clear();
  galleryEl.querySelectorAll(".animation-card").forEach((button) => {
    button.classList.remove("is-selected");
    button.setAttribute("aria-pressed", "false");
  });
  renderSelectionSummary();
}

renderGallery();
renderSelectionSummary();

galleryEl.addEventListener("click", handleGalleryClick);
galleryEl.addEventListener("keydown", handleGalleryKeydown);
clearSelectionButton.addEventListener("click", clearSelections);
