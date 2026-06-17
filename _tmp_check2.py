"""빌드된 distinct 결과에서 카테고리 모순이 사라졌는지 확인."""
from collections import Counter
from build_static import fetch_distinct_drugs

drugs = fetch_distinct_drugs()
print(f"distinct 약물: {len(drugs):,}개")

# 같은 short_name이 warning/normal 양쪽에 있는지
by_name = {}
for d in drugs:
    by_name.setdefault(d["short_name"], set()).add(d["category"])

conflicts = {n: c for n, c in by_name.items() if len(c) > 1}
print(f"카테고리 모순 (distinct 후): {len(conflicts)}개")
for n in list(conflicts)[:8]:
    print(f"  {n}: {conflicts[n]}")

# 글루코파지 직접 확인
print("\n글루코파지 관련 distinct 결과:")
for d in drugs:
    if "글루코파지" in d["short_name"]:
        print(f"  {d['short_name']} | {d['category']} | risk={d['risk_keyword']} ind={d['indication']}")
