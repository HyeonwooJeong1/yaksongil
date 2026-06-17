"""
DUR 성분정보 API 엔드포인트/필드 탐침.
여러 후보 서비스명을 시도해서 200 OK + JSON 구조를 찾는다.

실행: python probe_dur_api.py
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("MFDS_API_KEY", "").strip()
if not KEY:
    raise SystemExit("MFDS_API_KEY가 .env에 없습니다.")

# 후보 서비스 베이스명 (data.go.kr DUR 성분정보 계열)
SERVICE_CANDIDATES = [
    "DURPrdlstInfoService03",
    "DURPrdlstInfoService3",
    "DURPrdlstInfoService02",
    "DURPrdlstInfoService2",
    "DURIrdntInfoService03",
    "DURIrdntInfoService3",
    "DURIrdntInfoService02",
    "DURIrdntInfoService2",
    "DURIrdntInfoService",
]
# 병용금기 오퍼레이션 후보
OP_CANDIDATES = [
    "getUsjntTabooInfoList02",
    "getUsjntTabooInfoList2",
    "getUsjntTabooInfoList03",
    "getUsjntTabooInfoList",
]

BASE = "https://apis.data.go.kr/1471000"


def try_call(service, op):
    url = f"{BASE}/{service}/{op}"
    params = {
        "serviceKey": KEY,
        "numOfRows": 2,
        "pageNo": 1,
        "type": "json",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception as e:
        return None, f"EXC {e}"
    body = r.text[:300]
    return r.status_code, body


print(f"[INFO] 키 앞 8자리: {KEY[:8]}...\n")

# 모든 (service, op) 조합을 15개 워커로 병렬 호출
combos = [(svc, op) for svc in SERVICE_CANDIDATES for op in OP_CANDIDATES]
found = []

def probe(combo):
    svc, op = combo
    code, body = try_call(svc, op)
    ok = code == 200 and ("items" in body or '"item"' in body or "resultCode" in body)
    return svc, op, code, body, ok

with ThreadPoolExecutor(max_workers=15) as ex:
    futures = [ex.submit(probe, c) for c in combos]
    for fut in as_completed(futures):
        svc, op, code, body, ok = fut.result()
        flag = "  <<< 응답 OK 가능성" if ok else ""
        if ok:
            found.append((svc, op))
        print(f"[{code}] {svc}/{op}{flag}")
        if ok:
            print("      ↳ ", body.replace("\n", " ")[:200])

print()
if found:
    print("=" * 60)
    print("성공 후보:")
    for svc, op in found:
        print(f"  {BASE}/{svc}/{op}")
    # 첫 성공 후보의 전체 응답 구조 출력
    svc, op = found[0]
    url = f"{BASE}/{svc}/{op}"
    r = requests.get(url, params={"serviceKey": KEY, "numOfRows": 1, "pageNo": 1, "type": "json"}, timeout=15)
    try:
        data = r.json()
        print("\n[전체 JSON 구조 샘플]")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print("JSON 파싱 실패:", e)
        print(r.text[:1000])
else:
    print("성공 후보 없음 — 서비스명/오퍼레이션 후보를 더 넓혀야 함")
