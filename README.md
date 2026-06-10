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
| 🏢 사무실 뷰 | 4명의 역할 에이전트(기획자·대본가·편집장·마케터)가 한 화면에. 일하는 담당자가 실시간 애니메이션으로 표시 |
| 💬 지시창 | 담당자를 클릭해 선택하고 지시 → 해당 역할 프롬프트로 응답 |
| 📚 Skill list | 각 에이전트가 가진 스킬 목록 |
| 📦 결과물 창 | 작업이 끝나면 결과물이 카드로 자동 저장 (클릭 시 전체 보기·복사) |
| 🧩 업무 분담 | 각 에이전트의 역할 설명 |
| 🧠 장기 메모리 | `기억해: ___` 명령으로 `memory/memories.md`에 영구 저장 |
| 👤 프로필 | `memory/profile.md` — 모든 에이전트가 매 작업에 참고 |

## 에이전트 편집

`agents.json`을 메모장으로 열어 에이전트를 추가·수정할 수 있습니다 (이름, 이모지, 역할, 스킬, 역할 프롬프트).

## 구조

```
agent.py            ← 서버 전체 (표준 라이브러리만 사용)
agents.json         ← 에이전트 명단 (역할·스킬·프롬프트)
config.json         ← 모델·포트·비밀번호 설정
static/index.html   ← 4분할 사무실 대시보드
memory/
  profile.md        ← 내 정보 (직접 편집)
  memories.md       ← 장기 메모리 (자동 누적 + 직접 편집)
  history.jsonl     ← 대화 기록 (자동)
  outputs.jsonl     ← 완료된 결과물 (자동)
  archive/          ← 초기화한 옛 기록 보관
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
