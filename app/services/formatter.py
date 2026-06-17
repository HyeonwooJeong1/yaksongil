"""
약물 리스트를 응급 의료진용 초경량 텍스트로 포맷팅.

원칙:
- 200자 hard limit (QR 카메라 인식률 보장)
- 초과 시 ValueError raise → 약사가 직접 약물을 줄이도록 강제
"""
from datetime import date

MAX_LENGTH = 200


class TextTooLongError(ValueError):
    def __init__(self, length: int, text: str, normal_count: int):
        self.length = length
        self.text = text
        self.normal_count = normal_count
        super().__init__(
            f"텍스트가 {length}자로 {MAX_LENGTH}자 제한을 초과했습니다. "
            f"일반 약물 {normal_count}개 중 일부를 제거하세요."
        )


def _format_warning(drug: dict) -> str:
    return f"{drug['short_name']}({drug['risk_keyword']})"


def _format_normal(drug: dict) -> str:
    return f"{drug['short_name']}({drug['indication']})"


def format_emergency_text(
    drugs: list[dict],
    dispense_date: date | None = None,
) -> str:
    """
    drugs: database.fetch_drugs_by_codes()의 결과 (dict 리스트)
    dispense_date: 조제일 (기본=오늘)
    """
    dispense_date = dispense_date or date.today()

    warning = [d for d in drugs if d["category"] == "warning"]
    normal  = [d for d in drugs if d["category"] == "normal"]

    warning_str = ", ".join(_format_warning(d) for d in warning) if warning else "없음"
    normal_str  = ", ".join(_format_normal(d)  for d in normal)  if normal  else "없음"

    text = (
        "[응급의료정보(다제약물)]\n"
        f"조제: {dispense_date.isoformat()} (최신)\n"
        f"■ 주의: {warning_str}\n"
        f"■ 일반: {normal_str}"
    )

    if len(text) > MAX_LENGTH:
        raise TextTooLongError(
            length=len(text),
            text=text,
            normal_count=len(normal),
        )

    return text
