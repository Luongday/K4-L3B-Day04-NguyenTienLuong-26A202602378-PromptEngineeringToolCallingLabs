from __future__ import annotations

import argparse
import json
import threading
import uuid
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from chat import now_iso, run_model_tool_loop, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
STATIC_DIR = ROOT / "ui"
MAX_REQUEST_BYTES = 64 * 1024
MAX_USER_CHARS = 8_000
load_lab_env(ROOT)


class UiApplication:
    def __init__(
        self,
        *,
        provider_name: str,
        model: str | None,
        version: str,
        system_prompt_path: Path,
        tools_path: Path,
        transcripts_dir: Path,
        history_window: int,
        max_tool_rounds: int,
    ) -> None:
        self.provider_name = provider_name
        self.provider = make_provider(provider_name)
        self.model = model
        self.selected_model = model or getattr(self.provider, "default_model", None)
        self.version = version
        self.system_prompt_path = system_prompt_path
        self.tools_path = tools_path
        self.transcripts_dir = transcripts_dir
        self.history_window = history_window
        self.max_tool_rounds = max_tool_rounds
        self.system_prompt = system_prompt_path.read_text(encoding="utf-8")
        self.tools = to_openai_tools(load_tool_declarations(tools_path))
        self.artifact = build_artifact_version(version, system_prompt_path, tools_path)
        self.sessions: dict[str, dict[str, Any]] = {}
        self.sessions_lock = threading.Lock()

    def public_config(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "artifact_version": self.artifact.artifact_version,
            "provider": self.provider_name,
            "model": self.selected_model,
            "history_window": self.history_window,
            "max_tool_rounds": self.max_tool_rounds,
        }

    def create_session(self) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        transcript_id = f"{self.version}_{self.provider_name}_ui_{timestamp}_{session_id[:8]}"
        transcript_path = self.transcripts_dir / f"{transcript_id}.transcript.json"
        transcript: dict[str, Any] = {
            "transcript_id": transcript_id,
            **artifact_version_dict(self.artifact),
            "provider": self.provider_name,
            "model": self.selected_model,
            "system_prompt": str(self.system_prompt_path),
            "tools": str(self.tools_path),
            "interface": "local_web_ui",
            "history_window": self.history_window,
            "max_tool_rounds": self.max_tool_rounds,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "turns": [],
        }
        session = {
            "history": [],
            "transcript": transcript,
            "transcript_path": transcript_path,
            "lock": threading.Lock(),
        }
        with self.sessions_lock:
            self.sessions[session_id] = session
        write_transcript(transcript_path, transcript)
        return {
            "session_id": session_id,
            "transcript_path": self._display_path(transcript_path),
            **self.public_config(),
        }

    def chat(self, session_id: str, user_text: str) -> dict[str, Any]:
        with self.sessions_lock:
            session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("unknown_session")

        normalized_text = user_text.strip()
        if not normalized_text:
            raise ValueError("Message must not be empty.")
        if len(normalized_text) > MAX_USER_CHARS:
            raise ValueError(f"Message exceeds {MAX_USER_CHARS} characters.")

        with session["lock"]:
            history: list[dict[str, str]] = session["history"]
            transcript: dict[str, Any] = session["transcript"]
            transcript_path: Path = session["transcript_path"]
            turn_index = len(transcript["turns"]) + 1
            messages = [
                {"role": "system", "content": self.system_prompt},
                *trim_history(history, self.history_window),
                {"role": "user", "content": normalized_text},
            ]
            turn_record: dict[str, Any] = {
                "turn_index": turn_index,
                "started_at": now_iso(),
                "user": normalized_text,
                "status": "started",
                "assistant_text": None,
                "rounds": [],
                "tool_events": [],
            }

            try:
                result = run_model_tool_loop(
                    provider=self.provider,
                    messages=messages,
                    tools=self.tools,
                    model=self.model,
                    max_tool_rounds=self.max_tool_rounds,
                )
                turn_record.update(result)
                assistant_text = result["assistant_text"]
                history.append({"role": "user", "content": normalized_text})
                history.append({"role": "assistant", "content": assistant_text})
            except Exception as exc:
                turn_record.update({
                    "status": "provider_error",
                    "assistant_text": "Không thể hoàn thành lượt này do lỗi provider. Xem transcript để biết loại lỗi.",
                    "error": f"{type(exc).__name__}: {str(exc)}",
                })

            turn_record["ended_at"] = now_iso()
            transcript["turns"].append(turn_record)
            write_transcript(transcript_path, transcript)
            return {
                "turn": turn_record,
                "artifact_version": self.artifact.artifact_version,
                "transcript_path": self._display_path(transcript_path),
            }

    @staticmethod
    def _display_path(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)


class UiServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], app: UiApplication) -> None:
        super().__init__(server_address, UiRequestHandler)
        self.app = app


class UiRequestHandler(BaseHTTPRequestHandler):
    server: UiServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        static_files = {
            "/": (STATIC_DIR / "index.html", "text/html; charset=utf-8"),
            "/app.js": (STATIC_DIR / "app.js", "text/javascript; charset=utf-8"),
            "/styles.css": (STATIC_DIR / "styles.css", "text/css; charset=utf-8"),
        }
        if self.path == "/api/config":
            self._send_json(HTTPStatus.OK, self.server.app.public_config())
            return
        static = static_files.get(self.path)
        if static is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        path, content_type = static
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "missing_ui_asset"})
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        try:
            payload = self._read_json()
            if self.path == "/api/session":
                self._send_json(HTTPStatus.CREATED, self.server.app.create_session())
                return
            if self.path == "/api/chat":
                session_id = str(payload.get("session_id") or "")
                user_text = str(payload.get("message") or "")
                self._send_json(HTTPStatus.OK, self.server.app.chat(session_id, user_text))
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc).strip("'")})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": type(exc).__name__, "message": "Unexpected UI server error."},
            )

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length.") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Invalid request size.")
        data = self.rfile.read(length)
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the console useful without logging message bodies or secrets.
        print(f"[ui] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local web UI for the Northstar Labs IT Helpdesk Agent.")
    parser.add_argument("--provider", choices=["openrouter", "openai", "anthropic", "gemini"], required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--version", required=True)
    parser.add_argument("--system-prompt", type=Path, default=ARTIFACTS_DIR / "system_prompt.md")
    parser.add_argument("--tools", type=Path, default=ARTIFACTS_DIR / "tools.yaml")
    parser.add_argument("--transcripts-dir", type=Path, default=ROOT / "transcripts")
    parser.add_argument("--history-window", type=int, default=5)
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()

    app = UiApplication(
        provider_name=args.provider,
        model=args.model,
        version=args.version,
        system_prompt_path=args.system_prompt,
        tools_path=args.tools,
        transcripts_dir=args.transcripts_dir,
        history_window=args.history_window,
        max_tool_rounds=args.max_tool_rounds,
    )
    server = UiServer((args.host, args.port), app)
    url = f"http://{args.host}:{args.port}"
    print(f"Northstar Labs Helpdesk UI: {url}")
    print(f"artifact_version={app.artifact.artifact_version}")
    print("Press Ctrl+C to stop.")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping UI server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
