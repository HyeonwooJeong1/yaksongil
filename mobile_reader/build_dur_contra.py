"""
DUR 병용금기 CSV → JSON 매핑 가공.

CSV 컬럼:
  성분명A, 성분코드A, 제품코드A, 제품명A, 업체명A, 급여여부A,
  성분명B, 성분코드B, 제품코드B, 제품명B, 업체명B, 급여여부B,
  고시번호, 고시일자, 상세정보, 비고

전략:
  - 성분코드(앞 6자리)는 같은 활성 성분 → 그 단위로 distinct
  - 우리 DB의 short_name과 일관되게 매핑 (음식 매핑과 같은 키 사용)
  - 양방향 매핑 (A→B, B→A)

출력: mobile_reader/data/dur_contraindications.json
  {
    "와파린": {
      "contraindicated_with": [
        {"name": "아스피린", "reason": "출혈 위험..."},
        ...
      ]
    },
    ...
  }
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from app.database import get_conn, init_db
from mobile_reader.normalize import normalize_name

PROJECT_ROOT = Path(__file__).parent.parent
DUR_DIR      = PROJECT_ROOT / "건강보험심사평가원_의약품안전사용서비스(DUR) 의약품 목록_20250601"
CSV_PATH     = DUR_DIR / "의약품안전사용서비스(DUR)_병용금기 품목리스트 2025.6.csv"

DATA_DIR     = Path(__file__).parent / "data"
OUTPUT_JSON  = DATA_DIR / "dur_contraindications.json"

# csv 모듈 필드 크기 한도 늘리기 (긴 상세정보 대비)
csv.field_size_limit(2**31 - 1)


def load_ingredient_to_name() -> dict[str, str]:
    """
    drug_master에서 ingredient_code 앞 6자리 → 정규화된 대표 short_name 매핑.
    normalize_name으로 제조사/제형/함량 제거 후 같은 성분 약물을 통합.
    """
    init_db()
    mapping: dict[str, str] = {}
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                SUBSTR(ingredient_code, 1, 6) AS code,
                MIN(short_name) AS name
            FROM drug_master
            WHERE ingredient_code IS NOT NULL
              AND ingredient_code != ''
              AND LENGTH(ingredient_code) >= 6
              AND short_name IS NOT NULL AND short_name != ''
            GROUP BY code
        """).fetchall()
        for r in rows:
            mapping[r["code"]] = normalize_name(r["name"])
    return mapping


def parse_csv(csv_path: Path, code_to_name: dict[str, str]) -> tuple[dict[str, dict], int, int]:
    """
    병용금기 CSV → { 정규화된 약물명: { contraindicated_with: [...] } }

    중복 제거 단계 (3중 안전망):
      1. 성분코드 앞 6자리 페어 중복 제거 (같은 성분 페어는 1번만)
      2. 정규화된 한글 이름 기준 페어 중복 제거 (이름은 같지만 코드 다른 경우)
      3. 각 entry의 contraindicated_with 내에서 이름 중복 제거
    """
    # _seen은 임시 set (JSON 직렬화 전 제거)
    contra: dict[str, dict] = defaultdict(lambda: {"contraindicated_with": [], "_seen": set()})
    code_pair_seen: set[tuple[str, str]] = set()
    name_pair_seen: set[tuple[str, str]] = set()

    total_rows  = 0
    paired_rows = 0

    with open(csv_path, encoding="cp949") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1

            code_a_full = (row.get("성분코드A") or "").strip()
            code_b_full = (row.get("성분코드B") or "").strip()
            if len(code_a_full) < 6 or len(code_b_full) < 6:
                continue

            code_a = code_a_full[:6]
            code_b = code_b_full[:6]
            if code_a == code_b:
                continue

            # 1) 코드 페어 dedup
            code_pair = tuple(sorted([code_a, code_b]))
            if code_pair in code_pair_seen:
                continue
            code_pair_seen.add(code_pair)

            ingredient_a = (row.get("성분명A") or "").strip()
            ingredient_b = (row.get("성분명B") or "").strip()
            reason       = (row.get("상세정보") or "").strip()

            # 한글 이름 (정규화됨) — 없으면 영문 fallback도 정규화
            name_a = code_to_name.get(code_a) or normalize_name(ingredient_a)
            name_b = code_to_name.get(code_b) or normalize_name(ingredient_b)
            if not name_a or not name_b or name_a == name_b:
                continue

            # 2) 정규화된 이름 페어 dedup (다른 코드인데 같은 이름인 경우 흡수)
            name_pair = tuple(sorted([name_a, name_b]))
            if name_pair in name_pair_seen:
                continue
            name_pair_seen.add(name_pair)
            paired_rows += 1

            # 3) entry 내 이름 중복 체크 (이중 안전망)
            entry_a = contra[name_a]
            if name_b not in entry_a["_seen"]:
                entry_a["_seen"].add(name_b)
                entry_a["contraindicated_with"].append({"name": name_b, "reason": reason})

            entry_b = contra[name_b]
            if name_a not in entry_b["_seen"]:
                entry_b["_seen"].add(name_a)
                entry_b["contraindicated_with"].append({"name": name_a, "reason": reason})

    # JSON 직렬화 전에 _seen 제거
    for entry in contra.values():
        entry.pop("_seen", None)

    return dict(contra), total_rows, paired_rows


def main():
    if not CSV_PATH.exists():
        print(f"[ERROR] 파일 없음: {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("  DUR 병용금기 데이터 가공")
    print("=" * 60)

    print("[1/3] DB에서 성분코드 → 약물명 매핑 로드 중...")
    code_to_name = load_ingredient_to_name()
    print(f"      {len(code_to_name):,}개 매핑 로드됨")

    print("[2/3] DUR 병용금기 CSV 파싱 중...")
    contra, total_rows, paired_rows = parse_csv(CSV_PATH, code_to_name)
    print(f"      CSV 행:        {total_rows:,}건")
    print(f"      유니크 페어:   {paired_rows:,}건")
    print(f"      약물 항목:     {len(contra):,}건 (양방향 매핑)")

    print("[3/3] JSON 저장 중...")
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(contra, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    size_kb = OUTPUT_JSON.stat().st_size / 1024

    print()
    print("=" * 60)
    print(f"[OK] {OUTPUT_JSON}")
    print(f"  약물 항목:     {len(contra):,}건")
    print(f"  파일 크기:     {size_kb:,.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
