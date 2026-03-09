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
    .update-badge { display: inline-block; background: #f0f0f0; border: 1px solid #ddd; border-radius: 6px; padding: 4px 12px; font-size: 0.85rem; color: #555; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)

NAME_ID_LIST = [
    ("최수겸", "Sue"), ("최수림", "프수"), ("강민찬", "김보람아님"),
    ("곽민제", "곽카몰리"), ("김보람", "김봚"), ("김예덕", "예덕"),
    ("박건우", "베건이"), ("박성훈", "박성훈"), ("박예서", "바게서"),
    ("서민혁", "중화동고라니"), ("서지우", "쥬"), ("서희진", "희진"),
    ("심윤교", "윤교"), ("안수빈", "수비니"), ("유영현", "TIMYOU"),
    ("이건희", "R거U니N"), ("이찬우", "콜드가우"),
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
    "콜드카우": "콜드가우", "민찬": "김보람아님", "민찬이": "김보람아님",
    "베이비러너": "Sue", "오수완": "프수", "수완": "프수", "timyou": "TIMYOU",
})


def _parse_naver_date(date_str):
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
    if author and any(author == cid for _, cid in NAME_ID_LIST):
        return author
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
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    if not os.path.isfile(data_path):
        return [], ""
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return [], ""
    if isinstance(payload, list):
        return payload, ""
    if isinstance(payload, dict):
        return payload.get("rows", []), payload.get("last_updated", "")
    return [], ""


st.title("NEW START 운동 인증 대시보드")
cafe_rows, last_updated = _load_data()

if last_updated:
    st.markdown(f'<span class="update-badge">마지막 업데이트: {last_updated}</span>', unsafe_allow_html=True)

if not cafe_rows:
    st.info("데이터가 아직 업로드되지 않았습니다. data.json 파일을 추가해 주세요.")
    st.stop()

st.markdown("---")
st.subheader("주간 운동 인증 현황")

today = datetime.now().date()
days_since_sun = (today.weekday() + 1) % 7
week_sun = today - timedelta(days=days_since_sun)
week_sat = week_sun + timedelta(days=6)
week_dates = [week_sun + timedelta(days=i) for i in range(7)]
period_str = f"이번 주 기간: {week_sun.month}월 {week_sun.day}일 ({WEEKDAY_NAMES[week_sun.weekday()]}) ~ {week_sat.month}월 {week_sat.day}일 ({WEEKDAY_NAMES[week_sat.weekday()]})"
st.caption(period_str)

posted = {}
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
    for name, cid in NAME_ID_LIST:
        if author == cid or (author and cid and author.strip() == cid.strip()):
            posted[(name, d)] = True
            break

table_rows = []
for name, cid in NAME_ID_LIST:
    row_label = f"{name} ({cid})"
    count = 0
    day_cells = []
    for d in week_dates:
        if posted.get((name, d)):
            day_cells.append(("✓", True))
            count += 1
        else:
            day_cells.append(("", False))
    table_rows.append((row_label, day_cells, count))


def _fmt_date(d):
    return f"{d.month}/{d.day}({WEEKDAY_NAMES[d.weekday()]})"


header_cells = "".join(
    f'<th style="padding:6px 10px; border:1px solid #ddd;">{_fmt_date(d)}</th>' for d in week_dates
)
header_cells += '<th style="padding:6px 10px; border:1px solid #ddd;">비고</th>'

is_friday = today.weekday() == 4
body_rows = []
for row_label, day_cells, count in table_rows:
    row_bg = (ROW_HIGHLIGHT_UNDER_3 if count < 3 else "") if is_friday else ""
    tr_style = f"background-color:{row_bg};" if row_bg else ""
    cells = [f'<td style="padding:6px 10px; border:1px solid #ddd; font-weight:bold;">{row_label}</td>']
    for val, checked in day_cells:
        if checked:
            cells.append(f'<td style="padding:6px 10px; border:1px solid #ddd; background-color:{CHECK_GREEN}; text-align:center;">✓</td>')
        else:
            cells.append(f'<td style="padding:6px 10px; border:1px solid #ddd;"></td>')
    cells.append(f'<td style="padding:6px 10px; border:1px solid #ddd; text-align:center;">{count}회</td>')
    body_rows.append(f'<tr style="{tr_style}">' + "".join(cells) + "</tr>")

week_table_html = (
    '<div class="center-data week-table-wrap">'
    '<table style="border-collapse:collapse; width:100%; max-width:900px; font-size:14px;">'
    f'<thead><tr><th style="padding:6px 10px; border:1px solid #ddd;">실명 (아이디)</th>{header_cells}</tr></thead>'
    "<tbody>" + "".join(body_rows) + "</tbody>"
    "</table>"
    '<p style="margin-top:8px; font-size:12px; color:#666;">금요일 기준 주 3회 미만 시 해당 행을 연한 빨간색으로 표시합니다.</p>'
    "</div>"
)
st.markdown(week_table_html, unsafe_allow_html=True)

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

st.markdown("---")
st.caption("이 페이지는 읽기 전용입니다. 데이터는 관리자가 주기적으로 업데이트합니다.")
