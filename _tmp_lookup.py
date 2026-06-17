"""QR 약물명으로 drug_index lookup이 되는지 진단."""
import json

dc = json.load(open("mobile_reader/data/drug_cautions.json", encoding="utf-8"))
di = dc["drug_index"]
fi = dc["food_index"]

# QR에 들어갈 법한 약물명 (생성기가 만드는 short_name)
tests = ["노바스크", "리피토", "아스피린", "아마릴", "메트포르민",
         "노바스크정", "리피토정", "와파린"]

print("drug_index 키 샘플 10개:")
for k in list(di)[:10]:
    print("  ", repr(k))

print("\nfood_index 키 샘플 10개:")
for k in list(fi)[:10]:
    print("  ", repr(k))

print("\n=== lookup 테스트 ===")
for t in tests:
    in_di = t in di
    in_fi = t in fi
    # 부분 후보
    cand = [k for k in fi if t in k][:3]
    print(f"  {t:<12} drug_index={in_di}  food_index={in_fi}  유사키={cand}")
