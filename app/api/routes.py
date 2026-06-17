import hashlib

import requests
from fastapi import APIRouter, HTTPException

from app.database import (
    count_drugs,
    drug_exists,
    fetch_drugs_by_codes,
    insert_or_update_drug,
    search_drugs,
)
from app.models import (
    CacheDrugRequest,
    DrugInfo,
    DrugRequest,
    PreviewResponse,
    QRResponse,
)
from app.services.external.mfds_eyakeunyo import ApiKeyMissingError, search_drug
from app.services.formatter import TextTooLongError, format_emergency_text
from app.services.merger import merge_drug_codes
from app.services.qr_generator import generate_qr_image

router = APIRouter(prefix="/api", tags=["pharmacy"])


@router.get("/drugs")
def list_drugs(q: str = "", limit: int = 50, offset: int = 0):
    """
    약물 검색. 검색어가 비면 warning 약물 우선 50건 반환.
    응답: { total, limit, offset, drugs }
    """
    limit = max(1, min(limit, 200))  # 1~200 사이로 제한
    offset = max(0, offset)
    return search_drugs(q, limit, offset)


@router.get("/drugs/count")
def drugs_count():
    """마스터에 적재된 전체 약물 수."""
    return {"total": count_drugs()}


@router.get("/drugs/by-codes", response_model=list[DrugInfo])
def drugs_by_codes(codes: str):
    """선택된 약물 정보 일괄 조회. codes는 콤마 구분된 KD코드 리스트."""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    return fetch_drugs_by_codes(code_list)


def _build_text(req: DrugRequest) -> tuple[str, list[dict]]:
    codes = merge_drug_codes(req.existing, req.new)
    if not codes:
        raise HTTPException(status_code=400, detail="약물 코드가 비어있습니다.")
    drugs = fetch_drugs_by_codes(codes)
    if not drugs:
        raise HTTPException(status_code=404, detail="DB에 등록된 약물이 없습니다.")
    try:
        text = format_emergency_text(drugs)
    except TextTooLongError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "TEXT_TOO_LONG",
                "message": str(e),
                "length": e.length,
                "max_length": 200,
                "normal_count": e.normal_count,
                "preview": e.text,
            },
        )
    return text, drugs


@router.post("/preview", response_model=PreviewResponse)
def preview(req: DrugRequest):
    """병합된 약물 리스트로 응급 텍스트만 생성 (QR 인코딩 전 미리보기)."""
    text, drugs = _build_text(req)
    return PreviewResponse(
        text=text,
        length=len(text),
        warning_drugs=[d["short_name"] for d in drugs if d["category"] == "warning"],
        normal_drugs=[d["short_name"] for d in drugs if d["category"] == "normal"],
    )


@router.post("/generate-qr", response_model=QRResponse)
def generate_qr(req: DrugRequest):
    """최종 QR PNG 생성 (base64 + 파일 저장)."""
    text, _ = _build_text(req)
    file_path, qr_b64 = generate_qr_image(text)
    return QRResponse(
        text=text,
        length=len(text),
        qr_base64=qr_b64,
        file_path=file_path,
    )


@router.get("/search")
def search_external(q: str):
    """식약처 e약은요 OpenAPI로 약물 검색 (효능/주의사항/상호작용/부작용)."""
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="검색어가 비어있습니다.")
    try:
        results = search_drug(q.strip())
    except ApiKeyMissingError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"외부 API 호출 실패: {e}")
    return {"query": q, "count": len(results), "results": results}


@router.post("/cache-drug", response_model=DrugInfo)
def cache_external_drug(req: CacheDrugRequest):
    """
    외부 검색 결과를 마스터 DB에 추가.
    동일 (short_name + full_name) 해시 기반 KD코드 생성 → 중복 방지.
    """
    if not req.short_name.strip():
        raise HTTPException(status_code=400, detail="약물 이름이 비어있습니다.")
    if req.category == "warning" and not req.risk_keyword:
        raise HTTPException(status_code=400, detail="warning 약물은 risk_keyword가 필요합니다.")
    if req.category == "normal" and not req.indication:
        raise HTTPException(status_code=400, detail="normal 약물은 indication이 필요합니다.")

    key_src = f"{req.short_name}|{req.full_name or ''}"
    digest = hashlib.md5(key_src.encode("utf-8")).hexdigest()[:10].upper()
    kd_code = f"MFDS_{digest}"

    insert_or_update_drug(
        kd_code=kd_code,
        short_name=req.short_name.strip(),
        full_name=req.full_name,
        category=req.category,
        risk_keyword=req.risk_keyword,
        indication=req.indication,
    )

    return DrugInfo(
        kd_code=kd_code,
        short_name=req.short_name.strip(),
        full_name=req.full_name,
        category=req.category,
        risk_keyword=req.risk_keyword,
        indication=req.indication,
    )
