"""
심평원 약가마스터 의약품표준코드 CSV → drug_master 적재.

약 4-5만 건의 한국 시중 의약품을 ATC 코드 기반으로 자동 분류.

실행: python -m app.services.external.hira_drug_price_loader
"""
import csv
import re
import sys
from pathlib import Path

from app.database import (
    drop_secondary_indexes,
    get_conn,
    init_db,
    rebuild_secondary_indexes,
)
from app.services.external.category_mapper import is_herbal, map_intl_atc

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# 파일명 패턴 — 날짜가 바뀌어도 자동으로 찾기
CSV_PATTERN = "건강보험심사평가원_약가마스터_의약품표준코드_*.csv"

BATCH_SIZE = 1000

# CSV가 거대해서 Python 기본 필드 사이즈를 초과할 수 있음
csv.field_size_limit(2**31 - 1)


def _extract_short_name(product_name: str) -> str:
    """
    제품명에서 짧은 약물명 추출.
    복합제 함량 표기('5/40밀리그램')의 슬래시·숫자도 함량의 일부로 처리하여
    '노바스크오정5/'처럼 잘리지 않도록 한다.
    """
    name = re.split(r"[(_]", product_name, maxsplit=1)[0]
    # 함량 패턴: 숫자(소수/슬래시 조합 포함)가 단위 앞에 오면 거기서부터 제거.
    # 예: '노바스크오정5/40밀리그램' → '노바스크오정'
    #     '리피토정10mg' → '리피토정'
    name = re.sub(
        r"[\d./]+\s*(밀리그램|마이크로그램|밀리|mg|mcg|g|IU|단위|%|퍼센트|그램|밀리리터|mL|국제단위).*$",
        "",
        name,
    )
    # 단위 없이 끝에 '숫자/' 또는 '/숫자'만 남은 경우(슬래시 절단 흔적) 제거
    name = re.sub(r"[\d/]+$", "", name)
    name = name.strip()
    return name or product_name[:12]


def find_csv() -> Path:
    matches = list(PROJECT_ROOT.glob(CSV_PATTERN))
    if not matches:
        raise FileNotFoundError(
            f"약가마스터 CSV 파일을 찾을 수 없습니다.\n"
            f"패턴: {CSV_PATTERN}\n"
            f"위치: {PROJECT_ROOT}\n"
            f"공공데이터포털에서 다운로드 후 프로젝트 루트에 두세요."
        )
    return sorted(matches)[-1]  # 가장 최신 날짜


def load_drug_price_master() -> dict:
    """약가마스터 CSV 적재. 통계 dict 반환."""
    init_db()
    csv_path = find_csv()
    print(f"[INFO] 파일: {csv_path.name} ({csv_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # 대량 적재 전 보조 인덱스 제거 (적재 중 인덱스 갱신 비용 제거 → 후반 급가속).
    # PRIMARY KEY(kd_code) 인덱스는 INSERT OR REPLACE에 필요하므로 유지.
    drop_secondary_indexes()
    print("[INFO] 보조 인덱스 제거 후 적재 시작 (완료 후 재생성)")

    stats = {
        "total":        0,
        "skipped_empty": 0,
        "skipped_dup":   0,
        "warning":       0,
        "normal":        0,
        "uncategorized": 0,
        "herbal":        0,
    }
    seen: set[str] = set()
    batch: list[tuple] = []

    with open(csv_path, encoding="cp949") as f, get_conn() as conn:
        # ── 대량 적재 성능 튜닝 ──
        # 인덱스 5개가 매 INSERT마다 갱신되면 후반부로 갈수록 급격히 느려짐.
        # 적재 동안 동기화/저널을 완화하고, 단일 트랜잭션으로 묶는다.
        conn.execute("PRAGMA journal_mode = MEMORY")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -200000")  # 약 200MB 캐시
        conn.execute("BEGIN")

        reader = csv.DictReader(f)
        for row in reader:
            stats["total"] += 1

            product = (row.get("한글상품명") or "").strip()
            standard_code = (row.get("표준코드") or "").strip()
            ingredient_code_raw = (row.get("일반명코드(성분명코드)") or "").strip()
            atc = (row.get("국제표준코드(ATC코드)") or "").strip()
            cancel_date = (row.get("취소일자") or "").strip()
            drug_type = (row.get("전문일반구분") or "").strip()

            # 빈 데이터만 제외. 취소일자 약물도 적재한다.
            # (와파린 등 중요 약이 전부 '취소' 표기되어 통째로 누락되는 문제 방지.
            #  취소 여부는 병용금기/성분 매칭에 영향 없고, 데이터 전체를 활용)
            if not product or not standard_code:
                stats["skipped_empty"] += 1
                continue

            # 중복 제거 (같은 표준코드)
            kd_code = f"HIRA_{standard_code}"
            if kd_code in seen:
                stats["skipped_dup"] += 1
                continue
            seen.add(kd_code)

            short_name = _extract_short_name(product)
            category, keyword = map_intl_atc(atc)

            # 한약/생약은 응급 위험약(warning)으로 분류하면 의료진을 오도하므로
            # 무조건 normal로 강등 (예: B01AX 단 당귀작약산 → 출혈 오분류 방지)
            if is_herbal(product, drug_type):
                category = "normal"
                keyword = "한약/생약"
                stats["herbal"] = stats.get("herbal", 0) + 1

            if category == "warning":
                stats["warning"] += 1
                risk_keyword = keyword
                indication = None
            else:
                stats["normal"] += 1
                if keyword == "기타":
                    stats["uncategorized"] += 1
                risk_keyword = None
                indication = keyword

            # 일반명코드(성분코드)가 약가마스터에서 약 55% 비어있음(한약재/비급여 등).
            # 없으면 표준코드를 fallback으로 사용해 모든 약에 코드가 있도록 보장.
            # 단, 성분 기준 distinct를 위해 일반명코드 여부를 구분할 수 있게
            # 표준코드 fallback은 'STD:' 접두사를 붙여 저장.
            if ingredient_code_raw:
                ing_code = ingredient_code_raw
            else:
                ing_code = f"STD:{standard_code}"

            batch.append(
                (kd_code, short_name, product, category, risk_keyword, indication,
                 ing_code)
            )

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    """INSERT OR REPLACE INTO drug_master
                       (kd_code, short_name, full_name, category, risk_keyword, indication, ingredient_code)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    batch,
                )
                batch.clear()
                print(f"  진행: {len(seen):,}건...")

        if batch:
            conn.executemany(
                """INSERT OR REPLACE INTO drug_master
                   (kd_code, short_name, full_name, category, risk_keyword, indication, ingredient_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                batch,
            )

    return stats


def main():
    print("=" * 60)
    print("심평원 약가마스터 의약품표준코드 적재 시작")
    print("=" * 60)
    try:
        stats = load_drug_price_master()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print("[INFO] 보조 인덱스 재생성 중...")
    rebuild_secondary_indexes()
    print("[INFO] 인덱스 재생성 완료")

    print()
    print("=" * 60)
    print("[OK] 적재 완료")
    print(f"  전체 행:        {stats['total']:,}건")
    print(f"  빈 행/취소:     {stats['skipped_empty']:,}건 (제외)")
    print(f"  중복:           {stats['skipped_dup']:,}건 (제외)")
    print(f"  적재 합계:      {stats['warning'] + stats['normal']:,}건")
    print(f"    └ warning:    {stats['warning']:,}건")
    print(f"    └ normal:     {stats['normal']:,}건")
    print(f"       └ 미분류:  {stats['uncategorized']:,}건 (ATC 매핑 없음)")
    print(f"       └ 한약/생약: {stats['herbal']:,}건 (normal 강제)")
    print("=" * 60)


if __name__ == "__main__":
    main()
