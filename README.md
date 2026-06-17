# 다제약물 응급 QR 시스템 MVP

노인 다제약물 환자가 응급 상황 시, 의료진이 스마트폰 기본 카메라로 QR을 스캔하여
복용 중인 핵심 약물과 위험 키워드(출혈/저혈당/부정맥 등)를 즉시 확인할 수 있는 시스템.

## 배포: 단일 EXE 파일

```cmd
build.bat
```
→ `dist\EmergencyQR.exe` 생성. 약국 PC에 이 파일 하나만 복사하면 됨.
약사는 더블클릭 → 자동으로 콘솔 + 브라우저 열림.

DB와 .env는 `%APPDATA%\EmergencyQR\` 폴더에 저장 (사용자별 데이터 보존).

## 빠른 시작

```powershell
# 1. 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. 의존성 설치
pip install -r requirements.txt

# 3-1. DB 초기화 + Mock 시드 데이터 삽입 (15개)
python -m app.seed

# 3-2. (선택) 심평원 DUR 노인주의 약물 추가 적재
python -m app.services.external.hira_dur_loader

# 3-3. (선택) 심평원 약가마스터 적재 (4-5만 건, ATC 코드 자동 분류)
python -m app.services.external.hira_drug_price_loader

# 4. 서버 실행
uvicorn app.main:app --reload

# 5. 브라우저 접속
# - 약사 대시보드: http://localhost:8000
# - API 문서:      http://localhost:8000/docs
```

## 외부 API 연동

### 1. 심평원 DUR 노인주의 (파일 방식)
공공데이터포털에서 [DUR 의약품 목록](https://www.data.go.kr/data/15127983/fileData.do)
을 다운로드하여 프로젝트 루트에 압축 해제 후
`python -m app.services.external.hira_dur_loader` 실행.

### 2. 식약처 e약은요 (OpenAPI)
`.env.example`을 `.env`로 복사하고, 공공데이터포털에서 발급받은
[e약은요 인증키](https://www.data.go.kr/data/15075057/openapi.do)를 입력.

```
MFDS_API_KEY=발급받은_인증키
```

API: `GET /api/search?q=아스피린` → 효능/주의사항/상호작용/부작용 JSON 반환.

## 프로젝트 구조

```
app/
  main.py           FastAPI 진입점
  database.py       SQLite 연결
  models.py         Pydantic 모델
  seed.py           초기 약물 데이터 적재
  services/
    merger.py       약물 병합/중복제거
    formatter.py    응급 텍스트 포맷팅 (200자 제한)
    qr_generator.py QR PNG 생성
    external/
      hira_dur_loader.py   심평원 DUR 노인주의 CSV 적재
      mfds_eyakeunyo.py    식약처 e약은요 OpenAPI 클라이언트
      risk_mapper.py       사유 텍스트 → 위험 키워드 추출
  api/
    routes.py       API 엔드포인트
static/
  index.html        약사 대시보드
  app.js
output/             생성된 QR 이미지
```
