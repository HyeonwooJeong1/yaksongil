"""
심층 감사 2차 — 검색/중복/QR왕복/매칭오탐 점검.
실행: python audit_quality2.py
"""
import json
import re
import sqlite3
from collections import Counter

print("=" * 64)
print("  심층 데이터 감사 (2차)")
print("=" * 64)

dc = json.load(open("mobile_reader/data/drug_cautions.json", encoding="utf-8"))
cautions, di, fi = dc["cautions"], dc["drug_index"], dc["food_index"]

# ── 1. 과매칭 위험: 짧은 약물명이 부분매칭 오탐 ──
print("\n[1] 과매칭 위험 (짧은 약물명)")
short_keys = [k for k in di if len(k) <= 3]
print(f"  3글자 이하 drug_index 키: {len(short_keys)}개")
print(f"  예: {short_keys[:10]}")
danger = [k for k in di if len(k) <= 2]
if danger:
    print(f"  ⚠ 2글자 이하(과매칭 위험): {danger}")

# ── 2. 효능군중복 분포 ──
print("\n[2] 효능군중복 분포")
dup_counter = Counter()
for code, info in cautions.items():
    if info.get("duplicate"):
        dup_counter[info["duplicate"]] += 1
print(f"  효능군 종류: {len(dup_counter)}")
print(f"  상위: {dict(dup_counter.most_common(5))}")

# ── 3. QR 왕복 파싱 검증 ──
print("\n[3] QR 왕복 파싱 (생성 포맷 → reader 파서)")
sample = (
    "주의: 아스피린(출혈)[26.08.01], 아마릴(저혈당)[26.12.31]\n"
    "일반: 리피토(고지혈)[26.12.31], 노바스크(고혈압)[26.09.15]"
)
def parse_drug_list(s):
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([": depth += 1
        elif ch in ")]": depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else: cur += ch
    if cur.strip(): parts.append(cur)
    out = []
    for p in parts:
        m = re.match(r"^(.+?)\s*(?:\(([^)]*)\))?\s*(?:\[([^\]]*)\])?\s*$", p.strip())
        if m: out.append((m.group(1).strip(), m.group(2), m.group(3)))
    return out
for line in sample.split("\n"):
    label = line[:2]
    parsed = parse_drug_list(line[3:].strip())
    print(f"  {label} 파싱: {parsed}")

# ── 4. 종료일 형식 ──
print("\n[4] 종료일(YY.MM.DD) 파싱")
for d in ["26.08.01", "26.12.31", "27.01.05"]:
    print(f"  {d}: {'OK' if re.match(r'^(\\d{2})\\.(\\d{2})\\.(\\d{2})$', d) else 'FAIL'}")

# ── 5. 같은 약물명 warning/normal 모순 ──
print("\n[5] 같은 약물명이 warning+normal 양쪽 (모순)")
c = sqlite3.connect("drug_master.db")
rows = c.execute("""
    SELECT short_name, COUNT(DISTINCT category) nc
    FROM drug_master GROUP BY short_name HAVING nc > 1
""").fetchall()
print(f"  모순 약물명: {len(rows)}개")
for r in rows[:6]:
    cats = [x[0] for x in c.execute("SELECT DISTINCT category FROM drug_master WHERE short_name=?", (r[0],))]
    print(f"    {r[0]}: {cats}")

# ── 6. 음식 위험도/출처 ──
print("\n[6] 음식 위험도(level) 분포 + 출처 누락")
levels = Counter()
no_src = 0
for foods in fi.values():
    for f in foods:
        levels[f.get("level", "?")] += 1
        if not f.get("source"): no_src += 1
print(f"  위험도: {dict(levels)}")
print(f"  출처 없는 항목: {no_src}")

print("\n" + "=" * 64)
print("  2차 감사 완료")
print("=" * 64)
