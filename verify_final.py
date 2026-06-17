"""
최종 통합 데이터(drug_cautions.json)로 노인 다빈도 약 커버리지 검증.
실행: python verify_final.py
"""
import json
from pathlib import Path

data = json.loads(Path("mobile_reader/data/drug_cautions.json").read_text(encoding="utf-8"))
cautions = data["cautions"]
drug_index = data["drug_index"]
food_index = data.get("food_index", {})

ELDERLY = ["아스피린","클로피도그렐","와파린","메트포르민","글리메피리드",
           "암로디핀","로사르탄","발사르탄","아토르바스타틴","로수바스타틴",
           "심바스타틴","오메프라졸","레보티록신","알로푸리놀","콜히친",
           "도네페질","트라마돌","푸로세미드","스피로노락톤","디곡신",
           "알프라졸람","졸피뎀","에스시탈로프람","콜킨","씬지로이드",
           "리피토","노바스크","플라빅스","아마릴"]

def find(name):
    # 약물명 부분매칭으로 인덱스 검색
    codes = set()
    for k, v in drug_index.items():
        if name in k or k in name:
            codes.update(v)
    return codes

def find_food(name):
    foods = []
    seen = set()
    for k, v in food_index.items():
        if name in k or k in name:
            for f in v:
                if f["label"] not in seen:
                    seen.add(f["label"]); foods.append(f)
    return foods

print("=" * 86)
print(f"{'약물':<14}{'병용금기':<8}{'노인주의':<8}{'효능군중복':<10}{'음식'}")
print("=" * 86)
hit = food_hit = 0
for name in ELDERLY:
    codes = find(name)
    foods = find_food(name)
    if not codes and not foods:
        print(f"{name:<14}✗ 매칭없음")
        continue
    if codes: hit += 1
    if foods: food_hit += 1
    contra = elderly = dup = 0
    for c in codes:
        info = cautions.get(c, {})
        contra += len(info.get("contra", []))
        if info.get("elderly"): elderly = 1
        if info.get("duplicate"): dup = 1
    em = "✓" if elderly else "-"
    dm = "✓" if dup else "-"
    cm = f"✓{contra}" if contra else "-"
    fm = ", ".join(f["label"] for f in foods) if foods else "-"
    print(f"{name:<14}{cm:<8}{em:<8}{dm:<10}{fm[:34]}")

print("=" * 86)
print(f"병용금기 등 커버: {hit}/{len(ELDERLY)}  ({hit/len(ELDERLY)*100:.0f}%)")
print(f"음식 커버:        {food_hit}/{len(ELDERLY)}  ({food_hit/len(ELDERLY)*100:.0f}%)")

# 샘플 상세
print("\n[샘플] 심바스타틴 상세:")
for k, v in drug_index.items():
    if "심바스타틴" in k:
        for c in v:
            info = cautions[c]
            print(f"  성분: {info['name']}")
            print(f"  병용금기 {len(info['contra'])}건: " +
                  ", ".join(x["name"] for x in info["contra"][:5]))
            print(f"  노인주의: {info['elderly'][:50] or '-'}")
            print(f"  효능군중복: {info['duplicate'] or '-'}")
        break
