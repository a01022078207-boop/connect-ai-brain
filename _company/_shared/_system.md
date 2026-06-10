# 🧬 1인 에이전트 OS — 자가 매뉴얼

## 이 폴더는 무엇인가요?
당신의 **1인 에이전트**의 두뇌입니다. 단 한 명의 AI 에이전트(🎬 크리에이터)가 여기서 일합니다.

## 폴더 구조
- `_shared/` — 에이전트가 매번 읽는 공동 메모리
  - `identity.md` — 정체성 (이름, 톤, 가치)
  - `goals.md` — 목표
  - `decisions.md` — 의사결정 로그 (자가학습이 자동 누적)
  - `_system.md` — 이 파일
- `_agents/<id>/` — 에이전트 개인 공간
  - `memory.md` — 자가학습 (자동, append-only)
  - `prompt.md` — 페르소나 디테일 (사용자가 편집)
  - `tools.md` — 도구·자율도 정의
  - `skills/` — 검증된 재사용 패턴
  - `config.md` — API 키·시크릿 (`.gitignore`로 보호)
- `sessions/<ts>/` — 세션별 산출물 (자동)
- `_cache/` — API 응답 캐시 (sync 제외)

## 메모리 위계 (충돌 시 우선순위)
1. `decisions.md` — 가장 강한 신뢰
2. `identity.md`
3. `goals.md`
4. 개인 메모리 (`_agents/creator/memory.md`)
5. 스킬 (`_agents/creator/skills/`)

## 다른 PC로 옮길 때
1. 새 PC에 Connect AI 설치
2. 👔 모드 ON → "📥 다른 PC에서 가져오기" 선택
3. GitHub URL 입력 → 자동 clone
4. 끝.

## 동기화 정책
- `_shared/`, `_agents/*/memory.md`, `_agents/*/prompt.md`, `sessions/` → git sync ✅
- `_agents/*/config.md`, `_cache/` → git sync ❌ (시크릿·캐시)

## 에이전트
- 🎬 **Creator** (콘텐츠 크리에이터): 콘텐츠 기획·대본·카피·기획서 작성, 트렌드 반영, 썸네일/제목/후크 아이디어, 일정·아이디어 정리까지 — 1인 크리에이터의 모든 작업을 돕는 단일 파트너 에이전트.
