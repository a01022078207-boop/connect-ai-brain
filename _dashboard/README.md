# 🛰️ 에이전트 오케스트레이션 대시보드

CEO 오케스트레이션 아래 에이전트들이 무엇을 하는지 **한 화면**으로 보는 대시보드입니다.
앱·인터넷·서버 없이, 브라우저로 파일만 열면 됩니다.

## 보는 법
1. `_dashboard/dashboard.html` 을 더블클릭 → 브라우저로 열림. 끝.

## 무엇이 보이나요
- **회사 헤더** — 이름·소개, 완료 작업 수, 활성 에이전트/세션 통계
- **오케스트레이션 흐름** — 🧭 CEO(+비서) → 워커 에이전트들 (NEW 표시)
- **에이전트 카드** — 이모지·역할, 활성 여부, 자율도 레벨(L0~L3), 모델, 이번 주 목표,
  최근 활동, 참여 세션 수 / 상단 검색창으로 필터
- **최근 세션 타임라인** — 각 세션의 명령·요약, 참여 에이전트(이모지), 리포트 여부

## 갱신하는 법
데이터(에이전트·세션)가 바뀌면 다시 구워줍니다:

```bash
python3 _dashboard/build_dashboard.py
```

`build_dashboard.py` 가 `_company/` 를 스캔해 `dashboard.html` 안에 데이터를 직접
새겨 넣습니다. 그래서 서버 없이도 열리고, 다른 PC로 복사해도 그대로 보입니다.

## 데이터 출처
- `company_state.json`, `_company/_shared/{identity,goals,_system,active,agent_models}`
- `_company/_agents/<id>/{goal,tools,memory}.md`
- `_company/sessions/<ts>/{_brief,<agent>,_report}.md`

> 외부 의존성 0개 (순수 Python 표준 라이브러리 + 단일 HTML). 인터넷 연결 불필요.
