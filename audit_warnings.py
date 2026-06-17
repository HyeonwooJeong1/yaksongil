"""
오분류 감사 스크립트.
약가마스터 CSV의 모든 약을 실제 분류 로직에 태워서,
warning으로 잡히는 약물을 (위험키워드 × ATC) 별로 집계하고 샘플을 보여준다.

실행: python audit_warnings.py
"""
import csv
from collections import defaultdict
from pathlib import Path

from app.services.external.category_mapper import is_herbal, map_intl_atc

csv.field_size_limit(2**31 - 1)
CSV = next(Path(".").glob("건강보험심사평가원_약가마스터_의약품표준코드_*.csv"))

# (risk_keyword, atc4) -> [제품명 샘플들]
buckets = defaultdict(list)
counts  = defaultdict(int)
herbal_in_warning = []

with open(CSV, encoding="cp949") as f:
    for row in csv.DictReader(f):
        product = (row.get("한글상품명") or "").strip()
        atc     = (row.get("국제표준코드(ATC코드)") or "").strip()
        dtype   = (row.get("전문일반구분") or "").strip()
        cancel  = (row.get("취소일자") or "").strip()
        if not product or cancel:
            continue

        cat, kw = map_intl_atc(atc)
        if is_herbal(product, dtype):
            cat = "normal"

        if cat == "warning":
            atc4 = (atc[:4] if len(atc) >= 4 else atc) or "(없음)"
            key = (kw, atc4)
            counts[key] += 1
            if len(buckets[key]) < 4:
                buckets[key].append(product)
            # warning인데 한약 의심 키워드가 이름에 있으면 플래그
            if any(s in product for s in ("탕", "산", "환", "엑스", "단미", "한방")):
                if len(herbal_in_warning) < 30:
                    herbal_in_warning.append(f"{kw:6s} {atc4} {product}")

print("=" * 70)
print("  WARNING 분류 약물 — (위험키워드 × ATC4) 집계")
print("=" * 70)
for key in sorted(counts, key=lambda k: -counts[k]):
    kw, atc4 = key
    print(f"\n[{kw}] {atc4} — {counts[key]:,}건")
    for s in buckets[key]:
        print(f"     · {s}")

print("\n" + "=" * 70)
print(f"  ⚠ WARNING인데 한약 의심 이름 ({len(herbal_in_warning)}건 표시)")
print("=" * 70)
for s in herbal_in_warning:
    print("   ", s)
if not herbal_in_warning:
    print("    (없음 — 한약 필터 정상)")
