# 🎬 나만의 크리에이터 에이전트

로컬 Ollama(`gemma4:12b`)를 두뇌로 쓰는 **1인 콘텐츠 크리에이터 파트너**.
설치할 라이브러리 없음 — Python과 Ollama만 있으면 됩니다.

## 실행 방법 (가장 쉬운 길)

**준비물 (처음 한 번):**
1. [Python 설치](https://www.python.org/downloads/) — 설치 화면에서 **"Add Python to PATH" 체크 필수**
2. [Ollama 설치](https://ollama.com/download) 후 모델 받기: `ollama pull gemma4:12b`

**실행:**
- 이 폴더의 **`start.bat` 더블클릭** (Windows) → 브라우저가 자동으로 열립니다
- macOS/Linux: `sh start.sh`

검은 터미널 창이 함께 떠 있는 동안만 에이전트가 동작합니다. (창을 닫으면 종료)

**코드 받기 (git 없이):**
GitHub 저장소 페이지 → 초록색 `Code` 버튼 → `Download ZIP` → 압축 풀기 → `start.bat` 더블클릭.

## 어디서든 사용하기 (공개 링크)

폰이나 외부에서도 접속하고 싶다면:

1. `config.json`을 메모장으로 열어 비밀번호 설정: `"password": "내비밀번호123"`
2. **`share.bat` 더블클릭** — 에이전트 실행 + 무료 Cloudflare 터널 생성
3. 창에 나오는 `https://xxxx.trycloudflare.com` 주소를 폰에서 열기
4. 첫 접속 시 비밀번호 입력 (한 번만)

> ⚠️ PC가 켜져 있고 share.bat 창이 열려 있는 동안만 접속 가능합니다.
> 링크 주소는 실행할 때마다 바뀝니다 (무료 터널의 특성).
> macOS/Linux: `brew install cloudflared` 후 `cloudflared tunnel --url http://localhost:8800`

## 기능

| 기능 | 설명 |
|---|---|
| 💬 채팅 | 스트리밍 응답 웹 채팅 UI. 대화는 자동 저장되어 재시작해도 이어짐 |
| 🧠 장기 메모리 | `기억해: 내 채널은 OOO` 라고 보내면 `memory/memories.md`에 영구 저장 |
| 👤 프로필 | `memory/profile.md`에 나/채널 정보 — 매 대화에 자동 반영 |
| 🗑 새 대화 | 기록은 지워지지 않고 `memory/archive/`로 보관 |

## 구조

```
agent.py            ← 서버 전체 (표준 라이브러리만 사용)
config.json         ← 모델·포트 설정
static/index.html   ← 채팅 UI
memory/
  profile.md        ← 내 정보 (직접 편집)
  memories.md       ← 장기 메모리 (자동 누적 + 직접 편집)
  history.jsonl     ← 대화 기록 (자동)
  archive/          ← 초기화한 옛 대화 보관
```

## 설정 바꾸기 (`config.json`)

- `model` — 다른 Ollama 모델로 교체 (예: `"gemma4:e4b"` — 가볍고 빠름)
- `port` — 웹 UI 포트 (기본 8800)
- `context_turns` — 매 요청에 포함할 최근 대화 수 (기본 30)

## 메모리를 다른 PC와 동기화하려면

이 저장소를 git으로 push/pull 하면 `memory/`가 함께 옮겨집니다.

```bash
git add memory && git commit -m "메모리 동기화" && git push
```
