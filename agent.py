#!/usr/bin/env python3
"""나만의 콘텐츠 크리에이터 에이전트 사무실 — 로컬 Ollama + 4분할 대시보드.

여러 역할 에이전트(기획자·대본가·편집장·마케터)가 같은 모델(gemma4:12b)을
역할별 프롬프트로 나눠 쓰며, 사무실 화면에서 누가 일하는지 실시간으로 보입니다.

실행:  python agent.py   →  브라우저에서 http://localhost:8800
의존성: 없음 (Python 표준 라이브러리만 사용). Ollama가 실행 중이어야 합니다.
"""

import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(ROOT, "memory")
ARCHIVE_DIR = os.path.join(MEMORY_DIR, "archive")
HISTORY_PATH = os.path.join(MEMORY_DIR, "history.jsonl")
OUTPUTS_PATH = os.path.join(MEMORY_DIR, "outputs.jsonl")
PROFILE_PATH = os.path.join(MEMORY_DIR, "profile.md")
MEMORIES_PATH = os.path.join(MEMORY_DIR, "memories.md")

with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
    CONFIG = json.load(f)
with open(os.path.join(ROOT, "agents.json"), encoding="utf-8") as f:
    AGENTS = json.load(f)
AGENTS_BY_ID = {a["id"]: a for a in AGENTS}

OLLAMA_URL = CONFIG.get("ollama_url", "http://localhost:11434").rstrip("/")
MODEL = CONFIG.get("model", "gemma4:12b")
PORT = int(CONFIG.get("port", 8800))
CONTEXT_TURNS = int(CONFIG.get("context_turns", 30))
PASSWORD = CONFIG.get("password", "")  # 비어 있으면 인증 없음 (로컬 전용 권장)

BASE_PROMPT = """당신은 1인 콘텐츠 크리에이터를 돕는 AI 사무실의 직원입니다.

공통 원칙:
- 아래 [내 역할]에 충실하게, 바로 쓸 수 있게 구체적으로 답합니다.
- 추측이 필요하면 먼저 짧게 확인 질문을 한 뒤 초안을 만듭니다.
- 모호한 조언 대신 실제 문장·구조·예시로 답합니다.
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


def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_jsonl(path, limit=0):
    entries = []
    try:
        with open(path, encoding="utf-8") as fh:
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


def append_history(role, content, agent=None):
    append_jsonl(HISTORY_PATH, {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "role": role, "content": content, "agent": agent})


def save_output(agent_id, user_msg, reply):
    title = user_msg.strip().splitlines()[0][:40] if user_msg.strip() else "결과물"
    append_jsonl(OUTPUTS_PATH, {
        "ts": time.strftime("%Y-%m-%d %H:%M"),
        "agent": agent_id, "title": title, "content": reply.strip()})


def save_agents(new_list):
    """프런트에서 받은 에이전트 명단을 검증·저장하고 메모리에 반영."""
    global AGENTS, AGENTS_BY_ID
    cleaned, used_ids = [], set()
    for a in new_list:
        name = (a.get("name") or "").strip()
        if not name:
            continue
        aid = (a.get("id") or "").strip() or "agent"
        base = aid
        n = 2
        while aid in used_ids:  # id 중복 방지
            aid = "%s%d" % (base, n)
            n += 1
        used_ids.add(aid)
        skills = [s.strip() for s in a.get("skills", []) if isinstance(s, str) and s.strip()]
        cleaned.append({
            "id": aid,
            "name": name,
            "emoji": (a.get("emoji") or "🧑").strip() or "🧑",
            "role": (a.get("role") or "").strip() or "역할 설명을 입력하세요.",
            "skills": skills,
            "prompt": (a.get("prompt") or "").strip()
                      or ("당신은 %s 역할의 직원입니다. 맡은 일을 구체적으로 처리하세요." % name),
        })
    if not cleaned:
        return False
    with open(os.path.join(ROOT, "agents.json"), "w", encoding="utf-8") as fh:
        json.dump(cleaned, fh, ensure_ascii=False, indent=2)
    AGENTS = cleaned
    AGENTS_BY_ID = {a["id"]: a for a in AGENTS}
    return True


def remember(text):
    note = read_file(MEMORIES_PATH)
    if note and not note.endswith("\n"):
        note += "\n"
    note += "- [%s] %s\n" % (time.strftime("%Y-%m-%d"), text.strip())
    write_file(MEMORIES_PATH, note)


def build_messages(user_msg, agent):
    system = (BASE_PROMPT
              + "\n\n[내 역할 — %s %s]\n%s" % (agent["emoji"], agent["name"], agent["prompt"])
              + "\n\n[프로필]\n" + read_file(PROFILE_PATH, "(아직 비어 있음)")
              + "\n\n[장기 메모리]\n" + read_file(MEMORIES_PATH, "(아직 비어 있음)"))
    messages = [{"role": "system", "content": system}]
    for entry in load_jsonl(HISTORY_PATH, CONTEXT_TURNS * 2):
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

    # ---------- 인증 ----------
    def _authorized(self):
        if not PASSWORD:
            return True
        return self.headers.get("X-Password", "") == PASSWORD

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
            return
        if not self._authorized():
            self._send_json({"error": "unauthorized"}, status=401)
            return
        if self.path == "/agents":
            self._send_json({"model": MODEL, "agents": AGENTS})
        elif self.path == "/history":
            self._send_json({"messages": load_jsonl(HISTORY_PATH, 100)})
        elif self.path == "/outputs":
            self._send_json({"outputs": list(reversed(load_jsonl(OUTPUTS_PATH, 50)))})
        elif self.path == "/memory":
            self._send_json({
                "profile": read_file(PROFILE_PATH),
                "memories": read_file(MEMORIES_PATH),
            })
        else:
            self.send_error(404)

    # ---------- POST ----------
    def do_POST(self):
        if not self._authorized():
            self._send_json({"error": "unauthorized"}, status=401)
            return
        if self.path == "/chat":
            self._handle_chat()
        elif self.path == "/agents":
            body = self._read_body()
            if save_agents(body.get("agents", [])):
                self._send_json({"ok": True, "agents": AGENTS})
            else:
                self._send_json({"error": "에이전트가 최소 1명은 있어야 합니다"}, status=400)
        elif self.path == "/memory":
            body = self._read_body()
            if "profile" in body:
                write_file(PROFILE_PATH, body["profile"])
            if "memories" in body:
                write_file(MEMORIES_PATH, body["memories"])
            self._send_json({"ok": True})
        elif self.path == "/reset":
            for p in (HISTORY_PATH, OUTPUTS_PATH):
                if os.path.exists(p):
                    os.makedirs(ARCHIVE_DIR, exist_ok=True)
                    shutil.move(p, os.path.join(
                        ARCHIVE_DIR, time.strftime("%Y-%m-%dT%H-%M-%S-")
                        + os.path.basename(p)))
            self._send_json({"ok": True})
        else:
            self.send_error(404)

    def _handle_chat(self):
        body = self._read_body()
        user_msg = (body.get("message") or "").strip()
        agent = AGENTS_BY_ID.get(body.get("agent"), AGENTS[0])
        if not user_msg:
            self._send_json({"error": "빈 메시지"}, status=400)
            return

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
                append_history("user", user_msg, agent["id"])
                append_history("assistant", reply, agent["id"])
                self.wfile.write(reply.encode("utf-8"))
                return

        append_history("user", user_msg, agent["id"])
        full_reply = []
        try:
            for chunk in stream_ollama(build_messages(user_msg, agent)):
                full_reply.append(chunk)
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
        except urllib.error.URLError:
            msg = ("⚠️ Ollama에 연결할 수 없습니다 (%s).\n"
                   "터미널에서 Ollama가 실행 중인지, "
                   "`ollama list`에 %s 모델이 있는지 확인해 주세요." % (OLLAMA_URL, MODEL))
            self.wfile.write(msg.encode("utf-8"))
            return
        except (BrokenPipeError, ConnectionResetError):
            pass  # 브라우저가 중간에 끊은 경우 — 받은 만큼만 기록
        reply = "".join(full_reply)
        if reply:
            append_history("assistant", reply, agent["id"])
            save_output(agent["id"], user_msg, reply)  # 완료 시 결과물 자동 저장


def main():
    os.makedirs(MEMORY_DIR, exist_ok=True)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print("⚠️ 이미 에이전트가 실행 중입니다 (포트 %d 사용 중)." % PORT)
        print("   브라우저에서 http://localhost:%d 를 열어 그대로 사용하세요." % PORT)
        webbrowser.open("http://localhost:%d" % PORT)
        return
    print("🏢 크리에이터 에이전트 사무실 시작!")
    print("   직원: " + ", ".join("%s %s" % (a["emoji"], a["name"]) for a in AGENTS))
    print("   모델: %s  (Ollama: %s)" % (MODEL, OLLAMA_URL))
    print("   브라우저에서 열기 → http://localhost:%d" % PORT)
    print("   종료: Ctrl+C (이 창을 닫으면 사무실도 닫힙니다)")
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:%d" % PORT)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n사무실 문을 닫습니다. 👋")


if __name__ == "__main__":
    main()
