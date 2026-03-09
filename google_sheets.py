# -*- coding: utf-8 -*-
"""
Google Sheets 읽기/쓰기 유틸리티.
gspread + 서비스 계정 JSON 인증을 사용한다.

인증 방식 (우선순위):
  1. Streamlit secrets  → st.secrets["gcp_service_account"] (Streamlit Cloud 배포용)
  2. 환경변수            → GOOGLE_SERVICE_ACCOUNT_JSON (JSON 파일 경로)
  3. 기본 파일           → 프로젝트 루트의 service_account.json
"""
import os
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "")
DATA_SHEET_NAME = "크롤링데이터"
META_SHEET_NAME = "메타"


def _get_credentials():
    """서비스 계정 인증 정보를 가져온다."""
    # 1) Streamlit secrets (Cloud 배포용)
    try:
        import streamlit as st
        sa = st.secrets["gcp_service_account"]
        info = dict(sa) if not isinstance(sa, dict) else sa
        return Credentials.from_service_account_info(info, scopes=_SCOPES)
    except Exception:
        pass

    # 2) 환경변수 경로
    env_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if env_path and os.path.isfile(env_path):
        return Credentials.from_service_account_file(env_path, scopes=_SCOPES)

    # 3) 기본 파일
    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_account.json")
    if os.path.isfile(default_path):
        return Credentials.from_service_account_file(default_path, scopes=_SCOPES)

    raise FileNotFoundError(
        "Google 서비스 계정 JSON을 찾을 수 없습니다. "
        "service_account.json 파일을 프로젝트 폴더에 넣거나 "
        "GOOGLE_SERVICE_ACCOUNT_JSON 환경변수를 설정해 주세요."
    )


def _open_spreadsheet(spreadsheet_id: str = ""):
    sid = spreadsheet_id or SPREADSHEET_ID
    if not sid:
        raise ValueError(
            "GOOGLE_SPREADSHEET_ID 환경변수를 설정하거나, "
            "함수 호출 시 spreadsheet_id를 전달해 주세요."
        )
    creds = _get_credentials()
    gc = gspread.authorize(creds)
    return gc.open_by_key(sid)


def _get_or_create_sheet(spreadsheet, name: str):
    try:
        return spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=200, cols=20)


def upload_rows(rows: list[dict], spreadsheet_id: str = "") -> str:
    """크롤링 결과(rows)를 구글 시트에 덮어쓴다. 성공 시 업데이트 시각 문자열 반환."""
    ss = _open_spreadsheet(spreadsheet_id)

    # --- 데이터 시트 ---
    ws = _get_or_create_sheet(ss, DATA_SHEET_NAME)
    headers = ["작성자", "제목", "날짜", "링크"]
    values = [headers]
    for r in rows:
        if not isinstance(r, dict):
            continue
        values.append([
            r.get("작성자", ""),
            r.get("제목", ""),
            r.get("날짜", ""),
            r.get("링크", ""),
        ])
    ws.clear()
    ws.update(range_name="A1", values=values)

    # --- 메타 시트 (마지막 업데이트 시각) ---
    meta = _get_or_create_sheet(ss, META_SHEET_NAME)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta.clear()
    meta.update(range_name="A1", values=[["last_updated"], [now_str]])

    return now_str


def download_rows(spreadsheet_id: str = "") -> tuple[list[dict], str]:
    """구글 시트에서 크롤링 데이터와 마지막 업데이트 시각을 읽어온다."""
    ss = _open_spreadsheet(spreadsheet_id)

    # 데이터
    ws = _get_or_create_sheet(ss, DATA_SHEET_NAME)
    all_values = ws.get_all_values()
    rows = []
    if len(all_values) > 1:
        headers = all_values[0]
        for row_vals in all_values[1:]:
            d = {}
            for i, h in enumerate(headers):
                d[h] = row_vals[i] if i < len(row_vals) else ""
            rows.append(d)

    # 메타
    last_updated = ""
    try:
        meta = ss.worksheet(META_SHEET_NAME)
        meta_vals = meta.get_all_values()
        if len(meta_vals) > 1:
            last_updated = meta_vals[1][0]
    except Exception:
        pass

    return rows, last_updated
