"""
심평원 DUR 노인주의 의약품 목록 CSV → drug_master 적재.

실행: python -m app.services.external.hira_dur_loader
"""
import csv
import re
from pathlib import Path

from app.database import get_conn, init_db
from app.services.external.risk_mapper import extract_risk_keyword

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DUR_DIR = PROJECT_ROOT / "건강보험심사평가원_의약품안전사용서비스(DUR) 의약품 목록_20250601"

ELDERLY_CSV       = DUR_DIR / "의약품안전사용서비스(DUR)_노인주의 품목리스트 2025.6.csv"
ELDERLY_NSAID_CSV = DUR_DIR / "의약품안전사용서비스(DUR)_노인주의(해열진통소염제) 품목리스트 2025.6.csv"


def _extract_short_name(product_name: str) -> str:
    """
    제품명에서 짧은 약물명을 뽑아낸다.
    예) '쿠티아핀정12.5밀리그램(쿠에티아핀푸마르산염)_(14.39mg/1정)' → '쿠티아핀'
    """
    name = re.split(r"[(_]", product_name, maxsplit=1)[0]
    name = re.sub(
        r"\d+(\.\d+)?\s*(밀리그램|마이크로그램|밀리|mg|mcg|g|IU|단위).*$",
        "",
        name,
    )
    name = name.strip()
    return name or product_name[:12]


def load_dur_csv(csv_path: Path, code_prefix: str) -> int:
    """
    DUR CSV 파일을 읽어 drug_master에 적재.
    같은 성분명은 첫 1건만 사용 (중복 제거).
    """
    init_db()

    seen_ingredients: set[str] = set()
    rows_to_insert: list[tuple] = []

    with open(csv_path, encoding="cp949") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ingredient = (row.get("성분명") or "").strip()
            main_code  = (row.get("성분코드") or "").strip()
            product    = (row.get("제품명") or "").strip()
            reason     = (row.get("약품상세정보") or "").strip()

            if not ingredient or ingredient in seen_ingredients:
                continue
            seen_ingredients.add(ingredient)

            short_name = _extract_short_name(product)
            risk       = extract_risk_keyword(reason)
            kd_code    = f"{code_prefix}{main_code}"

            rows_to_insert.append(
                (kd_code, short_name, product, "warning", risk, None,
                 main_code or None, ingredient or None)
            )

    with get_conn() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO drug_master
               (kd_code, short_name, full_name, category, risk_keyword,
                indication, ingredient_code, english_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows_to_insert,
        )

    return len(rows_to_insert)


def load_all():
    if not DUR_DIR.exists():
        raise FileNotFoundError(f"DUR 디렉토리 없음: {DUR_DIR}")

    n1 = load_dur_csv(ELDERLY_CSV,       "DUR_ELD_")
    n2 = load_dur_csv(ELDERLY_NSAID_CSV, "DUR_NSD_")

    print(f"[OK] DUR 노인주의 약물 적재 완료")
    print(f"     - 일반 노인주의:    {n1}건")
    print(f"     - 해열진통소염제:   {n2}건")
    print(f"     - 합계:             {n1 + n2}건")


if __name__ == "__main__":
    load_all()
