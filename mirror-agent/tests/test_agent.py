import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path

from agent import MirrorAgent, should_end_session
from config import AppConfig
from ollama_client import OllamaClient
from main import build_parser


REPO_SOUL_PROMPT = (Path(__file__).resolve().parents[1] / "soul.md").read_text(encoding="utf-8")


class FakeStreamingCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def stream(self, model: str, messages: list[dict[str, object]], extra_body: dict[str, object] | None = None):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "extra_body": extra_body or {},
            }
        )
        yield "今天"
        yield "看着还行"


class FakeStreamingClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeStreamingCompletions()})()


class FakeVisualStreamingCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def stream(self, model: str, messages: list[dict[str, object]], extra_body: dict[str, object] | None = None):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "extra_body": extra_body or {},
            }
        )
        yield "这张图里"
        yield "今天看着还行"


class FakeVisualStreamingClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeVisualStreamingCompletions()})()


class FakeNonStreamingCompletions:
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
                        "content": "我看到左脸颊这边啦。",
                    }
                }
            ]
        }


class FakeNonStreamingClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeNonStreamingCompletions()})()


class FakeLongReplyCompletions:
    def create(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
        extra_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            "第一句很长很长地夸你今天状态不错。第二句继续认真分析你的皮肤状态。"
                            "第三句再补一点作息和饮食相关的原因。第四句再给一条额外建议。"
                            "第五句再多安慰你一下。第六句其实已经超了，所以不该保留。"
                        ),
                    }
                }
            ]
        }


class FakeLongReplyClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeLongReplyCompletions()})()


class FakeLongSentenceCompletions:
    def create(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
        extra_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            "这一句会故意写得很长很长，长到超过一百个字，但它本身还是一个完整句子，所以系统应该保留这整句内容，"
                            "而不是在中间硬切开或者补一个省略号让它听起来像没说完，而且这一句还会继续往下补更多口语化的内容，"
                            "比如你今天状态其实挺稳的、先别焦虑、慢慢来就好，这些也都应该作为同一句的一部分完整保留下来。"
                        ),
                    }
                }
            ]
        }


class FakeLongSentenceClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeLongSentenceCompletions()})()


class FakeMarkdownReplyCompletions:
    def create(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None = None,
        extra_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "## 今日观察\n- 你今天状态其实不错\n- 左脸颊这边有一点点泛红，先别焦虑",
                    }
                }
            ]
        }


class FakeMarkdownReplyClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeMarkdownReplyCompletions()})()


class FakeMaskTimerOfferCompletions:
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
                        "content": "你现在像是在敷面膜耶，要不要我帮你开始15分钟计时？",
                    }
                }
            ]
        }


class FakeMaskTimerOfferClient:
    def __init__(self) -> None:
        self.chat = type("ChatAPI", (), {"completions": FakeMaskTimerOfferCompletions()})()


class AgentTests(unittest.TestCase):
    def test_should_end_session_detects_bye(self) -> None:
        self.assertTrue(should_end_session("拜拜啦"))
        self.assertTrue(should_end_session("晚安镜子虾"))
        self.assertFalse(should_end_session("今天有点爆痘"))

    def test_build_memory_context_includes_core_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "memory" / "profile.md").write_text("# 用户画像\n油皮\n", encoding="utf-8")
            (project_root / "memory" / "insights.md").write_text("# 洞察\n最近压力大\n", encoding="utf-8")
            (project_root / "memory" / "diary" / "2026-04-04.md").write_text(
                "# 2026-04-04\n\n今天有点红。\n",
                encoding="utf-8",
            )
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(project_root=project_root, api_key="test-key")
            agent = MirrorAgent(config=config, client=None)

            context = agent.build_memory_context()

            self.assertIn("油皮", context)
            self.assertIn("最近压力大", context)
            self.assertIn("今天有点红", context)

    def test_build_system_prompt_includes_reply_length_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(project_root=project_root, api_key="test-key")
            agent = MirrorAgent(config=config, client=None)

            prompt = agent.build_system_prompt()

            self.assertIn("100字以内", prompt)
            self.assertIn("最多5句", prompt)
            self.assertIn("直接说你能确认到的现象和区域", prompt)

    def test_build_system_prompt_includes_first_meeting_name_and_companionship_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text(REPO_SOUL_PROMPT, encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(project_root=project_root, api_key="test-key")
            agent = MirrorAgent(config=config, client=None)

            prompt = agent.build_system_prompt()

            self.assertIn("你想叫我什么", prompt)
            self.assertIn("跟我说说你呗", prompt)
            self.assertIn("聊着聊着我就懂你了", prompt)
            self.assertIn("把作息、吃饭和护肤习惯养稳", prompt)

    def test_build_system_prompt_includes_tcm_face_mapping_and_food_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text(REPO_SOUL_PROMPT, encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(project_root=project_root, api_key="test-key")
            agent = MirrorAgent(config=config, client=None)

            prompt = agent.build_system_prompt()

            self.assertIn("左脸颊：肝气不舒", prompt)
            self.assertIn("玫瑰花茶", prompt)
            self.assertIn("下巴：肾气不足", prompt)
            self.assertIn("黑芝麻", prompt)

    def test_respond_shortens_overlong_model_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            agent = MirrorAgent(config=config, client=FakeLongReplyClient())

            reply = agent.respond("夸夸我")

            self.assertLessEqual(len(reply), 100)
            sentence_count = sum(reply.count(mark) for mark in "。！？!?")
            self.assertLessEqual(sentence_count, 5)
            self.assertNotIn("第六句", reply)
            self.assertNotEqual("…", reply[-1])
            self.assertIn(reply[-1], "。！？!?")

    def test_respond_keeps_complete_sentence_even_when_one_sentence_exceeds_soft_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            agent = MirrorAgent(config=config, client=FakeLongSentenceClient())

            reply = agent.respond("继续说")

            self.assertGreater(len(reply), 100)
            self.assertNotEqual("…", reply[-1])
            self.assertIn(reply[-1], "。！？!?")

    def test_respond_strips_headings_and_bullets_into_conversational_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            agent = MirrorAgent(config=config, client=FakeMarkdownReplyClient())

            reply = agent.respond("我脸有点红")

            self.assertNotIn("##", reply)
            self.assertNotIn("- ", reply)
            self.assertIn("你今天状态其实不错", reply)
            self.assertIn("左脸颊这边有一点点泛红", reply)

    def test_display_name_uses_saved_mirror_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是一个住在镜子里的AI护肤闺蜜。", encoding="utf-8")
            (project_root / "memory" / "profile.md").write_text(
                "# 用户画像\n\n## 2026-04-05\n\n- 镜中名字：小镜\n",
                encoding="utf-8",
            )
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(project_root=project_root, api_key="test-key")
            agent = MirrorAgent(config=config, client=None)

            self.assertEqual("小镜", agent.display_name())

    def test_builds_ollama_client_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            agent = MirrorAgent(config=config, client=None)

            self.assertIsInstance(agent.client, OllamaClient)

    def test_main_parser_enables_voice_mode(self) -> None:
        parser = build_parser()

        args: Namespace = parser.parse_args(["--voice"])

        self.assertTrue(args.voice)

    def test_photo_trigger_uses_face_to_face_copy_without_photo_upload_words(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            agent = MirrorAgent(config=config, client=object())

            reply = agent.respond("看看我的脸")

            self.assertIn("靠近", reply)
            self.assertNotIn("照片", reply)
            self.assertNotIn("图片", reply)
            self.assertTrue(agent.awaiting_photo)

    def test_camera_mode_does_not_fall_back_to_send_photo_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            agent = MirrorAgent(config=config, client=object())

            reply = agent.respond("看看我", camera_active=True)

            self.assertNotIn("发张照片", reply)
            self.assertIn("镜头", reply)
            self.assertFalse(agent.awaiting_photo)

    def test_image_path_after_photo_trigger_routes_to_selfie_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "selfie.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            agent = MirrorAgent(config=config, client=object())
            agent.respond("看看我")

            calls: list[tuple[str, str]] = []

            def fake_respond_to_image(path: str, note: str = "") -> str:
                calls.append((path, note))
                return "今天气色还不错嘛！7分。"

            agent.respond_to_image = fake_respond_to_image  # type: ignore[method-assign]

            reply = agent.respond(str(image_path))

            self.assertEqual("今天气色还不错嘛！7分。", reply)
            self.assertEqual([(str(image_path.resolve()), "")], calls)
            self.assertFalse(agent.awaiting_photo)

    def test_respond_to_image_writes_selfie_result_to_today_diary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "selfie.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            agent = MirrorAgent(config=config, client=object())

            analysis = {
                "is_selfie": True,
                "complexion_score": 7,
                "skin_issues": ["黑眼圈", "轻微干燥"],
                "emotion": "有点疲惫",
                "comparison": "比昨天好一点",
                "reply": "今天气色还不错嘛！7分。不过眼下有点黑眼圈，昨晚几点睡的？比昨天好一些，继续保持～",
            }
            diary_path = project_root / "memory" / "diary" / f"{date.today().isoformat()}.md"

            agent.tools.analyze_selfie = lambda image_path, note="": analysis  # type: ignore[method-assign]
            agent.tools.record_selfie_analysis = (  # type: ignore[method-assign]
                lambda analysis, image_path, note="", diary_date=None: diary_path
            )

            reply = agent.respond_to_image(str(image_path))

            self.assertIn("今天气色还不错嘛", reply)
            self.assertIn(reply, [item["content"] for item in agent.history if item["role"] == "assistant"])

    def test_respond_to_image_sanitizes_photo_wording_in_analysis_reply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "selfie.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            agent = MirrorAgent(config=config, client=object())
            agent.tools.analyze_selfie = lambda image_path, note="": {  # type: ignore[method-assign]
                "reply": "这张图里你下巴有点红，照片里鼻头也有点油。",
            }
            agent.tools.record_selfie_analysis = lambda analysis, image_path, note="", diary_date=None: image_path  # type: ignore[method-assign]

            reply = agent.respond_to_image(str(image_path))

            self.assertNotIn("这张图", reply)
            self.assertNotIn("照片", reply)
            self.assertIn("你下巴有点红", reply)

    def test_prepare_visual_reply_keeps_concrete_observation_and_drops_media_request_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            agent = MirrorAgent(config=config, client=object())

            reply = agent._prepare_visual_reply(
                "这张图片里你下巴有点红，不过还要再发一张更近一点的照片，我才能看得更清楚。"
            )

            self.assertNotIn("图片", reply)
            self.assertNotIn("照片", reply)
            self.assertNotIn("发一张", reply)
            self.assertNotIn("看得更清楚", reply)
            self.assertIn("你下巴有点红", reply)

    def test_prepare_visual_reply_drops_uncertainty_prefix_but_keeps_region_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            agent = MirrorAgent(config=config, client=object())

            reply = agent._prepare_visual_reply("画面有点模糊，不过我看到你左脸颊靠鼻翼这块有点泛红，鼻头也有点油。")

            self.assertNotIn("画面", reply)
            self.assertNotIn("模糊", reply)
            self.assertIn("左脸颊靠鼻翼这块有点泛红", reply)
            self.assertIn("鼻头也有点油", reply)

    def test_mask_activity_without_minutes_uses_default_fifteen_minute_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            config = AppConfig(project_root=project_root, api_key="")
            agent = MirrorAgent(config=config, client=FakeNonStreamingClient())

            reply = agent.respond("我刚敷上面膜了")
            due = agent.reminder_scheduler.pop_due()

            self.assertIn("15 分钟后", reply)
            self.assertEqual([], due)

    def test_mask_offer_confirmation_schedules_reminder_after_visual_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "camera-frame.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            agent = MirrorAgent(config=config, client=FakeMaskTimerOfferClient())

            offer_reply = agent.respond("我现在状态怎么样", image_paths=[str(image_path)])
            confirm_reply = agent.respond("好呀，开始吧")

            self.assertIn("15分钟计时", offer_reply)
            self.assertIn("15 分钟后", confirm_reply)
            self.assertIsNone(agent.pending_timer_offer)

    def test_mask_reminder_request_with_camera_frame_schedules_instead_of_multimodal_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "camera-frame.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(project_root=project_root, api_key="")
            agent = MirrorAgent(config=config, client=FakeNonStreamingClient())

            reply = agent.respond("我刚敷上面膜了", image_paths=[str(image_path)], camera_active=True)

            self.assertIn("15 分钟后", reply)
            self.assertEqual(1, len(agent.reminder_scheduler._items))

    def test_stream_mask_reminder_request_with_camera_frame_schedules_instead_of_multimodal_chat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "camera-frame.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(project_root=project_root, api_key="")
            agent = MirrorAgent(config=config, client=FakeNonStreamingClient())

            chunks = list(agent.stream_respond("我刚敷上面膜了", image_paths=[str(image_path)], camera_active=True))

            self.assertEqual(
                "好呀，我已经替你记下了。15 分钟后，我会提醒你：面膜时间到了，记得摘掉并轻轻按摩一下哦。",
                "".join(chunks),
            )
            self.assertEqual(1, len(agent.reminder_scheduler._items))

    def test_stream_respond_can_include_camera_frame_as_multimodal_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "camera-frame.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            client = FakeStreamingClient()
            agent = MirrorAgent(config=config, client=client)

            chunks = list(agent.stream_respond("我现在皮肤状态怎么样", image_paths=[str(image_path)]))

            self.assertEqual(["今天看着还行。"], chunks)
            stream_call = client.chat.completions.calls[0]
            messages = stream_call["messages"]
            self.assertEqual("system", messages[0]["role"])
            self.assertEqual("user", messages[-1]["role"])
            self.assertTrue(messages[-1]["content"].startswith("我现在皮肤状态怎么样"))
            self.assertIn("当前这一轮你面前可参考的视角顺序如下", messages[-1]["content"])
            self.assertEqual(1, len(messages[-1]["images"]))
            self.assertIn("今天看着还行。", [item["content"] for item in agent.history if item["role"] == "assistant"])

    def test_stream_multimodal_sanitizes_photo_wording_before_emitting_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "camera-frame.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            client = FakeVisualStreamingClient()
            agent = MirrorAgent(config=config, client=client)

            chunks = list(agent.stream_respond("我现在皮肤状态怎么样", image_paths=[str(image_path)]))

            reply = "".join(chunks)
            self.assertNotIn("这张图", reply)
            self.assertNotIn("照片", reply)
            self.assertEqual("你今天看着还行。", reply)

    def test_stream_multimodal_fallback_uses_vision_model_when_provider_has_no_stream_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            image_path = project_root / "camera-frame.jpg"
            image_path.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            client = FakeNonStreamingClient()
            agent = MirrorAgent(config=config, client=client)

            chunks = list(agent.stream_respond("我脸上这里长了个痘痘", image_paths=[str(image_path)]))

            self.assertEqual(["我看到左脸颊这边", "啦。"], chunks)
            self.assertEqual("Qwen2.5-VL-32B-Instruct", client.chat.completions.calls[0]["model"])

    def test_build_user_message_formats_structured_multimodal_payload_for_aiping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            full_face = project_root / "mirror-region-full-face.jpg"
            left_cheek = project_root / "mirror-region-left-cheek.jpg"
            full_face.write_bytes(b"fake-image")
            left_cheek.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="aiping",
                api_key="test-key",
                chat_model="Qwen3-14B",
                vision_model="Qwen2.5-VL-32B-Instruct",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            agent = MirrorAgent(config=config, client=object())

            message = agent._build_user_message(
                "我脸上这里长了个痘痘",
                image_paths=[str(full_face), str(left_cheek)],
            )

            self.assertEqual("user", message["role"])
            self.assertIsInstance(message["content"], list)
            self.assertEqual("text", message["content"][0]["type"])
            self.assertIn("完整画面", message["content"][0]["text"])
            self.assertIn("左脸颊局部", message["content"][0]["text"])
            self.assertEqual("image_url", message["content"][1]["type"])
            self.assertTrue(message["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_build_user_message_adds_direct_observation_guidance_for_ollama_multimodal_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "soul.md").write_text("你是镜子虾。", encoding="utf-8")
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")
            full_face = project_root / "mirror-region-full-face.jpg"
            left_cheek = project_root / "mirror-region-left-cheek.jpg"
            full_face.write_bytes(b"fake-image")
            left_cheek.write_bytes(b"fake-image")

            config = AppConfig(
                project_root=project_root,
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            agent = MirrorAgent(config=config, client=object())

            message = agent._build_user_message(
                "我脸上这里长了个痘痘",
                image_paths=[str(full_face), str(left_cheek)],
            )

            self.assertEqual("user", message["role"])
            self.assertIn("完整画面", message["content"])
            self.assertIn("左脸颊局部", message["content"])
            self.assertIn("直接说你能确认到的现象、区域和轻重", message["content"])
            self.assertNotIn("这一轮还不够稳", message["content"])
