"""
다단계 매칭 검증 — ATC 우회 없이 성분명 직접 매칭 추가.
경로 우선순위:
  1. 일반명코드6 → ATC → DUR
  2. full_name 괄호 안 한글 성분명 → DUR 한글 성분명 직접
  3. english_name / ATC영문 → DUR 영문 성분명
실행: python verify_chain2.py
"""
import csv
import json
import re
from pathlib import Path

from app.database import get_conn, init_db

csv.field_size_limit(2**31 - 1)
ATC_CSV = next(Path(".").glob("건강보험심사평가원_ATC코드 매핑 목록_*.csv"))
DUR = Path("mobile_reader/data/dur_ingredient")

# ATC 인덱스
atc_by_ingr6 = {}
with open(ATC_CSV, encoding="cp949") as f:
    for row in csv.DictReader(f):
        m6 = (row.get("주성분코드") or "")[:6]
        atc = (row.get("ATC코드") or "").strip()
        if m6 and atc:
            atc_by_ingr6.setdefault(m6, set()).add(atc)

# DUR 병용금기 인덱스: 한글성분명 → 금기, 영문성분명 → 금기, ATC → 금기
taboo = json.loads((DUR / "usjnt_taboo.json").read_text(encoding="utf-8"))["items"]
by_kor, by_eng = {}, {}
for it in taboo:
    kor = (it.get("INGR_KOR_NAME") or "").strip()
    eng = (it.get("INGR_ENG_NAME") or "").strip().lower()
    other = it.get("MIXTURE_INGR_KOR_NAME", "")
    if kor: by_kor.setdefault(kor, []).append(other)
    if eng: by_eng.setdefault(eng, []).append(other)

def extract_korean_ingredients(full_name):
    """full_name 괄호 안 한글 성분명 추출: '...(와파린나트륨)' → ['와파린나트륨']"""
    if not full_name: return []
    return re.findall(r"\(([가-힣A-Za-z0-9·,\s]+)\)", full_name)

def match_drug(short_name, full_name, ingr_code, eng_name):
    # 1) 한글 성분명 직접 (full_name 괄호 안)
    for ing in extract_korean_ingredients(full_name):
        for kor in by_kor:
            if kor in ing or ing in kor:
                return ("한글성분", kor, len(by_kor[kor]))
    # 2) short_name 자체가 성분명인 경우
    for kor in by_kor:
        if kor in short_name or short_name in kor:
            return ("이름매칭", kor, len(by_kor[kor]))
    return (None, None, 0)

init_db()
ELDERLY = ["아스피린","클로피도그렐","와파린","메트포르민","글리메피리드",
           "암로디핀","로사르탄","발사르탄","아토르바스타틴","로수바스타틴",
           "심바스타틴","오메프라졸","레보티록신","알로푸리놀","콜히친",
           "도네페질","트라마돌","푸로세미드","스피로노락톤","디곡신",
           "알프라졸람","졸피뎀","에스시탈로프람","콜킨","씬지로이드"]

print("="*72)
print(f"{'약물':<14}{'경로':<10}{'매칭성분':<16}{'병용금기'}")
print("="*72)
hit = 0
with get_conn() as conn:
    for name in ELDERLY:
        row = conn.execute("""
            SELECT short_name, full_name, ingredient_code, english_name
            FROM drug_master WHERE short_name LIKE ?
            ORDER BY CASE WHEN ingredient_code NOT LIKE 'STD:%'
                          AND ingredient_code IS NOT NULL THEN 0 ELSE 1 END
            LIMIT 1
        """, (f"%{name}%",)).fetchone()
        if not row:
            print(f"{name:<14}{'(DB없음)'}")
            continue
        path, ing, cnt = match_drug(row["short_name"], row["full_name"],
                                     row["ingredient_code"], row["english_name"])
        if cnt: hit += 1
        print(f"{name:<14}{(path or '✗'):<10}{(ing or '-'):<16}{('✓'+str(cnt)) if cnt else '✗'}")

print("="*72)
print(f"성분명 직접 매칭: {hit}/{len(ELDERLY)}  ({hit/len(ELDERLY)*100:.0f}%)")
