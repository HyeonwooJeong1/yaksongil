from pydantic import BaseModel, Field


class DrugRequest(BaseModel):
    existing: list[str] = Field(default_factory=list, description="기존 복용 약물 KD코드 리스트")
    new: list[str] = Field(default_factory=list, description="신규 처방 약물 KD코드 리스트")


class DrugInfo(BaseModel):
    kd_code: str
    short_name: str
    full_name: str | None = None
    category: str
    risk_keyword: str | None = None
    indication: str | None = None


class PreviewResponse(BaseModel):
    text: str
    length: int
    warning_drugs: list[str]
    normal_drugs: list[str]


class QRResponse(BaseModel):
    text: str
    length: int
    qr_base64: str
    file_path: str


class CacheDrugRequest(BaseModel):
    """외부 검색 결과를 마스터 DB에 추가할 때 사용."""
    short_name: str
    full_name: str | None = None
    category: str = Field(default="normal", pattern="^(warning|normal)$")
    risk_keyword: str | None = None
    indication: str | None = None
