"""
텍스트를 QR PNG 이미지로 변환.
오류정정 레벨 M (약 15% 손상까지 복구) — 라벨 인쇄 + 카메라 인식 안정성 균형.
"""
import base64
from datetime import datetime
from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from app.paths import output_dir

OUTPUT_DIR = output_dir()


def generate_qr_image(text: str) -> tuple[str, str]:
    """
    text를 QR PNG로 변환.
    반환: (file_path, base64_string)
    """
    qr = qrcode.QRCode(
        version=None,             # 데이터 크기에 따라 자동 결정
        error_correction=ERROR_CORRECT_M,
        box_size=10,              # 픽셀 단위 (셀 1개 크기)
        border=4,                 # 최소 4 (스펙 권장)
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = OUTPUT_DIR / f"qr_{timestamp}.png"
    img.save(file_path)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    return str(file_path), b64
