import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def test_send_button_can_fallback_to_bottom_input_text(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('const draft = messageInput.value.trim() || imageNoteInput.value.trim();', script)

    def test_selecting_image_no_longer_auto_sends(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn('imageInput.addEventListener("change", async () => {', script)

    def test_image_note_placeholder_is_explicitly_auxiliary(self) -> None:
        template = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn('图片说明（选图后再填，可空着）', template)

    def test_voice_button_exists_in_template(self) -> None:
        template = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="voice-button"', template)

    def test_camera_controls_exist_in_template(self) -> None:
        template = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="camera-button"', template)
        self.assertIn('id="camera-preview"', template)
        self.assertIn('id="camera-canvas"', template)

    def test_frontend_calls_voice_chat_endpoint(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('fetch("/api/voice-chat"', script)
        self.assertIn('fetch("/api/voice-chat-stream"', script)

    def test_frontend_renders_audio_player_for_voice_reply(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('document.createElement("audio")', script)
        self.assertIn("audioPlayer.controls = true;", script)

    def test_frontend_surfaces_autoplay_block_status(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("自动播放被浏览器拦住了", script)

    def test_frontend_uses_voice_activity_detection_for_single_tap_flow(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("new AudioContext()", script)
        self.assertIn("createAnalyser()", script)
        self.assertIn("window.setTimeout(stopVoiceRecording", script)

    def test_voice_button_copy_matches_manual_and_hands_free_modes(self) -> None:
        template = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn("点一下开口", template)
        self.assertIn("想免按键直接对话，就先开镜头", template)

    def test_web_voice_flow_no_longer_requires_wake_word_copy(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("记得先叫我“小镜”", script)

    def test_frontend_uses_browser_speech_recognition_for_live_user_subtitles(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("window.SpeechRecognition || window.webkitSpeechRecognition", script)
        self.assertIn("recognition.interimResults = true;", script)

    def test_frontend_reads_streaming_reply_chunks(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("response.body.getReader()", script)
        self.assertIn('type === "reply_delta"', script)
        self.assertIn('type === "transcript"', script)

    def test_frontend_plays_voice_reply_after_image_analysis(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("replyPayload.audio_url", script)
        self.assertIn("appendAgentVoiceReply(replyPayload.reply, replyPayload.audio_url)", script)

    def test_frontend_serializes_audio_playback_to_single_channel(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("let activeAudioPlayer = null;", script)
        self.assertIn("let playbackQueue = Promise.resolve();", script)
        self.assertIn("await waitForAudioPlayback(activeAudioPlayer);", script)

    def test_frontend_opens_camera_and_captures_frame_for_voice_round(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('navigator.mediaDevices.getUserMedia({ video: true, audio: false })', script)
        self.assertIn('cameraCanvas.toBlob', script)
        self.assertIn('formData.append("frame", frameBlob, "mirror-agent-frame.jpg");', script)
        self.assertIn('formData.append("camera_active", "true");', script)

    def test_frontend_attempts_face_region_capture_for_camera_round(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("typeof FaceDetector", script)
        self.assertIn('formData.append("frame_regions"', script)

    def test_frontend_polls_due_reminders(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('fetch("/api/reminders/due"', script)
        self.assertIn("window.setInterval", script)

    def test_frontend_auto_starts_voice_round_when_camera_turns_on(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("let autoMirrorMode = false;", script)
        self.assertIn("await startVoiceRecording({ autoStarted: true });", script)

    def test_main_page_exposes_tablet_screen_link(self) -> None:
        template = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn('href="/tablet"', template)
        self.assertIn("打开平板页", template)

    def test_main_frontend_syncs_display_state_to_tablet_screen(self) -> None:
        script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('new BroadcastChannel("mirror-tablet-display")', script)
        self.assertIn('localStorage.setItem("mirror-tablet-state"', script)
        self.assertIn("pushTabletScene(", script)

    def test_tablet_frontend_uses_only_the_selected_five_animation_variants(self) -> None:
        script = (PROJECT_ROOT / "static" / "tablet.js").read_text(encoding="utf-8")

        self.assertIn('"startup": "crown-trace"', script)
        self.assertIn('"listening": "wand-sweep"', script)
        self.assertIn('"thinking": "star-spiral"', script)
        self.assertIn('"reply": "bow-flash"', script)
        self.assertIn('"idle": "ribbon-sway"', script)
