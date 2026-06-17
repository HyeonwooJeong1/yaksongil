"""
데이터 품질 종합 감사 — 숨은 버그/이상 패턴 탐지.
실행: python audit_quality.py
"""
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

print("=" * 64)
print("  데이터 품질 감사")
print("=" * 64)

# ── 1. DB 약물명 이상 패턴 ──
c = sqlite3.connect("drug_master.db")
c.row_factory = sqlite3.Row
names = [r[0] for r in c.execute("SELECT DISTINCT short_name FROM drug_master WHERE short_name IS NOT NULL")]
print(f"\n[1] DB 고유 short_name: {len(names):,}개")

issues = {
    "슬래시로 끝남 (절단 흔적)": [n for n in names if n.endswith("/")],
    "숫자로 끝남 (함량 잔재)":   [n for n in names if re.search(r"\d$", n)],
    "1글자":                   [n for n in names if len(n) == 1],
    "특수문자 포함":            [n for n in names if re.search(r"[\[\]()_]", n)],
    "괄호 안 남음":             [n for n in names if "(" in n or ")" in n],
    "공백 포함":               [n for n in names if " " in n],
}
for label, lst in issues.items():
    print(f"  {label:<26}: {len(lst):>6,}개  예: {lst[:3]}")

# ── 2. 카테고리 분포 ──
print("\n[2] 카테고리 분포")
for row in c.execute("SELECT category, COUNT(*) c FROM drug_master GROUP BY category"):
    print(f"  {row['category']:<10}: {row['c']:,}")

# warning인데 위험키워드 없는 것 (데이터 깨짐)
broken_w = c.execute("SELECT COUNT(*) FROM drug_master WHERE category='warning' AND (risk_keyword IS NULL OR risk_keyword='')").fetchone()[0]
broken_n = c.execute("SELECT COUNT(*) FROM drug_master WHERE category='normal' AND (indication IS NULL OR indication='')").fetchone()[0]
print(f"  ⚠ warning인데 위험키워드 없음: {broken_w:,}")
print(f"  ⚠ normal인데 적응증 없음:     {broken_n:,}")

# ── 3. ingredient_code 상태 ──
print("\n[3] ingredient_code 상태")
total = c.execute("SELECT COUNT(*) FROM drug_master").fetchone()[0]
null_ic = c.execute("SELECT COUNT(*) FROM drug_master WHERE ingredient_code IS NULL OR ingredient_code=''").fetchone()[0]
std_ic = c.execute("SELECT COUNT(*) FROM drug_master WHERE ingredient_code LIKE 'STD:%'").fetchone()[0]
real_ic = total - null_ic - std_ic
print(f"  전체:        {total:,}")
print(f"  일반명코드:   {real_ic:,} ({real_ic/total*100:.0f}%)")
print(f"  STD fallback: {std_ic:,} ({std_ic/total*100:.0f}%)")
print(f"  코드 없음:    {null_ic:,} ({null_ic/total*100:.0f}%)")

# ── 4. 통합 데이터(drug_cautions) 정합성 ──
print("\n[4] 통합 데이터 정합성")
dc = json.load(open("mobile_reader/data/drug_cautions.json", encoding="utf-8"))
cautions, di, fi = dc["cautions"], dc["drug_index"], dc["food_index"]
print(f"  성분 cautions:  {len(cautions):,}")
print(f"  drug_index:     {len(di):,}")
print(f"  food_index:     {len(fi):,}")

# drug_index가 가리키는 성분코드가 cautions에 실제 있는지
dangling = 0
for name, codes in di.items():
    for code in codes:
        if code not in cautions:
            dangling += 1
print(f"  ⚠ 끊긴 참조(drug_index→cautions 없음): {dangling:,}")

# food_index 음식 라벨 분포
food_labels = Counter()
for foods in fi.values():
    for f in foods:
        food_labels[f["label"]] += 1
print(f"  음식 라벨 종류: {len(food_labels)}")
print(f"  음식 라벨 분포: {dict(food_labels.most_common(8))}")

# ── 5. 병용금기 자기참조/빈값 ──
print("\n[5] 병용금기 데이터 점검")
self_ref = empty_name = 0
for code, info in cautions.items():
    for con in info.get("contra", []):
        if not con.get("name"): empty_name += 1
        if con.get("name") == info.get("name"): self_ref += 1
print(f"  ⚠ 자기 자신 금기:  {self_ref:,}")
print(f"  ⚠ 금기 상대 빈값:  {empty_name:,}")

print("\n" + "=" * 64)
print("  감사 완료")
print("=" * 64)
