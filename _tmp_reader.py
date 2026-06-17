"""리더기 lookup 시뮬레이션: QR 약물명으로 food/contra 매칭되는지."""
import json

dc = json.load(open("mobile_reader/data/drug_cautions.json", encoding="utf-8"))
fi = dc["food_index"]
di = dc["drug_index"]

# QR에 실제 들어가는 약물명 형태 (생성기가 short_name 그대로 기록)
# 예시 QR: "주의: 경동아스피린장용정(출혈)[26.08.01]"
# 리더기 파서가 추출하는 이름 = "경동아스피린장용정"
qr_names = ["경동아스피린장용정", "건일염산메트포르민서방정", "리피토엠서방정",
            "건일심바스타틴정", "아마릴-멕스서방정"]

print("리더기 lookup (정확매칭만):")
for n in qr_names:
    f = n in fi
    c = n in di
    print(f"  {n:<24} food={f}  contra={c}")

# food_index에 이 이름들이 실제 있는지
print("\nfood_index에 '메트포르민' 포함 키 개수:", len([k for k in fi if '메트포르민' in k]))
print("food_index에 '아스피린' 포함 키 개수:", len([k for k in fi if '아스피린' in k]))
