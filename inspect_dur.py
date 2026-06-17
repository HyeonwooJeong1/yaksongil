"""
수집한 DUR 성분정보 구조 확인 + 우리 약가마스터와 매핑 가능성 점검.
실행: python inspect_dur.py
"""
import json
from collections import Counter
from pathlib import Path

from app.database import get_conn, init_db

DUR_DIR = Path("mobile_reader/data/dur_ingredient")

# 1) 병용금기 샘플 필드 구조
taboo = json.loads((DUR_DIR / "usjnt_taboo.json").read_text(encoding="utf-8"))
print("=" * 60)
print("병용금기 item 필드:")
print("=" * 60)
sample = taboo["items"][0]
for k, v in sample.items():
    print(f"  {k:24s}: {str(v)[:50]}")

# 2) 노인주의 샘플
odsn = json.loads((DUR_DIR / "odsn_atent.json").read_text(encoding="utf-8"))
print("\n" + "=" * 60)
print("노인주의 item 필드:")
print("=" * 60)
for k, v in odsn["items"][0].items():
    print(f"  {k:24s}: {str(v)[:50]}")

# 3) DUR에 등장하는 한글 성분명 집합
dur_names = set()
for item in taboo["items"]:
    if item.get("INGR_KOR_NAME"):
        dur_names.add(item["INGR_KOR_NAME"])
    if item.get("MIXTURE_INGR_KOR_NAME"):
        dur_names.add(item["MIXTURE_INGR_KOR_NAME"])
print(f"\n병용금기 등장 고유 성분명: {len(dur_names)}개")
print("  예시:", list(dur_names)[:10])

# 4) 우리 약가마스터 약물명과 매칭 테스트
init_db()
with get_conn() as conn:
    rows = conn.execute(
        "SELECT DISTINCT short_name FROM drug_master WHERE short_name IS NOT NULL"
    ).fetchall()
master_names = set(r["short_name"] for r in rows)
print(f"\n약가마스터 고유 short_name: {len(master_names):,}개")

# DUR 성분명이 약가마스터 short_name에 포함되는지 (부분매칭)
matched = 0
sample_match = []
for dn in dur_names:
    hit = any(dn in mn or mn in dn for mn in master_names)
    if hit:
        matched += 1
        if len(sample_match) < 10:
            sample_match.append(dn)
print(f"\nDUR 성분명 ↔ 약가마스터 매칭(부분): {matched}/{len(dur_names)}")
print("  매칭 예:", sample_match)

# 5) ORI 필드 구조 (제품명 연결)
print("\n" + "=" * 60)
print("ORI 필드 예시 (성분 → 제품 연결):")
print("=" * 60)
for item in taboo["items"][:3]:
    print(f"  {item.get('INGR_KOR_NAME')}: {item.get('ORI', '')[:80]}")
