"""
노인 다빈도 약 → ATC 허브 → DUR 병용금기 전체 체인 검증.
약가마스터 약물명으로 시작해 끝까지 연결되는지 확인.
실행: python verify_chain.py
"""
import csv
import json
from pathlib import Path

from app.database import get_conn, init_db

csv.field_size_limit(2**31 - 1)
ATC_CSV = next(Path(".").glob("건강보험심사평가원_ATC코드 매핑 목록_*.csv"))
DUR = Path("mobile_reader/data/dur_ingredient")

# ── ATC 파일: 주성분6 → ATC, 영문명 → ATC ──
atc_by_ingr6 = {}
atc_eng_to_atc = {}
with open(ATC_CSV, encoding="cp949") as f:
    for row in csv.DictReader(f):
        main6 = (row.get("주성분코드") or "")[:6]
        atc = (row.get("ATC코드") or "").strip()
        eng = (row.get("ATC코드 명칭") or "").strip().lower()
        if main6 and atc:
            atc_by_ingr6.setdefault(main6, set()).add(atc)
        if eng and atc:
            atc_eng_to_atc.setdefault(eng, set()).add(atc)

# ── DUR 병용금기: ATC(7→5→3 앞자리) → 금기상대 ──
# DUR 성분의 ATC를 영문명으로 얻어서, ATC 기준으로 금기 인덱스 구축
taboo = json.loads((DUR / "usjnt_taboo.json").read_text(encoding="utf-8"))["items"]
taboo_by_atc = {}   # ATC → [(상대한글명, 사유)]
for it in taboo:
    eng = (it.get("INGR_ENG_NAME") or "").strip().lower()
    other = it.get("MIXTURE_INGR_KOR_NAME", "")
    why = it.get("PROHBT_CONTENT", "")
    for atc in atc_eng_to_atc.get(eng, []):
        taboo_by_atc.setdefault(atc, []).append((other, why))

# ── 약가마스터: 노인 다빈도 약의 일반명코드6 찾기 ──
init_db()
ELDERLY = ["아스피린","클로피도그렐","와파린","메트포르민","글리메피리드",
           "암로디핀","로사르탄","발사르탄","아토르바스타틴","로수바스타틴",
           "심바스타틴","오메프라졸","레보티록신","알로푸리놀","콜히친",
           "도네페질","트라마돌","푸로세미드","스피로노락톤","디곡신",
           "알프라졸람","졸피뎀","에스시탈로프람"]

def atc_match(atc_set, target):
    # ATC 앞 5자리 또는 3자리로도 매칭 허용
    for a in atc_set:
        if a in taboo_by_atc: return a
        for L in (5,4,3):
            for b in taboo_by_atc:
                if a[:L] == b[:L] and len(a)>=L: return b
    return None

print("="*70)
print(f"{'약물':<14}{'코드':<10}{'ATC':<10}{'병용금기':<8}")
print("="*70)
hit = 0
with get_conn() as conn:
    for name in ELDERLY:
        row = conn.execute("""
            SELECT ingredient_code FROM drug_master
            WHERE short_name LIKE ? AND ingredient_code NOT LIKE 'STD:%'
              AND ingredient_code IS NOT NULL AND ingredient_code != ''
            LIMIT 1
        """, (f"%{name}%",)).fetchone()
        if not row:
            print(f"{name:<14}{'(없음)':<10}")
            continue
        c6 = row["ingredient_code"][:6]
        atcs = atc_by_ingr6.get(c6, set())
        m = atc_match(atcs, taboo_by_atc) if atcs else None
        tcount = len(taboo_by_atc.get(m, [])) if m else 0
        if tcount: hit += 1
        atc_show = list(atcs)[0] if atcs else "-"
        print(f"{name:<14}{c6:<10}{atc_show:<10}{('✓'+str(tcount)) if tcount else '✗':<8}")

print("="*70)
print(f"ATC 체인으로 병용금기 매칭: {hit}/{len(ELDERLY)}  ({hit/len(ELDERLY)*100:.0f}%)")
