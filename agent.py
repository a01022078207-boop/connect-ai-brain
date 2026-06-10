#!/usr/bin/env python3
"""나만의 콘텐츠 크리에이터 에이전트 — 로컬 Ollama + 웹 채팅 UI.

실행:  python agent.py   →  브라우저에서 http://localhost:8800
의존성: 없음 (Python 표준 라이브러리만 사용). Ollama가 실행 중이어야 합니다.
"""

import json
import os
import shutil
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(ROOT, "memory")
ARCHIVE_DIR = os.path.join(MEMORY_DIR, "archive")
HISTORY_PATH = os.path.join(MEMORY_DIR, "history.jsonl")
PROFILE_PATH = os.path.join(MEMORY_DIR, "profile.md")
MEMORIES_PATH = os.path.join(MEMORY_DIR, "memories.md")

with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
    CONFIG = json.load(f)

OLLAMA_URL = CONFIG.get("ollama_url", "http://localhost:11434").rstrip("/")
MODEL = CONFIG.get("model", "gemma4:12b")
PORT = int(CONFIG.get("port", 8800))
CONTEXT_TURNS = int(CONFIG.get("context_turns", 30))

BASE_PROMPT = """당신은 사용자의 1인 콘텐츠 크리에이터 파트너입니다.

역할:
- 콘텐츠 기획: 주제 발굴, 영상/글 구조 설계, 시리즈 기획
- 대본·카피: 후크, 본문 대본, 캡션, 제목·썸네일 문구
- 정리: 아이디어·일정·할 일 정리, 산출물 폴리싱

일하는 방식:
- 아래 [프로필]과 [장기 메모리]를 항상 반영해서 답합니다.
- 추측이 필요하면 먼저 짧게 확인 질문을 하고, 그다음 초안을 만듭니다.
- 결과물은 바로 쓸 수 있게 구체적으로 — 모호한 조언 대신 실제 문장과 구조로.
- 한국어로 답합니다."""

REMEMBER_PREFIXES = ("기억해:", "기억해줘:", "remember:")


def read_file(path, default=""):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return default


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def append_history(role, content):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "role": role, "content": content},
            ensure_ascii=False) + "\n")


def load_history(limit):
    entries = []
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return entries[-limit:] if limit else entries


def remember(text):
    note = read_file(MEMORIES_PATH)
    if note and not note.endswith("\n"):
        note += "\n"
    note += "- [%s] %s\n" % (time.strftime("%Y-%m-%d"), text.strip())
    write_file(MEMORIES_PATH, note)


def build_messages(user_msg):
    system = (BASE_PROMPT
              + "\n\n[프로필]\n" + read_file(PROFILE_PATH, "(아직 비어 있음)")
              + "\n\n[장기 메모리]\n" + read_file(MEMORIES_PATH, "(아직 비어 있음)"))
    messages = [{"role": "system", "content": system}]
    for entry in load_history(CONTEXT_TURNS * 2):
        if entry.get("role") in ("user", "assistant"):
            messages.append({"role": entry["role"], "content": entry["content"]})
    messages.append({"role": "user", "content": user_msg})
    return messages


def stream_ollama(messages):
    """Ollama /api/chat 스트리밍 — 응답 텍스트 조각을 yield."""
    payload = json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 콘솔 잡음 줄이기

    # ---------- 응답 헬퍼 ----------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    # ---------- GET ----------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(ROOT, "static", "index.html"), "rb") as fh:
                    body = fh.read()
            except FileNotFoundError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/history":
            self._send_json({"model": MODEL, "messages": load_history(100)})
        elif self.path == "/memory":
            self._send_json({
                "profile": read_file(PROFILE_PATH),
                "memories": read_file(MEMORIES_PATH),
            })
        else:
            self.send_error(404)

    # ---------- POST ----------
    def do_POST(self):
        if self.path == "/chat":
            self._handle_chat()
        elif self.path == "/memory":
            body = self._read_body()
            if "profile" in body:
                write_file(PROFILE_PATH, body["profile"])
            if "memories" in body:
                write_file(MEMORIES_PATH, body["memories"])
            self._send_json({"ok": True})
        elif self.path == "/reset":
            if os.path.exists(HISTORY_PATH):
                os.makedirs(ARCHIVE_DIR, exist_ok=True)
                shutil.move(HISTORY_PATH, os.path.join(
                    ARCHIVE_DIR, time.strftime("%Y-%m-%dT%H-%M-%S") + ".jsonl"))
            self._send_json({"ok": True})
        else:
            self.send_error(404)

    def _handle_chat(self):
        user_msg = (self._read_body().get("message") or "").strip()
        if not user_msg:
            self._send_json({"error": "빈 메시지"}, status=400)
            return

        # 스트리밍 응답 시작 (HTTP/1.0 connection-close 방식)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        # "기억해:" 명령 → LLM 없이 장기 메모리에 바로 저장
        for prefix in REMEMBER_PREFIXES:
            if user_msg.startswith(prefix):
                note = user_msg[len(prefix):].strip()
                if note:
                    remember(note)
                    reply = "기억했습니다 ✅ → \"%s\"\n(memory/memories.md에 저장됨)" % note
                else:
                    reply = "기억할 내용이 비어 있어요. 예: 기억해: 내 채널 이름은 OOO"
                append_history("user", user_msg)
                append_history("assistant", reply)
                self.wfile.write(reply.encode("utf-8"))
                return

        append_history("user", user_msg)
        full_reply = []
        try:
            for chunk in stream_ollama(build_messages(user_msg)):
                full_reply.append(chunk)
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
        except urllib.error.URLError:
            msg = ("⚠️ Ollama에 연결할 수 없습니다 (%s).\n"
                   "터미널에서 `ollama serve`가 실행 중인지, "
                   "`ollama list`에 %s 모델이 있는지 확인해 주세요." % (OLLAMA_URL, MODEL))
            self.wfile.write(msg.encode("utf-8"))
            return
        except (BrokenPipeError, ConnectionResetError):
            pass  # 브라우저가 중간에 끊은 경우 — 받은 만큼만 기록
        if full_reply:
            append_history("assistant", "".join(full_reply))


def main():
    os.makedirs(MEMORY_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("🎬 크리에이터 에이전트 시작!")
    print("   모델: %s  (Ollama: %s)" % (MODEL, OLLAMA_URL))
    print("   브라우저에서 열기 → http://localhost:%d" % PORT)
    print("   종료: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n안녕히 가세요! 👋")


if __name__ == "__main__":
    main()
