"""
레보티록신/콜히친이 약가마스터 CSV에 있는지, 왜 DB에서 빠졌는지 확인.
실행: python check_missing.py
"""
import csv
from pathlib import Path

csv.field_size_limit(2**31 - 1)
CSV = next(Path(".").glob("건강보험심사평가원_약가마스터_의약품표준코드_*.csv"))

TARGETS = ["레보티록신", "콜히친", "와파린", "씬지로이드", "콜킨", "쿠마딘"]

found = {t: [] for t in TARGETS}
total = 0
with open(CSV, encoding="cp949") as f:
    for row in csv.DictReader(f):
        total += 1
        name = row.get("한글상품명", "")
        for t in TARGETS:
            if t in name:
                found[t].append({
                    "name": name,
                    "ingr": row.get("일반명코드(성분명코드)", ""),
                    "atc": row.get("국제표준코드(ATC코드)", ""),
                    "cancel": row.get("취소일자", ""),
                    "type": row.get("전문일반구분", ""),
                })

print(f"CSV 전체 {total:,}행 검사\n")
for t in TARGETS:
    rows = found[t]
    print(f"[{t}] {len(rows)}건 발견")
    for r in rows[:3]:
        cancel = f" 취소일:{r['cancel']}" if r['cancel'] else ""
        print(f"   {r['name'][:30]:32s} 일반명:{r['ingr'] or '없음':12s} ATC:{r['atc'] or '없음':10s}{cancel}")
    print()
