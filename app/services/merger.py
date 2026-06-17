"""
기존 복용 약물 + 신규 처방 약물 병합 (중복 제거).
신규 처방이 우선순위 — 동일 KD코드가 양쪽에 있으면 신규로 간주.
"""


def merge_drug_codes(existing: list[str], new: list[str]) -> list[str]:
    """
    KD코드 리스트를 병합하고 중복 제거.
    순서 보존: 신규 약물 먼저, 그 다음 기존 약물.
    """
    seen: set[str] = set()
    merged: list[str] = []

    for code in list(new) + list(existing):
        if code and code not in seen:
            merged.append(code)
            seen.add(code)

    return merged
