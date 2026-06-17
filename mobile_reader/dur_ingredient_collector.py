"""
DUR 성분정보 7종 수집기 → 로컬 JSON 캐싱 (오프라인용).

엔드포인트: https://apis.data.go.kr/1471000/DURIrdntInfoService03/...
성분코드(INGR_CODE) 기준이라 우리 약가마스터 일반명코드와 연동 가능.

7종:
  1. 병용금기      getUsjntTabooInfoList02
  2. 노인주의      getOdsnAtentInfoList02
  3. 특정연령대금기 getSpcifyAgrdeTabooInfoList02
  4. 임부금기      getPwnmTabooInfoList02
  5. 용량주의      getCpctyAtentInfoList02
  6. 투여기간주의  getMdctnPdAtentInfoList02
  7. 효능군중복    getEfcyDplctInfoList02

실행:
  python -m mobile_reader.dur_ingredient_collector            # 7종 전체
  python -m mobile_reader.dur_ingredient_collector --check     # totalCount만 확인
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("MFDS_API_KEY", "").strip()

BASE = "https://apis.data.go.kr/1471000/DURIrdntInfoService03"
DATA_DIR = Path(__file__).parent / "data" / "dur_ingredient"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# (파일명, 오퍼레이션, 한글라벨)
DUR_TYPES = [
    ("usjnt_taboo",   "getUsjntTabooInfoList02",        "병용금기"),
    ("odsn_atent",    "getOdsnAtentInfoList02",         "노인주의"),
    ("agrde_taboo",   "getSpcifyAgrdeTabooInfoList02",  "특정연령대금기"),
    ("pwnm_taboo",    "getPwnmTabooInfoList02",         "임부금기"),
    ("cpcty_atent",   "getCpctyAtentInfoList02",        "용량주의"),
    ("mdctn_atent",   "getMdctnPdAtentInfoList02",      "투여기간주의"),
    ("efcy_dplct",    "getEfcyDplctInfoList02",         "효능군중복"),
]

NUM_ROWS = 100  # 페이지당 행 수


def fetch_page(op: str, page: int) -> tuple[int, list[dict]]:
    """한 페이지 호출 → (totalCount, items). XML 파싱."""
    url = f"{BASE}/{op}"
    params = {
        "serviceKey": KEY,
        "pageNo": page,
        "numOfRows": NUM_ROWS,
        "type": "xml",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    result_code = root.findtext(".//resultCode")
    if result_code not in (None, "00"):
        msg = root.findtext(".//resultMsg")
        raise RuntimeError(f"API 오류 [{result_code}] {msg}")

    total = int(root.findtext(".//totalCount") or "0")
    items = []
    for item in root.findall(".//item"):
        d = {child.tag: (child.text or "").strip() for child in item}
        items.append(d)
    return total, items


def collect_type(file_key: str, op: str, label: str, workers: int) -> dict:
    """한 DUR 종류 전체 수집 (병렬 페이지)."""
    # 1페이지로 totalCount 파악
    total, first_items = fetch_page(op, 1)
    if total == 0:
        print(f"  [{label}] 데이터 없음")
        return {"label": label, "total": 0, "items": []}

    pages = (total + NUM_ROWS - 1) // NUM_ROWS
    print(f"  [{label}] 전체 {total:,}건 / {pages}페이지 — 병렬 수집...")

    all_items = list(first_items)
    if pages > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(fetch_page, op, p): p for p in range(2, pages + 1)}
            done = 1
            for fut in as_completed(futures):
                try:
                    _, items = fut.result()
                    all_items.extend(items)
                except Exception as e:
                    print(f"    [WARN] {label} 페이지 실패: {e}", file=sys.stderr)
                done += 1
                if done % 10 == 0:
                    print(f"     {done}/{pages} 페이지...")

    out = {"label": label, "total": total, "items": all_items}
    path = DATA_DIR / f"{file_key}.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"  [{label}] 저장: {path.name} ({len(all_items):,}건, {path.stat().st_size/1024:.0f} KB)")
    return out


def check_counts():
    """7종 totalCount만 확인 (일일 한도 계산용)."""
    print("=" * 60)
    print("  DUR 성분정보 7종 — totalCount 확인")
    print("=" * 60)
    grand = 0
    for file_key, op, label in DUR_TYPES:
        try:
            total, _ = fetch_page(op, 1)
            pages = (total + NUM_ROWS - 1) // NUM_ROWS
            grand += total
            print(f"  {label:<14} {total:>7,}건  ({pages}페이지)")
        except Exception as e:
            print(f"  {label:<14} 오류: {e}")
    print("-" * 60)
    print(f"  {'합계':<14} {grand:>7,}건")
    print(f"  예상 호출 수: {sum((fetch_page(op,1)[0]+NUM_ROWS-1)//NUM_ROWS for _,op,_ in DUR_TYPES):,}회")
    print(f"  (일일 한도 10,000건 — {'안전' if grand < 10000*NUM_ROWS else '주의'})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="totalCount만 확인")
    parser.add_argument("--workers", type=int, default=15, help="동시 호출 수")
    args = parser.parse_args()

    if not KEY:
        print("[ERROR] MFDS_API_KEY가 .env에 없습니다.", file=sys.stderr)
        sys.exit(1)

    if args.check:
        check_counts()
        return

    print("=" * 60)
    print("  DUR 성분정보 7종 수집 시작")
    print("=" * 60)
    summary = []
    for file_key, op, label in DUR_TYPES:
        out = collect_type(file_key, op, label, args.workers)
        summary.append((label, out["total"]))

    print()
    print("=" * 60)
    print("[OK] 수집 완료")
    for label, total in summary:
        print(f"  {label:<14} {total:>7,}건")
    print(f"  저장 위치: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
