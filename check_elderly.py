"""
노인 다빈도 약물의 음식/병용금기 데이터 매칭 확인.
실행: python check_elderly.py
"""
import json
from pathlib import Path

DATA = Path("mobile_reader/data")
food   = json.loads((DATA / "food_interactions.json").read_text(encoding="utf-8"))
contra = json.loads((DATA / "dur_contraindications.json").read_text(encoding="utf-8"))

# 노인 다빈도 처방 약물 (성분명/대표상품명)
ELDERLY = [
    "아스피린", "클로피도그렐", "와파린", "리바록사반", "아픽사반",   # 항혈전
    "메트포르민", "글리메피리드", "글리클라지드", "시타글립틴", "엠파글리플로진",  # 당뇨
    "암로디핀", "로사르탄", "발사르탄", "텔미사르탄", "히드로클로로티아지드",  # 혈압
    "아토르바스타틴", "로수바스타틴", "심바스타틴",  # 고지혈
    "오메프라졸", "판토프라졸", "라베프라졸", "에스오메프라졸",  # 위장
    "레보티록신", "알로푸리놀", "콜히친",  # 갑상선/통풍
    "도네페질", "메만틴",  # 치매
    "트라마돌", "아세트아미노펜", "셀레콕시브",  # 진통
    "푸로세미드", "스피로노락톤", "디곡신",  # 심부전
    "알프라졸람", "졸피뎀", "에스시탈로프람",  # 정신과
]

def find(name, db):
    if name in db:
        return db[name]
    # 부분 매칭
    for k in db:
        if name in k or k in name:
            return db[k]
    return None

print("=" * 64)
print(f"{'약물':<16}{'음식':<8}{'병용금기':<8}  내용")
print("=" * 64)
for drug in ELDERLY:
    f = find(drug, food)
    c = find(drug, contra)
    fcount = len(f["foods"]) if f and f.get("foods") else 0
    ccount = len(c["contraindicated_with"]) if c and c.get("contraindicated_with") else 0
    foods_txt = ", ".join(x["label"] for x in f["foods"]) if fcount else "-"
    mark_f = f"✓{fcount}" if fcount else "✗"
    mark_c = f"✓{ccount}" if ccount else "✗"
    print(f"{drug:<16}{mark_f:<8}{mark_c:<8}  음식: {foods_txt[:40]}")

print("=" * 64)
print(f"음식 데이터 총 약물: {len([k for k,v in food.items() if v.get('foods')])}건")
print(f"병용금기 총 약물:    {len(contra)}건")
