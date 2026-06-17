"""
DUR 품목정보 API 탐침 — 엔드포인트 확정 + 필드 구조 + 7종 건수.
품목정보는 제품(품목기준코드) 단위라 약가마스터와 직결.

실행: python probe_dur_prdlst.py
"""
import os
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("MFDS_API_KEY", "").strip()

# 품목정보 서비스명 후보 (성분정보는 DURIrdntInfoService03였음)
BASES = [
    "https://apis.data.go.kr/1471000/DURPrdlstInfoService03",
    "https://apis.data.go.kr/1471000/DURPrdlstInfoService3",
]
# 병용금기 오퍼레이션 후보
OPS = ["getUsjntTabooInfoList03", "getUsjntTabooInfoList02", "getUsjntTabooInfoList"]


def call(base, op):
    url = f"{base}/{op}"
    params = {"serviceKey": KEY, "pageNo": 1, "numOfRows": 2, "type": "xml"}
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)


print(f"[INFO] 키 앞 8: {KEY[:8]}\n")
ok_url = None
for base in BASES:
    for op in OPS:
        code, body = call(base, op)
        is_ok = code == 200 and "resultCode" in body and "NORMAL" in body
        mark = "  <<< OK" if is_ok else ""
        print(f"[{code}] {base.split('/')[-1]}/{op}{mark}")
        if is_ok and not ok_url:
            ok_url = f"{base}/{op}"

if ok_url:
    print(f"\n[확정] {ok_url}\n")
    r = requests.get(ok_url, params={"serviceKey": KEY, "pageNo": 1, "numOfRows": 1, "type": "xml"}, timeout=15)
    root = ET.fromstring(r.content)
    total = root.findtext(".//totalCount")
    print(f"병용금기 totalCount: {total}")
    print("\n[item 필드 구조]")
    item = root.find(".//item")
    if item is not None:
        for c in item:
            print(f"  {c.tag:24s}: {str(c.text)[:50]}")
else:
    print("\n품목정보 OK 엔드포인트 못 찾음 — 후보 확대 필요")
