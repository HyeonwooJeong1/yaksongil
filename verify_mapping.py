"""
3개 데이터 코드 연결 검증:
  약가마스터 일반명코드 ↔ ATC 주성분코드 ↔ DUR 성분(ATC/영문명)
실행: python verify_mapping.py
"""
import csv
import json
from pathlib import Path

from app.database import get_conn, init_db

csv.field_size_limit(2**31 - 1)
ATC_CSV = next(Path(".").glob("건강보험심사평가원_ATC코드 매핑 목록_*.csv"))
DUR = Path("mobile_reader/data/dur_ingredient")

# ── 1) ATC 매핑 파일 로드 ──
# 주성분코드 앞 6자리 → set(ATC코드),  ATC명칭(영문) → set(주성분6)
atc_by_ingr6 = {}      # 일반명코드 6자리 → ATC코드들
ingr6_by_atc = {}      # ATC코드 → 주성분6자리들
atc_eng_to_atc = {}    # 영문ATC명칭(소문자) → ATC코드
n_atc = 0
with open(ATC_CSV, encoding="cp949") as f:
    for row in csv.DictReader(f):
        n_atc += 1
        main6 = (row.get("주성분코드") or "")[:6]
        atc = (row.get("ATC코드") or "").strip()
        eng = (row.get("ATC코드 명칭") or "").strip().lower()
        if main6 and atc:
            atc_by_ingr6.setdefault(main6, set()).add(atc)
            ingr6_by_atc.setdefault(atc, set()).add(main6)
        if eng and atc:
            atc_eng_to_atc[eng] = atc

print(f"[ATC 파일] {n_atc:,}행")
print(f"  주성분6 → ATC: {len(atc_by_ingr6):,}개")
print(f"  ATC → 주성분6: {len(ingr6_by_atc):,}개")
print(f"  영문명 → ATC:  {len(atc_eng_to_atc):,}개")

# ── 2) DUR 병용금기의 영문 성분명 → ATC 연결 가능성 ──
taboo = json.loads((DUR / "usjnt_taboo.json").read_text(encoding="utf-8"))["items"]
dur_eng = set()
for it in taboo:
    if it.get("INGR_ENG_NAME"): dur_eng.add(it["INGR_ENG_NAME"].strip().lower())
    if it.get("MIXTURE_INGR_ENG_NAME"): dur_eng.add(it["MIXTURE_INGR_ENG_NAME"].strip().lower())

dur_matched = sum(1 for e in dur_eng if e in atc_eng_to_atc)
print(f"\n[DUR 병용금기] 고유 영문성분: {len(dur_eng)}개")
print(f"  ATC 영문명과 직접 매칭: {dur_matched}/{len(dur_eng)}  ({dur_matched/len(dur_eng)*100:.0f}%)")

# ── 3) 약가마스터 일반명코드6 → ATC 연결 가능성 ──
init_db()
with get_conn() as conn:
    rows = conn.execute("""
        SELECT DISTINCT SUBSTR(ingredient_code,1,6) AS c6
        FROM drug_master
        WHERE ingredient_code IS NOT NULL AND ingredient_code != ''
          AND ingredient_code NOT LIKE 'STD:%'
    """).fetchall()
master6 = set(r["c6"] for r in rows if r["c6"])
master_matched = sum(1 for c in master6 if c in atc_by_ingr6)
print(f"\n[약가마스터] 고유 일반명코드6: {len(master6):,}개")
print(f"  ATC 주성분코드와 매칭: {master_matched:,}/{len(master6):,}  ({master_matched/max(len(master6),1)*100:.0f}%)")

# ── 4) 전체 체인 가능성: 약가마스터 약 → ATC → DUR ──
print("\n" + "="*56)
print("전체 연결 체인 요약")
print("="*56)
print("약가마스터 약물 → (일반명코드6=주성분코드6) → ATC")
print("DUR 성분 → (영문명=ATC명칭) → ATC")
print("→ 공통 ATC로 약물↔DUR 연결 가능")
