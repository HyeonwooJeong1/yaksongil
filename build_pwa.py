"""
PWA 배포 빌드 — 생성기 + 리더를 docs/ 로 묶고 각자 서비스워커/매니페스트 부착.

GitHub Pages(/docs 폴더) 정적 호스팅용. 서버 관리 불필요.
오프라인 사용 + 백그라운드 자동 갱신(매 빌드마다 버전 갱신 → 다음 실행 때 최신 반영).

실행: python build_pwa.py   (PYTHONUTF8=1 권장)
산출:
  docs/
    index.html                 (랜딩: 생성기/리더 링크)
    generator/ index.html sw.js manifest.json   (약사용)
    reader/    index.html sw.js manifest.json   (환자/응급용)
"""
import datetime
import re
import shutil
import sys
from pathlib import Path

import build_static
from mobile_reader import build_reader

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
PWA = ROOT / "pwa"
SW_TEMPLATE = (PWA / "sw.template.js").read_text(encoding="utf-8")
MANIFEST_TEMPLATE = (PWA / "manifest.template.json").read_text(encoding="utf-8")
VERSION = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

# HTML <head>에 삽입: 매니페스트 링크 + 서비스워커 등록 (file:// 에서는 무해하게 무시됨)
REG_SNIPPET = """
  <link rel="manifest" href="./manifest.json" />
  <script>
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js").catch(e => console.warn("[PWA] SW 등록 실패", e));
    });
  }
  </script>
"""

# <body> 끝에 삽입: "앱 설치" 버튼 + 설치 프롬프트
#   - Android/PC Chrome·Edge: beforeinstallprompt 캡처 → 1탭 설치(아이콘 생성)
#   - iOS Safari: 프롬프트 미지원 → 버튼 탭 시 "홈 화면에 추가" 안내
BODY_SNIPPET = """
  <style>
  #pwa-install-btn{position:fixed;left:16px;bottom:16px;z-index:9999;background:{{ACCENT}};color:#fff;
    font-weight:700;padding:10px 16px;border-radius:9999px;box-shadow:0 4px 14px rgba(0,0,0,.28);
    border:none;cursor:pointer;font-size:14px;font-family:inherit}
  </style>
  <button id="pwa-install-btn" style="display:none">📲 앱 설치</button>
  <script>
  (function(){
    var btn=document.getElementById('pwa-install-btn'); var dp=null;
    if(window.matchMedia('(display-mode: standalone)').matches||window.navigator.standalone) return;
    window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();dp=e;});
    btn.style.display='block';   // 항상 표시
    btn.addEventListener('click',function(){
      if(dp){dp.prompt();dp.userChoice.then(function(){dp=null;});return;}
      // 설치 신호가 없음 = 보통 "이미 설치됨". 바탕화면 아이콘만 지운 경우 앱은 그대로 남아있음.
      alert('아이콘 만들기 / 설치 방법\\n\\n[PC Chrome/Edge] 주소창 오른쪽 설치(+) 아이콘 클릭\\n\\n[바탕화면 아이콘만 지웠을 때]\\n앱은 그대로 설치돼 있습니다. 시작 메뉴에서 실행하거나,\\nchrome://apps 에서 우클릭 → 바로가기 만들기.\\n\\n[완전히 다시 설치하려면]\\nchrome://apps 에서 먼저 제거 → 이 버튼 다시 클릭.\\n\\n[iPhone] 하단 [공유] → 홈 화면에 추가\\n[Android] 메뉴(⋮) → 앱 설치');
    });
    window.addEventListener('appinstalled',function(){btn.style.display='none';});
  })();
  </script>
"""


def assemble(app_id, name, short, theme, bg, accent, icon_prefix, src_html: Path, out_dir: Path):
    if not src_html.exists():
        print(f"[ERROR] 소스 없음: {src_html}", file=sys.stderr)
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)

    html = src_html.read_text(encoding="utf-8")
    # 기존 manifest 링크 제거(특히 reader의 inline data-URI) → 우리 파일 매니페스트로 통일
    html = re.sub(r'<link[^>]*rel=["\']manifest["\'][^>]*/?>', "", html, flags=re.I)
    # <head>: 매니페스트 + 서비스워커 등록
    if "</head>" in html:
        html = html.replace("</head>", REG_SNIPPET + "</head>", 1)
    else:
        html = REG_SNIPPET + html
    # <body> 끝: "앱 설치" 버튼 (앱별 색상)
    body_snip = BODY_SNIPPET.replace("{{ACCENT}}", accent)
    if "</body>" in html:
        html = html.replace("</body>", body_snip + "</body>", 1)
    else:
        html = html + body_snip

    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "sw.js").write_text(
        SW_TEMPLATE.replace("{{VERSION}}", VERSION).replace("{{APP_ID}}", app_id),
        encoding="utf-8",
    )
    (out_dir / "manifest.json").write_text(
        MANIFEST_TEMPLATE.replace("{{NAME}}", name).replace("{{SHORT_NAME}}", short)
                         .replace("{{THEME}}", theme).replace("{{BG}}", bg),
        encoding="utf-8",
    )
    # 아이콘 복사 (앱별 색상)
    for s in (192, 512):
        shutil.copy(PWA / "icons" / f"{icon_prefix}-{s}.png", out_dir / f"icon-{s}.png")
    mb = (out_dir / "index.html").stat().st_size / 1024 / 1024
    print(f"  [OK] docs/{out_dir.name}/  (index.html {mb:.2f}MB, icons + sw v{VERSION})")


LANDING = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>다제약물 응급 QR</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-slate-50 min-h-screen flex items-center justify-center p-6">
<div class="max-w-md w-full space-y-4 text-center">
  <h1 class="text-2xl font-bold text-slate-800 mb-2">🏥 다제약물 응급 QR</h1>
  <a href="./generator/" class="block bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-2xl shadow">💊 약사용 — QR 생성기</a>
  <a href="./reader/" class="block bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-4 rounded-2xl shadow">📱 환자·응급용 — QR 리더</a>
  <p class="text-xs text-slate-400 pt-2">설치: 브라우저 메뉴 → "홈 화면에 추가 / 앱 설치"<br>한 번 열면 오프라인에서도 작동하고, 온라인일 때 자동 갱신됩니다.</p>
</div></body></html>"""


def main():
    print("=" * 60)
    print("  PWA 배포 빌드 (docs/) — 오프라인 + 백그라운드 자동 갱신")
    print("=" * 60)
    print("[1/3] 생성기(qr_generator.html) 빌드...")
    build_static.build()
    print("[2/3] 리더(reader.html) 빌드...")
    build_reader.build()

    print("[3/3] docs/ 조립 (서비스워커 + 매니페스트 부착)...")
    assemble("druginfo-gen", "다제약물 응급 QR 생성기", "QR생성기",
             "#1e293b", "#f8fafc", "#2563eb", "gen",
             ROOT / "dist" / "qr_generator.html", DOCS / "generator")
    assemble("druginfo-reader", "응급의료정보 QR 리더", "응급QR리더",
             "#1e293b", "#f8fafc", "#059669", "reader",
             ROOT / "mobile_reader" / "dist" / "reader.html", DOCS / "reader")
    (DOCS / "index.html").write_text(LANDING, encoding="utf-8")

    print()
    print("=" * 60)
    print(f"[OK] docs/ 준비 완료 (버전 {VERSION})")
    print("  docs/generator/  → 약사용 생성기")
    print("  docs/reader/     → 환자/응급용 리더")
    print("  이제 git push 하면 GitHub Pages가 자동 서빙합니다.")
    print("=" * 60)


if __name__ == "__main__":
    main()
