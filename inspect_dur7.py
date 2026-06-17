"""DUR 7종 각각의 필드 구조 + 성분명/사유 필드명 확인."""
import json
from pathlib import Path

DUR = Path("mobile_reader/data/dur_ingredient")
FILES = [
    ("usjnt_taboo", "병용금기"),
    ("odsn_atent", "노인주의"),
    ("agrde_taboo", "특정연령대금기"),
    ("pwnm_taboo", "임부금기"),
    ("cpcty_atent", "용량주의"),
    ("mdctn_atent", "투여기간주의"),
    ("efcy_dplct", "효능군중복"),
]

for key, label in FILES:
    data = json.loads((DUR / f"{key}.json").read_text(encoding="utf-8"))
    items = data["items"]
    print("=" * 60)
    print(f"[{label}] {len(items)}건")
    print("=" * 60)
    if items:
        # 성분명/사유 관련 필드만 추려서 표시
        for k in items[0].keys():
            v = items[0][k]
            print(f"  {k:24s}: {str(v)[:45]}")
    print()
