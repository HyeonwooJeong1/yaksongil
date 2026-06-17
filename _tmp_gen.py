"""생성기가 쓰는 distinct 약물의 short_name과 food_index 매칭 확인."""
import json
from build_static import fetch_distinct_drugs

dc = json.load(open("mobile_reader/data/drug_cautions.json", encoding="utf-8"))
fi = dc["food_index"]
di = dc["drug_index"]

drugs = fetch_distinct_drugs()
# 노바스크/리피토/아마릴 등 찾아서 short_name 확인 + food 매칭
targets = ["노바스크", "리피토", "아마릴", "아스피린", "메트포르민", "심바스타틴"]
for t in targets:
    for d in drugs:
        if t in (d["short_name"] or ""):
            sn = d["short_name"]
            food = sn in fi
            contra = sn in di
            print(f"  검색'{t}' → short_name='{sn}'  food={food}  contra={contra}")
            break
