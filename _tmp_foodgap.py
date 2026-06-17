"""음식 규칙 없는 약효군(ATC) 중 약물 수 많은 것 찾기."""
import csv
from collections import Counter
from pathlib import Path

from mobile_reader.food_rules import FOOD_RULES

csv.field_size_limit(2**31 - 1)
ATC_CSV = next(Path(".").glob("건강보험심사평가원_ATC코드 매핑 목록_*.csv"))

# 음식 규칙이 커버하는 ATC 접두사
covered = set(r[0] for r in FOOD_RULES)

# 약가마스터 ATC별 약물 수 (제품 기준)
atc3_count = Counter()  # 앞 3자리(약효군)
atc_name = {}
with open(ATC_CSV, encoding="cp949") as f:
    for row in csv.DictReader(f):
        atc = (row.get("ATC코드") or "").strip()
        name = (row.get("ATC코드 명칭") or "").strip()
        if len(atc) >= 4:
            atc3_count[atc[:4]] += 1
            atc_name[atc[:4]] = name

def is_covered(atc4):
    return any(atc4.startswith(c) or c.startswith(atc4[:len(c)]) for c in covered)

print("음식 규칙 없는 ATC군 (약물 수 많은 순 TOP 25):")
print("=" * 60)
for atc4, cnt in atc3_count.most_common(60):
    if not is_covered(atc4):
        print(f"  {atc4:<6} {cnt:>5}개  {atc_name.get(atc4,'')[:40]}")
