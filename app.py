# -*- coding: utf-8 -*-
"""
NEW START 운동 인증 대시보드 — 외부 공유용 (읽기 전용)
data.json 파일에서 크롤링 데이터를 읽어 표시한다.
Hugging Face Spaces 또는 Streamlit Cloud에 배포 가능.
"""
import json
import os
import re

import plotly.graph_objects as go
import requests
import streamlit as st
from datetime import datetime, timedelta
from collections import OrderedDict

st.set_page_config(
    page_title="NEW START 운동 인증 대시보드",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; background: #ffffff; color: #000000; }
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1600px; }
    h1 { color: #000000 !important; font-weight: 700 !important; border: none !important; font-size: 1.75rem !important; margin-bottom: 0 !important; }
    .main p { color: #333333; }
    .center-data { width: 100%; max-width: 1600px; margin-left: auto; margin-right: auto; }
    .week-table-wrap { background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin: 0.5rem 0 1rem 0; }
    .week-table-wrap table { background: #ffffff; }
    .top3-badge { display: inline-block; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 0.9rem; margin-left: 8px; }
    .top3-1 { background: #D4AF37; color: #FFFFFF; }
    .top3-2 { background: #E5E4E2; color: #0D0D0D; }
    .top3-3 { background: #B87333; color: #FFFFFF; }
    .update-badge { display: inline-block; background: #f0f0f0; border: 1px solid #ddd; border-radius: 6px; padding: 4px 12px; font-size: 0.85rem; color: #555; margin-top: 4px; margin-bottom: 18px; }
    .kpi-card { border: 1px solid #e6e8ef; border-radius: 14px; padding: 16px 18px; background: #ffffff; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08); min-height: 104px; }
    .kpi-title { font-size: 0.95rem; color: #5b6475; font-weight: 600; margin-bottom: 10px; }
    .kpi-value { font-size: 2rem; font-weight: 800; line-height: 1; color: #111827; }
    .kpi-unit { font-size: 1rem; font-weight: 700; margin-left: 2px; color: #4b5563; }
    .top3-card { border: 1px solid #e6e8ef; border-radius: 14px; padding: 14px 18px; background: #ffffff; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08); width: 100%; box-sizing: border-box; overflow: hidden; }
    .top3-item { padding: 10px 0; border-bottom: 1px solid #eceff4; }
    .top3-item:last-child { border-bottom: none; }
    .dashboard-top-gap { margin-top: 8px; margin-bottom: 12px; }
    .graph-head { margin-top: 18px; margin-bottom: 0; }
    .graph-head h3 { margin: 0; }
    .graph-head p { margin: 0; font-size: 0.92rem; color: #667085; }
    .arrow-wrap { margin-top: 14px; }
    .arrow-wrap [data-testid="stButton"] > button {
        background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important;
        min-height: 72px !important; width: 72px !important; height: 72px !important; color: #0D0D0D !important; line-height: 1 !important;
    }
    .arrow-wrap [data-testid="stButton"] > button p,
    .arrow-wrap [data-testid="stButton"] > button span,
    .arrow-wrap [data-testid="stButton"] > button div { margin: 0 !important; font-size: 72px !important; line-height: 1 !important; font-weight: 700 !important; }
    .arrow-wrap [data-testid="stButton"] > button:disabled { color: #808080 !important; opacity: 1 !important; cursor: default !important; }
    .arrow-wrap [data-testid="stButton"] > button:disabled p,
    .arrow-wrap [data-testid="stButton"] > button:disabled span,
    .arrow-wrap [data-testid="stButton"] > button:disabled div { color: #808080 !important; }
    .avg-bar-title-main { font-size: 1.35rem; font-weight: 700; color: #000; margin-bottom: 0.35rem; }
    .avg-bar-title-sub { font-size: 1rem; color: #000; margin-bottom: 0.25rem; line-height: 1.4; }
    .avg-bar-title-note { font-size: 0.8rem; color: #888888; line-height: 1.35; margin-bottom: 0.75rem; }
    .avg-bar-chart-section-marker { display: none !important; }
    [data-testid="stMarkdown"]:has(.avg-bar-chart-section-marker) + div [data-testid="stPlotlyChart"] iframe {
        border-radius: 12px !important;
        border: 1px solid #e8e8e8 !important;
        box-sizing: border-box;
    }
    @keyframes plotly-today-pulse {
        0%, 100% { opacity: 1; stroke-width: 3px; }
        50% { opacity: 0.28; stroke-width: 10px; }
    }
    .js-plotly-plot .scatterlayer > g:nth-child(3) path {
        animation: plotly-today-pulse 1.35s ease-in-out infinite;
    }
    /* 탭: 선택 #000000 Bold 700, 비선택 #646464 Bold 700, 선택 탭 밑줄 4px #000000만 (초록/빨강 제거) */
    [data-testid="stTabs"] [role="tab"], [data-testid="stTabs"] button { font-weight: 700 !important; color: #646464 !important; border-bottom: none !important; }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"], [data-testid="stTabs"] button[aria-selected="true"] { color: #000000 !important; font-weight: 700 !important; border-bottom: 4px solid #000000 !important; border-bottom-color: #000000 !important; box-shadow: none !important; background: transparent !important; }
    [data-testid="stTabs"] [role="tabpanel"] { border: none !important; }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"] { background: transparent !important; border: none !important; border-bottom: none !important; }
    @media (min-width: 797px) and (max-width: 1920px) {
        .main .block-container { max-width: 1600px; padding-left: 32px; padding-right: 32px; }
    }
    @media (min-width: 360px) and (max-width: 796px) {
        .main .block-container { max-width: 100%; padding-left: 14px; padding-right: 14px; }
        h1 { font-size: 1.55rem !important; }
        .kpi-value { font-size: 1.7rem; }
        .dashboard-top-gap { margin-top: 4px; margin-bottom: 10px; }
        .graph-head { margin-top: 12px; }
    }
</style>
""", unsafe_allow_html=True)

# ── 데이터 상수 ──
NAME_ID_LIST = [
    ("최수겸", "Sue"),
    ("최수림", "프수"),
    ("강민찬", "민찬이"),
    ("곽민제", "곽카몰리"),
    ("김보람", "김봚"),
    ("김예덕", "예덕"),
    ("박건우", "베건이"),
    ("박성훈", "박성훈"),
    ("박예서", "바게서"),
    ("서민혁", "중화동고라니"),
    ("서지우", "쥬"),
    ("서희진", "희진"),
    ("심윤교", "윤교"),
    ("안수빈", "수비니"),
    ("유영현", "TIMYOU"),
    ("이건희", "R거U니N"),
    ("이찬우", "콜드카우"),
]
ID_TO_NAME = {tid: name for name, tid in NAME_ID_LIST}
WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
_DAY_LONG_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
ROW_HIGHLIGHT_UNDER_3 = "#FFB3B3"
CHECK_BLUE = "#4E6FFF"

# archive/table_rows 등에 남아있던 과거 cid를 현재 cid로 정규화
CID_LEGACY_TO_CURRENT = {
    "김보람아님": "민찬이",
}


def _normalize_row_label(row_label):
    if not isinstance(row_label, str):
        return row_label
    out = row_label
    for old_cid, new_cid in CID_LEGACY_TO_CURRENT.items():
        out = out.replace(f"({old_cid})", f"({new_cid})")
    return out

_TITLE_ALIASES = {}
for _n, _c in NAME_ID_LIST:
    _TITLE_ALIASES[_c.lower()] = _c
    _TITLE_ALIASES[_n] = _c
    if len(_n) >= 3:
        _TITLE_ALIASES[_n[1:]] = _c
_TITLE_ALIASES.update({
    "콜드가우": "콜드카우",
    "민찬": "민찬이",
    "민찬이": "민찬이",
    # 과거 데이터(김보람아님) 호환
    "김보람아님": "민찬이",
    "베이비러너": "Sue",
    "오수완": "프수",
    "수완": "프수",
    "timyou": "TIMYOU",
})


def _parse_naver_date(date_str: str):
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    if re.match(r"^\d{1,2}:\d{2}$", date_str):
        return datetime.now()
    for fmt in ("%Y.%m.%d", "%Y.%m.%d.", "%Y-%m-%d", "%m.%d", "%m.%d."):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt
        except ValueError:
            continue
    m = re.match(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})", date_str)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _author_from_row(r):
    author = (r.get("작성자") or "").strip()
    # 작성자-아이디 매칭 시 대소문자 무시 (예: TimYou → TIMYOU)
    if author:
        for _, cid in NAME_ID_LIST:
            if cid and (author == cid or author.strip().upper() == cid.strip().upper()):
                return cid
        # 작성자 필드 자체가 과거 cid(예: 김보람아님)로 들어오는 경우 호환
        author_lower = author.lower()
        if author_lower in _TITLE_ALIASES:
            return _TITLE_ALIASES[author_lower]
        if author in _TITLE_ALIASES:
            return _TITLE_ALIASES[author]
    title = (r.get("제목") or "").strip()
    title_lower = title.lower()
    best_match = None
    best_pos = len(title)
    for alias, cid in _TITLE_ALIASES.items():
        for sep in [" ", "/", "\u3000"]:
            pattern = alias + sep
            idx = title_lower.find(pattern.lower())
            if idx != -1 and idx < best_pos:
                best_match = cid
                best_pos = idx
        if title_lower == alias.lower():
            return cid
    if best_match:
        return best_match
    return author


def _is_bible_copy(row):
    title = (row.get("제목") or "").strip()
    return "필사" in title


def _table_rows_for_week_range(rows, week_sun, week_sat):
    """지난주·이번주 공통: rows 전체에서 해당 일~토만 집계 (data.json의 옛 아카이브 스냅샷 대신 사용)."""
    week_dates_w = [week_sun + timedelta(days=i) for i in range(7)]
    posted = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        author = _author_from_row(r)
        date_str = (r.get("날짜") or "").strip()
        dt = _parse_naver_date(date_str) if date_str else None
        if dt is None:
            continue
        d = dt.date()
        if d < week_sun or d > week_dates_w[-1]:
            continue
        is_bible = _is_bible_copy(r)
        for name, cid in NAME_ID_LIST:
            if not cid:
                continue
            if author == cid or (author and author.strip().upper() == cid.strip().upper()):
                key = (name, d)
                if key not in posted:
                    posted[key] = {"exercise": 0, "bible": False}
                if is_bible:
                    posted[key]["bible"] = True
                else:
                    posted[key]["exercise"] = 1
                break
    table_rows = []
    for name, cid in NAME_ID_LIST:
        # legacy cid(예: 김보람아님) 그대로 남아있는 배포본이 있어도
        # 항상 현재 cid(예: 민찬이)로 표기되게 보정한다.
        row_label = _normalize_row_label(f"{name} ({cid})")
        count = 0
        day_cells = []
        for d in week_dates_w:
            info = posted.get((name, d))
            if not info:
                day_cells.append(("", False, None))
                continue
            ex, bible = info.get("exercise", 0), info.get("bible", False)
            if bible:
                day_cells.append(("성경필사", True, "bible"))
                count += 1
            elif ex and ex > 0:
                day_cells.append(("✓", True, "exercise"))
                count += 1
            else:
                day_cells.append(("", False, None))
        table_rows.append((row_label, day_cells, count))
    return table_rows


def _deserialize_archive_table_rows(ser):
    """data.json archive 안의 table_rows 직렬화 형식 → (row_label, day_cells, count) 리스트."""
    out = []
    for row in ser or []:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        row_label, cells, count = row[0], row[1], row[2]
        row_label = _normalize_row_label(row_label)
        day_cells = [(v, bool(c), (t if t else None)) for v, c, t in cells]
        out.append((row_label, day_cells, count))
    return out


def _or_merge_cell_fe(a, b):
    va, ca, ta = a
    vb, cb, tb = b
    if not ca and not cb:
        return ("", False, None)
    if ca and not cb:
        return (va, ca, ta)
    if cb and not ca:
        return (vb, cb, tb)
    if ta == "bible" or tb == "bible":
        return ("성경필사", True, "bible")
    return (va or vb, True, ta or tb or "exercise")


def _merge_two_week_tables_fe(rows_a, rows_b):
    """두 주간 표를 이름·요일 칸 단위 OR (대칭)."""
    by_label = {}
    for lst in (rows_a or [], rows_b or []):
        for row_label, cells, _ in lst:
            row_label = _normalize_row_label(row_label)
            if row_label not in by_label:
                by_label[row_label] = [("", False, None)] * 7
            cur = by_label[row_label]
            for i in range(7):
                v, c, t = cells[i] if i < len(cells) else ("", False, None)
                cur[i] = _or_merge_cell_fe(cur[i], (v, c, t))
    out = []
    for name, cid in NAME_ID_LIST:
        row_label = _normalize_row_label(f"{name} ({cid})")
        cells = by_label.get(row_label, [("", False, None)] * 7)
        cnt = sum(1 for _, c, _ in cells if c)
        out.append((row_label, cells, cnt))
    return out


def _merge_live_and_snapshot_week(rows_live, snap_deserialized):
    """지난 주 탭: rows 집계 + 저장 스냅샷을 대칭 OR 병합(한쪽만 비어 있어도 다른 쪽 체크 유지)."""
    if not snap_deserialized:
        return rows_live
    return _merge_two_week_tables_fe(rows_live, snap_deserialized)


def _daily_cert_counts_for_week_readonly(rows, week_sun, week_sat):
    tr = _table_rows_for_week_range(rows, week_sun, week_sat)
    totals = [0] * 7
    for _rl, day_cells, _ in tr:
        for j in range(7):
            if j < len(day_cells):
                _v, checked, _t = day_cells[j]
                if checked:
                    totals[j] += 1
    return totals


def _fig_realtime_exercise_lines(rows, week_sun, today_d):
    prev_sun = week_sun - timedelta(days=7)
    prev_sat = prev_sun + timedelta(days=6)
    week_dates = [week_sun + timedelta(days=i) for i in range(7)]
    prev_dates = [prev_sun + timedelta(days=i) for i in range(7)]
    y_last = _daily_cert_counts_for_week_readonly(rows, prev_sun, prev_sat)
    y_this = _daily_cert_counts_for_week_readonly(rows, week_sun, week_sun + timedelta(days=6))
    x_cat = [WEEKDAY_NAMES[d.weekday()] for d in week_dates]
    hover_last = [f"{_DAY_LONG_KR[d.weekday()]} 운동인증: {y_last[i]}회" for i, d in enumerate(prev_dates)]
    y_this_plot = []
    hover_this = []
    for i, d in enumerate(week_dates):
        if d > today_d:
            y_this_plot.append(None)
            hover_this.append("")
        else:
            y_this_plot.append(y_this[i])
            hover_this.append(f"{_DAY_LONG_KR[d.weekday()]} 운동인증: {y_this[i]}회")
    all_y = list(y_last) + [v for v in y_this_plot if v is not None]
    y_max = max(all_y) if all_y else 0
    y_top = max(int(y_max * 1.15) + 1, 5)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_cat,
            y=y_last,
            mode="lines+markers",
            name="지난주",
            line=dict(color="#9e9e9e", width=2),
            marker=dict(size=10, color="#9e9e9e", line=dict(width=1, color="#ffffff")),
            hoverinfo="text",
            hovertext=hover_last,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_cat,
            y=y_this_plot,
            mode="lines+markers",
            name="이번주",
            line=dict(color="#2196F3", width=2),
            marker=dict(size=10, color="#2196F3", line=dict(width=1, color="#ffffff")),
            hoverinfo="text",
            hovertext=[h if h else None for h in hover_this],
            connectgaps=False,
        )
    )
    x_today = (today_d - week_sun).days
    if 0 <= x_today < 7 and week_dates[x_today] == today_d:
        yt = y_this_plot[x_today]
        if yt is not None:
            fig.add_trace(
                go.Scatter(
                    x=[x_cat[x_today]],
                    y=[yt],
                    mode="markers",
                    name="오늘",
                    showlegend=False,
                    marker=dict(
                        size=24,
                        color="rgba(33,150,243,0.22)",
                        line=dict(width=3, color="#1976D2"),
                    ),
                    hoverinfo="text",
                    hovertext=[hover_this[x_today]],
                    legendgroup="today_pulse",
                )
            )
    fig.update_layout(
        title=None,
        xaxis_title="요일",
        yaxis_title="인증 수 (명)",
        yaxis=dict(range=[0, y_top]),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        margin=dict(t=24, b=48),
        height=360,
        hovermode="closest",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _fig_avg_week_mean_bars(rows, week_sun, today_d):
    prev_sun = week_sun - timedelta(days=7)
    y_last = _daily_cert_counts_for_week_readonly(rows, prev_sun, prev_sun + timedelta(days=6))
    y_this = _daily_cert_counts_for_week_readonly(rows, week_sun, week_sun + timedelta(days=6))
    this_vals = []
    for i in range(7):
        d = week_sun + timedelta(days=i)
        if d <= today_d:
            this_vals.append(y_this[i])
    v_last = sum(y_last) / 7.0
    v_this = sum(this_vals) / len(this_vals) if this_vals else 0.0
    color_last = "#9E9E9E"
    if v_this < v_last:
        color_this = "#4E6FFF"
    elif v_this > v_last:
        color_this = "#FF5050"
    else:
        color_this = "#4E6FFF"
    bar_marker = dict(color=[color_last, color_this], line=dict(width=0), cornerradius=12)
    fig = go.Figure(
        data=[
            go.Bar(
                x=["지난주", "이번주"],
                y=[v_last, v_this],
                width=0.4,
                marker=bar_marker,
                text=[f"{v_last:.1f}", f"{v_this:.1f}"],
                textposition="outside",
                hovertemplate="%{x}<br>%{y:.1f}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        showlegend=False,
        height=360,
        margin=dict(t=16, b=48, l=24, r=24),
        yaxis=dict(range=[0, max(v_last, v_this, 1) * 1.28], showgrid=True, title=None),
        xaxis=dict(title=None),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


DATA_JSON_REMOTE_URL = os.environ.get(
    "DATA_JSON_REMOTE_URL",
    "https://raw.githubusercontent.com/01026093900s-max/dashboard-workout/main/data.json",
)


@st.cache_data(ttl=45, show_spinner="최신 데이터를 불러오는 중…")
def _fetch_remote_data_json(url: str):
    """Streamlit Cloud에서 배포 시점의 옛 data.json이 남는 문제를 피하기 위해
    GitHub raw에서 주기적으로 읽는다."""
    r = requests.get(url, timeout=25, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    return r.json()


def _parse_data_payload(payload):
    if isinstance(payload, list):
        return payload, "", []
    if isinstance(payload, dict):
        rows = payload.get("rows", [])
        updated = payload.get("last_updated", "")
        archive = payload.get("archive", [])
        return rows, updated, archive
    return [], "", []


def _load_data():
    """원격(GitHub raw) 우선, 실패 시 로컴 data.json. 로컴만 쓰려면 FORCE_LOCAL_DATA_JSON=1."""
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    force_local = os.environ.get("FORCE_LOCAL_DATA_JSON", "").lower() in ("1", "true", "yes")

    if not force_local:
        try:
            payload = _fetch_remote_data_json(DATA_JSON_REMOTE_URL)
            return _parse_data_payload(payload)
        except Exception:
            pass

    if not os.path.isfile(data_path):
        return [], "", []
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return [], "", []
    return _parse_data_payload(payload)


# ── 메인 ──
st.title("NEW START 운동 인증 대시보드")
st.caption("인증게시판 최근 7일 글을 수집합니다.")

cafe_rows, last_updated, archive = _load_data()

if last_updated:
    st.markdown(f'<span class="update-badge">마지막 업데이트: {last_updated}</span>', unsafe_allow_html=True)

if not cafe_rows:
    st.info("데이터가 아직 업로드되지 않았습니다. data.json 파일을 추가해 주세요.")
    st.stop()

today = datetime.now().date()
days_since_sun = (today.weekday() + 1) % 7
week_sun = today - timedelta(days=days_since_sun)
week_sat = week_sun + timedelta(days=6)
week_dates = [week_sun + timedelta(days=i) for i in range(7)]
period_str = f"이번 주 기간: {week_sun.month}월 {week_sun.day}일 ({WEEKDAY_NAMES[week_sun.weekday()]}) ~ {week_sat.month}월 {week_sat.day}일 ({WEEKDAY_NAMES[week_sat.weekday()]})"

# 표 데이터: rows 전체에서 이번 주만 집계 (지난 주 탭도 동일 로직으로 재계산)
table_rows = _table_rows_for_week_range(cafe_rows, week_sun, week_sat)
this_week_total_certs = sum(r[2] for r in table_rows)
under_three_count = sum(1 for r in table_rows if r[2] < 3)
if "graph_view_mode" not in st.session_state:
    st.session_state["graph_view_mode"] = "realtime"

st.markdown('<div class="dashboard-top-gap"></div>', unsafe_allow_html=True)
top_left, top_right = st.columns([1.75, 1.1], gap="medium")
with top_left:
    kpi_col1, kpi_col2 = st.columns(2, gap="medium")
    with kpi_col1:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-title">이번주 총 인증글 수 (누적)</div>'
            f'<div><span class="kpi-value">{this_week_total_certs}</span><span class="kpi-unit">회</span></div></div>',
            unsafe_allow_html=True,
        )
    with kpi_col2:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-title">3회 이상 인증하지 않은 인원 수</div>'
            f'<div><span class="kpi-value" style="color:#ef4444;">{under_three_count}</span><span class="kpi-unit">명</span></div></div>',
            unsafe_allow_html=True,
        )
    g_title_col, g_btn_col = st.columns([0.88, 0.12], gap="small")
    with g_title_col:
        if st.session_state["graph_view_mode"] == "realtime":
            st.markdown(
                '<div class="graph-head"><h3>실시간 운동 인증 그래프</h3><p>지난주와 이번주의 운동인증량을 실시간으로 비교합니다.</p></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="graph-head"><h3>지난주 평균 운동 인증 그래프</h3><p>지난주와 이번주의 평균 운동 인증량을 비교합니다.</p></div>',
                unsafe_allow_html=True,
            )
    with g_btn_col:
        st.markdown('<div class="arrow-wrap">', unsafe_allow_html=True)
        pcol, ncol = st.columns(2, gap="small")
        with pcol:
            if st.button("‹", key="graph_prev_public", disabled=st.session_state["graph_view_mode"] == "realtime"):
                st.session_state["graph_view_mode"] = "realtime"
                st.rerun()
        with ncol:
            if st.button("›", key="graph_next_public", disabled=st.session_state["graph_view_mode"] == "avg"):
                st.session_state["graph_view_mode"] = "avg"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    if st.session_state["graph_view_mode"] == "realtime":
        st.plotly_chart(
            _fig_realtime_exercise_lines(cafe_rows, week_sun, today),
            width="stretch",
            key="weekly_rt_line_public_top",
        )
    else:
        st.plotly_chart(
            _fig_avg_week_mean_bars(cafe_rows, week_sun, today),
            width="stretch",
            key="weekly_bar_mean_public_top",
        )

with top_right:
    top3_html = '<div class="top3-card"><h4 style="margin:0 0 8px 0;">이번주 Top3</h4>'
    sorted_by_count = sorted(table_rows, key=lambda x: -x[2])
    top3_list = [(label, cnt) for label, _, cnt in sorted_by_count if cnt > 0]
    _groups = OrderedDict()
    for label, cnt in top3_list:
        _groups.setdefault(cnt, []).append(label)
    ranked_groups = []
    rank = 0
    for cnt, labels in _groups.items():
        rank += 1
        if rank > 3:
            break
        ranked_groups.append((rank, labels, cnt))
    if ranked_groups:
        badge_class = ["top3-1", "top3-2", "top3-3"]
        for r, labels, cnt in ranked_groups:
            bc = badge_class[r - 1] if r <= 3 else "top3-3"
            bold_labels = []
            for lb in labels:
                if " (" in lb:
                    real_name, rest = lb.split(" (", 1)
                    bold_labels.append(f"<b>{real_name}</b> ({rest}")
                else:
                    bold_labels.append(f"<b>{lb}</b>")
            top3_html += (
                f'<div class="top3-item"><b>{r}등</b> {", ".join(bold_labels)} '
                f'<span class="top3-badge {bc}">{cnt}회</span></div>'
            )
    else:
        top3_html += '<div class="top3-item">이번 주 인증 데이터가 없습니다.</div>'
    top3_html += "</div>"
    st.markdown(top3_html, unsafe_allow_html=True)

# ── 탭: 이번주 운동 인증 현황 / 지난 운동 인증 기록 ──
tab_weekly, tab_archive = st.tabs(["이번주 운동 인증 현황", "지난 운동 인증 기록"])


def _fmt_date(d):
    return f"{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})"


def _render_week_table_html(table_rows_arg, week_dates_arg, apply_red_highlight=False, highlight_under_3_always=False):
    """테이블 HTML 생성. apply_red_highlight=True면 금·토에 3회 미만 이름·비고 빨강. highlight_under_3_always=True면 지난 기록에서도 3회 미만 빨강 유지."""
    header_cells = "".join(
        f'<th style="padding:6px 10px; border:1px solid #ddd;">{_fmt_date(d)}</th>' for d in week_dates_arg
    )
    header_cells += '<th style="padding:6px 10px; border:1px solid #ddd;">비고</th>'
    BIBLE_BG = "#FFE98F"
    BIBLE_TEXT = "#0D0D0D"
    is_red_window = apply_red_highlight and today.weekday() in (4, 5)
    body_rows = []
    for row_label, day_cells, count in table_rows_arg:
        is_under_3 = (highlight_under_3_always and count < 3) or (is_red_window and count < 3)
        name_cell_style = "padding:6px 10px; border:1px solid #ddd; font-weight:bold;"
        if is_under_3:
            name_cell_style += f" background-color:{ROW_HIGHLIGHT_UNDER_3};"
        cells = [f'<td style="{name_cell_style}">{row_label}</td>']
        for val, checked, cell_type in day_cells:
            if checked and cell_type == "bible":
                cells.append(
                    f'<td style="padding:6px 10px; border:1px solid #ddd; background-color:{BIBLE_BG}; color:{BIBLE_TEXT}; text-align:center;">{val}</td>'
                )
            elif checked and cell_type == "exercise":
                cells.append(
                    f'<td style="padding:6px 10px; border:1px solid #ddd; background-color:{CHECK_BLUE}; color:#FFFFFF; font-weight:700; text-align:center;">{val}</td>'
                )
            else:
                cells.append(f'<td style="padding:6px 10px; border:1px solid #ddd;"></td>')
        remarks_style = "padding:6px 10px; border:1px solid #ddd; text-align:center;"
        if is_under_3:
            remarks_style += f" background-color:{ROW_HIGHLIGHT_UNDER_3};"
        cells.append(f'<td style="{remarks_style}">{count}회</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="center-data week-table-wrap">'
        '<table style="border-collapse:collapse; width:100%; table-layout:fixed; font-size:14px;">'
        f'<thead><tr><th style="padding:6px 10px; border:1px solid #ddd;">실명 (아이디)</th>{header_cells}</tr></thead>'
        "<tbody>" + "".join(body_rows) + "</tbody>"
        "</table></div>"
    )


with tab_weekly:
    st.caption(period_str)
    week_table_html = _render_week_table_html(table_rows, week_dates, apply_red_highlight=True)
    st.markdown(week_table_html, unsafe_allow_html=True)
    st.caption("하루에 여러 번 올려도 1회로 인정합니다. 금요일 00:00~토요일 23:59 구간에서 주 3회 미만 시 이름·비고란을 연한 빨간색으로 표시합니다.")

with tab_archive:
    st.caption("지난 주간 운동 인증 기록입니다. 로컬 서버에서 수정·추가 후 데이터 가져오기(push)로 Streamlit에 배포됩니다. 조회 전용이며, 해당 주에 주 3회 미만이었던 인원은 이름·비고란을 연한 빨간색으로 표시합니다. 매주 일요일 00:00에 새 주로 전환됩니다.")
    if not archive:
        st.info("아직 아카이브된 주간 기록이 없습니다.")
    else:
        for entry in reversed(archive):
            week_sun_s = entry.get("week_sun") or ""
            period_label = entry.get("period_label") or f"{week_sun_s} 주간"
            try:
                sun_d = datetime.strptime(week_sun_s, "%Y-%m-%d").date()
            except Exception:
                sun_d = week_sun
            sat_d = sun_d + timedelta(days=6)
            week_dates_arch = [sun_d + timedelta(days=i) for i in range(7)]
            rows_live = _table_rows_for_week_range(cafe_rows, sun_d, sat_d)
            ser = entry.get("table_rows") or []
            snap = _deserialize_archive_table_rows(ser)
            rows_show = _merge_live_and_snapshot_week(rows_live, snap)
            table_html = _render_week_table_html(rows_show, week_dates_arch, apply_red_highlight=False, highlight_under_3_always=True)
            with st.expander(f"📅 {period_label}", expanded=False):
                st.markdown(table_html, unsafe_allow_html=True)
                st.caption("(최신 크롤 rows + 저장된 주간 스냅샷을 합쳐 표시 · 조회 전용)")

st.markdown("---")
st.caption("이 페이지는 읽기 전용입니다. 주간 현황·지난 운동 인증 기록 데이터는 로컬 서버에서 관리하며, 데이터 가져오기(push) 시 Streamlit에 반영됩니다. 매주 일요일 00:00에 새 주로 전환됩니다.")
