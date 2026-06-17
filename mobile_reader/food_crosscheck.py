"""
음식 데이터 교차검증 빌더.

두 소스를 합쳐 신뢰도를 표시:
  1. ATC 규칙 (food_rules.py) — 임상근거, 출처 명시
  2. e약은요 자동추출 (food_interactions.json) — 식약처 공식 텍스트 기반

약물(성분코드)별로:
  - ATC 규칙으로 나온 음식
  - e약은요에서 추출된 음식
  - 둘 다 나오면 "확정"(verified), 한쪽만이면 "참고"

이 빌더는 ATC 규칙을 1차로 쓰되, e약은요 추출과 겹치는 항목에
verified 플래그를 달아 신뢰도를 높인다.

실행: python -m mobile_reader.food_crosscheck
"""
import json
from pathlib import Path

from mobile_reader.food_keywords import FOOD_PATTERNS

DATA = Path(__file__).parent / "data"
EYAK = DATA / "food_interactions.json"   # 기존 e약은요 추출 (약물명 기준)

# food_rules의 음식 라벨 ↔ food_keywords의 라벨 정규화 매핑
# (두 소스의 라벨 표기가 다를 수 있어 통일)
LABEL_ALIAS = {
    "자몽": ["자몽"],
    "알코올": ["알코올"],
    "비타민K식품": ["비타민K식품"],
    "우유/유제품": ["우유/유제품"],
    "콩/칼슘/철": ["콩/대두"],
    "치즈/발효식품": ["발효식품"],
    "칼륨식품": ["칼륨식품"],
    "마늘/은행": ["마늘"],
    "녹차/홍차": ["녹차/홍차"],
    "카페인": ["카페인"],
    "감초": ["감초"],
    "감초/고섬유": ["감초"],
    "우유/칼슘": ["우유/유제품"],
}


def load_eyak_foods_by_name() -> dict:
    """e약은요 추출: 약물명 → set(음식라벨)."""
    if not EYAK.exists():
        return {}
    data = json.loads(EYAK.read_text(encoding="utf-8"))
    out = {}
    for name, info in data.items():
        labels = set(f["label"] for f in info.get("foods", []))
        if labels:
            out[name] = labels
    return out


def crosscheck_summary():
    """ATC 규칙 vs e약은요 겹침 통계만 출력 (검증용)."""
    eyak = load_eyak_foods_by_name()
    print(f"[e약은요 추출] 음식 있는 약물: {len(eyak)}개")

    # food_rules 라벨이 e약은요에서 얼마나 확인되는지
    from mobile_reader.food_rules import FOOD_RULES
    rule_labels = set(r[1] for r in FOOD_RULES)
    eyak_labels = set()
    for s in eyak.values():
        eyak_labels |= s

    print(f"\n[라벨 교차]")
    print(f"  ATC 규칙 음식 종류: {len(rule_labels)}")
    print(f"  e약은요 음식 종류:  {len(eyak_labels)}")
    print(f"\n  규칙 라벨별 e약은요 확인 여부:")
    for label in sorted(rule_labels):
        aliases = LABEL_ALIAS.get(label, [label])
        verified = any(a in eyak_labels for a in aliases)
        mark = "✓ 교차확인" if verified else "· 규칙만"
        print(f"    {label:<14} {mark}")


if __name__ == "__main__":
    crosscheck_summary()
