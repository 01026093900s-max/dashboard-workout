# -*- coding: utf-8 -*-
"""
NEW START 운동 인증 대시보드 — 외부 공유용 (읽기 전용)
data.json 파일에서 크롤링 데이터를 읽어 표시한다.
Hugging Face Spaces 또는 Streamlit Cloud에 배포 가능.
"""
import json
import os
import re
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
    /* 탭 라벨: Bold, 색상 #000000 */
    [data-testid="stTabs"] [role="tab"] { font-weight: 700 !important; color: #000000 !important; }
    [data-testid="stTabs"] button { font-weight: 700 !important; color: #000000 !important; }
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
    return None


def _author_from_row(r):
    author = (r.get("작성자") or "").strip()
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


def _load_data():
    """data.json 파일에서 크롤링 데이터와 아카이브를 읽는다."""
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    if not os.path.isfile(data_path):
        return [], "", []
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return [], "", []

    if isinstance(payload, list):
        return payload, "", []
    if isinstance(payload, dict):
        rows = payload.get("rows", [])
        updated = payload.get("last_updated", "")
        archive = payload.get("archive", [])
        return rows, updated, archive
    return [], "", []


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

posted = {}


def _is_bible_copy(row):
    title = (row.get("제목") or "").strip()
    return "필사" in title


for r in cafe_rows:
    if not isinstance(r, dict):
        continue
    author = _author_from_row(r)
    date_str = (r.get("날짜") or "").strip()
    dt = _parse_naver_date(date_str) if date_str else None
    if dt is None:
        continue
    d = dt.date()
    if d < week_sun or d > week_dates[-1]:
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
    for d in week_dates:
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


def _fmt_date(d):
    return f"{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})"


def _render_week_table_html(table_rows_arg, week_dates_arg, apply_red_highlight=False):
    header_cells = "".join(
        f'<th style="padding:6px 10px; border:1px solid #ddd;">{_fmt_date(d)}</th>' for d in week_dates_arg
    )
    header_cells += '<th style="padding:6px 10px; border:1px solid #ddd;">비고</th>'
    BIBLE_BG = "#FFE98F"
    BIBLE_TEXT = "#0D0D0D"
    is_red_window = apply_red_highlight and today.weekday() in (4, 5)
    body_rows = []
    for row_label, day_cells, count in table_rows_arg:
        is_under_3 = is_red_window and count < 3
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
    st.caption("지난 주간 운동 인증 기록입니다. 조회만 가능하며 수정할 수 없습니다. 매주 일요일 00:00에 새 주로 전환됩니다.")
    if not archive:
        st.info("아직 아카이브된 주간 기록이 없습니다.")
    else:
        for entry in reversed(archive):
            week_sun_s = entry.get("week_sun") or ""
            period_label = entry.get("period_label") or f"{week_sun_s} 주간"
            ser = entry.get("table_rows") or []
            rows_restored = []
            for row_label, cells, count in ser:
                day_cells = [(v, bool(c), (t if t else None)) for v, c, t in cells]
                rows_restored.append((row_label, day_cells, count))
            try:
                sun_d = datetime.strptime(week_sun_s, "%Y-%m-%d").date()
            except Exception:
                sun_d = week_sun
            week_dates_arch = [sun_d + timedelta(days=i) for i in range(7)]
            table_html = _render_week_table_html(rows_restored, week_dates_arch, apply_red_highlight=False)
            with st.expander(f"📅 {period_label}", expanded=False):
                st.markdown(table_html, unsafe_allow_html=True)
                st.caption("(해당 주간 스냅샷 · 수정 불가)")

st.markdown("---")
st.caption("이 페이지는 읽기 전용입니다. 데이터는 관리자가 주기적으로 업데이트합니다. 매주 일요일 00:00에 새 주로 전환됩니다.")
