"""
Mock 시드 데이터 적재 스크립트.
인증키 발급 전까지 사용. 발급 후에는 app/services/external/hira_dur_loader.py로 대체.

실행: python -m app.seed
"""
from app.database import get_conn, init_db

SEED_DRUGS = [
    # 주의 약물 (warning) — 응급 시 의료진이 즉시 인지해야 할 약물
    ("KD001", "아스피린",   "아스피린장용정 100mg",   "warning", "출혈",     None),
    ("KD002", "와파린",     "쿠마딘정 2mg",            "warning", "출혈",     None),
    ("KD003", "클로피도그렐", "플라빅스정 75mg",       "warning", "출혈",     None),
    ("KD004", "아마릴",     "아마릴정 2mg",            "warning", "저혈당",   None),
    ("KD005", "인슐린",     "휴마로그주 100IU/mL",     "warning", "저혈당",   None),
    ("KD006", "디곡신",     "디고신정 0.25mg",         "warning", "부정맥",   None),
    ("KD007", "메트포르민", "다이아벡스정 500mg",      "warning", "유산산증", None),
    ("KD008", "프레드니솔론", "소론도정 5mg",          "warning", "부신저하", None),

    # 일반 약물 (normal) — 적응증만 표시
    ("KD101", "리피토",     "리피토정 10mg",           "normal",  None, "고지혈"),
    ("KD102", "크레스토",   "크레스토정 10mg",         "normal",  None, "고지혈"),
    ("KD103", "노바스크",   "노바스크정 5mg",          "normal",  None, "고혈압"),
    ("KD104", "코자",       "코자정 50mg",             "normal",  None, "고혈압"),
    ("KD105", "오메프라졸", "오메프라졸캡슐 20mg",     "normal",  None, "위산"),
    ("KD106", "타이레놀",   "타이레놀정 500mg",        "normal",  None, "진통"),
    ("KD107", "글루코파지", "글루코파지정 500mg",      "normal",  None, "당뇨"),
]


def seed():
    init_db()
    with get_conn() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO drug_master
               (kd_code, short_name, full_name, category, risk_keyword, indication)
               VALUES (?, ?, ?, ?, ?, ?)""",
            SEED_DRUGS,
        )
    print(f"[OK] {len(SEED_DRUGS)}개 약물 시드 데이터 삽입 완료")


if __name__ == "__main__":
    seed()
