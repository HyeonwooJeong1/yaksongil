"""
모바일 PWA 리더 빌드 스크립트.

입력:
  - mobile_reader/templates/reader.html  (PWA 템플릿)
  - mobile_reader/data/drug_cautions.json (통합 주의정보)
  - jsQR 라이브러리 (CDN에서 캐시)

출력:
  - mobile_reader/dist/reader.html (단일 PWA 파일)

실행:
    python -m mobile_reader.build_reader
"""
import base64
import gzip
import json
import sys
from pathlib import Path

import requests

MOBILE_DIR  = Path(__file__).parent
TEMPLATE    = MOBILE_DIR / "templates" / "reader.html"
DATA_DIR    = MOBILE_DIR / "data"
DIST_DIR    = MOBILE_DIR / "dist"
OUTPUT      = DIST_DIR / "reader.html"

CAUTIONS_JSON = DATA_DIR / "drug_cautions.json"

JSQR_URL    = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"
JSQR_CACHE  = MOBILE_DIR / "templates" / "_jsQR.js"


def fetch_jsqr() -> str:
    """jsQR 라이브러리 로드 (캐시 우선)."""
    if JSQR_CACHE.exists():
        return JSQR_CACHE.read_text(encoding="utf-8")
    print(f"[INFO] jsQR 다운로드: {JSQR_URL}")
    r = requests.get(JSQR_URL, timeout=20)
    r.raise_for_status()
    JSQR_CACHE.write_text(r.text, encoding="utf-8")
    print(f"[INFO] 캐시 저장: {JSQR_CACHE.name} ({len(r.text)/1024:.1f} KB)")
    return r.text


def gzip_b64(json_path: Path) -> str:
    """JSON 파일을 gzip + base64로 인코딩."""
    if not json_path.exists():
        raise FileNotFoundError(f"데이터 파일 없음: {json_path}")
    raw  = json_path.read_text(encoding="utf-8").encode("utf-8")
    comp = gzip.compress(raw, compresslevel=9)
    b64  = base64.b64encode(comp).decode("ascii")
    print(f"  {json_path.name}: "
          f"{len(raw)/1024:.0f} KB → gzip {len(comp)/1024:.0f} KB "
          f"({len(comp)/len(raw)*100:.1f}%)")
    return b64


def build():
    print("=" * 60)
    print("  모바일 PWA 리더 빌드")
    print("=" * 60)

    if not TEMPLATE.exists():
        print(f"[ERROR] 템플릿 없음: {TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    print("[1/3] 통합 주의정보 압축 중...")
    cautions_b64 = gzip_b64(CAUTIONS_JSON)

    print("[2/3] jsQR 라이브러리 로드 중...")
    jsqr_js = fetch_jsqr()
    print(f"  jsQR: {len(jsqr_js)/1024:.1f} KB (인라인)")

    print("[3/3] HTML 빌드 중...")
    template = TEMPLATE.read_text(encoding="utf-8")
    for ph in ("{{CAUTIONS_GZIP_B64}}", "{{JSQR_JS}}"):
        if ph not in template:
            print(f"[ERROR] 템플릿에 {ph} 자리표시자 없음", file=sys.stderr)
            sys.exit(1)

    html = (
        template
        .replace("{{CAUTIONS_GZIP_B64}}", cautions_b64)
        .replace("{{JSQR_JS}}",           jsqr_js)
    )

    DIST_DIR.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    size_mb = OUTPUT.stat().st_size / 1024 / 1024

    print()
    print("=" * 60)
    print(f"[OK] {OUTPUT}")
    print(f"     최종 크기: {size_mb:.2f} MB")
    print()
    print("배포: 이 파일 하나를 환자/보호자 스마트폰으로 전송")
    print("실행: 모바일 브라우저(Chrome/Safari)로 파일 열기 또는")
    print("       서버에 업로드 후 URL 접속 → 홈 화면에 추가(PWA)")
    print("=" * 60)


if __name__ == "__main__":
    build()
