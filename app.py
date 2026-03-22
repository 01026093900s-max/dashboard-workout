# -*- coding: utf-8 -*-
"""
NEW START 운동 인증 대시보드 — 외부 공유용 (읽기 전용)
data.json 파일에서 크롤링 데이터를 읽어 표시한다.
Hugging Face Spaces 또는 Streamlit Cloud에 배포 가능.
"""
import json
import os
import re

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
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 100%; }
    h1 { color: #000000 !important; font-weight: 700 !important; border: none !important; font-size: 1.75rem !important; margin-bottom: 0.25rem !important; }
    .main p { color: #333333; }
    .center-data { width: 100%; max-width: 900px; margin-left: 0; margin-right: auto; }
    .week-table-wrap { background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin: 0.5rem 0 1rem 0; }
    .week-table-wrap table { background: #ffffff; }
    .top3-badge { display: inline-block; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 0.9rem; margin-left: 8px; }
    .top3-1 { background: #D4AF37; color: #FFFFFF; }
    .top3-2 { background: #E5E4E2; color: #0D0D0D; }
    .top3-3 { background: #B87333; color: #FFFFFF; }
    .update-badge { display: inline-block; background: #f0f0f0; border: 1px solid #ddd; border-radius: 6px; padding: 4px 12px; font-size: 0.85rem; color: #555; margin-top: 4px; margin-bottom: 32px; }
    /* 탭: 선택 #000000 Bold 700, 비선택 #646464 Bold 700, 선택 탭 밑줄 4px #000000만 (초록/빨강 제거) */
    [data-testid="stTabs"] [role="tab"], [data-testid="stTabs"] button { font-weight: 700 !important; color: #646464 !important; border-bottom: none !important; }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"], [data-testid="stTabs"] button[aria-selected="true"] { color: #000000 !important; font-weight: 700 !important; border-bottom: 4px solid #000000 !important; border-bottom-color: #000000 !important; box-shadow: none !important; background: transparent !important; }
    [data-testid="stTabs"] [role="tabpanel"] { border: none !important; }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"] { background: transparent !important; border: none !important; border-bottom: none !important; }
</style>
""", unsafe_allow_html=True)

# ── 데이터 상수 ──
NAME_ID_LIST = [
    ("최수겸", "Sue"),
    ("최수림", "프수"),
    ("강민찬", "김보람아님"),
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
ROW_HIGHLIGHT_UNDER_3 = "#FFB3B3"
CHECK_GREEN = "#90EE90"

_TITLE_ALIASES = {}
for _n, _c in NAME_ID_LIST:
    _TITLE_ALIASES[_c.lower()] = _c
    _TITLE_ALIASES[_n] = _c
    if len(_n) >= 3:
        _TITLE_ALIASES[_n[1:]] = _c
_TITLE_ALIASES.update({
    "콜드가우": "콜드카우",
    "민찬": "김보람아님",
    "민찬이": "김보람아님",
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
        row_label = f"{name} ({cid})"
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
        day_cells = [(v, bool(c), (t if t else None)) for v, c, t in cells]
        out.append((row_label, day_cells, count))
    return out


def _merge_live_and_snapshot_week(rows_live, snap_deserialized):
    """지난 주 탭: rows로 다시 계산한 표 + 예전에 저장된 스냅샷을 칸 단위 OR 병합.
    rows에 과거 글이 잘려 나가도 스냅샷에 있던 ✓는 유지되고, 새로 크롤된 글도 반영된다."""
    if not snap_deserialized:
        return rows_live
    snap_by_label = {r[0]: r for r in snap_deserialized}
    merged = []
    for row_label, live_cells, _ in rows_live:
        snap_row = snap_by_label.get(row_label)
        if not snap_row:
            cnt = sum(1 for _, c, _ in live_cells if c)
            merged.append((row_label, live_cells, cnt))
            continue
        _, snap_cells, _ = snap_row
        mcells = []
        for i in range(7):
            lv, lc, lt = live_cells[i] if i < len(live_cells) else ("", False, None)
            sv, sc, st = snap_cells[i] if i < len(snap_cells) else ("", False, None)
            if lc:
                mcells.append((lv, lc, lt))
            elif sc:
                mcells.append((sv, sc, st))
            else:
                mcells.append(("", False, None))
        cnt = sum(1 for _, c, _ in mcells if c)
        merged.append((row_label, mcells, cnt))
    return merged


DATA_JSON_REMOTE_URL = os.environ.get(
    "DATA_JSON_REMOTE_URL",
    "https://raw.githubusercontent.com/01026093900s-max/dashboard-workout/main/data.json",
)


@st.cache_data(ttl=45, show_spinner="최신 데이터를 불러오는 중…")
def _fetch_remote_data_json(url: str):
    """Streamlit Cloud에서 배포 시점의 옛 data.json이 남는 문제를 피하기 위해 GitHub raw에서 주기적으로 읽는다."""
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

# ── 탭: 주간 운동 인증 현황 / 지난 운동 인증 기록 ──
tab_weekly, tab_archive = st.tabs(["주간 운동 인증 현황", "지난 운동 인증 기록"])

today = datetime.now().date()
days_since_sun = (today.weekday() + 1) % 7
week_sun = today - timedelta(days=days_since_sun)
week_sat = week_sun + timedelta(days=6)
week_dates = [week_sun + timedelta(days=i) for i in range(7)]
period_str = f"이번 주 기간: {week_sun.month}월 {week_sun.day}일 ({WEEKDAY_NAMES[week_sun.weekday()]}) ~ {week_sat.month}월 {week_sat.day}일 ({WEEKDAY_NAMES[week_sat.weekday()]})"

# 표 데이터: rows 전체에서 이번 주만 집계 (지난 주 탭도 동일 로직으로 재계산)
table_rows = _table_rows_for_week_range(cafe_rows, week_sun, week_sat)


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
                    f'<td style="padding:6px 10px; border:1px solid #ddd; background-color:{CHECK_GREEN}; text-align:center;">{val}</td>'
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
        '<table style="border-collapse:collapse; width:100%; max-width:900px; font-size:14px;">'
        f'<thead><tr><th style="padding:6px 10px; border:1px solid #ddd;">실명 (아이디)</th>{header_cells}</tr></thead>'
        "<tbody>" + "".join(body_rows) + "</tbody>"
        "</table></div>"
    )


with tab_weekly:
    st.caption(period_str)
    week_table_html = _render_week_table_html(table_rows, week_dates, apply_red_highlight=True)
    st.markdown(week_table_html, unsafe_allow_html=True)
    st.caption("하루에 여러 번 올려도 1회로 인정합니다. 금요일 00:00~토요일 23:59 구간에서 주 3회 미만 시 이름·비고란을 연한 빨간색으로 표시합니다.")

    st.markdown("---")
    st.subheader("이번주 인증 TOP3")
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
            names_str = ", ".join(bold_labels)
            st.markdown(
                f'**{r}등** {names_str} <span class="top3-badge {bc}">{cnt}회</span>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("이번 주 인증 데이터가 없습니다.")

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
st.capti
