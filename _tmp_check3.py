"""검색 시 같은 이름이 중복 표시되는지 + 후처리 통합 효과 확인."""
from build_static import fetch_distinct_drugs

drugs = fetch_distinct_drugs()
print(f"distinct 원본: {len(drugs):,}개")

# short_name 기준 후처리 통합: 같은 이름이면 warning 우선, 1개로
merged = {}
for d in drugs:
    n = d["short_name"]
    if n not in merged:
        merged[n] = d
    else:
        # 기존이 normal이고 새게 warning이면 교체
        if merged[n]["category"] == "normal" and d["category"] == "warning":
            merged[n] = d

print(f"이름 기준 통합 후: {len(merged):,}개")

# 통합 후 모순 재확인
from collections import Counter
cat_by_name = {}
for d in merged.values():
    cat_by_name.setdefault(d["short_name"], set()).add(d["category"])
conflicts = sum(1 for c in cat_by_name.values() if len(c) > 1)
print(f"통합 후 모순: {conflicts}개")

# 글루코파지 확인
print("\n통합 후 글루코파지:")
for n, d in merged.items():
    if "글루코파지" in n:
        print(f"  {n} | {d['category']} | risk={d['risk_keyword']} ind={d['indication']}")
