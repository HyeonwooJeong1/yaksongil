"""
e약은요 API 호출 + 음식 키워드 자동 추출 → food_interactions.json.

DB의 자주 쓰이는 약물(상위 N개)을 식약처 e약은요 API로 조회하여
주의사항/상호작용 텍스트에서 음식 키워드를 추출.

실행:
    python -m mobile_reader.build_food_interactions [--limit 300]
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from app.database import get_conn, init_db
from app.services.external.mfds_eyakeunyo import (
    ApiKeyMissingError,
    search_drug,
)
from mobile_reader.food_keywords import find_food_matches
from mobile_reader.normalize import normalize_name

MOBILE_DIR  = Path(__file__).parent
DATA_DIR    = MOBILE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_JSON = DATA_DIR / "food_interactions.json"


# 노인 다제약물 시나리오 기준 임상 중요도 순서.
# 위쪽일수록 환자가 마주칠 확률 높고, 음식 상호작용 알려진 것 많음.
INDICATION_PRIORITY: list[str] = [
    # === 1순위: 노인 만성질환 빈도 최상위 (4대 대사질환) ===
    "고혈압", "고지혈", "당뇨", "위산",

    # === 2순위: 노인 흔한 동반 처방 ===
    "진통", "항히스타민", "갑상선", "골다공증",
    "변비", "위장운동", "구토",

    # === 3순위: 정신과·신경과 (다제약물 + 음식 상호작용 큼) ===
    "항우울", "정신과", "파킨슨", "치매", "항전간",

    # === 4순위: 감염·면역·호흡기 ===
    "항생제", "항진균", "항바이러스", "천식", "진해거담", "비강",

    # === 5순위: 비뇨·기타 만성질환 ===
    "비뇨", "통풍", "전립선", "녹내장",

    # === 6순위: 호르몬·대사·보충 ===
    "스테로이드", "호르몬", "성호르몬",
    "비타민", "칼슘", "무기질",

    # === 7순위: 외용·국소 (음식 상호작용 거의 없음) ===
    "외용소독", "외용진통", "안과", "이과", "피부",

    # 매핑 안 된 것은 최하위
]


def _priority_score(indication: str | None) -> int:
    """indication을 임상 중요도 점수로 변환 (낮을수록 우선)."""
    if not indication:
        return 999
    for i, ind in enumerate(INDICATION_PRIORITY):
        if ind in indication:  # 부분 매칭
            return i
    return 999


def fetch_target_drugs(limit: int | None = None,
                       only_meaningful: bool = True) -> list[dict]:
    """
    DB에서 음식 매핑 대상 약물 선택.

    우선순위 (점수 낮을수록 우선):
      0. warning 카테고리 (응급 위험 약물 — 무조건 1순위)
      1~N. normal 약물 중 indication이 INDICATION_PRIORITY 리스트에 가까운 순
      999. indication 매핑 안 된 것 (제외 가능)

    short_name 기준 distinct.
    """
    init_db()
    with get_conn() as conn:
        # 한국 표준 일반명코드 형식: 앞 6자리=성분 ID, 뒤 3자리=제형 코드
        # 예: 378610ATB (쿠에티아핀 12.5mg 정), 378605ATB (쿠에티아핀 25mg 정)
        # 같은 성분 → 앞 6자리 동일. 제형 코드 떼고 distinct.
        #
        # ingredient_code가 NULL/빈 행은 제외:
        #   - 한약재 (e약은요에 정보 없음)
        #   - 매핑 안 된 약물
        warning_rows = conn.execute("""
            SELECT
                SUBSTR(ingredient_code, 1, 6) AS gk,
                MIN(short_name)  AS short_name,
                MIN(kd_code)     AS kd_code,
                'warning'        AS category,
                MAX(risk_keyword) AS risk_keyword,
                NULL             AS indication
            FROM drug_master
            WHERE category='warning'
              AND ingredient_code IS NOT NULL
              AND ingredient_code != ''
              AND LENGTH(ingredient_code) >= 6
              AND short_name IS NOT NULL AND short_name != ''
            GROUP BY gk
        """).fetchall()

        normal_query = """
            SELECT
                SUBSTR(ingredient_code, 1, 6) AS gk,
                MIN(short_name)  AS short_name,
                MIN(kd_code)     AS kd_code,
                'normal'         AS category,
                NULL             AS risk_keyword,
                MAX(indication)  AS indication
            FROM drug_master
            WHERE category='normal'
              AND ingredient_code IS NOT NULL
              AND ingredient_code != ''
              AND LENGTH(ingredient_code) >= 6
              AND short_name IS NOT NULL AND short_name != ''
        """
        if only_meaningful:
            normal_query += " AND indication != '기타'"
        normal_query += " GROUP BY gk"
        normal_rows = conn.execute(normal_query).fetchall()

        # warning은 점수 -1 (최우선)
        warning_list = [(-1, dict(r)) for r in warning_rows]
        # normal은 indication 기반 점수
        normal_list = [(_priority_score(dict(r).get("indication")), dict(r))
                       for r in normal_rows]

        combined = sorted(warning_list + normal_list,
                          key=lambda x: (x[0], x[1]["short_name"] or ""))

        # normalized 이름 기준 distinct (제조사/제형 제거 후 같은 약물 묶기)
        seen_norm: set[str] = set()
        result: list[dict] = []
        for _, d in combined:
            original = (d.get("short_name") or "").strip()
            if not original or len(original) < 2 or original.isdigit():
                continue
            norm = normalize_name(original)
            if norm in seen_norm:
                continue
            seen_norm.add(norm)
            # short_name을 정규화된 이름으로 교체 (검색/저장용)
            d["short_name"] = norm
            d["original_name"] = original
            result.append(d)

        if limit:
            result = result[:limit]
        return result


def extract_for_drug(drug: dict) -> dict | None:
    """
    한 약물에 대해 e약은요 검색 → 음식 키워드 추출.
    매칭이 없으면 None.
    """
    name = drug["short_name"]
    try:
        results = search_drug(name, num_of_rows=3)
    except Exception as e:
        print(f"  [WARN] {name}: API 호출 실패 — {e}", file=sys.stderr)
        return None

    if not results:
        return None

    # 첫 1~3건의 텍스트를 결합 (같은 성분 다른 제품이라 정보 유사)
    text = " ".join(
        (r.get("caution") or "") + " " + (r.get("interaction") or "")
        for r in results[:3]
    )
    foods = find_food_matches(text)
    if not foods:
        return None

    return {
        "short_name": name,
        "foods":      foods,
    }


def load_progress() -> dict[str, dict]:
    """이전 실행에서 부분 완료된 결과가 있으면 로드 (재개)."""
    if OUTPUT_JSON.exists():
        try:
            return json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_progress(data: dict) -> None:
    """중간 저장 — 끊겨도 부분 결과 보존."""
    OUTPUT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="처리할 약물 최대 수 (생략하면 전체)")
    parser.add_argument("--workers", type=int, default=10,
                        help="동시 API 호출 수 (기본 10). 너무 높으면 차단 위험")
    parser.add_argument("--fresh", action="store_true",
                        help="기존 진행 무시하고 처음부터 다시")
    args = parser.parse_args()

    # API 키 확인
    from app.services.external.mfds_eyakeunyo import API_KEY
    if not API_KEY:
        print("[ERROR] MFDS_API_KEY가 .env에 없습니다.", file=sys.stderr)
        sys.exit(1)

    targets = fetch_target_drugs(args.limit)
    output = {} if args.fresh else load_progress()
    todo = [d for d in targets if d["short_name"] not in output]

    print("=" * 60)
    print("  음식-약물 상호작용 자동 추출 (병렬 호출)")
    print(f"  전체 대상:   {len(targets):,}건")
    print(f"  이미 완료:   {len(output):,}건")
    print(f"  처리 예정:   {len(todo):,}건")
    print(f"  동시 호출:   {args.workers}개 worker")
    # 단일 호출 약 0.5초 가정, workers로 나눔
    eta_min = len(todo) * 0.5 / args.workers / 60
    print(f"  예상 소요:   약 {eta_min:.1f}분")
    print("=" * 60)
    print()

    SAVE_EVERY = 50
    lock = Lock()
    completed = 0
    matched_in_session = 0

    def worker(drug: dict) -> tuple[str, dict | None]:
        return drug["short_name"], extract_for_drug(drug)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(worker, d): d for d in todo}
        for future in as_completed(futures):
            try:
                name, result = future.result()
            except Exception as e:
                print(f"  [ERR] {e}", file=sys.stderr)
                continue

            with lock:
                completed += 1
                prefix = f"  [{completed:>4d}/{len(todo)}]"

                if result:
                    foods_summary = ", ".join(f["label"] for f in result["foods"])
                    print(f"{prefix} {name:>20s} → {foods_summary}")
                    output[name] = result
                    matched_in_session += 1
                else:
                    output[name] = {"short_name": name, "foods": []}
                    if completed % 50 == 0:
                        print(f"{prefix} (...진행 중, 매칭 누적 {matched_in_session}건)")

                if completed % SAVE_EVERY == 0:
                    save_progress(output)

    save_progress(output)

    matched = {k: v for k, v in output.items() if v.get("foods")}
    total_mappings = sum(len(v["foods"]) for v in matched.values())
    print()
    print("=" * 60)
    print(f"[OK] {OUTPUT_JSON}")
    print(f"  처리 완료:   {len(output):,}건")
    print(f"  음식 매칭:   {len(matched):,}건 ({len(matched)/max(len(output),1)*100:.1f}%)")
    print(f"  매핑 항목:   {total_mappings:,}건")
    print(f"  파일 크기:   {OUTPUT_JSON.stat().st_size / 1024:.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
