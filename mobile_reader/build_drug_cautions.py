"""
DUR 7종 + ATC 매핑 → 약물별 통합 주의정보 JSON 빌더.

핵심: 성분코드(INGR_CODE, D000xxx) 기준으로 7종을 통합하고,
약가마스터 약물을 다단계 매칭으로 연결.

매칭 경로 (OR, 누락 최소화):
  1. 약가마스터 일반명코드6 → ATC매핑 → 같은 ATC의 DUR 성분
  2. full_name 괄호 안 한글 성분명 → DUR INGR_NAME 직접
  3. short_name → DUR 성분명

출력:
  mobile_reader/data/drug_cautions.json
  {
    "<DUR성분코드>": {
      "name": "와파린",
      "contra":    [{"name": 상대약, "reason": 사유}],
      "elderly":   "노인주의 사유",
      "duplicate": "효능군명",
      "dosage":    "최대용량",
      "age":       {"limit": "18세이하", "reason": ...},
      "pregnancy": {"grade": "1등급", "reason": ...},
      "period":    "최대투여기간",
    }, ...
  }
  + 약물명/코드 → 성분코드 인덱스도 포함

실행: python -m mobile_reader.build_drug_cautions
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from app.database import get_conn, init_db
from mobile_reader.food_rules import foods_for_atc
from mobile_reader.normalize import normalize_name

csv.field_size_limit(2**31 - 1)
ROOT = Path(__file__).parent.parent
ATC_CSV = next(ROOT.glob("건강보험심사평가원_ATC코드 매핑 목록_*.csv"))
DUR = Path(__file__).parent / "data" / "dur_ingredient"
OUT = Path(__file__).parent / "data" / "drug_cautions.json"


def load(key):
    return json.loads((DUR / f"{key}.json").read_text(encoding="utf-8"))["items"]


def build():
    init_db()
    print("[1/4] DUR 7종 → 성분코드 기준 통합...")

    # 성분코드 → 통합 주의정보
    cautions = defaultdict(lambda: {
        "name": "", "eng": "",
        "contra": [], "elderly": "", "duplicate": "",
        "dosage": "", "age": None, "pregnancy": None, "period": "",
    })

    def set_name(code, kor, eng):
        if code and not cautions[code]["name"]:
            cautions[code]["name"] = kor
            cautions[code]["eng"] = eng

    # 병용금기
    for it in load("usjnt_taboo"):
        c = it.get("INGR_CODE", "")
        set_name(c, it.get("INGR_KOR_NAME", ""), it.get("INGR_ENG_NAME", ""))
        other = it.get("MIXTURE_INGR_KOR_NAME", "")
        why = it.get("PROHBT_CONTENT", "")
        if c and other:
            # 중복 상대 제거
            if not any(x["name"] == other for x in cautions[c]["contra"]):
                cautions[c]["contra"].append({"name": other, "reason": why})

    # 노인주의
    for it in load("odsn_atent"):
        c = it.get("INGR_CODE", "")
        set_name(c, it.get("INGR_NAME", ""), it.get("INGR_ENG_NAME", ""))
        if c:
            cautions[c]["elderly"] = it.get("PROHBT_CONTENT", "")

    # 효능군중복
    for it in load("efcy_dplct"):
        c = it.get("INGR_CODE", "")
        set_name(c, it.get("INGR_NAME", ""), it.get("INGR_ENG_NAME", ""))
        if c:
            cautions[c]["duplicate"] = it.get("SERS_NAME", "") or it.get("EFFECT_CODE", "")

    # 용량주의
    for it in load("cpcty_atent"):
        c = it.get("INGR_CODE", "")
        set_name(c, it.get("INGR_NAME", ""), it.get("INGR_ENG_NAME", ""))
        if c:
            cautions[c]["dosage"] = it.get("MAX_QTY", "")

    # 특정연령대금기
    for it in load("agrde_taboo"):
        c = it.get("INGR_CODE", "")
        set_name(c, it.get("INGR_NAME", ""), it.get("INGR_ENG_NAME", ""))
        if c:
            cautions[c]["age"] = {"limit": it.get("AGE_BASE", ""), "reason": it.get("PROHBT_CONTENT", "")}

    # 임부금기
    for it in load("pwnm_taboo"):
        c = it.get("INGR_CODE", "")
        set_name(c, it.get("INGR_NAME", ""), it.get("INGR_ENG_NAME", ""))
        if c:
            cautions[c]["pregnancy"] = {"grade": it.get("GRADE", ""), "reason": it.get("PROHBT_CONTENT", "")}

    # 투여기간주의
    for it in load("mdctn_atent"):
        c = it.get("INGR_CODE", "")
        set_name(c, it.get("INGR_NAME", ""), it.get("INGR_ENG_NAME", ""))
        if c:
            cautions[c]["period"] = it.get("MAX_DOSAGE_TERM", "")

    cautions = dict(cautions)
    print(f"      통합 성분: {len(cautions)}개")

    # ── 매칭 인덱스 구축 ──
    print("[2/4] 매칭 인덱스 구축 (ATC + 성분명)...")

    # ATC: 일반명코드6 → set(ATC),  ATC → set(DUR성분코드)
    atc_by_ingr6 = defaultdict(set)
    with open(ATC_CSV, encoding="cp949") as f:
        atc_rows = list(csv.DictReader(f))
    for row in atc_rows:
        m6 = (row.get("주성분코드") or "")[:6]
        atc = (row.get("ATC코드") or "").strip()
        if m6 and atc:
            atc_by_ingr6[m6].add(atc)

    # DUR 성분 영문명 → 성분코드 (ATC명칭과 매칭용)
    eng_to_code = {}
    kor_to_code = {}
    for code, info in cautions.items():
        if info["eng"]:
            eng_to_code[info["eng"].lower()] = code
        if info["name"]:
            kor_to_code[info["name"]] = code

    # ATC → DUR성분코드: ATC명칭(영문) ↔ DUR 영문명
    atc_to_code = defaultdict(set)
    for row in atc_rows:
        atc = (row.get("ATC코드") or "").strip()
        eng = (row.get("ATC코드 명칭") or "").strip().lower()
        if atc and eng in eng_to_code:
            atc_to_code[atc].add(eng_to_code[eng])

    # ── 약가마스터 약물 → 성분코드 매핑 ──
    print("[3/4] 약가마스터 약물 → DUR 성분코드 매핑...")

    def kor_ingredients(full_name):
        if not full_name:
            return []
        return re.findall(r"\(([가-힣A-Za-z0-9·,\s]+)\)", full_name)

    def match_codes(short_name, full_name, ingr_code):
        """
        약물 → 매칭되는 DUR 성분코드 set (다단계, 정밀).
        ATC는 전체(7자리) 정확 일치만 사용 — 계열(앞 5자리) 매칭은
        같은 계열 다른 약을 섞어버려 정밀도를 떨어뜨리므로 제외.
        """
        codes = set()
        # 1) 일반명코드6 → ATC(전체 일치) → DUR
        if ingr_code and not ingr_code.startswith("STD:") and len(ingr_code) >= 6:
            for atc in atc_by_ingr6.get(ingr_code[:6], []):
                codes |= atc_to_code.get(atc, set())
        # 2) 한글 성분명 직접 (full_name 괄호 안)
        for ing in kor_ingredients(full_name):
            for kor, code in kor_to_code.items():
                if kor in ing or ing in kor:
                    codes.add(code)
        # 3) short_name 자체가 성분명
        for kor, code in kor_to_code.items():
            if kor in short_name or short_name in kor:
                codes.add(code)
        return codes

    def atcs_for_drug(ingr_code):
        """약물 일반명코드6 → ATC 코드들."""
        if ingr_code and not ingr_code.startswith("STD:") and len(ingr_code) >= 6:
            return atc_by_ingr6.get(ingr_code[:6], set())
        return set()

    # 약물명 → 성분코드 인덱스 + 음식 인덱스
    drug_to_codes = {}
    drug_to_food = {}   # 약물명 → [음식규칙]
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT short_name, full_name, ingredient_code
            FROM drug_master WHERE short_name IS NOT NULL
        """).fetchall()
    rows = [dict(r) for r in rows]

    # DUR 성분코드 → ATC 역매핑 (음식 규칙 적용용).
    # 음식은 ATC 기준인데, 일부 제형(서방정 등)은 일반명코드가 비어 ATC를 직접
    # 못 얻는다. 그러나 match_codes()는 성분명으로도 DUR 성분코드를 정확히 찾으므로,
    # 그 성분코드의 ATC로 음식을 적용하면 제형 무관하게 커버된다.
    code_to_atcs = defaultdict(set)
    for row in atc_rows:
        atc = (row.get("ATC코드") or "").strip()
        eng = (row.get("ATC코드 명칭") or "").strip().lower()
        if atc and eng in eng_to_code:
            code_to_atcs[eng_to_code[eng]].add(atc)

    for r in rows:
        sname = r["short_name"] or ""
        ic = r["ingredient_code"] or ""
        codes = match_codes(sname, r["full_name"] or "", ic)
        if codes:
            drug_to_codes.setdefault(sname, set()).update(codes)

        # 음식: ① 일반명코드 직접 ATC + ② 매칭된 DUR 성분코드의 ATC (제형 결손 보완)
        atc_set = set()
        if ic and not ic.startswith("STD:") and len(ic) >= 6:
            atc_set |= atc_by_ingr6.get(ic[:6], set())
        for code in codes:
            atc_set |= code_to_atcs.get(code, set())

        for atc in atc_set:
            for f in foods_for_atc(atc):
                bucket = drug_to_food.setdefault(sname, [])
                if not any(x["label"] == f["label"] for x in bucket):
                    bucket.append(f)

    drug_index = {k: sorted(v) for k, v in drug_to_codes.items()}
    food_index = drug_to_food

    print(f"      병용금기 등 매칭 약물: {len(drug_index):,}개")
    print(f"      음식 매칭 약물:        {len(food_index):,}개")

    # ── 저장 ──
    print("[4/4] 저장...")
    out = {
        "cautions":   cautions,     # 성분코드 → 주의정보(병용금기/노인주의 등)
        "drug_index": drug_index,   # 약물명 → [성분코드]
        "food_index": food_index,   # 약물명 → [음식규칙]
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    size = OUT.stat().st_size / 1024
    print(f"\n[OK] {OUT}")
    print(f"  통합 성분:     {len(cautions)}개")
    print(f"  병용금기 약물: {len(drug_index):,}개")
    print(f"  음식 약물:     {len(food_index):,}개")
    print(f"  파일 크기:     {size:,.0f} KB")


if __name__ == "__main__":
    build()
