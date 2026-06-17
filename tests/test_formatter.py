"""
formatter.py 단위 테스트.
실행: python -m tests.test_formatter
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.formatter import (
    MAX_LENGTH,
    TextTooLongError,
    format_emergency_text,
)


def make_warning(name, risk):
    return {"category": "warning", "short_name": name, "risk_keyword": risk, "indication": None}


def make_normal(name, indication):
    return {"category": "normal", "short_name": name, "risk_keyword": None, "indication": indication}


def test_basic_format():
    drugs = [
        make_warning("아스피린", "출혈"),
        make_warning("아마릴", "저혈당"),
        make_normal("리피토", "고지혈"),
        make_normal("노바스크", "고혈압"),
    ]
    text = format_emergency_text(drugs, dispense_date=date(2026, 6, 1))
    expected = (
        "[응급의료정보(다제약물)]\n"
        "조제: 2026-06-01 (최신)\n"
        "■ 주의: 아스피린(출혈), 아마릴(저혈당)\n"
        "■ 일반: 리피토(고지혈), 노바스크(고혈압)"
    )
    assert text == expected, f"\n[예상]\n{expected}\n[실제]\n{text}"
    print(f"[PASS] test_basic_format  ({len(text)}자)")


def test_empty_warning():
    drugs = [make_normal("리피토", "고지혈")]
    text = format_emergency_text(drugs, dispense_date=date(2026, 6, 1))
    assert "■ 주의: 없음" in text
    print(f"[PASS] test_empty_warning  ({len(text)}자)")


def test_empty_normal():
    drugs = [make_warning("아스피린", "출혈")]
    text = format_emergency_text(drugs, dispense_date=date(2026, 6, 1))
    assert "■ 일반: 없음" in text
    print(f"[PASS] test_empty_normal  ({len(text)}자)")


def test_length_limit_exceeded():
    drugs = [make_warning("아스피린", "출혈")]
    # 일반 약물을 매우 길게 추가하여 200자 초과 유도
    drugs += [make_normal(f"약물{i:02d}", "적응증") for i in range(20)]
    try:
        format_emergency_text(drugs, dispense_date=date(2026, 6, 1))
        assert False, "200자 초과 시 TextTooLongError가 발생해야 함"
    except TextTooLongError as e:
        assert e.length > MAX_LENGTH
        print(f"[PASS] test_length_limit_exceeded  ({e.length}자, 일반 {e.normal_count}개)")


def test_length_within_limit():
    drugs = [
        make_warning("아스피린", "출혈"),
        make_warning("아마릴", "저혈당"),
        make_warning("디곡신", "부정맥"),
        make_normal("리피토", "고지혈"),
        make_normal("노바스크", "고혈압"),
        make_normal("타이레놀", "진통"),
    ]
    text = format_emergency_text(drugs, dispense_date=date(2026, 6, 1))
    assert len(text) <= MAX_LENGTH
    print(f"[PASS] test_length_within_limit  ({len(text)}자)")


if __name__ == "__main__":
    test_basic_format()
    test_empty_warning()
    test_empty_normal()
    test_length_limit_exceeded()
    test_length_within_limit()
    print("\n[전체 통과]")
