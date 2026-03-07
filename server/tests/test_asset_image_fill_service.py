from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.services.asset_image_fill import AssetImageFillService
from app.services.asset_categories import ASSET_CATEGORY_KEYS
from app.services.llm import LLMService


class _FakeUpload:
    def __init__(self, *, content: bytes, content_type: str = "image/jpeg") -> None:
        self._content = content
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._content

    async def close(self) -> None:
        return None


class _FlakyAssetLLM:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def extract_asset_amounts_from_images(
        self,
        *,
        image_data_urls: list[str],
    ) -> dict[str, float]:
        self.calls.append(len(image_data_urls))
        if len(image_data_urls) > 1:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="batch failed",
                status_code=502,
            )
        return {
            "stock": 1.11,
            "equity_fund": 0.0,
            "gold": 0.0,
            "bond_and_bond_fund": 0.0,
            "money_market_fund": 0.0,
            "bank_fixed_deposit": 0.0,
            "bank_current_deposit": 0.0,
            "housing_fund": 0.0,
        }


@pytest.mark.asyncio
async def test_extract_from_uploads_should_fallback_to_single_image_when_batch_failed() -> None:
    settings = get_settings().model_copy(deep=True)
    settings.asset_image_fill.fallback_single_image_on_upstream_error = True
    llm = _FlakyAssetLLM()
    service = AssetImageFillService(settings=settings, llm_service=llm)  # type: ignore[arg-type]

    uploads = [
        _FakeUpload(content=b"\xff\xd8\xff\xdbmock-1"),
        _FakeUpload(content=b"\xff\xd8\xff\xdbmock-2"),
    ]
    result = await service.extract_from_uploads(uploads)  # type: ignore[arg-type]

    assert result.image_count == 2
    assert result.category_amounts["stock"] == 2.22
    assert result.total_amount_wan == 2.22
    assert llm.calls == [2, 1, 1]


def test_parse_asset_amounts_response_accepts_float_values() -> None:
    settings = get_settings().model_copy(deep=True)
    llm_service = LLMService(settings=settings)

    parsed = llm_service._parse_asset_amounts_response(
        '{"category_amounts":{"stock":123.456,"gold":5.2}}'
    )

    assert set(parsed.keys()) == set(ASSET_CATEGORY_KEYS)
    assert parsed["stock"] == 123.46
    assert parsed["gold"] == 5.2
