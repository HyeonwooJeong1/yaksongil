"""
식약처 e약은요 (의약품개요정보) OpenAPI 클라이언트.

엔드포인트: https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList
응답: 효능/용법/주의사항/상호작용/부작용/보관방법 (Q&A 형식 텍스트)
"""
import os
from typing import Any

import requests
from dotenv import load_dotenv

from app.paths import env_path

_env = env_path()
if _env.exists():
    load_dotenv(_env)
else:
    load_dotenv()  # 개발 환경: 프로젝트 루트의 .env

API_KEY  = os.getenv("MFDS_API_KEY")
BASE_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"


class ApiKeyMissingError(RuntimeError):
    pass


def search_drug(name: str, num_of_rows: int = 5) -> list[dict[str, Any]]:
    if not API_KEY:
        raise ApiKeyMissingError(
            "MFDS_API_KEY가 .env에 설정되지 않았습니다. "
            "공공데이터포털에서 e약은요 인증키 발급 후 .env에 추가하세요."
        )

    params = {
        "serviceKey": API_KEY,
        "itemName":   name,
        "type":       "json",
        "numOfRows":  num_of_rows,
        "pageNo":     1,
    }

    r = requests.get(BASE_URL, params=params, timeout=10)
    r.raise_for_status()

    try:
        data = r.json()
    except ValueError:
        # API 키 오류 시 XML 에러 응답이 올 수 있음
        raise RuntimeError(f"e약은요 API 응답 파싱 실패: {r.text[:200]}")

    body = data.get("body") or {}
    items = body.get("items") or []
    if isinstance(items, dict):
        items = [items]

    return [
        {
            "name":        item.get("itemName", ""),
            "company":     item.get("entpName", ""),
            "efficacy":    item.get("efcyQesitm", ""),
            "use_method":  item.get("useMethodQesitm", ""),
            "caution":     item.get("atpnQesitm", ""),
            "interaction": item.get("intrcQesitm", ""),
            "side_effect": item.get("seQesitm", ""),
            "storage":     item.get("depositMethodQesitm", ""),
        }
        for item in items
    ]
