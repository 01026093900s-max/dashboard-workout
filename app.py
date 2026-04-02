# -*- coding: utf-8 -*-
"""
네이버 카페 데이터 대시보드 - Streamlit
"""
import os
import smtplib
import json
import urllib.parse
from urllib.request import urlopen
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from cafe_scraper import scrape_cafe_safe, CAFE_URL, DAYS_RECENT, TARGET_CAFE_BOARD_URL
from cafe_scraper import _parse_naver_date
from push_payload import (
    build_rows_for_github_push,
    crawl_row_stable_id,
    filter_crawl_rows,
    load_ignored_crawl_ids,
    merge_live_and_snapshot_week_rows,
    save_ignored_crawl_ids,
)

# 로컬 접속 주소 (Streamlit 기본 포트). × 삭제 링크에 쓰임. 다른 PC에서 접속하면 localhost가 아니므로
# 환경변수 STREAMLIT_APP_BASE_URL=http://<이_PC_IP>:8501 로 맞추면 삭제 링크가 동작합니다.
LOCAL_URL = os.environ.get("STREAMLIT_APP_BASE_URL", "http://localhost:8501").strip() or "http://localhost:8501"
# 자동 크롤링(10시/22시) 시 저장 파일 → 앱 시작 시 여기서 불러옴
CAFE_ROWS_LATEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cafe_rows_latest.json")
# 매주 일요일 00:00에 넘어간 주간 기록 아카이브 (지난 운동 인증 기록 탭용)
ARCHIVE_WEEKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archive_weeks.json")
# 수동 인증 목록 (앱 재시작 후에도 유지)
MANUAL_CERTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_certs.json")
REMOTE_DATA_JSON_URL = os.environ.get(
    "REMOTE_DATA_JSON_URL",
    "https://raw.githubusercontent.com/01026093900s-max/dashboard-workout/main/data.json",
)


@st.cache_data(ttl=30, show_spinner=False)
def _load_remote_payload():
    """GitHub raw data.json 로드. 실패 시 None."""
    try:
        with urlopen(REMOTE_DATA_JSON_URL, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return None


def _load_cafe_rows_from_file():
    """저장된 크롤링 결과 불러오기 (자동 크롤링용)."""
    remote = _load_remote_payload()
    if isinstance(remote, dict):
        rows = remote.get("rows")
        if isinstance(rows, list):
            return [r for r in rows if r is not None and isinstance(r, dict)]
    try:
        if os.path.isfile(CAFE_ROWS_LATEST_FILE):
            with open(CAFE_ROWS_LATEST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [r for r in data if r is not None and isinstance(r, dict)]
    except Exception:
        pass
    return None


def _resolve_last_updated_label():
    """화면 상단 '마지막 업데이트' 표시 문자열."""
    remote = _load_remote_payload()
    if isinstance(remote, dict):
        lu = str(remote.get("last_updated") or "").strip()
        if lu:
            return lu
    try:
        if os.path.isfile(CAFE_ROWS_LATEST_FILE):
            ts = datetime.fromtimestamp(os.path.getmtime(CAFE_ROWS_LATEST_FILE))
            return ts.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return None


def _save_cafe_rows_to_file(rows):
    """크롤링 결과를 파일로 저장 (수동 크롤링 후 + 자동 크롤링 스크립트에서 사용)."""
    try:
        import json
        with open(CAFE_ROWS_LATEST_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _load_archive():
    """아카이브된 주간 기록 목록 불러오기 (최신이 뒤에 오도록 유지)."""
    remote = _load_remote_payload()
    if isinstance(remote, dict):
        arc = remote.get("archive")
        if isinstance(arc, list):
            return arc
    try:
        if os.path.isfile(ARCHIVE_WEEKS_FILE):
            with open(ARCHIVE_WEEKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_archive(archive_list):
    """아카이브 목록을 파일로 저장."""
    try:
        import json
        with open(ARCHIVE_WEEKS_FILE, "w", encoding="utf-8") as f:
            json.dump(archive_list, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _load_manual_certs():
    """수동 인증 목록을 파일에서 불러오기 (앱 재시작 후 복원용)."""
    try:
        import json
        if os.path.isfile(MANUAL_CERTS_FILE):
            with open(MANUAL_CERTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            out = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                d = item.get("date")
                if name is None or d is None:
                    continue
                if isinstance(d, str):
                    try:
                        from datetime import datetime as _dt
                        d = _dt.strptime(d, "%Y-%m-%d").date()
                    except Exception:
                        continue
                out.append({
                    "name": name,
                    "date": d,
                    "exercise": bool(item.get("exercise", True)),
                    "bible": bool(item.get("bible", False)),
                })
            return out
    except Exception:
        pass
    return []


def _save_manual_certs(manual_certs):
    """수동 인증 목록을 파일로 저장 (date는 문자열로)."""
    try:
        import json
        out = []
        for item in manual_certs or []:
            if not isinstance(item, dict):
                continue
            d = item.get("date")
            if hasattr(d, "strftime"):
                d = d.strftime("%Y-%m-%d")
            out.append({
                "name": item.get("name"),
                "date": d,
                "exercise": bool(item.get("exercise", True)),
                "bible": bool(item.get("bible", False)),
            })
        with open(MANUAL_CERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def send_failure_email(error_msg: str) -> bool:
    """크롤링 실패 시 이메일 알림 전송. 환경변수 설정 시에만 동작."""
    host = os.environ.get("EMAIL_SMTP_HOST")
    port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    user = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASSWORD")
    to_addr = os.environ.get("EMAIL_TO", user)
    if not all([host, user, password]):
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = "[네이버 카페 대시보드] 데이터 크롤링 실패"
        msg["From"] = user
        msg["To"] = to_addr
        body = f"데이터 크롤링에 실패하였습니다.\n\n오류 내용:\n{error_msg}"
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, to_addr, msg.as_string())
        return True
    except Exception:
        return False

st.set_page_config(
    page_title="NEW START 운동 인증 대시보드",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# NEW START 대시보드 디자인 (첨부 이미지 100% 동일)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; background: #ffffff; color: #000000; }
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1600px; }
    [data-testid="stMainBlockContainer"] { padding-top: 40px !important; }
    /* 메인 타이틀: 검정 굵은 글씨 (이미지와 동일) */
    h1 {
        color: #000000 !important;
        font-weight: 700 !important;
        border: none !important;
        font-size: 1.75rem !important;
        line-height: 1.25 !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        padding-top: 0 !important;
        overflow: visible !important;
    }
    .main p { color: #333333; }
    .center-data { width: 100%; max-width: 1600px; margin-left: auto; margin-right: auto; }
    /* 주간 현황 테이블 영역: 연한 회색 배경 플레이스홀더 느낌 */
    .week-table-wrap { background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin: 0.5rem 0 1rem 0; overflow: visible; }
    .week-table-wrap table { background: #ffffff; }
    .week-table-sticky-head {
        position: sticky;
        top: 56px;
        z-index: 200;
        background: #ffffff;
        box-shadow: 0 1px 0 rgba(0, 0, 0, 0.06);
    }
    .id-medium { font-weight: 500; }
    /* 좌측 SNB: 데이터 가져오기 버튼 밝은 녹색 */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] { background-color: #5cb85c !important; color: white !important; border: none !important; width: 100%; }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover { background-color: #4cae4c !important; }
    section[data-testid="stSidebar"] h2 { font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem; color: #000; }
    /* 수동 인증·메인 추가 버튼 녹색 */
    .main .stButton > button[kind="primary"] { background-color: #5cb85c !important; color: white !important; border: none !important; }
    /* TOP3 뱃지 */
    .top3-badge { display: inline-block; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 0.9rem; margin-left: 8px; }
    .top3-1 { background: #D4AF37; color: #FFFFFF; }
    .top3-2 { background: #E5E4E2; color: #0D0D0D; }
    .top3-3 { background: #B87333; color: #FFFFFF; }
    .kpi-card { border: 1px solid #e6e8ef; border-radius: 14px; padding: 16px 18px; background: #ffffff; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08); min-height: 104px; }
    .kpi-title { font-size: 0.95rem; color: #5b6475; font-weight: 600; margin-bottom: 10px; }
    .kpi-value { font-size: 2rem; font-weight: 800; line-height: 1; color: #111827; }
    .kpi-unit { font-size: 1rem; font-weight: 700; margin-left: 2px; color: #4b5563; }
    .top3-card { border: 1px solid #e6e8ef; border-radius: 14px; padding: 14px 18px; background: #ffffff; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08); width: 100%; box-sizing: border-box; overflow: hidden; }
    .top3-item { padding: 10px 0; border-bottom: 1px solid #eceff4; }
    .top3-item:last-child { border-bottom: none; }
    .update-badge { display: inline-block; background: #f0f0f0; border: 1px solid #ddd; border-radius: 6px; padding: 4px 12px; font-size: 0.85rem; color: #555; margin-top: 4px; margin-bottom: 18px; }
    .dashboard-top-gap { margin-top: 8px; margin-bottom: 12px; }
    .graph-head { margin-top: 40px; margin-bottom: 0; }
    .graph-head h3 { margin: 0 !important; margin-bottom: 8px !important; padding: 0 !important; line-height: 1.25 !important; }
    .graph-head p { margin: 0 !important; padding: 0 !important; font-size: 14px !important; font-weight: 500 !important; color: #667085; }
    .weekly-tab-title { font-size: 28px !important; font-weight: 600 !important; line-height: 1.25 !important; margin: 0 0 8px 0 !important; color: #111827 !important; }
    .weekly-tab-subtitle { font-size: 14px !important; font-weight: 500 !important; line-height: 1.45 !important; margin: 0 0 20px 0 !important; color: #667085 !important; }
    .weekly-tab-intro { margin-top: 40px; }
    .arrow-wrap { margin-top: 40px; }
    .arrow-wrap [data-testid="stButton"] > button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        min-height: 72px !important;
        width: 72px !important;
        height: 72px !important;
        color: #0D0D0D !important;
        line-height: 1 !important;
    }
    .arrow-wrap [data-testid="stButton"] > button p,
    .arrow-wrap [data-testid="stButton"] > button span,
    .arrow-wrap [data-testid="stButton"] > button div {
        margin: 0 !important;
        font-size: 72px !important;
        line-height: 1 !important;
        font-weight: 700 !important;
    }
    .arrow-wrap [data-testid="stButton"] > button:disabled {
        color: #808080 !important;
        opacity: 1 !important;
        cursor: default !important;
    }
    .arrow-wrap [data-testid="stButton"] > button:disabled p,
    .arrow-wrap [data-testid="stButton"] > button:disabled span,
    .arrow-wrap [data-testid="stButton"] > button:disabled div {
        color: #808080 !important;
    }
    /* 토스트 메시지 화면 정중앙, 3초 표시는 duration=3으로 처리 */
    div[data-testid="stToast"] { left: 50% !important; transform: translateX(-50%) !important; }
    /* 수동 인증 칸: 20% 검정 딤 + 호버 시 삭제 X */
    .manual-cert-wrap { position: relative; min-height: 36px; display: flex; align-items: center; justify-content: center; box-sizing: border-box; }
    .manual-cert-wrap.dimmed::after {
        content: ""; position: absolute; inset: 0; background: rgba(0, 0, 0, 0.2); pointer-events: none; z-index: 1;
    }
    .manual-cert-wrap .manual-cert-inner { position: relative; z-index: 2; }
    .manual-cert-wrap .manual-del-x {
        position: absolute; top: 2px; right: 2px; width: 22px; height: 22px; line-height: 20px;
        text-align: center; background: #dc3545; color: #fff !important; border-radius: 4px;
        font-weight: 700; font-size: 15px; text-decoration: none !important; z-index: 3;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    @media (hover: hover) {
        .manual-cert-wrap .manual-del-x { opacity: 0; pointer-events: none; transition: opacity 0.15s ease; }
        .manual-cert-wrap:hover .manual-del-x { opacity: 1; pointer-events: auto; }
    }
    @media (hover: none) {
        .manual-cert-wrap .manual-del-x { opacity: 0.9; pointer-events: auto; }
    }
    /* 크롤 전용 칸: 호버 시 제외 × (수동과 동일 패턴) */
    .crawl-exclude-wrap { position: relative; min-height: 36px; display: flex; align-items: center; justify-content: center; box-sizing: border-box; }
    .crawl-exclude-wrap .crawl-exclude-x {
        position: absolute; top: 2px; right: 2px; width: 22px; height: 22px; line-height: 20px;
        text-align: center; background: #6c757d; color: #fff !important; border-radius: 4px;
        font-weight: 700; font-size: 14px; text-decoration: none !important; z-index: 3;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    @media (hover: hover) {
        .crawl-exclude-wrap .crawl-exclude-x { opacity: 0; pointer-events: none; transition: opacity 0.15s ease; }
        .crawl-exclude-wrap:hover .crawl-exclude-x { opacity: 1; pointer-events: auto; }
    }
    @media (hover: none) {
        .crawl-exclude-wrap .crawl-exclude-x { opacity: 0.85; pointer-events: auto; }
    }
    /* 지난주 평균 막대 그래프 타이틀 블록 */
    .avg-bar-title-main { font-size: 1.35rem; font-weight: 700; color: #000; margin-bottom: 0.35rem; }
    .avg-bar-title-sub { font-size: 1rem; color: #000; margin-bottom: 0.25rem; line-height: 1.4; }
    .avg-bar-title-note { font-size: 0.8rem; color: #888888; line-height: 1.35; margin-bottom: 0.75rem; }
    .avg-bar-chart-section-marker { display: none !important; }
    /* 평균 막대 차트(타이틀 블록 바로 다음): 플롯 영역 상단 좌우 12px */
    [data-testid="stMarkdown"]:has(.avg-bar-chart-section-marker) + div [data-testid="stPlotlyChart"] iframe {
        border-radius: 12px !important;
        border: 1px solid #e8e8e8 !important;
        box-sizing: border-box;
    }
    /* 실시간 그래프: 이번주 '오늘' 강조 마커(마지막 scatter trace) 외곽선 깜빡임 */
    @keyframes plotly-today-pulse {
        0%, 100% { opacity: 1; stroke-width: 3px; }
        50% { opacity: 0.28; stroke-width: 10px; }
    }
    /* 라인 차트에 trace 3개일 때만(지난주·이번주·오늘강조): 3번째 = 오늘 점 */
    .js-plotly-plot .scatterlayer > g:nth-child(3) path {
        animation: plotly-today-pulse 1.35s ease-in-out infinite;
    }
    @media (min-width: 797px) and (max-width: 1920px) {
        .main .block-container { max-width: 1600px; padding-left: 32px; padding-right: 32px; }
    }
    @media (min-width: 360px) and (max-width: 796px) {
        .main .block-container { max-width: 100%; padding-left: 14px; padding-right: 14px; }
        h1 { font-size: 1.55rem !important; }
        .kpi-value { font-size: 1.7rem; }
        .dashboard-top-gap { margin-top: 4px; margin-bottom: 10px; }
        .graph-head { margin-top: 12px; }
        .arrow-wrap [data-testid="stButton"] > button p,
        .arrow-wrap [data-testid="stButton"] > button span,
        .arrow-wrap [data-testid="stButton"] > button div { font-size: 72px !important; }
    }
    @media (prefers-color-scheme: dark) {
        html, body, [class*="css"] { background: #0f1117 !important; color: #f3f4f6 !important; }
        .main p, .avg-bar-title-sub, .avg-bar-title-note, .kpi-title { color: #c8d0dd !important; }
        h1, .avg-bar-title-main { color: #f8fafc !important; }
        .week-table-wrap { background: #171a22 !important; border-color: #2c3342 !important; }
        .week-table-wrap table { background: #11141b !important; color: #f3f4f6 !important; }
        .kpi-card, .top3-card { background: #171a22 !important; border-color: #2c3342 !important; box-shadow: none !important; }
        .kpi-value, .kpi-unit { color: #f3f4f6 !important; }
        .top3-item { border-bottom-color: #2c3342 !important; }
    }
</style>
""", unsafe_allow_html=True)

st.title("NEW START 운동 인증 대시보드")
st.caption("인증게시판 최근 7일 글을 수집합니다.")
_last_updated_label = _resolve_last_updated_label()
if _last_updated_label:
    st.markdown(
        f'<span class="update-badge">마지막 업데이트: {_last_updated_label}</span>',
        unsafe_allow_html=True,
    )

# 기본 네이버 계정 (비공개 카페 수집용 로그인 안내)
DEFAULT_NAVER_ACCOUNT = "tom119829@naver.com"

# 실명 - 카페 아이디 매핑 (가로: 날짜, 세로: 실명/아이디, 주 3회 미만 시 행 강조)
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
NAME_TO_ID = {name: cid for name, cid in NAME_ID_LIST}

# 그래프 툴팁용 (월=0 … 일=6)
_DAY_LONG_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

# Python weekday(): 월=0, 화=1, …, 일=6
WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
ROW_HIGHLIGHT_UNDER_3 = "#FFD8D8"
CHECK_BLUE = "#4E6FFF"


def _serialize_archive_cells_only(rows_tuples):
    """주간 표 튜플 → 아카이브 JSON table_rows (셀은 v,c,t 3요소만 저장)."""
    out = []
    for row_label, dc, cnt in rows_tuples:
        slim = []
        for cell in dc:
            if isinstance(cell, (list, tuple)) and len(cell) >= 3:
                slim.append([cell[0], bool(cell[1]), (cell[2] or "")])
            else:
                slim.append(["", False, ""])
        out.append([row_label, slim, cnt])
    return out


def _sync_archive_for_push(cafe_rows_all, manual_certs, ignored_ids_list):
    """Push 직전: 원격+로컬 아카이브에 이전 주 스냅·라이브 reconcile 반영 (사이드바는 본문 archive보다 먼저 실행됨)."""
    from push_payload import (
        filter_crawl_rows,
        manual_certs_to_rows,
        merge_live_and_snapshot_week_rows,
        table_rows_for_week_from_rows,
    )

    filtered = filter_crawl_rows(list(cafe_rows_all or []), set(ignored_ids_list or []))
    rows_push = filtered + manual_certs_to_rows(manual_certs or [])
    arc = list(_load_archive())
    today_d = datetime.now().date()
    days_since_sun = (today_d.weekday() + 1) % 7
    week_sun_d = today_d - timedelta(days=days_since_sun)
    week_sat_d = week_sun_d + timedelta(days=6)
    prev_sun = week_sun_d - timedelta(days=7)
    prev_sat = week_sat_d - timedelta(days=7)
    existing_suns = {a.get("week_sun") for a in arc if a.get("week_sun")}
    if prev_sun.isoformat() not in existing_suns:
        table_prev = table_rows_for_week_from_rows(rows_push, prev_sun, prev_sat)
        period_prev = (
            f"{prev_sun.month}월 {prev_sun.day}일 ({WEEKDAY_NAMES[prev_sun.weekday()]}) ~ "
            f"{prev_sat.month}월 {prev_sat.day}일 ({WEEKDAY_NAMES[prev_sat.weekday()]})"
        )
        arc.append({
            "week_sun": prev_sun.isoformat(),
            "week_sat": prev_sat.isoformat(),
            "period_label": period_prev,
            "table_rows": _serialize_archive_cells_only(table_prev),
        })
        _save_archive(arc)
    changed = False
    for entry in arc:
        ws = entry.get("week_sun")
        if not ws:
            continue
        try:
            sun_d = datetime.strptime(ws, "%Y-%m-%d").date()
        except Exception:
            continue
        sat_d = sun_d + timedelta(days=6)
        live = table_rows_for_week_from_rows(rows_push, sun_d, sat_d)
        ser_old = entry.get("table_rows") or []
        merged = merge_live_and_snapshot_week_rows(live, ser_old)
        new_ser = _serialize_archive_cells_only(merged)
        if new_ser != ser_old:
            entry["table_rows"] = new_ser
            changed = True
    if changed:
        _save_archive(arc)
    return arc


def _is_public_streamlit_deploy() -> bool:
    """공개 Streamlit 앱이면 True → 수동 인증 UI·mdel 삭제 비활성화.

    Cloud Secrets 는 **프로젝트 안의 파일이 아닙니다.**
    share.streamlit.io 에 로그인 → 해당 앱 → 오른쪽 ⋮ 또는 Settings → **Secrets**
    에서 TOML 을 **웹 화면에 붙여 넣는 값**입니다. 예:

      public_streamlit_app = true

    GitHub 저장소에 커밋하지 않아도 됩니다.
    """
    try:
        v = st.secrets.get("public_streamlit_app", False)
        if v in (True, "true", "1", 1, "yes"):
            return True
    except Exception:
        pass
    if os.environ.get("PUBLIC_STREAMLIT_APP", "").strip().lower() in ("1", "true", "yes"):
        return True
    return False


def _manual_cert_ui_allowed() -> bool:
    """수동 인증 추가·표에서 × 삭제·mdel 처리. 공개 배포에서는 항상 False."""
    o = os.environ.get("LOCAL_MANUAL_EDIT", "").strip().lower()
    if o in ("0", "false", "no"):
        return False
    if o in ("1", "true", "yes"):
        return True
    return not _is_public_streamlit_deploy()


def _qp_get_single(name: str):
    """query string 단일 값 (Streamlit이 list로 줄 때 대응)."""
    try:
        v = st.query_params.get(name)
        if v is None:
            return None
        if isinstance(v, (list, tuple)):
            return str(v[0]).strip() if v else None
        return str(v).strip()
    except Exception:
        pass
    try:
        p = st.experimental_get_query_params()
        vals = p.get(name) or []
        return str(vals[0]).strip() if vals else None
    except Exception:
        return None


def _qp_remove_mdel():
    """URL에서 mdel만 제거 (전체 새로고침 시에도 남지 않게)."""
    try:
        if hasattr(st, "query_params") and "mdel" in st.query_params:
            del st.query_params["mdel"]
            return
    except Exception:
        pass
    try:
        p = dict(st.experimental_get_query_params())
        p.pop("mdel", None)
        if not p:
            st.experimental_set_query_params()
            return
        flat = {}
        for k, v in p.items():
            if isinstance(v, list) and len(v) == 1:
                flat[k] = v[0]
            elif isinstance(v, list):
                flat[k] = v[0]
            else:
                flat[k] = v
        st.experimental_set_query_params(**flat)
    except Exception:
        pass


def _mdel_href(del_kind: str, del_idx: int) -> str:
    """× 링크: 상대 ?mdel= 만으로는 SPA에서 무시되는 경우가 있어 절대 URL 사용(LOCAL_URL·STREAMLIT_APP_BASE_URL)."""
    base = LOCAL_URL.strip().rstrip("/")
    if base:
        return f"{base}/?mdel={del_kind}_{del_idx}"
    return f"./?mdel={del_kind}_{del_idx}"


def _apply_mdel_query_param():
    """?mdel=b_0 / ?mdel=e_0 — 로컬·비공개에서만 동작. 공개 배포에서는 무시 후 URL만 정리."""
    qdel = _qp_get_single("mdel")
    if not _manual_cert_ui_allowed():
        if qdel:
            _qp_remove_mdel()
            st.rerun()
        return
    if not qdel:
        return
    s = qdel
    try:
        kind, idx_s = s.split("_", 1)
        kind = kind.lower()
        if kind not in ("b", "e"):
            raise ValueError("kind")
        idx = int(idx_s)
        mc = st.session_state.get("manual_certs") or []
        if 0 <= idx < len(mc):
            cert = mc[idx]
            if kind == "b":
                cert["bible"] = False
            else:
                cert["exercise"] = False
            if not cert.get("exercise") and not cert.get("bible"):
                mc.pop(idx)
            _save_manual_certs(mc)
    except Exception:
        pass
    _qp_remove_mdel()
    st.rerun()


def _qp_remove_cdel():
    try:
        if hasattr(st, "query_params") and "cdel" in st.query_params:
            del st.query_params["cdel"]
            return
    except Exception:
        pass
    try:
        p = dict(st.experimental_get_query_params())
        p.pop("cdel", None)
        if not p:
            st.experimental_set_query_params()
            return
        flat = {}
        for k, v in p.items():
            if isinstance(v, list) and len(v) == 1:
                flat[k] = v[0]
            elif isinstance(v, list):
                flat[k] = v[0]
            else:
                flat[k] = v
        st.experimental_set_query_params(**flat)
    except Exception:
        pass


def _cdel_href(crawl_ids: list) -> str:
    """크롤 글 제외: JSON id 목록을 쿼리 한 덩어리로 전달."""
    base = LOCAL_URL.strip().rstrip("/")
    payload = json.dumps(crawl_ids, ensure_ascii=False)
    q = urllib.parse.quote(payload, safe="")
    if base:
        return f"{base}/?cdel={q}"
    return f"./?cdel={q}"


def _apply_cdel_query_param():
    raw = _qp_get_single("cdel")
    if not _manual_cert_ui_allowed():
        if raw:
            _qp_remove_cdel()
            st.rerun()
        return
    if not raw:
        return
    try:
        s = urllib.parse.unquote(raw)
        ids = json.loads(s)
        if isinstance(ids, list):
            lst = st.session_state.setdefault("ignored_crawl_ids", [])
            ch = False
            for i in ids:
                if isinstance(i, str) and i and i not in lst:
                    lst.append(i)
                    ch = True
            if ch:
                save_ignored_crawl_ids(lst)
    except Exception:
        pass
    _qp_remove_cdel()
    st.rerun()


# 사이드바: 데이터 새로고침 (저장 파일 있으면 우선 불러오기) — 본문은 archive 준비 후에 렌더(아래쪽)
if "cafe_rows" not in st.session_state:
    loaded = _load_cafe_rows_from_file()
    st.session_state["cafe_rows"] = loaded if loaded is not None else []
if "cafe_error" not in st.session_state:
    st.session_state["cafe_error"] = None
# 수동 인증 추가 (아이디, 날짜) — 스크래핑에 없는 인증을 수동으로 반영 (파일에서 복원)
if "manual_certs" not in st.session_state:
    st.session_state["manual_certs"] = _load_manual_certs()
if "ignored_crawl_ids" not in st.session_state:
    st.session_state["ignored_crawl_ids"] = load_ignored_crawl_ids()

_apply_mdel_query_param()
_apply_cdel_query_param()

with st.sidebar:
    st.header("데이터 가져오기")
    if not _manual_cert_ui_allowed():
        st.caption(
            "공개 대시보드 모드: 수동 인증 추가·삭제(×)는 사용할 수 없습니다. "
            "로컬에서 `streamlit run` 시에는 기본적으로 사용 가능합니다."
        )
    st.markdown("데이터 가져오기를 누르면 Brave(또는 Chrome) 창이 자동으로 열립니다.")
    if st.button("데이터 가져오기", type="primary", use_container_width=True):
        st.session_state["cafe_error"] = None
        with st.spinner("브라우저를 여는 중… 로그인 유지 시 곧바로 인증게시판으로 이동합니다."):
            rows, err = scrape_cafe_safe()
        if err:
            st.session_state["cafe_error"] = err
            st.session_state["cafe_rows"] = []
            st.toast("데이터 크롤링에 실패하였습니다.")
            if send_failure_email(err):
                st.caption("이메일 알림을 발송했습니다.")
        else:
            st.session_state["cafe_rows"] = rows
            st.session_state["cafe_error"] = None
            _raw_push = [r for r in rows if isinstance(r, dict)]
            _ign_push = st.session_state.get("ignored_crawl_ids") or []
            _arc_push = _sync_archive_for_push(
                _raw_push,
                st.session_state.get("manual_certs", []),
                _ign_push,
            )
            rows_for_push, archive_for_push = build_rows_for_github_push(
                st.session_state["cafe_rows"],
                st.session_state.get("manual_certs", []),
                ignored_crawl_ids=_ign_push,
                archive_list=_arc_push,
            )
            _save_cafe_rows_to_file(rows_for_push)
            github_ok = False
            try:
                from github_push import push_data_json

                push_data_json(rows_for_push, archive=archive_for_push)
                github_ok = True
            except Exception as e:
                st.session_state["github_push_error"] = str(e)
            st.session_state["show_toast_count"] = len(rows)
            st.session_state["github_push_ok"] = github_ok
            st.rerun()

    with st.expander("데이터 가져오는 방법", expanded=True):
        st.markdown("1. 카페에서 데이터 가져오기 버튼을 누르세요.")
        st.markdown("2. 브라우저가 뜨면 3초 안에 네이버 로그인만 해 주세요. (로그인 유지 시 곧바로 이동)")
        st.markdown("3. 자동으로 인증게시판 주소로 이동한 뒤 게시글 목록을 수집하고 브라우저가 닫힙니다.")

    st.markdown("**수동 인증만 수정한 경우** 아래 **웹 대시보드에 반영**을 누르면 크롤링 없이 GitHub에 올라가 streamlit.app에 반영됩니다.")
    if st.button("웹 대시보드에 반영 (Push만)", use_container_width=True):
        _raw_rows = st.session_state.get("cafe_rows") or []
        cafe_ok = [r for r in _raw_rows if r is not None and isinstance(r, dict)]
        if not cafe_ok:
            st.warning("저장된 크롤 데이터가 없습니다. 먼저 **데이터 가져오기**로 수집해 주세요.")
        else:
            try:
                from github_push import push_data_json

                _ign_p = st.session_state.get("ignored_crawl_ids") or []
                _arc_p = _sync_archive_for_push(
                    cafe_ok,
                    st.session_state.get("manual_certs", []),
                    _ign_p,
                )
                rows_for_push, archive_for_push = build_rows_for_github_push(
                    cafe_ok,
                    st.session_state.get("manual_certs", []),
                    ignored_crawl_ids=_ign_p,
                    archive_list=_arc_p,
                )
                _save_cafe_rows_to_file(rows_for_push)
                ts = push_data_json(rows_for_push, archive=archive_for_push)
                st.success(f"GitHub 반영 완료 ({ts}). 공개 앱은 최대 약 1분 내 최신 data.json을 불러옵니다.")
            except Exception as e:
                st.error(str(e))

    if _manual_cert_ui_allowed():
        with st.expander("크롤링 글 대시보드에서 제외", expanded=False):
            st.caption(
                "오늘 올라온 글인데 목록 날짜가 어긋난 경우 등, 자동 크롤 한 건을 표·그래프·Push에서 빼려면 아래에서 선택하세요. "
                "설정은 `ignored_crawl_ids.json`에 저장됩니다."
            )
            _full_crawl = [r for r in (st.session_state.get("cafe_rows") or []) if isinstance(r, dict)]
            _ign_set = set(st.session_state.get("ignored_crawl_ids") or [])
            _cand = [(i, r) for i, r in enumerate(_full_crawl) if crawl_row_stable_id(r) not in _ign_set]
            if not _cand:
                st.caption("(제외 가능한 크롤 글이 없습니다. 이미 모두 제외됐거나 데이터가 없습니다.)")
            else:
                def _fmt_pick(j):
                    _i, rr = _cand[j]
                    tt = (rr.get("제목") or "")[:40]
                    if len((rr.get("제목") or "")) > 40:
                        tt += "…"
                    return f"{j + 1}. {tt} | {rr.get('작성자') or ''} | {rr.get('날짜') or ''}"

                _pj = st.selectbox(
                    "제외할 글",
                    options=list(range(len(_cand))),
                    format_func=_fmt_pick,
                    key="sidebar_pick_crawl_ignore",
                )
                if st.button("선택한 글 제외", key="sidebar_btn_crawl_ignore"):
                    _rid = crawl_row_stable_id(_cand[_pj][1])
                    _lst = st.session_state.setdefault("ignored_crawl_ids", [])
                    if _rid not in _lst:
                        _lst.append(_rid)
                    save_ignored_crawl_ids(_lst)
                    st.rerun()
            _ign_list = list(st.session_state.get("ignored_crawl_ids") or [])
            if _ign_list:

                def _fmt_ign_id(rid):
                    for rr in _full_crawl:
                        if crawl_row_stable_id(rr) == rid:
                            t0 = (rr.get("제목") or "")[:32]
                            if len((rr.get("제목") or "")) > 32:
                                t0 += "…"
                            return f"{t0} | {rr.get('작성자') or ''} | {rid[:28]}…"
                    return rid if len(rid) < 72 else rid[:69] + "…"

                _rem = st.multiselect(
                    "제외 해제",
                    options=_ign_list,
                    format_func=_fmt_ign_id,
                    key="sidebar_multirem_crawl_ignore",
                )
                if st.button("선택 항목 제외 해제", key="sidebar_btn_unignore_crawl"):
                    _new = [x for x in _ign_list if x not in _rem]
                    st.session_state["ignored_crawl_ids"] = _new
                    save_ignored_crawl_ids(_new)
                    st.rerun()

    st.markdown("**로컬 접속 주소**")
    st.code(LOCAL_URL, language=None)

    st.markdown("---")
    st.caption(
        "크롤링·Push만 버튼 완료 시 GitHub의 data.json이 갱신됩니다. "
        "「크롤링 글 대시보드에서 제외」에 넣은 글은 Push에 포함되지 않습니다. streamlit.app은 GitHub에서 주기적으로 읽어 반영합니다."
    )

    with st.expander("이메일 알림 설정 (데이터 크롤링 실패 시)"):
        st.caption(
            "환경변수: EMAIL_SMTP_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_TO. "
            "설정 시 크롤링 실패하면 이메일로 알림이 갑니다."
        )

# 크롤링 완료 토스트 (rerun 후 이번 렌더에서 표시)
if "show_toast_count" in st.session_state and st.session_state["show_toast_count"] is not None:
    n = st.session_state.pop("show_toast_count")
    if st.session_state.pop("github_push_ok", False):
        st.toast(f"총 {n}건 크롤링 완료 + 웹 대시보드 자동 반영됨", duration=4)
    else:
        st.toast(f"총 {n}건 크롤링 완료", duration=3)
        err = st.session_state.pop("github_push_error", "")
        if err:
            st.warning(f"웹 대시보드 자동 반영 실패: {err}")

# None/비정상 항목 제거 후, 크롤 제외 목록 적용 → 표·그래프·아카이브 집계용
_raw = st.session_state["cafe_rows"] or []
_cafe_rows_all = [r for r in _raw if r is not None and isinstance(r, dict)]
_ignored_ids_list = st.session_state.get("ignored_crawl_ids") or []
cafe_rows = filter_crawl_rows(_cafe_rows_all, set(_ignored_ids_list))
df = pd.DataFrame(cafe_rows)
err_msg = st.session_state["cafe_error"]

# 실패 시 메인 화면에 오류/경고 표시
if err_msg:
    if "게시글을 찾을 수 없습니다" in err_msg:
        st.warning("⚠️ **" + err_msg + "**")
        st.info("**cafe_main** 프레임이 로드되었는지, 게시판 목록이 보이는 페이지인지 확인한 뒤 다시 시도해 주세요.")
    elif "cafe_main" in err_msg or "프레임" in err_msg:
        st.warning("⚠️ **iframe 접근 문제**")
        st.error(err_msg)
        st.info("**해결 방법:** 버튼을 다시 누른 뒤, 브라우저가 뜨면 **3초 안에** 로그인하고 **인증게시판**을 클릭해 게시글 목록이 보이도록 해 주세요.")
    else:
        st.error("❌ **데이터를 가져오지 못했습니다**")
        st.error(err_msg)
        st.info("네트워크·Brave(또는 Chrome) 설치를 확인하거나, 로그인 후 **인증게시판을 클릭해 목록이 보이는 페이지**까지 왔는지 확인한 뒤 다시 **카페에서 데이터 가져오기**를 눌러 주세요.")
    with st.expander("📌 네이버 카페에서 데이터를 긁어오지 못하는 흔한 이유"):
        st.markdown("""
        - **로그인·접속 안 함** : 브라우저가 뜬 뒤 네이버 로그인 후 **인증게시판**을 클릭해 게시글 목록이 보여야 합니다.
        - **브라우저 미설치** : Brave 또는 Chrome이 설치되어 있어야 합니다. (Brave가 있으면 Brave로 실행)
        - **페이지 구조 변경** : 네이버 카페 HTML이 바뀌면 선택자(selector)가 안 맞아 수집 실패할 수 있음
        - **iframe/지연 로딩** : 게시판이 iframe 안에 있거나 로딩이 느리면 대기 시간 부족 가능
        - **네트워크/타임아웃** : 접속 지연이나 일시적 오류
        """)
    st.stop()

if df.empty:
    st.info("👈 왼쪽에서 **카페에서 데이터 가져오기**를 눌러 주세요. (로그인 유지 시 곧바로 수집됩니다)")
    st.stop()

# 데이터 수집 완료 시에는 토스트로 안내됨 (문구 변경 없음)

# ----- 주간(일~토) 계산: 매주 일요일 00:00에 새 주로 전환 -----
today = datetime.now().date()
days_since_sun = (today.weekday() + 1) % 7  # 0=월, 6=일
week_sun = today - timedelta(days=days_since_sun)
week_sat = week_sun + timedelta(days=6)
week_dates = [week_sun + timedelta(days=i) for i in range(7)]
period_str = f"이번 주 기간: {week_sun.month}월 {week_sun.day}일 ({WEEKDAY_NAMES[week_sun.weekday()]}) ~ {week_sat.month}월 {week_sat.day}일 ({WEEKDAY_NAMES[week_sat.weekday()]})"

# 제목에서 작성자를 추출하기 위한 별칭 매핑 (카페아이디, 실명, 실명 일부, 별명 등)
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
})


def _author_from_row(r):
    """작성자 필드가 비어 있거나 매칭 안 되면 제목에서 이름/아이디/별칭으로 추정."""
    author = (r.get("작성자") or "").strip()
    if author:
        for _, cid in NAME_ID_LIST:
            if cid and (author == cid or author.strip().upper() == cid.strip().upper()):
                return cid
        # 작성자 닉네임이 (예: 민찬이) 내부 cid(예: 김보람아님)와 직접 일치하지 않는 경우,
        # 별칭 매핑을 통해 cid로 보정한다.
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
        for sep in [" ", "/", "　"]:
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
    """제목에 '필사' 키워드가 있으면 성경필사로 분류 (예: 1주차 보충필사, 성경 필사)."""
    title = (row.get("제목") or "").strip()
    return "필사" in title


def _empty_posted_sources():
    return {
        "bible_manual": False,
        "bible_crawl_ids": [],
        "exercise_manual": False,
        "exercise_crawl_ids": [],
        "mi_bible": None,
        "mi_ex": None,
    }


def _build_table_rows_for_week(rows, manual_certs, week_sun, week_sat):
    """지정한 주(일~토) posted 집계. day_cell = (val, checked, type, dim_manual, del_kind, del_idx).
    del_kind: 'b' 성경필사 / 'e' 운동, del_idx: manual_certs 인덱스 (수동만 삭제용).
    """
    week_dates_w = [week_sun + timedelta(days=i) for i in range(7)]
    posted = {}
    for mi, item in enumerate(manual_certs or []):
        name = d = None
        is_exercise, is_bible = False, False
        if isinstance(item, dict):
            name, d = item.get("name"), item.get("date")
            is_exercise, is_bible = bool(item.get("exercise")), bool(item.get("bible"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            name, d = item[0], item[1]
            is_exercise = True
        if name is None or d is None:
            continue
        try:
            if hasattr(d, "date") and callable(d.date):
                d = d.date()
            if not hasattr(d, "year") or not hasattr(d, "month"):
                continue
        except Exception:
            continue
        if week_sun <= d <= week_sat:
            key = (name, d)
            if key not in posted:
                posted[key] = _empty_posted_sources()
            p = posted[key]
            if is_bible:
                p["bible_manual"] = True
                if p["mi_bible"] is None:
                    p["mi_bible"] = mi
            if is_exercise:
                p["exercise_manual"] = True
                if p["mi_ex"] is None:
                    p["mi_ex"] = mi
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
                    posted[key] = _empty_posted_sources()
                p = posted[key]
                rid = crawl_row_stable_id(r)
                if is_bible:
                    if rid and rid not in p["bible_crawl_ids"]:
                        p["bible_crawl_ids"].append(rid)
                else:
                    if rid and rid not in p["exercise_crawl_ids"]:
                        p["exercise_crawl_ids"].append(rid)
                break
    empty_cell = ("", False, None, False, None, None, [])
    table_rows = []
    for name, cid in NAME_ID_LIST:
        row_label = f"{name} ({cid})"
        total_count = 0
        day_cells = []
        for d in week_dates_w:
            p = posted.get((name, d))
            if not p:
                day_cells.append(empty_cell)
                continue
            bcids = p.get("bible_crawl_ids") or []
            ecids = p.get("exercise_crawl_ids") or []
            b_any = p["bible_manual"] or bool(bcids)
            e_any = p["exercise_manual"] or bool(ecids)
            if b_any:
                dim = p["bible_manual"] and not bcids
                dk = "b" if dim else None
                di = p["mi_bible"] if dim else None
                day_cells.append(("성경필사", True, "bible", dim, dk, di, list(bcids)))
                total_count += 1
            elif e_any:
                dim = p["exercise_manual"] and not ecids
                dk = "e" if dim else None
                di = p["mi_ex"] if dim else None
                day_cells.append(("✓", True, "exercise", dim, dk, di, list(ecids)))
                total_count += 1
            else:
                day_cells.append(empty_cell)
        table_rows.append((row_label, day_cells, total_count))
    return table_rows


def _cell_checked_simple(cell):
    if isinstance(cell, (list, tuple)) and len(cell) >= 2:
        return bool(cell[1])
    return False


def _daily_cert_counts_for_week(rows, manual_certs, week_sun, week_sat):
    """해당 주 일~토 각 날짜의 '인증 칸' 합계(명 수)."""
    tr = _build_table_rows_for_week(rows, manual_certs, week_sun, week_sat)
    totals = [0] * 7
    for _rl, day_cells, _ in tr:
        for j in range(7):
            if j < len(day_cells) and _cell_checked_simple(day_cells[j]):
                totals[j] += 1
    return totals


def _render_top3_section(table_rows, title: str, empty_msg=None):
    """주간/아카이브 공통 TOP3 (인증현황과 동일 스타일)."""
    st.markdown("---")
    st.subheader(title)
    sorted_by_count = sorted(table_rows, key=lambda x: -x[2])
    top3_list = [(label, cnt) for label, _, cnt in sorted_by_count if cnt > 0]
    from collections import OrderedDict

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
            names_str = ", ".join(bold_labels)
            st.markdown(
                f'**{r}등** {names_str} <span class="top3-badge {bc}">{cnt}회</span>',
                unsafe_allow_html=True,
            )
    else:
        st.caption(empty_msg or "이번 주간 인증 데이터가 없습니다.")


def _fig_realtime_exercise_lines(rows, manual_certs, week_sun, today_d):
    """지난주 vs 이번주 일별 인증 건수 라인. 이번주는 오늘까지만 선 연결."""
    prev_sun = week_sun - timedelta(days=7)
    prev_sat = prev_sun + timedelta(days=6)
    week_dates = [week_sun + timedelta(days=i) for i in range(7)]
    prev_dates = [prev_sun + timedelta(days=i) for i in range(7)]
    y_last = _daily_cert_counts_for_week(rows, manual_certs, prev_sun, prev_sat)
    y_this = _daily_cert_counts_for_week(rows, manual_certs, week_sun, week_sun + timedelta(days=6))
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
        title="",
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


def _fig_avg_week_mean_bars(rows, manual_certs, week_sun, today_d):
    """지난주(일~토) vs 이번주(일~오늘) 일평균 막대. 이번주 < 지난주 #4E6FFF, > 이면 #FF5050, 같으면 파랑."""
    prev_sun = week_sun - timedelta(days=7)
    y_last = _daily_cert_counts_for_week(rows, manual_certs, prev_sun, prev_sun + timedelta(days=6))
    y_this = _daily_cert_counts_for_week(rows, manual_certs, week_sun, week_sun + timedelta(days=6))
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
        title="",
        showlegend=False,
        height=360,
        margin=dict(t=16, b=48, l=24, r=24),
        yaxis=dict(range=[0, max(v_last, v_this, 1) * 1.28], showgrid=True, title=None),
        xaxis=dict(title=None),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _serialize_archive_table_rows(rows_tuples):
    """아카이브 JSON은 3요소 셀만 저장 (호환)."""
    out = []
    for row_label, dc, cnt in rows_tuples:
        slim = []
        for cell in dc:
            if isinstance(cell, (list, tuple)) and len(cell) >= 3:
                v, c, t = cell[0], cell[1], cell[2]
                slim.append([v, bool(c), (t or "")])
            else:
                slim.append(["", False, ""])
        out.append([row_label, slim, cnt])
    return out


def _reconcile_archive_against_live(archive_list, cafe_rows, manual_certs):
    """지난 주 탭용: 저장된 각 주 table_rows와 현재 rows+수동 집계를 OR 합쳐 파일에 다시 저장(누적·유실 방지)."""
    if not archive_list:
        return
    changed = False
    for entry in archive_list:
        ws = entry.get("week_sun")
        if not ws:
            continue
        try:
            sun_d = datetime.strptime(ws, "%Y-%m-%d").date()
        except Exception:
            continue
        sat_d = sun_d + timedelta(days=6)
        live = _build_table_rows_for_week(cafe_rows, manual_certs, sun_d, sat_d)
        ser_old = entry.get("table_rows") or []
        merged = merge_live_and_snapshot_week_rows(live, ser_old)
        new_ser = _serialize_archive_table_rows(merged)
        if new_ser != ser_old:
            entry["table_rows"] = new_ser
            changed = True
    if changed:
        _save_archive(archive_list)


# 현재 주 테이블 생성 및 지난 주 아카이브 (매주 일요일 00:00에 넘어간 주는 아카이브에 추가)
table_rows = _build_table_rows_for_week(cafe_rows, st.session_state.get("manual_certs", []), week_sun, week_sat)
archive = _load_archive()
prev_sun = week_sun - timedelta(days=7)
prev_sat = week_sat - timedelta(days=7)
existing_suns = {a.get("week_sun") for a in archive if a.get("week_sun")}
if prev_sun.isoformat() not in existing_suns:
    table_prev = _build_table_rows_for_week(cafe_rows, st.session_state.get("manual_certs", []), prev_sun, prev_sat)
    period_prev = f"{prev_sun.month}월 {prev_sun.day}일 ({WEEKDAY_NAMES[prev_sun.weekday()]}) ~ {prev_sat.month}월 {prev_sat.day}일 ({WEEKDAY_NAMES[prev_sat.weekday()]})"

    archive.append({
        "week_sun": prev_sun.isoformat(),
        "week_sat": prev_sat.isoformat(),
        "period_label": period_prev,
        "table_rows": _serialize_archive_table_rows(table_prev),
    })
    _save_archive(archive)

_reconcile_archive_against_live(archive, cafe_rows, st.session_state.get("manual_certs", []))

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
            f'<div><span class="kpi-value" style="color:#ef4444;">{under_three_count}</span><span class="kpi-unit">명</span>'
            f'<span class="kpi-unit" style="margin-left:0;"> / {len(NAME_ID_LIST)}명</span></div></div>',
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
            if st.button("‹", key="graph_prev", disabled=st.session_state["graph_view_mode"] == "realtime"):
                st.session_state["graph_view_mode"] = "realtime"
                st.rerun()
        with ncol:
            if st.button("›", key="graph_next", disabled=st.session_state["graph_view_mode"] == "avg"):
                st.session_state["graph_view_mode"] = "avg"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    if st.session_state["graph_view_mode"] == "realtime":
        _fig_rt_top = _fig_realtime_exercise_lines(
            cafe_rows, st.session_state.get("manual_certs", []), week_sun, today
        )
        st.plotly_chart(_fig_rt_top, width="stretch", key="weekly_rt_line_top")
    else:
        _fig_avg_top = _fig_avg_week_mean_bars(
            cafe_rows, st.session_state.get("manual_certs", []), week_sun, today
        )
        st.plotly_chart(_fig_avg_top, width="stretch", key="weekly_bar_mean_top")

with top_right:
    top3_html = '<div class="top3-card"><h4 style="margin:0 0 8px 0;">이번주 Top3</h4>'
    sorted_by_count = sorted(table_rows, key=lambda x: -x[2])
    top3_list = [(label, cnt) for label, _, cnt in sorted_by_count if cnt > 0]
    from collections import OrderedDict
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

# ----- 탭: 운동인증 현황 / 지난 운동 인증 기록 -----
st.markdown(
    '<div class="weekly-tab-intro">'
    '<div class="weekly-tab-title">운동 인증 대시보드</div>'
    '<div class="weekly-tab-subtitle">이번주에 운동인증을 한 인원들을 한눈에 파악가능합니다. 지난 운동 기록도 조회가능합니다.</div>'
    '</div>',
    unsafe_allow_html=True,
)
tab_weekly, tab_archive = st.tabs(["운동인증 현황", "지난 운동 인증 기록"])

def _fmt_date(d):
    return f"{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})"


def _cell_six(cell):
    """셀을 (val, checked, ctype, dim_manual, del_kind, del_idx)로 정규화."""
    if not isinstance(cell, (list, tuple)):
        return ("", False, None, False, None, None)
    c = list(cell) + [None] * 6
    dk, di = c[4], c[5]
    if dk is not None and di is not None:
        try:
            di = int(di)
        except (TypeError, ValueError):
            dk, di = None, None
    else:
        dk, di = None, None
    return (c[0], bool(c[1]), c[2], bool(c[3]), dk, di)


def _cell_head_three(cell):
    """병합/스냅샷 셀에서 표시용 (val, checked, type)만."""
    if not isinstance(cell, (list, tuple)) or len(cell) < 3:
        return ("", False, None)
    return (cell[0], bool(cell[1]), cell[2])


def _cell_crawl_ids(cell):
    if isinstance(cell, (list, tuple)) and len(cell) > 6 and isinstance(cell[6], list):
        return list(cell[6])
    return []


def _archive_rows_with_manual_delete_meta(merged_rows, live_rows):
    """아카이브용: 병합 표시(스냅샷+라이브) + 해당 칸이 수동 전용이면 딤·삭제 메타 유지."""
    empty = ("", False, None, False, None, None, [])
    out = []
    for row_m, row_l in zip(merged_rows, live_rows):
        rl_m, dc_m, _ = row_m
        rl_l, dc_l, _ = row_l
        new_dc = []
        if rl_m != rl_l:
            for cm in dc_m:
                vm, cchk, tm = _cell_head_three(cm)
                new_dc.append((vm, cchk, tm, False, None, None, []) if cchk else empty)
        else:
            for cm, cl in zip(dc_m, dc_l):
                vm, cm_chk, tm = _cell_head_three(cm)
                _, cl_chk, tl, dim_l, dk_l, di_l = _cell_six(cl)
                cr = _cell_crawl_ids(cl)
                if not cm_chk:
                    new_dc.append(empty)
                elif (
                    cl_chk
                    and tm is not None
                    and tl is not None
                    and tm == tl
                    and dim_l
                    and dk_l in ("b", "e")
                    and di_l is not None
                ):
                    new_dc.append((vm, cm_chk, tm, True, dk_l, di_l, cr))
                else:
                    new_dc.append((vm, cm_chk, tm, False, None, None, cr))
        cnt = sum(1 for c in new_dc if _cell_six(c)[1])
        out.append((rl_m, new_dc, cnt))
    return out


def _render_week_table_html(
    table_rows_arg,
    week_dates_arg,
    apply_red_highlight=False,
    highlight_under_3_always=False,
    interactive_manual_delete=False,
    interactive_crawl_exclude=False,
):
    """테이블 HTML. 수동 전용 칸 딤·× / 크롤만 반영된 칸은 호버 ×로 제외 목록 추가."""
    sticky_th_style = "padding:6px 10px; border:1px solid #ddd; background:#ffffff;"
    header_cells = "".join(
        f'<th style="{sticky_th_style}">{_fmt_date(d)}</th>' for d in week_dates_arg
    )
    header_cells += f'<th style="{sticky_th_style}">비고</th>'
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
        for cell in day_cells:
            val, checked, cell_type, dim_manual, del_kind, del_idx = _cell_six(cell)
            crawl_ids = _cell_crawl_ids(cell)
            if checked and cell_type == "bible":
                inner_bg = f"background-color:{BIBLE_BG}; color:{BIBLE_TEXT};"
            elif checked and cell_type == "exercise":
                inner_bg = f"background-color:{CHECK_BLUE}; color:#FFFFFF; font-weight:700;"
            else:
                cells.append('<td style="padding:6px 10px; border:1px solid #ddd;"></td>')
                continue
            if (
                interactive_manual_delete
                and dim_manual
                and del_kind in ("b", "e")
                and del_idx is not None
            ):
                href = _mdel_href(del_kind, del_idx)
                wrap_cls = "manual-cert-wrap dimmed"
                cells.append(
                    f'<td style="padding:0; border:1px solid #ddd; vertical-align:middle;">'
                    f'<div class="{wrap_cls}" style="padding:6px 10px; {inner_bg} text-align:center;">'
                    f'<span class="manual-cert-inner">{val}</span>'
                    f'<a class="manual-del-x" href="{href}" target="_top" rel="noopener noreferrer" title="수동 인증 삭제">×</a>'
                    f"</div></td>"
                )
            elif (
                interactive_crawl_exclude
                and crawl_ids
                and not dim_manual
            ):
                chref = _cdel_href(crawl_ids)
                cells.append(
                    f'<td style="padding:0; border:1px solid #ddd; vertical-align:middle;">'
                    f'<div class="crawl-exclude-wrap" style="padding:6px 10px; {inner_bg} text-align:center;">'
                    f"<span>{val}</span>"
                    f'<a class="crawl-exclude-x" href="{chref}" target="_top" rel="noopener noreferrer" '
                    f'title="크롤 글 대시보드에서 제외">×</a>'
                    f"</div></td>"
                )
            else:
                if dim_manual and not interactive_manual_delete:
                    inner = (
                        f'<div class="manual-cert-wrap dimmed" style="padding:6px 10px; {inner_bg} '
                        f'text-align:center;"><span class="manual-cert-inner">{val}</span></div>'
                    )
                    cells.append(
                        f'<td style="padding:0; border:1px solid #ddd; vertical-align:middle;">{inner}</td>'
                    )
                else:
                    if cell_type == "bible":
                        cells.append(
                            f'<td style="padding:6px 10px; border:1px solid #ddd; background-color:{BIBLE_BG}; '
                            f'color:{BIBLE_TEXT}; text-align:center;">{val}</td>'
                        )
                    else:
                        cells.append(
                            f'<td style="padding:6px 10px; border:1px solid #ddd; background-color:{CHECK_BLUE}; color:#FFFFFF; font-weight:700; '
                            f'text-align:center;">{val}</td>'
                        )
        remarks_style = "padding:6px 10px; border:1px solid #ddd; text-align:center;"
        if is_under_3:
            remarks_style += f" background-color:{ROW_HIGHLIGHT_UNDER_3};"
        cells.append(f'<td style="{remarks_style}">{count}회</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="center-data week-table-wrap">'
        '<div class="week-table-sticky-head">'
        '<table style="border-collapse:separate; border-spacing:0; width:100%; table-layout:fixed; font-size:14px;">'
        f'<thead><tr><th style="{sticky_th_style}">실명 <span class="id-medium">(아이디)</span></th>{header_cells}</tr></thead>'
        "</table></div>"
        '<table style="border-collapse:separate; border-spacing:0; width:100%; table-layout:fixed; font-size:14px;">'
        "<tbody>" + "".join(body_rows) + "</tbody>"
        "</table></div>"
    )

with tab_weekly:
    st.caption(period_str)
    _allow_manual_ui = _manual_cert_ui_allowed()
    week_table_html = _render_week_table_html(
        table_rows,
        week_dates,
        apply_red_highlight=True,
        interactive_manual_delete=_allow_manual_ui,
        interactive_crawl_exclude=_allow_manual_ui,
    )
    st.markdown(week_table_html, unsafe_allow_html=True)
    _cap_weekly = (
        "하루에 여러 번 올려도 1회로 인정합니다. 금요일 00:00~토요일 23:59 구간에서 주 3회 미만 시 이름·비고란을 연한 빨간색으로 표시합니다."
    )
    if _allow_manual_ui:
        _cap_weekly += (
            " **수동으로 추가한 칸**은 살짝 어둡게 보이며, 마우스를 올리면 **빨간 ×**로 해당 수동 인증만 삭제할 수 있습니다. "
            "다른 기기(같은 Wi‑Fi)에서 접속해 삭제 링크를 쓰는 경우 `STREAMLIT_APP_BASE_URL`을 그 기기에서 열 수 있는 주소로 설정하세요. "
            "**자동 크롤만 반영된 칸**에는 마우스를 올리면 **회색 ×**가 나와 대시보드·Push에서 해당 글을 제외할 수 있습니다. "
            "사이드바 **「크롤링 글 대시보드에서 제외」**로도 동일하게 설정할 수 있습니다."
        )
    st.caption(_cap_weekly)

    # 수동 인증 추가 (이번 주 표 바로 아래 — 로컬·비공개에서만)
    if _allow_manual_ui:
        with st.expander("수동 인증 추가"):
            opt = [f"{n} ({c})" for n, c in NAME_ID_LIST]
            sel = st.selectbox("아이디 선택", opt, key="manual_id")
            manual_date = st.date_input("날짜", value=today, key="manual_date")

            col_left, col_mid, col_right = st.columns([1, 1, 1])
            with col_left:
                manual_is_exercise = st.checkbox("운동", value=True, key="manual_is_exercise")
            with col_mid:
                manual_is_bible = st.checkbox("성경필사", value=False, key="manual_is_bible")
            with col_right:
                add_clicked = st.button("추가", type="primary")

            if add_clicked:
                name = NAME_ID_LIST[opt.index(sel)][0]
                st.session_state.setdefault("manual_certs", []).append(
                    {
                        "name": name,
                        "date": manual_date,
                        "exercise": manual_is_exercise,
                        "bible": manual_is_bible,
                    }
                )
                _save_manual_certs(st.session_state["manual_certs"])
                kinds = []
                if manual_is_exercise:
                    kinds.append("운동")
                if manual_is_bible:
                    kinds.append("성경필사")
                kind_str = ", ".join(kinds) if kinds else "인증"
                st.success(f"{sel} — {manual_date} ({kind_str}) 추가됨")
                st.rerun()


with tab_archive:
    _ama = _manual_cert_ui_allowed()
    if _ama:
        st.caption(
            "지난 주간 운동 인증 기록입니다. 각 주에서 **수동 인증 추가**·**수동 전용 칸 빨간 × 삭제**·**크롤만 반영된 칸 회색 × 제외**가 가능합니다. "
            "웹 반영은 **웹 대시보드에 반영 (Push만)** 또는 데이터 가져오기 후 자동 Push로 해 주세요. "
            "주 3회 미만 인원은 이름·비고란 연한 빨강 표시입니다."
        )
    else:
        st.caption(
            "지난 주간 운동 인증 기록입니다. 공개 대시보드에서는 수동 인증 추가·삭제는 제공하지 않습니다. "
            "주 3회 미만 인원은 이름·비고란 연한 빨강 표시입니다."
        )

    # 수동 인증 추가 성공 메시지 (rerun 후에도 상단에 표시)
    _msg = st.session_state.pop("manual_add_success_archive_msg", None)
    if _msg:
        st.success(_msg)

    if not archive:
        st.info("아직 아카이브된 주간 기록이 없습니다. 일요일 00:00 이후 첫 조회 시 이전 주가 자동으로 쌓입니다.")
    else:
        # 추가 후 해당 주 아코디언·수동 인증 열린 상태 유지 (한 번 표시 후 제거)
        expand_week = st.session_state.pop("archive_expanded_week", None)
        expand_manual = st.session_state.pop("manual_add_expanded_week", None)

        # 최신 주가 위에 오도록 역순 (아카이브는 과거→최신 순으로 쌓임)
        for idx, entry in enumerate(reversed(archive)):
            week_sun_s = entry.get("week_sun") or ""
            period_label = entry.get("period_label") or f"{week_sun_s} 주간"
            try:
                sun_d = datetime.strptime(week_sun_s, "%Y-%m-%d").date()
            except Exception:
                sun_d = week_sun
            sat_d = sun_d + timedelta(days=6)
            live_w = _build_table_rows_for_week(cafe_rows, st.session_state.get("manual_certs", []), sun_d, sat_d)
            merged_w = merge_live_and_snapshot_week_rows(live_w, entry.get("table_rows") or [])
            week_dates_arch = [sun_d + timedelta(days=i) for i in range(7)]
            if _ama:
                hybrid_arch = _archive_rows_with_manual_delete_meta(merged_w, live_w)
                table_html = _render_week_table_html(
                    hybrid_arch,
                    week_dates_arch,
                    apply_red_highlight=False,
                    highlight_under_3_always=True,
                    interactive_manual_delete=True,
                    interactive_crawl_exclude=True,
                )
            else:
                table_html = _render_week_table_html(
                    merged_w,
                    week_dates_arch,
                    apply_red_highlight=False,
                    highlight_under_3_always=True,
                    interactive_manual_delete=False,
                )
            outer_expanded = expand_week == week_sun_s
            with st.expander(f"📅 {period_label}", expanded=outer_expanded):
                st.markdown(table_html, unsafe_allow_html=True)
                if _ama:
                    st.caption(
                        "(크롤·수동 + 저장 스냅샷 합산 · 유실 방지) · 수동만 넣은 칸: 어둡게, 호버 시 빨간 × / 크롤만: 호버 시 회색 × 제외"
                    )
                else:
                    st.caption("(크롤·수동 + 저장 스냅샷 합산 · 유실 방지)")
                _render_top3_section(
                    merged_w,
                    f"{period_label} 인증 TOP3",
                    empty_msg="해당 주 인증 데이터가 없습니다.",
                )
                if _ama:
                    inner_expanded = expand_manual == week_sun_s
                    with st.expander("✏️ 수동 인증 추가", expanded=inner_expanded):
                        opt_ar = [f"{n} ({c})" for n, c in NAME_ID_LIST]
                        sel_ar = st.selectbox("아이디 선택", opt_ar, key=f"manual_arch_{idx}_id")
                        manual_date_ar = st.date_input("날짜", value=sun_d, key=f"manual_arch_{idx}_date")
                        col_a, col_b, col_c = st.columns([1, 1, 1])
                        with col_a:
                            manual_ex_ar = st.checkbox("운동", value=True, key=f"manual_arch_{idx}_ex")
                        with col_b:
                            manual_bible_ar = st.checkbox("성경필사", value=False, key=f"manual_arch_{idx}_bible")
                        with col_c:
                            add_ar_clicked = st.button("추가", type="primary", key=f"manual_arch_{idx}_btn")
                        if add_ar_clicked:
                            name_ar = NAME_ID_LIST[opt_ar.index(sel_ar)][0]
                            st.session_state.setdefault("manual_certs", []).append({
                                "name": name_ar,
                                "date": manual_date_ar,
                                "exercise": manual_ex_ar,
                                "bible": manual_bible_ar,
                            })
                            _save_manual_certs(st.session_state["manual_certs"])
                            kinds_ar = []
                            if manual_ex_ar:
                                kinds_ar.append("운동")
                            if manual_bible_ar:
                                kinds_ar.append("성경필사")
                            st.session_state["manual_add_success_archive_msg"] = (
                                f"{sel_ar} — {manual_date_ar} ({', '.join(kinds_ar) or '인증'}) 추가됨"
                            )
                            st.session_state["archive_expanded_week"] = week_sun_s
                            st.session_state["manual_add_expanded_week"] = week_sun_s
                            st.rerun()

st.caption("해당 페이지는 읽기 전용페이지입니다. 매일 19~23시 정각에 최신화됩니다.")
