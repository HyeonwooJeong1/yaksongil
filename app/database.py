import sqlite3
from contextlib import contextmanager

from app.paths import db_path

DB_PATH = db_path()

# 약물 distinct GROUP BY 키:
#   - ingredient_code가 'STD:'로 시작(표준코드 fallback) → 전체를 키로 (품목별 구분)
#   - 일반명코드(성분코드)면 → 앞 6자리(성분 ID)로 묶어 같은 성분 변형 통합
#   - 둘 다 없으면 → short_name fallback
GROUP_KEY_SQL = (
    "CASE "
    "WHEN ingredient_code LIKE 'STD:%' THEN ingredient_code "
    "WHEN ingredient_code IS NOT NULL AND ingredient_code != '' "
    "  THEN SUBSTR(ingredient_code, 1, 6) "
    "ELSE '_NC_' || short_name END"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS drug_master (
    kd_code         TEXT PRIMARY KEY,
    short_name      TEXT NOT NULL,
    full_name       TEXT,
    category        TEXT NOT NULL CHECK (category IN ('warning', 'normal')),
    risk_keyword    TEXT,
    indication      TEXT,
    ingredient_code TEXT,
    english_name    TEXT
);

CREATE INDEX IF NOT EXISTS idx_short_name ON drug_master(short_name);
CREATE INDEX IF NOT EXISTS idx_category   ON drug_master(category);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SECONDARY_INDEXES = {
    "idx_short_name":      "short_name",
    "idx_category":        "category",
    "idx_ingredient_code": "ingredient_code",
    "idx_english_name":    "english_name",
}


def drop_secondary_indexes():
    """대량 적재 전 보조 인덱스 제거 (PK 제외)."""
    with get_conn() as conn:
        for idx in SECONDARY_INDEXES:
            conn.execute(f"DROP INDEX IF EXISTS {idx}")


def rebuild_secondary_indexes():
    """적재 후 보조 인덱스 재생성."""
    with get_conn() as conn:
        for idx, col in SECONDARY_INDEXES.items():
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON drug_master({col})")


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Migration: 기존 DB에 새 컬럼이 없으면 추가 (idempotent)
        # ALTER TABLE → INDEX 순서 분리 (인덱스 생성 전 컬럼 존재 보장)
        for col in ("ingredient_code", "english_name"):
            try:
                conn.execute(f"ALTER TABLE drug_master ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass  # 컬럼 이미 존재
        for col, idx in [
            ("ingredient_code", "idx_ingredient_code"),
            ("english_name",    "idx_english_name"),
        ]:
            try:
                conn.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON drug_master({col})")
            except sqlite3.OperationalError:
                pass


def fetch_drugs_by_codes(codes: list[str]) -> list[dict]:
    if not codes:
        return []
    placeholders = ",".join("?" * len(codes))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM drug_master WHERE kd_code IN ({placeholders})",
            codes,
        ).fetchall()
        return [dict(r) for r in rows]


def fetch_all_drugs() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM drug_master ORDER BY category DESC, short_name"
        ).fetchall()
        return [dict(r) for r in rows]


import re as _re


def search_drugs(query: str = "", limit: int = 50, offset: int = 0) -> dict:
    """
    검색어 매칭으로 약물 조회.

    개선점:
      - ingredient_code 앞 6자리 기준 distinct (같은 성분의 변형 통합)
      - 검색 컬럼 확장: short_name + full_name + kd_code + ingredient_code + english_name
      - 콤마/공백으로 여러 검색어 분리 (OR 매칭)
      - warning 약물이 항상 먼저 나오도록 정렬
    """
    query = (query or "").strip()
    # 콤마 또는 공백으로 다중 검색어 분리
    terms = [t.strip() for t in _re.split(r"[,\s]+", query) if t.strip()]

    group_key = GROUP_KEY_SQL

    # 대표 ingredient_code 선택: 실제 일반명코드(숫자 시작) > STD: > NULL 순.
    # 일반명코드는 '168402BIJ'처럼 숫자 시작, STD는 'STD:' 시작이라
    # 'STD:' 행을 NULL로 치환 후 MIN하면 실제 코드가 우선 선택됨.
    select_cols = f"""
        MIN(kd_code)         AS kd_code,
        MIN(short_name)      AS short_name,
        MIN(full_name)       AS full_name,
        category             AS category,
        MAX(risk_keyword)    AS risk_keyword,
        MAX(indication)      AS indication,
        COALESCE(
            MIN(CASE WHEN ingredient_code NOT LIKE 'STD:%' THEN ingredient_code END),
            MIN(ingredient_code)
        )                    AS ingredient_code,
        MAX(english_name)    AS english_name
    """

    where = ""
    params: list = []
    if terms:
        # 각 term은 여러 컬럼에서 LIKE OR 매칭, 모든 term은 다시 OR로 묶임
        conds = []
        for t in terms:
            p = f"%{t}%"
            conds.append(
                "(short_name LIKE ? OR full_name LIKE ? "
                "OR kd_code LIKE ? OR ingredient_code LIKE ? OR english_name LIKE ?)"
            )
            params.extend([p, p, p, p, p])
        where = " WHERE " + " OR ".join(conds)

    with get_conn() as conn:
        # 전체 distinct 그룹 개수
        count_sql = f"""
            SELECT COUNT(*) FROM (
                SELECT {group_key} AS gk
                FROM drug_master
                {where}
                GROUP BY {group_key}, category
            )
        """
        count = conn.execute(count_sql, params).fetchone()[0]

        # 결과 조회 (distinct + 정렬 + 페이지네이션)
        results_sql = f"""
            SELECT {select_cols}
            FROM drug_master
            {where}
            GROUP BY {group_key}, category
            ORDER BY CASE category WHEN 'warning' THEN 0 ELSE 1 END,
                     MIN(short_name)
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(results_sql, params + [limit, offset]).fetchall()

        return {
            "total":  count,
            "limit":  limit,
            "offset": offset,
            "drugs":  [dict(r) for r in rows],
        }


def count_drugs() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM drug_master").fetchone()[0]


def insert_or_update_drug(
    kd_code: str,
    short_name: str,
    full_name: str | None,
    category: str,
    risk_keyword: str | None,
    indication: str | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO drug_master
               (kd_code, short_name, full_name, category, risk_keyword, indication)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (kd_code, short_name, full_name, category, risk_keyword, indication),
        )


def drug_exists(kd_code: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM drug_master WHERE kd_code = ?", (kd_code,)
        ).fetchone()
        return row is not None
