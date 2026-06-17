"""노인주의 매칭 점검 — 노인주의 112건이 약물에 제대로 붙는지."""
import json
from pathlib import Path

data = json.loads(Path("mobile_reader/data/drug_cautions.json").read_text(encoding="utf-8"))
cautions = data["cautions"]
drug_index = data["drug_index"]

# 노인주의 있는 성분코드
elderly_codes = {c: info for c, info in cautions.items() if info.get("elderly")}
print(f"노인주의 정보 있는 성분: {len(elderly_codes)}개")
print("샘플 5개:")
for c, info in list(elderly_codes.items())[:5]:
    print(f"  {c} {info['name']}: {info['elderly'][:40]}")

# 이 성분들이 drug_index에서 약물로 연결되는지
print("\n노인주의 성분 → 연결된 약물명:")
hit = 0
for c, info in list(elderly_codes.items())[:10]:
    drugs = [name for name, codes in drug_index.items() if c in codes]
    if drugs: hit += 1
    print(f"  {info['name']:<16} → {', '.join(drugs[:3]) or '(약물 연결 없음)'}")

# 벤조 약물이 노인주의 코드를 갖는지
print("\n주요 노인주의 약 직접 확인:")
for name in ["알프라졸람", "디아제팜", "로라제팜", "졸피뎀", "아미트리프틸린"]:
    codes = set()
    for k, v in drug_index.items():
        if name in k:
            codes.update(v)
    has_elderly = any(cautions.get(c, {}).get("elderly") for c in codes)
    print(f"  {name:<14} 성분코드 {len(codes)}개, 노인주의: {'✓' if has_elderly else '✗'}")
