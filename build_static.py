"""
정적 HTML 빌드 스크립트.

DB의 약물 마스터를 JSON → gzip → base64로 인코딩하여
templates/standalone.html의 {{DRUGS_GZIP_B64}} 자리에 삽입.

결과: dist/qr_generator.html (백엔드 불필요한 단일 파일)

실행:
    python build_static.py
"""
import base64
import gzip
import json
import sys
from pathlib import Path

import requests

from app.database import get_conn, init_db

PROJECT_ROOT     = Path(__file__).parent
TEMPLATE         = PROJECT_ROOT / "templates" / "standalone.html"
# 통합 주의정보 (병용금기+노인주의+효능군중복+음식+출처). 옛 분리 파일 대체.
CAUTIONS_JSON    = PROJECT_ROOT / "mobile_reader" / "data" / "drug_cautions.json"
# 보험코드(제품코드 9자리) → 우리 약물 매핑 (약제급여목록 기반). 전산 프로그램 코드 붙여넣기용.
BOHUM_JSON       = PROJECT_ROOT / "mobile_reader" / "data" / "bohum_index.json"
QRCODE_JS_CACHE  = PROJECT_ROOT / "templates" / "_qrcode.min.js"
QRCODE_JS_URL    = "https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.min.js"
# QR 스캔용 jsQR (mobile_reader 빌드와 캐시 공유)
JSQR_JS_CACHE    = PROJECT_ROOT / "mobile_reader" / "templates" / "_jsQR.js"
JSQR_JS_URL      = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"
DIST_DIR         = PROJECT_ROOT / "dist"
OUTPUT           = DIST_DIR / "qr_generator.html"


def _fetch_cached(cache: Path, url: str, label: str) -> str:
    """캐시 우선 로드, 없으면 다운로드."""
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    print(f"[INFO] {label} 다운로드: {url}")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(r.text, encoding="utf-8")
    print(f"[INFO] 캐시 저장: {cache.name} ({len(r.text)/1024:.1f} KB)")
    return r.text


def fetch_qrcode_js() -> str:
    return _fetch_cached(QRCODE_JS_CACHE, QRCODE_JS_URL, "qrcode.js")


def fetch_jsqr_js() -> str:
    return _fetch_cached(JSQR_JS_CACHE, JSQR_JS_URL, "jsQR.js")


def gzip_b64_file(json_path: Path, label: str) -> str:
    """JSON 파일 → gzip → base64. 없으면 빈 객체 '{}'를 인코딩."""
    if json_path.exists():
        raw = json_path.read_text(encoding="utf-8").encode("utf-8")
    else:
        print(f"[WARN] {label} 파일 없음 ({json_path.name}) — 빈 데이터로 진행")
        raw = b"{}"
    comp = gzip.compress(raw, compresslevel=9)
    b64 = base64.b64encode(comp).decode("ascii")
    print(f"  {label}: {len(raw)/1024:>7,.0f} KB → gzip {len(comp)/1024:>6,.0f} KB")
    return b64


def slim(drug: dict) -> dict:
    """HTML 임베드용 축소 — 필요한 필드만, null은 제거."""
    out = {
        "kd_code":    drug["kd_code"],
        "short_name": drug["short_name"],
        "category":   drug["category"],
    }
    if drug.get("risk_keyword"):    out["risk_keyword"]    = drug["risk_keyword"]
    if drug.get("indication"):      out["indication"]      = drug["indication"]
    # 'STD:' 접두사(표준코드 fallback)는 내부용이므로 표시에서 제거
    ic = drug.get("ingredient_code")
    if ic:
        out["ingredient_code"] = ic[4:] if ic.startswith("STD:") else ic
    if drug.get("english_name"):    out["english_name"]    = drug["english_name"]
    if drug.get("full_name") and drug["full_name"] != drug["short_name"]:
        out["full_name"] = drug["full_name"]
    return out


def fetch_distinct_drugs() -> list[dict]:
    """
    성분 기준 distinct로 약물 조회 (database.GROUP_KEY_SQL 재사용).
    검색용 모든 컬럼(short_name, full_name, kd_code, ingredient_code, english_name) 포함.
    """
    from app.database import GROUP_KEY_SQL
    init_db()
    group_key = GROUP_KEY_SQL
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
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
            FROM drug_master
            GROUP BY {group_key}, category
            ORDER BY CASE category WHEN 'warning' THEN 0 ELSE 1 END,
                     MIN(short_name)
        """).fetchall()
        return [dict(r) for r in rows]


def build():
    init_db()
    drugs = fetch_distinct_drugs()
    if not drugs:
        print("[ERROR] DB가 비어있습니다. 먼저 데이터 적재가 필요합니다:", file=sys.stderr)
        print("  python -m app.seed", file=sys.stderr)
        print("  python -m app.services.external.hira_dur_loader", file=sys.stderr)
        print("  python -m app.services.external.hira_drug_price_loader", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print(f"  정적 HTML 빌드 시작 — {len(drugs):,}건")
    print("=" * 60)

    slimmed = [slim(d) for d in drugs]
    json_str = json.dumps(slimmed, ensure_ascii=False, separators=(",", ":"))
    json_size = len(json_str.encode("utf-8"))

    compressed = gzip.compress(json_str.encode("utf-8"), compresslevel=9)
    b64 = base64.b64encode(compressed).decode("ascii")

    print(f"  JSON 원본:    {json_size / 1024:>8,.1f} KB")
    print(f"  gzip 압축:    {len(compressed) / 1024:>8,.1f} KB  ({len(compressed)/json_size*100:.1f}%)")
    print(f"  base64 인코딩: {len(b64) / 1024:>8,.1f} KB")
    print()

    if not TEMPLATE.exists():
        print(f"[ERROR] 템플릿 없음: {TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    template = TEMPLATE.read_text(encoding="utf-8")
    for placeholder in ("{{DRUGS_GZIP_B64}}", "{{QRCODE_JS}}", "{{JSQR_JS}}",
                        "{{CAUTIONS_GZIP_B64}}", "{{BOHUM_GZIP_B64}}"):
        if placeholder not in template:
            print(f"[ERROR] 템플릿에 {placeholder} 자리 표시자 없음", file=sys.stderr)
            sys.exit(1)

    qrcode_js = fetch_qrcode_js()
    jsqr_js   = fetch_jsqr_js()
    print(f"  qrcode.js:   {len(qrcode_js) / 1024:>8,.1f} KB (인라인)")
    print(f"  jsQR.js:     {len(jsqr_js) / 1024:>8,.1f} KB (인라인, QR 스캔용)")

    # 통합 주의정보 임베드 (병용금기+노인주의+효능군중복+음식)
    cautions_b64 = gzip_b64_file(CAUTIONS_JSON, "통합 주의정보")
    bohum_b64 = gzip_b64_file(BOHUM_JSON, "보험코드 매핑")
    print()

    html = (
        template
        .replace("{{DRUGS_GZIP_B64}}",     b64)
        .replace("{{QRCODE_JS}}",          qrcode_js)
        .replace("{{JSQR_JS}}",            jsqr_js)
        .replace("{{CAUTIONS_GZIP_B64}}",  cautions_b64)
        .replace("{{BOHUM_GZIP_B64}}",     bohum_b64)
    )

    DIST_DIR.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    size_mb = OUTPUT.stat().st_size / 1024 / 1024

    print(f"[OK] {OUTPUT}")
    print(f"     최종 크기:   {size_mb:.2f} MB")
    print()
    print("이 파일 하나를 약국에 전달하면 됩니다.")
    print("약사는 더블클릭하여 브라우저에서 바로 실행할 수 있습니다.")


if __name__ == "__main__":
    build()
