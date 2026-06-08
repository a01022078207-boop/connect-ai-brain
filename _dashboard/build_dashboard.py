#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛰️  Connect AI — 에이전트 오케스트레이션 대시보드 생성기

저장소(_company/...)를 스캔해서, 인터넷·서버 없이 브라우저로 바로 열리는
단일 파일 대시보드(_dashboard/dashboard.html)를 만듭니다.

쓰는 법:
    python3 _dashboard/build_dashboard.py
그다음 _dashboard/dashboard.html 을 더블클릭해서 브라우저로 열면 됩니다.
데이터(에이전트·세션)가 바뀌면 이 스크립트만 다시 실행하세요.
"""

import json
import re
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANY = ROOT / "_company"
AGENTS = COMPANY / "_agents"
SHARED = COMPANY / "_shared"
SESSIONS = COMPANY / "sessions"
OUT = Path(__file__).resolve().parent / "dashboard.html"


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def load_json(p: Path, default):
    try:
        return json.loads(read(p))
    except Exception:
        return default


def section(md: str, header: str) -> list[str]:
    """'## header' 아래의 불릿(- ...)들을 다음 '## '까지 모아서 반환."""
    lines = md.splitlines()
    out, grab = [], False
    for ln in lines:
        if ln.strip().startswith("## "):
            grab = header in ln
            continue
        if grab:
            s = ln.strip()
            if s.startswith("- "):
                out.append(s[2:].strip())
    return out


def first_heading(md: str) -> str:
    for ln in md.splitlines():
        if ln.startswith("# "):
            return ln[2:].split("페르소나")[0].split("—")[0].strip()
    return ""


# _system.md 의 에이전트 명단 한 줄에서 이모지/영문롤/설명 추출
SYS_LINE = re.compile(r"^- (\S+) \*\*(.+?)\*\*\s*\((.+?)\):\s*(.+)$")


def parse_system_roster() -> dict:
    roster = {}
    for ln in read(SHARED / "_system.md").splitlines():
        m = SYS_LINE.match(ln.strip())
        if m:
            emoji, name, role, desc = m.groups()
            roster[name.strip().lower()] = {
                "emoji": emoji,
                "name": name.strip(),
                "role": role.strip(),
                "desc": desc.strip(),
            }
    return roster


AUTONOMY_LABELS = {
    0: ("Off", "채팅만"),
    1: ("Read-only", "읽기·분석·보고만"),
    2: ("Draft", "초안→승인 후 실행"),
    3: ("Auto", "화이트리스트 내 자동"),
}


def parse_autonomy(md: str) -> int:
    m = re.search(r"AUTONOMY_LEVEL:\s*([0-3])", md)
    return int(m.group(1)) if m else 2


def build():
    state = load_json(ROOT / "company_state.json", {})
    active = load_json(SHARED / "active.json", {})
    models = load_json(SHARED / "agent_models.json", {})
    roster = parse_system_roster()

    # 회사 정체성
    ident_md = read(SHARED / "identity.md")

    def ident(field):
        m = re.search(r"\*\*" + re.escape(field) + r":\*\*\s*(.+)", ident_md)
        return m.group(1).strip() if m else ""

    company = {
        "name": ident("회사 이름") or "내 1인 기업",
        "tagline": ident("한 줄 소개"),
        "target": ident("타깃 청중"),
        "tone": ident("브랜드 톤"),
        "tasksCompleted": state.get("tasksCompleted", 0),
        "knowledgeInjected": state.get("knowledgeInjected", 0),
        "foundedAt": state.get("foundedAt", ""),
    }
    company["goalsYear"] = section(read(SHARED / "goals.md"), "올해 핵심 목표")
    company["goalsMonth"] = section(read(SHARED / "goals.md"), "1개월")

    # 세션별 에이전트 참여 집계
    agent_session_count = {}
    sessions = []
    if SESSIONS.exists():
        for sdir in sorted(SESSIONS.iterdir(), reverse=True):
            if not sdir.is_dir():
                continue
            files = {f.stem: f for f in sdir.glob("*.md")}
            participants = sorted(
                k for k in files if not k.startswith("_")
            )
            for a in participants:
                agent_session_count[a] = agent_session_count.get(a, 0) + 1
            brief = read(files["_brief"]) if "_brief" in files else ""
            cmd = re.search(r"\*\*원 명령:\*\*\s*(.+)", brief)
            summary = section(brief, "요약")
            sessions.append({
                "ts": sdir.name,
                "command": cmd.group(1).strip() if cmd else "",
                "summary": summary[0] if summary else "",
                "participants": participants,
                "hasReport": "_report" in files,
            })

    # 에이전트 카드
    agents = []
    role_order = {  # 오케스트레이션 흐름 순서(있으면 우선 정렬)
        "ceo": 0, "secretary": 1, "researcher": 2, "marketing": 3,
        "content": 4, "writer": 5, "designer": 6, "critic": 7,
        "business": 8, "youtube": 9, "instagram": 10, "editor": 11,
        "developer": 12,
    }
    if AGENTS.exists():
        for adir in sorted(AGENTS.iterdir()):
            if not adir.is_dir():
                continue
            aid = adir.name
            goal_md = read(adir / "goal.md")
            mem_md = read(adir / "memory.md")
            r = roster.get(aid, {})
            persona = first_heading(goal_md)
            # 페르소나에서 이모지 떼어내기
            persona_clean = re.sub(r"^[^\w가-힣]+", "", persona).replace("에이전트", "").strip()
            recent = [l.strip()[2:] for l in mem_md.splitlines()
                      if l.strip().startswith("- [")][-4:]
            recent.reverse()
            auto = parse_autonomy(read(adir / "tools.md"))
            agents.append({
                "id": aid,
                "emoji": r.get("emoji", "🤖"),
                "name": r.get("name", aid.capitalize()),
                "persona": persona_clean,
                "role": r.get("role", ""),
                "desc": r.get("desc", ""),
                "active": aid == "ceo" or isinstance(active.get(aid), dict),
                "model": models.get(aid, "—"),
                "autonomy": auto,
                "autonomyLabel": AUTONOMY_LABELS[auto][0],
                "autonomyHint": AUTONOMY_LABELS[auto][1],
                "weekGoals": section(goal_md, "이번 주 목표"),
                "recent": recent,
                "sessions": agent_session_count.get(aid, 0),
                "isNew": aid in ("marketing", "critic", "content"),
                "order": role_order.get(aid, 99),
            })
    agents.sort(key=lambda a: (not a["active"], a["order"], a["id"]))

    data = {
        "company": company,
        "agents": agents,
        "sessions": sessions[:30],
        "sessionTotal": len(sessions),
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    html = HTML_TEMPLATE.replace(
        "/*__DATA__*/null",
        json.dumps(data, ensure_ascii=False)
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"✅ 대시보드 생성 완료 → {OUT}")
    print(f"   에이전트 {len(agents)}명 · 세션 {len(sessions)}개")
    print(f"   브라우저로 열기: file://{OUT}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🛰️ 에이전트 오케스트레이션 대시보드</title>
<style>
  :root{
    --bg:#0b0e14; --panel:#141925; --panel2:#1b2230; --line:#262e3d;
    --txt:#e6e9ef; --dim:#8b93a7; --accent:#6ea8fe; --green:#46d39a;
    --amber:#f5c451; --red:#f47174; --new:#b08cff;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
    line-height:1.55;font-size:14px}
  a{color:var(--accent)}
  .wrap{max-width:1180px;margin:0 auto;padding:28px 20px 80px}
  header.hero{display:flex;flex-wrap:wrap;align-items:flex-end;gap:16px;
    border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:24px}
  .hero h1{font-size:22px;margin:0 0 4px}
  .hero .tag{color:var(--dim);max-width:680px;font-size:13px}
  .hero .stats{display:flex;gap:10px;margin-left:auto;flex-wrap:wrap}
  .stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;
    padding:10px 14px;min-width:92px;text-align:center}
  .stat b{display:block;font-size:20px}
  .stat span{color:var(--dim);font-size:11px}
  h2.sec{font-size:13px;letter-spacing:.04em;color:var(--dim);
    text-transform:uppercase;margin:34px 0 14px}
  /* 오케스트레이션 흐름 */
  .flow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;
    background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
  .node{background:var(--panel2);border:1px solid var(--line);border-radius:10px;
    padding:8px 12px;font-size:13px;white-space:nowrap}
  .node.ceo{border-color:var(--accent);color:#cfe0ff}
  .node.new{border-color:var(--new)}
  .arrow{color:var(--dim)}
  /* 카드 그리드 */
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
    padding:16px;display:flex;flex-direction:column;gap:10px;position:relative}
  .card.off{opacity:.5}
  .card .top{display:flex;align-items:flex-start;gap:10px}
  .card .emoji{font-size:26px;line-height:1}
  .card .who{flex:1;min-width:0}
  .card .who b{font-size:15px}
  .card .who .persona{color:var(--dim);font-size:12px}
  .card .role{color:var(--dim);font-size:12px;margin-top:2px}
  .badges{display:flex;gap:6px;flex-wrap:wrap}
  .b{font-size:11px;padding:2px 8px;border-radius:20px;border:1px solid var(--line);color:var(--dim)}
  .b.on{color:var(--green);border-color:#1e5a44;background:#0f2a20}
  .b.new{color:var(--new);border-color:#4b3a78;background:#241a3a}
  .b.a0{color:var(--dim)} .b.a1{color:var(--accent);border-color:#2c4a78}
  .b.a2{color:var(--amber);border-color:#5a4a1e} .b.a3{color:var(--green);border-color:#1e5a44}
  .block{background:var(--panel2);border-radius:10px;padding:10px 12px}
  .block h4{margin:0 0 6px;font-size:11px;color:var(--dim);letter-spacing:.03em}
  .block ul{margin:0;padding-left:16px}
  .block li{margin:3px 0;font-size:12.5px}
  .block .empty{color:var(--dim);font-size:12px}
  .card .foot{margin-top:auto;display:flex;justify-content:space-between;
    color:var(--dim);font-size:11px;border-top:1px solid var(--line);padding-top:8px}
  /* 세션 타임라인 */
  .sessions{display:flex;flex-direction:column;gap:8px}
  .srow{display:flex;gap:12px;background:var(--panel);border:1px solid var(--line);
    border-radius:10px;padding:10px 14px;align-items:center}
  .srow .ts{font-variant-numeric:tabular-nums;color:var(--dim);font-size:12px;
    min-width:130px}
  .srow .cmd{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .srow .who{display:flex;gap:4px}
  .chip{font-size:14px}
  .srow .rep{font-size:11px;color:var(--green)}
  .filter{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
  .filter input{background:var(--panel);border:1px solid var(--line);color:var(--txt);
    border-radius:8px;padding:8px 12px;flex:1;min-width:200px;font-size:13px}
  .foot-note{color:var(--dim);font-size:12px;margin-top:40px;text-align:center}
  @media(max-width:640px){.srow .ts{min-width:auto}.hero .stats{width:100%;margin-left:0}}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div>
      <h1 id="coName"></h1>
      <div class="tag" id="coTag"></div>
    </div>
    <div class="stats" id="coStats"></div>
  </header>

  <h2 class="sec">🔀 오케스트레이션 흐름</h2>
  <div class="flow" id="flow"></div>

  <h2 class="sec">🤖 에이전트 (<span id="agCount"></span>)</h2>
  <div class="filter">
    <input id="q" placeholder="에이전트 이름·역할 검색…">
  </div>
  <div class="grid" id="agents"></div>

  <h2 class="sec">🗂️ 최근 세션 (총 <span id="sesTotal"></span>개)</h2>
  <div class="sessions" id="sessions"></div>

  <div class="foot-note" id="genAt"></div>
</div>

<script>
const DATA = /*__DATA__*/null;
const esc = s => (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const emojiById = {};
DATA.agents.forEach(a=>emojiById[a.id]=a.emoji);

// 회사 헤더
const c = DATA.company;
coName.textContent = "🏢 " + c.name;
coTag.textContent = c.tagline || "";
const stats = [
  ["완료 작업", c.tasksCompleted],
  ["지식 주입", c.knowledgeInjected],
  ["에이전트", DATA.agents.filter(a=>a.active).length],
  ["세션", DATA.sessionTotal],
];
coStats.innerHTML = stats.map(([k,v])=>`<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");

// 오케스트레이션 흐름: CEO/비서 → 워커들
const ceo = DATA.agents.filter(a=>["ceo","secretary"].includes(a.id));
const workers = DATA.agents.filter(a=>a.active && !["ceo","secretary"].includes(a.id));
let flowHtml = ceo.map(a=>`<div class="node ceo">${a.emoji} ${esc(a.name)}</div>`).join('<span class="arrow">+</span>');
flowHtml += '<span class="arrow">→</span>';
flowHtml += workers.map(a=>`<div class="node ${a.isNew?'new':''}">${a.emoji} ${esc(a.name)}</div>`).join('<span class="arrow">·</span>');
flow.innerHTML = flowHtml || '<span class="arrow">활성 에이전트 없음</span>';

// 에이전트 카드
agCount.textContent = DATA.agents.length;
function renderAgents(filter=""){
  const f = filter.trim().toLowerCase();
  const list = DATA.agents.filter(a=>!f ||
    (a.name+a.persona+a.role+a.desc+a.id).toLowerCase().includes(f));
  agents.innerHTML = list.map(a=>{
    const wk = a.weekGoals.length
      ? `<ul>${a.weekGoals.slice(0,3).map(g=>`<li>${esc(g)}</li>`).join("")}</ul>`
      : `<div class="empty">설정된 주간 목표 없음 — 회사 공동 목표를 따름</div>`;
    const rc = a.recent.length
      ? `<ul>${a.recent.map(r=>`<li>${esc(r)}</li>`).join("")}</ul>`
      : `<div class="empty">아직 활동 기록 없음</div>`;
    return `<div class="card ${a.active?'':'off'}">
      <div class="top">
        <div class="emoji">${a.emoji}</div>
        <div class="who">
          <b>${esc(a.name)}</b> <span class="persona">${esc(a.persona)}</span>
          <div class="role">${esc(a.role||a.desc)}</div>
        </div>
      </div>
      <div class="badges">
        <span class="b ${a.active?'on':''}">${a.active?'● 활성':'○ 대기'}</span>
        <span class="b a${a.autonomy}">⚙ L${a.autonomy} ${a.autonomyLabel}</span>
        ${a.isNew?'<span class="b new">NEW</span>':''}
        <span class="b">🧠 ${esc(a.model)}</span>
      </div>
      <div class="block"><h4>🎯 이번 주 목표</h4>${wk}</div>
      <div class="block"><h4>🕒 최근 활동</h4>${rc}</div>
      <div class="foot"><span>id: ${a.id}</span><span>참여 세션 ${a.sessions}회</span></div>
    </div>`;
  }).join("");
}
renderAgents();
q.addEventListener("input", e=>renderAgents(e.target.value));

// 세션
sesTotal.textContent = DATA.sessionTotal;
sessions.innerHTML = DATA.sessions.map(s=>{
  const chips = s.participants.map(p=>`<span class="chip" title="${p}">${emojiById[p]||"📄"}</span>`).join("");
  const label = s.summary || s.command || "(요약 없음)";
  return `<div class="srow">
    <div class="ts">${s.ts}</div>
    <div class="cmd" title="${esc(s.command)}">${esc(label)}</div>
    <div class="who">${chips}</div>
    ${s.hasReport?'<span class="rep">📝 리포트</span>':''}
  </div>`;
}).join("") || '<div class="empty">세션 없음</div>';

genAt.textContent = "생성 시각: " + DATA.generatedAt + " · python3 _dashboard/build_dashboard.py 로 갱신";
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
