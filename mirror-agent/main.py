from __future__ import annotations

import argparse

from agent import MirrorAgent, parse_image_command, should_end_session
from voice_input import VoiceInput
from voice_output import VoiceOutput


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="镜中闺蜜 CLI")
    parser.add_argument("--voice", action="store_true", help="启用语音模式")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = MirrorAgent()
    voice_input = VoiceInput(wake_word="") if args.voice else None
    voice_output = VoiceOutput() if args.voice else None
    print(f"{agent.display_name()}：嗨，我在镜子里等你了。直接跟我聊天就行，发图用 /image <图片路径> <补充描述>。")
    if args.voice:
        print(f"{agent.display_name()}：语音模式开了。你直接说话就行，我会听。")

    while True:
        try:
            if args.voice:
                raw = voice_input.listen_for_prompt().strip()  # type: ignore[union-attr]
                if not raw:
                    print(f"{agent.display_name()}：这句我听到了个开头，后半句有点糊。你再说一次。")
                    continue
                print(f"你（语音）:{raw}")
            else:
                raw = input("你：").strip()
        except Exception as exc:
            if args.voice:
                print(f"[voice] 语音输入出了点岔子：{exc}")
                print("[voice] 先检查麦克风权限、ffmpeg 和 pyaudio，再重试。")
                break
            raise
        except (EOFError, KeyboardInterrupt):
            print()
            raw = "晚安"

        if not raw:
            continue

        if raw in {"/quit", "/exit"}:
            raw = "晚安"

        if raw.startswith("/image"):
            try:
                image_path, note = parse_image_command(raw)
                reply = agent.respond_to_image(image_path, note)
            except ValueError as exc:
                reply = str(exc)
            print(f"{agent.display_name()}：{reply}")
            if args.voice:
                try:
                    voice_output.speak(reply)  # type: ignore[union-attr]
                except Exception as exc:
                    print(f"[voice] 语音播报失败：{exc}")
            continue

        if should_end_session(raw):
            reply, diary_path = agent.close_session(raw)
            print(f"{agent.display_name()}：{reply}")
            print(f"[memory] 已写入 {diary_path}")
            if args.voice:
                try:
                    voice_output.speak(reply)  # type: ignore[union-attr]
                except Exception as exc:
                    print(f"[voice] 语音播报失败：{exc}")
            break

        reply = agent.respond(raw)
        print(f"{agent.display_name()}：{reply}")
        if args.voice:
            try:
                voice_output.speak(reply)  # type: ignore[union-attr]
            except Exception as exc:
                print(f"[voice] 语音播报失败：{exc}")


if __name__ == "__main__":
    main()
