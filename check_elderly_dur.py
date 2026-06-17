"""
노인 다빈도 약물이 DUR 성분정보(병용금기/노인주의)에 매칭되는지 확인.
실행: python check_elderly_dur.py
"""
import json
from pathlib import Path

DUR = Path("mobile_reader/data/dur_ingredient")
taboo = json.loads((DUR / "usjnt_taboo.json").read_text(encoding="utf-8"))["items"]
odsn  = json.loads((DUR / "odsn_atent.json").read_text(encoding="utf-8"))["items"]
efcy  = json.loads((DUR / "efcy_dplct.json").read_text(encoding="utf-8"))["items"]
cpcty = json.loads((DUR / "cpcty_atent.json").read_text(encoding="utf-8"))["items"]

# 병용금기: 성분명 → 금기 상대 목록
taboo_map = {}
for it in taboo:
    a = it.get("INGR_KOR_NAME", "")
    b = it.get("MIXTURE_INGR_KOR_NAME", "")
    why = it.get("PROHBT_CONTENT", "")
    if a and b:
        taboo_map.setdefault(a, []).append((b, why))
        taboo_map.setdefault(b, []).append((a, why))

# 노인주의 성분 집합
odsn_map = {}
for it in odsn:
    n = it.get("INGR_NAME", "")
    if n:
        odsn_map[n] = it.get("PROHBT_CONTENT", "")

ELDERLY = [
    "아스피린", "클로피도그렐", "와파린", "리바록사반", "아픽사반",
    "메트포르민", "글리메피리드", "글리클라지드", "시타글립틴", "엠파글리플로진",
    "암로디핀", "로사르탄", "발사르탄", "텔미사르탄", "히드로클로로티아지드",
    "아토르바스타틴", "로수바스타틴", "심바스타틴",
    "오메프라졸", "판토프라졸", "라베프라졸", "에스오메프라졸",
    "레보티록신", "알로푸리놀", "콜히친",
    "도네페질", "메만틴",
    "트라마돌", "아세트아미노펜", "셀레콕시브",
    "푸로세미드", "스피로노락톤", "디곡신",
    "알프라졸람", "졸피뎀", "에스시탈로프람",
]

def find(name, mp):
    if name in mp:
        return mp[name]
    for k in mp:
        if name in k or k in name:
            return mp[k]
    return None

print("=" * 70)
print(f"{'약물':<14}{'병용금기':<10}{'노인주의':<10}내용")
print("=" * 70)
hit_t = hit_o = 0
for d in ELDERLY:
    t = find(d, taboo_map)
    o = find(d, odsn_map)
    tc = len(t) if t else 0
    if tc: hit_t += 1
    if o: hit_o += 1
    om = "✓" if o else "✗"
    sample = ", ".join(x[0] for x in t[:3]) if t else "-"
    print(f"{d:<14}{('✓'+str(tc)):<10}{om:<10}{sample[:36]}")

print("=" * 70)
print(f"병용금기 매칭: {hit_t}/{len(ELDERLY)}  ({hit_t/len(ELDERLY)*100:.0f}%)")
print(f"노인주의 매칭: {hit_o}/{len(ELDERLY)}  ({hit_o/len(ELDERLY)*100:.0f}%)")
print(f"\nDUR 병용금기 성분 수: {len(taboo_map)}")
print(f"DUR 노인주의 성분 수: {len(odsn_map)}")
