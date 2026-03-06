from __future__ import annotations

import base64
import math

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import AssetImageFillData
from app.services.asset_categories import ASSET_CATEGORY_KEYS
from app.services.llm import LLMService


class AssetImageFillService:
    def __init__(
        self,
        settings: Settings,
        llm_service: LLMService | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm_service or LLMService(settings)

    async def extract_from_uploads(
        self,
        uploads: list[UploadFile],
    ) -> AssetImageFillData:
        normalized_uploads = [item for item in uploads if item is not None]
        if not normalized_uploads:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="请至少上传 1 张资产图片。",
                status_code=400,
            )

        max_images = max(int(self._settings.asset_image_fill.max_images), 1)
        if len(normalized_uploads) > max_images:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message=f"最多支持上传 {max_images} 张图片。",
                status_code=400,
            )

        max_image_bytes = max(int(self._settings.asset_image_fill.max_image_bytes), 64 * 1024)
        image_data_urls: list[str] = []
        for index, upload in enumerate(normalized_uploads, start=1):
            content_type = (upload.content_type or "").strip().lower()
            if not content_type.startswith("image/"):
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"第 {index} 张文件不是图片类型。",
                    status_code=400,
                )

            content = await upload.read()
            await upload.close()
            if not content:
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"第 {index} 张图片为空，请重新上传。",
                    status_code=400,
                )
            if len(content) > max_image_bytes:
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=(
                        f"第 {index} 张图片超过大小限制（>{max_image_bytes} bytes），"
                        "请在端侧压缩后重试。"
                    ),
                    status_code=400,
                )

            encoded = base64.b64encode(content).decode("ascii")
            image_data_urls.append(f"data:{content_type};base64,{encoded}")

        llm_amounts = await self._llm.extract_asset_amounts_from_images(
            image_data_urls=image_data_urls,
        )
        normalized_amounts = {
            key: self._normalize_amount(llm_amounts.get(key, 0.0))
            for key in ASSET_CATEGORY_KEYS
        }
        total_amount_wan = round(sum(normalized_amounts.values()), 2)
        return AssetImageFillData(
            image_count=len(image_data_urls),
            category_amounts=normalized_amounts,
            total_amount_wan=total_amount_wan,
        )

    def _normalize_amount(self, raw: object) -> float:
        if isinstance(raw, bool):
            value = float(int(raw))
        elif isinstance(raw, (int, float)):
            value = float(raw)
        elif isinstance(raw, str):
            normalized = raw.strip().replace(",", "")
            value = float(normalized) if normalized else 0.0
        else:
            value = 0.0
        if value < 0 or not math.isfinite(value):
            return 0.0
        return round(value, 2)
