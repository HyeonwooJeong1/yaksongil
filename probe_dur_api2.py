"""
DUR 성분정보 API 2차 탐침.
403 후보 엔드포인트에 대해:
  - serviceKey 인코딩/디코딩 처리 방식 4가지
  - 응답 본문(에러 메시지)을 그대로 출력 → 진짜 원인 파악

실행: python probe_dur_api2.py
"""
import os
import urllib.parse

import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("MFDS_API_KEY", "").strip()

BASE = "https://apis.data.go.kr/1471000"
# 403이 떴던(=존재 유력) 엔드포인트들
ENDPOINTS = [
    "DURPrdlstInfoService03/getUsjntTabooInfoList03",
    "DURIrdntInfoService03/getUsjntTabooInfoList02",
    "DURPrdlstInfoService03/getUsjntTabooInfoList02",
]


def call(url, key_mode):
    """key_mode: 'raw'(그대로), 'unquote'(디코딩), 'quote'(인코딩), 'params'(requests에 맡김)"""
    base_params = "numOfRows=3&pageNo=1&type=json"
    if key_mode == "params":
        # requests가 serviceKey를 자동 인코딩
        full = f"{url}?{base_params}"
        return requests.get(full, params={"serviceKey": KEY}, timeout=15)
    elif key_mode == "raw":
        full = f"{url}?serviceKey={KEY}&{base_params}"
    elif key_mode == "unquote":
        full = f"{url}?serviceKey={urllib.parse.unquote(KEY)}&{base_params}"
    elif key_mode == "quote":
        full = f"{url}?serviceKey={urllib.parse.quote(KEY)}&{base_params}"
    return requests.get(full, timeout=15)


print(f"[INFO] 키 길이: {len(KEY)}, 앞 8: {KEY[:8]}\n")

for ep in ENDPOINTS:
    url = f"{BASE}/{ep}"
    print("=" * 64)
    print(ep)
    print("=" * 64)
    for mode in ("params", "raw", "unquote", "quote"):
        try:
            r = call(url, mode)
            body = r.text.replace("\n", " ")[:400]
            print(f"\n[{mode}] HTTP {r.status_code}")
            print(f"   {body}")
        except Exception as e:
            print(f"\n[{mode}] EXC {e}")
    print()
