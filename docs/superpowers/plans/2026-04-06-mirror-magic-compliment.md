# Mirror Magic Compliment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic “魔镜魔镜告诉我，谁是世界上最漂亮的女孩子” compliment easter egg that replies with personalized praise across both text-only and camera-assisted chat.

**Architecture:** Keep the feature inside `MirrorAgent` so the trigger, prompt building, fallback copy, and multimodal routing all live next to the existing reminder, naming, and photo-analysis flows. Reuse the existing system prompt, memory context, multimodal message builder, reply limiter, and visual-reply sanitizer so the new branch feels special without introducing new endpoints or tool contracts.

**Tech Stack:** Python, `unittest`, existing `MirrorAgent` chat/multimodal abstractions

---

### Task 1: Add the fixed-phrase matcher and dedicated compliment prompt builder

**Files:**
- Modify: `mirror-agent/agent.py:21-314`
- Modify: `mirror-agent/tests/test_agent.py:1-320`

- [ ] **Step 1: Write the failing tests for phrase matching and prompt content**

```python
from agent import (
    MirrorAgent,
    parse_reminder_request,
    should_end_session,
    should_trigger_magic_compliment,
)


class AgentTests(unittest.TestCase):
    def test_magic_compliment_trigger_matches_demo_phrase_variants(self) -> None:
        self.assertTrue(should_trigger_magic_compliment("魔镜魔镜告诉我，谁是世界上最漂亮的女孩子"))
        self.assertTrue(should_trigger_magic_compliment("魔镜魔镜告诉我谁是世界上最漂亮的女孩子"))
        self.assertTrue(should_trigger_magic_compliment("魔镜魔镜，谁是世界上最漂亮的女孩子呀"))
        self.assertFalse(should_trigger_magic_compliment("魔镜魔镜夸夸我"))
        self.assertFalse(should_trigger_magic_compliment("谁是世界上最漂亮的女孩子"))

    def test_build_magic_compliment_system_prompt_includes_memory_and_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是一个住在镜子里的 AI 护肤闺蜜。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            (project_root / "memory" / "profile.md").write_text(
                "# 用户画像\n\n## 2026-04-06\n\n- 互动偏好：喜欢被直接一点地夸\n",
                encoding="utf-8",
            )

            agent = MirrorAgent(
                config=AppConfig(project_root=project_root, api_key="test-key"),
                client=object(),
            )

            prompt = agent._build_magic_compliment_system_prompt(has_image=False)

            self.assertIn("喜欢被直接一点地夸", prompt)
            self.assertIn("当然是你啊", prompt)
            self.assertIn("2到4句", prompt)
            self.assertIn("不要空泛地只说“你很漂亮”", prompt)
            self.assertIn("没有画面时，不要编造具体五官或皮肤细节", prompt)
```

- [ ] **Step 2: Run the tests to verify they fail before implementation**

Run from `/Users/bytedance/Desktop/A2A黑客松/mira/.worktrees/halo-home-display/mirror-agent`:

```bash
/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest \
  tests.test_agent.AgentTests.test_magic_compliment_trigger_matches_demo_phrase_variants \
  tests.test_agent.AgentTests.test_build_magic_compliment_system_prompt_includes_memory_and_structure \
  -v
```

Expected: `FAILED` with an import or attribute error because `should_trigger_magic_compliment` and `_build_magic_compliment_system_prompt` do not exist yet.

- [ ] **Step 3: Implement the exact matcher and the easter-egg prompt builder in `agent.py`**

```python
MAGIC_COMPLIMENT_PATTERNS = (
    re.compile(r"^魔镜魔镜(?:告诉我)?[，,\s]*谁是世界上最漂亮的女孩子(?:呀|啊|呢|嘛)?[。！？!?]?$"),
)


def should_trigger_magic_compliment(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    return any(pattern.fullmatch(normalized) for pattern in MAGIC_COMPLIMENT_PATTERNS)


class MirrorAgent:
    def _build_magic_compliment_system_prompt(self, has_image: bool) -> str:
        visual_rule = (
            "当前回合带了画面，第二句必须优先夸现在这一刻能看到的气色、皮肤、眼神、光线或镜前氛围。"
            if has_image
            else "没有画面时，不要编造具体五官或皮肤细节，改用记忆、最近状态变化和她这一句问法里的情绪来夸。"
        )
        return "\n\n".join(
            [
                self.build_system_prompt(),
                "## 魔镜夸夸彩蛋",
                "- 这轮已经命中固定彩蛋句：魔镜魔镜告诉我，谁是世界上最漂亮的女孩子。",
                "- 你要明显偏心她，但不能像模板文案，也不能像客服。",
                "- 第一句必须直接回答“当然是你啊。”或者“除了你还能有谁呀。”",
                "- 第二句必须给一个具体夸点，不能空泛地只说“你很漂亮”。",
                "- 第三句尽量补一层记忆、最近变化，或镜前空间和光线带来的氛围加成。",
                f"- {visual_rule}",
                "- 回复控制在2到4句内，像微信语音一样自然，不要列表，不要解释规则。",
                "- 可参考这种感觉但不要照抄：当然是你啊。你今天站在镜子前这一下就很亮，脸颊状态也软软净净的，连旁边的光都在偷偷偏心你。",
            ]
        ).strip()
```

- [ ] **Step 4: Re-run the targeted tests and make sure they pass**

Run from `/Users/bytedance/Desktop/A2A黑客松/mira/.worktrees/halo-home-display/mirror-agent`:

```bash
/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest \
  tests.test_agent.AgentTests.test_magic_compliment_trigger_matches_demo_phrase_variants \
  tests.test_agent.AgentTests.test_build_magic_compliment_system_prompt_includes_memory_and_structure \
  -v
```

Expected: both tests pass with `OK`.

- [ ] **Step 5: Commit the matcher and prompt-builder work**

```bash
git add mirror-agent/agent.py mirror-agent/tests/test_agent.py
git commit -m "feat: add magic compliment trigger and prompt"
```

### Task 2: Route text chat and stream chat through the dedicated compliment branch

**Files:**
- Modify: `mirror-agent/agent.py:316-520`
- Modify: `mirror-agent/tests/test_agent.py:13-360`

- [ ] **Step 1: Add failing tests for the text-only response and stream paths**

```python
class FakeMagicComplimentCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
        extra_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "tools": tools or [],
                "extra_body": extra_body or {},
            }
        )
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "当然是你啊。你今天一开口问这句就已经很会赢了，整个人的状态都软乎乎亮晶晶的。"
                    }
                }
            ]
        }


class FakeMagicComplimentClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeMagicComplimentCompletions()})()


class FakeMagicComplimentStreamingCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def stream(self, model: str, messages: list[dict[str, object]], extra_body: dict[str, object] | None = None):
        self.calls.append({"model": model, "messages": messages, "extra_body": extra_body or {}})
        yield "当然是你啊。"
        yield "你今天这股松松亮亮的劲儿很加分。"


class FakeMagicComplimentStreamingClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeMagicComplimentStreamingCompletions()})()


class AgentTests(unittest.TestCase):
    def test_respond_magic_compliment_routes_to_dedicated_prompt_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是一个住在镜子里的 AI 护肤闺蜜。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            client = FakeMagicComplimentClient()
            agent = MirrorAgent(
                config=AppConfig(project_root=project_root, api_key="test-key", provider="aiping"),
                client=client,
            )

            reply = agent.respond("魔镜魔镜告诉我，谁是世界上最漂亮的女孩子")

            self.assertIn("当然是你啊", reply)
            call = client.chat.completions.calls[0]
            self.assertEqual(agent.config.chat_model, call["model"])
            self.assertIn("## 魔镜夸夸彩蛋", call["messages"][0]["content"])
            self.assertEqual("魔镜魔镜告诉我，谁是世界上最漂亮的女孩子", call["messages"][-1]["content"])
            self.assertEqual(reply, agent.history[-1]["content"])

    def test_stream_magic_compliment_uses_dedicated_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是一个住在镜子里的 AI 护肤闺蜜。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            client = FakeMagicComplimentStreamingClient()
            agent = MirrorAgent(
                config=AppConfig(project_root=project_root, api_key="", provider="ollama"),
                client=client,
            )

            chunks = list(agent.stream_respond("魔镜魔镜，谁是世界上最漂亮的女孩子"))

            self.assertEqual(["当然是你啊。", "你今天这股松松亮亮的劲儿很加分。"], chunks)
            call = client.chat.completions.calls[0]
            self.assertEqual(agent.config.chat_model, call["model"])
            self.assertIn("第一句必须直接回答", call["messages"][0]["content"])
```

- [ ] **Step 2: Run the targeted tests and confirm they fail**

Run from `/Users/bytedance/Desktop/A2A黑客松/mira/.worktrees/halo-home-display/mirror-agent`:

```bash
/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest \
  tests.test_agent.AgentTests.test_respond_magic_compliment_routes_to_dedicated_prompt_and_history \
  tests.test_agent.AgentTests.test_stream_magic_compliment_uses_dedicated_prompt \
  -v
```

Expected: `FAILED` because `respond()` and `stream_respond()` still follow the normal chat path.

- [ ] **Step 3: Add dedicated response helpers and wire both chat paths to them**

```python
class MirrorAgent:
    def _build_magic_compliment_messages(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._build_magic_compliment_system_prompt(has_image=bool(image_paths)),
            }
        ]
        messages.extend(self.history[-10:])
        if image_paths:
            messages.append(self._build_user_message(user_text, image_paths=image_paths))
        else:
            messages.append({"role": "user", "content": user_text})
        return messages

    def _magic_compliment_fallback(self, has_image: bool) -> str:
        if has_image:
            return "当然是你啊。你今天站在镜子前这一秒就很亮眼，气色和那股松弛感都在发光，连旁边的光都在偏心你。"
        return "当然是你啊。你一开口问这句就已经赢了，我今天就是要偏心你。"

    def _respond_with_magic_compliment(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
    ) -> str:
        if not self.client:
            reply = self._magic_compliment_fallback(has_image=bool(image_paths))
        else:
            model = self.config.vision_model if image_paths else self.config.chat_model
            messages = self._build_magic_compliment_messages(user_text, image_paths=image_paths)
            raw_reply = self._chat_with_tools(messages, model=model)
            reply = self._prepare_visual_reply(raw_reply) if image_paths else self._limit_reply(raw_reply)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _stream_magic_compliment(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
    ) -> Iterator[str]:
        if not self.client:
            reply = self._magic_compliment_fallback(has_image=bool(image_paths))
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            yield from self._chunk_text(reply)
            return

        messages = self._build_magic_compliment_messages(user_text, image_paths=image_paths)
        model = self.config.vision_model if image_paths else self.config.chat_model
        stream_method = getattr(getattr(self.client.chat, "completions", None), "stream", None)
        if callable(stream_method):
            parts: list[str] = []
            for chunk in stream_method(model=model, messages=messages, extra_body={"temperature": 0.8}):
                if not chunk:
                    continue
                parts.append(chunk)
                yield chunk
            reply = "".join(parts).strip()
            if reply:
                normalized = self._prepare_visual_reply(reply) if image_paths else self._limit_reply(reply)
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": normalized})
                return

        reply = self._respond_with_magic_compliment(user_text, image_paths=image_paths)
        yield from self._chunk_text(reply)
```

Then add the early branch in both entrypoints before the generic `image_paths` and normal chat sections:

```python
if should_trigger_magic_compliment(user_text):
    return self._respond_with_magic_compliment(user_text, image_paths=image_paths)
```

```python
if should_trigger_magic_compliment(user_text):
    yield from self._stream_magic_compliment(user_text, image_paths=image_paths)
    return
```

- [ ] **Step 4: Re-run the targeted tests and verify they pass**

Run from `/Users/bytedance/Desktop/A2A黑客松/mira/.worktrees/halo-home-display/mirror-agent`:

```bash
/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest \
  tests.test_agent.AgentTests.test_respond_magic_compliment_routes_to_dedicated_prompt_and_history \
  tests.test_agent.AgentTests.test_stream_magic_compliment_uses_dedicated_prompt \
  -v
```

Expected: both tests pass with `OK`.

- [ ] **Step 5: Commit the dedicated text-route work**

```bash
git add mirror-agent/agent.py mirror-agent/tests/test_agent.py
git commit -m "feat: route magic compliment through dedicated chat paths"
```

### Task 3: Preserve multimodal specificity and replace generic fallback copy for the demo

**Files:**
- Modify: `mirror-agent/agent.py:370-512,622-689`
- Modify: `mirror-agent/tests/test_agent.py:55-205,738-891`

- [ ] **Step 1: Add failing tests for multimodal routing and the special fallback copy**

```python
class FakeEmptyReplyCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
        extra_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "tools": tools or [],
                "extra_body": extra_body or {},
            }
        )
        return {"choices": [{"message": {"role": "assistant", "content": ""}}]}


class FakeEmptyReplyClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeEmptyReplyCompletions()})()


class AgentTests(unittest.TestCase):
    def test_magic_compliment_with_camera_frame_uses_vision_model_and_multimodal_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是一个住在镜子里的 AI 护肤闺蜜。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "camera-frame.jpg"
            image_path.write_bytes(b"fake-image")
            client = FakeMagicComplimentClient()
            agent = MirrorAgent(
                config=AppConfig(
                    project_root=project_root,
                    provider="aiping",
                    api_key="test-key",
                    chat_model="Qwen3-14B",
                    vision_model="Qwen2.5-VL-32B-Instruct",
                    base_url="https://aiping.cn/api/v1/chat/completions",
                ),
                client=client,
            )

            reply = agent.respond(
                "魔镜魔镜告诉我，谁是世界上最漂亮的女孩子",
                image_paths=[str(image_path)],
            )

            self.assertIn("当然是你啊", reply)
            call = client.chat.completions.calls[0]
            self.assertEqual("Qwen2.5-VL-32B-Instruct", call["model"])
            self.assertIsInstance(call["messages"][-1]["content"], list)
            self.assertEqual("text", call["messages"][-1]["content"][0]["type"])
            self.assertIn("当前这一轮你面前可参考的视角顺序如下", call["messages"][-1]["content"][0]["text"])

    def test_magic_compliment_replaces_generic_chat_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是一个住在镜子里的 AI 护肤闺蜜。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            client = FakeEmptyReplyClient()
            agent = MirrorAgent(
                config=AppConfig(project_root=project_root, provider="aiping", api_key="test-key"),
                client=client,
            )

            reply = agent.respond("魔镜魔镜，谁是世界上最漂亮的女孩子")

            self.assertIn("当然是你啊", reply)
            self.assertNotIn("我有点卡住了", reply)
```

- [ ] **Step 2: Run the new tests and verify they fail before the final implementation step**

Run from `/Users/bytedance/Desktop/A2A黑客松/mira/.worktrees/halo-home-display/mirror-agent`:

```bash
/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest \
  tests.test_agent.AgentTests.test_magic_compliment_with_camera_frame_uses_vision_model_and_multimodal_payload \
  tests.test_agent.AgentTests.test_magic_compliment_replaces_generic_chat_fallback \
  -v
```

Expected: `FAILED` because the current special branch does not yet replace the generic stall copy and does not assert multimodal payload details.

- [ ] **Step 3: Make the dedicated branch image-aware and replace the generic fallback with demo-safe praise**

```python
class MirrorAgent:
    def _respond_with_magic_compliment(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
    ) -> str:
        if not self.client:
            reply = self._magic_compliment_fallback(has_image=bool(image_paths))
        else:
            model = self.config.vision_model if image_paths else self.config.chat_model
            messages = self._build_magic_compliment_messages(user_text, image_paths=image_paths)
            raw_reply = self._chat_with_tools(messages, model=model)
            if not raw_reply or raw_reply.startswith("嗯，这次我有点卡住了。"):
                raw_reply = self._magic_compliment_fallback(has_image=bool(image_paths))
            reply = self._prepare_visual_reply(raw_reply) if image_paths else self._limit_reply(raw_reply)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _stream_magic_compliment(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
    ) -> Iterator[str]:
        if not self.client:
            reply = self._magic_compliment_fallback(has_image=bool(image_paths))
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            yield from self._chunk_text(reply)
            return

        messages = self._build_magic_compliment_messages(user_text, image_paths=image_paths)
        model = self.config.vision_model if image_paths else self.config.chat_model
        stream_method = getattr(getattr(self.client.chat, "completions", None), "stream", None)
        if callable(stream_method):
            parts: list[str] = []
            for chunk in stream_method(model=model, messages=messages, extra_body={"temperature": 0.8}):
                if not chunk:
                    continue
                parts.append(chunk)
                yield chunk
            raw_reply = "".join(parts).strip()
            if raw_reply:
                normalized = self._prepare_visual_reply(raw_reply) if image_paths else self._limit_reply(raw_reply)
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": normalized})
                return

        reply = self._respond_with_magic_compliment(user_text, image_paths=image_paths)
        yield from self._chunk_text(reply)
```

- [ ] **Step 4: Run the multimodal and fallback tests again**

Run from `/Users/bytedance/Desktop/A2A黑客松/mira/.worktrees/halo-home-display/mirror-agent`:

```bash
/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest \
  tests.test_agent.AgentTests.test_magic_compliment_with_camera_frame_uses_vision_model_and_multimodal_payload \
  tests.test_agent.AgentTests.test_magic_compliment_replaces_generic_chat_fallback \
  -v
```

Expected: both tests pass with `OK`.

- [ ] **Step 5: Run the full `tests.test_agent` suite as the final verification gate**

Run from `/Users/bytedance/Desktop/A2A黑客松/mira/.worktrees/halo-home-display/mirror-agent`:

```bash
/Users/bytedance/Desktop/A2A黑客松/mira/mirror-agent/.venv/bin/python -m unittest tests.test_agent -v
```

Expected: the existing agent tests still pass and the new magic-compliment coverage is included in the same green run.

- [ ] **Step 6: Commit the multimodal and fallback completion**

```bash
git add mirror-agent/agent.py mirror-agent/tests/test_agent.py
git commit -m "feat: support multimodal magic compliment demo"
```
