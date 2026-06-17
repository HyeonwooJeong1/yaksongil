"""
심평원 약제급여목록(급여상한금액표) xlsx → 보험코드 → 우리 약물 매핑.

약국 전산 프로그램이 쓰는 보험코드(제품코드, 청구/EDI 9자리)를 우리 DB 약물에 연결.
경로:  보험코드(제품코드) → 주성분코드(앞 6자리) → drug_master 대표 kd_code
        (대표 선정은 build_static.py의 distinct 기준과 동일: 성분6 GROUP BY → MIN(kd_code))

입력: 프로젝트 루트의 약제급여목록*.xlsx (제품코드 + 주성분코드 컬럼)
출력: mobile_reader/data/bohum_index.json   { "645302132": "HIRA_8806...", ... }

실행: python -m app.services.external.hira_benefit_loader
      (xlsx 파싱을 위해 openpyxl 필요 — conda 환경에 기본 포함)
"""
import glob
import json
import sys
from pathlib import Path

import openpyxl

from app.database import get_conn, init_db

ROOT = Path(__file__).parent.parent.parent.parent
OUT = ROOT / "mobile_reader" / "data" / "bohum_index.json"
XLSX_PATTERN = "약제급여목록*.xlsx"


def find_xlsx() -> Path:
    matches = sorted(ROOT.glob(XLSX_PATTERN))
    if not matches:
        raise FileNotFoundError(
            f"{XLSX_PATTERN} 파일이 프로젝트 루트에 없습니다.\n"
            f"심평원 '약제급여목록 및 급여상한금액표' xlsx를 다운로드해 두세요."
        )
    return matches[-1]  # 가장 최신(파일명 정렬)


def _norm(h) -> str:
    return ("" if h is None else str(h)).replace("\n", "").replace(" ", "")


def build() -> dict:
    init_db()

    # 1) 우리 DB: 성분6 → 대표 kd_code (build_static의 distinct 대표와 동일)
    ingr6_to_kd: dict[str, str] = {}
    with get_conn() as conn:
        for c6, kd in conn.execute("""
            SELECT SUBSTR(ingredient_code, 1, 6) AS c6, MIN(kd_code) AS kd
            FROM drug_master
            WHERE ingredient_code NOT LIKE 'STD:%'
              AND ingredient_code != '' AND ingredient_code IS NOT NULL
              AND LENGTH(ingredient_code) >= 6
            GROUP BY c6
        """):
            if c6:
                ingr6_to_kd[c6] = kd
    print(f"[INFO] 성분6 → 대표약물: {len(ingr6_to_kd):,}개")

    # 2) xlsx 헤더에서 제품코드 / 주성분코드 컬럼 인덱스 탐색 (위치 변동 대비, 이름 기준)
    xlsx = find_xlsx()
    print(f"[INFO] 약제급여목록: {xlsx.name}")
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows)

    ci_prod = next((i for i, h in enumerate(header) if "제품코드" in _norm(h)), None)
    # '주성분코드'(동일제형 아님) 정확 매칭 우선, 없으면 '주성분코드' 포함 첫 컬럼
    ci_ingr = next((i for i, h in enumerate(header) if _norm(h) == "주성분코드"), None)
    if ci_ingr is None:
        ci_ingr = next((i for i, h in enumerate(header) if "주성분코드" in _norm(h)), None)
    if ci_prod is None or ci_ingr is None:
        print(f"[ERROR] 컬럼 탐색 실패 (제품코드={ci_prod}, 주성분코드={ci_ingr})", file=sys.stderr)
        print(f"        헤더: {[_norm(h) for h in header]}", file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] 컬럼 인덱스 - 제품코드={ci_prod}, 주성분코드={ci_ingr}")

    # 3) 보험코드 → 대표 kd_code
    bohum: dict[str, str] = {}
    total = mapped = miss = 0
    for row in rows:
        total += 1
        prod = ("" if row[ci_prod] is None else str(row[ci_prod])).strip()
        ingr = ("" if row[ci_ingr] is None else str(row[ci_ingr])).strip()
        if not prod or len(ingr) < 6:
            continue
        kd = ingr6_to_kd.get(ingr[:6])
        if kd:
            bohum[prod] = kd
            mapped += 1
        else:
            miss += 1

    print(f"[INFO] 급여목록 행: {total:,}")
    print(f"[INFO] 매핑 성공:   {mapped:,}  ({mapped/max(total,1)*100:.1f}%)")
    print(f"[INFO] 성분 미보유: {miss:,}  (우리 DB에 해당 성분 없음)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bohum, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return {"total": total, "mapped": mapped, "miss": miss}


if __name__ == "__main__":
    build()
