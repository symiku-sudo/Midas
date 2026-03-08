from __future__ import annotations

import uuid
from datetime import datetime

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.models.schemas import AssetCurrentData, AssetSnapshotHistoryData, AssetSnapshotRecord
from app.repositories.note_repo import NoteLibraryRepository
from app.services.asset_categories import ASSET_CATEGORY_KEYS


class AssetSnapshotService:
    def __init__(
        self,
        settings: Settings,
        repository: NoteLibraryRepository | None = None,
    ) -> None:
        self._repository = repository or NoteLibraryRepository(settings.xiaohongshu.db_path)

    def list_history(self) -> AssetSnapshotHistoryData:
        items = [AssetSnapshotRecord(**item) for item in self._repository.list_asset_snapshots()]
        return AssetSnapshotHistoryData(total=len(items), items=items)

    def get_current(self) -> AssetCurrentData:
        current = self._repository.get_asset_current()
        if current is None:
            return AssetCurrentData(total_amount_wan=0.0, amounts={})
        return AssetCurrentData(
            total_amount_wan=float(current.get("total_amount_wan", 0.0) or 0.0),
            amounts=self._normalize_amounts(dict(current.get("amounts", {}))),
        )

    def save_current(
        self,
        *,
        total_amount_wan: float = 0.0,
        amounts: dict[str, float],
    ) -> AssetCurrentData:
        normalized_amounts = self._normalize_amounts(amounts)
        normalized_total = total_amount_wan
        if normalized_total <= 0 and normalized_amounts:
            normalized_total = round(sum(normalized_amounts.values()), 4)
        if normalized_total < 0:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="总资产金额不能为负数。",
            )
        self._repository.upsert_asset_current(
            total_amount_wan=normalized_total,
            amounts=normalized_amounts,
        )
        self._repository.backup_database()
        return AssetCurrentData(
            total_amount_wan=normalized_total,
            amounts=normalized_amounts,
        )

    def save_snapshot(
        self,
        *,
        record_id: str = "",
        saved_at: str = "",
        total_amount_wan: float = 0.0,
        amounts: dict[str, float],
    ) -> AssetSnapshotRecord:
        normalized_id = record_id.strip() or uuid.uuid4().hex
        normalized_saved_at = saved_at.strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized_amounts = self._normalize_amounts(amounts)
        normalized_total = total_amount_wan
        if normalized_total <= 0 and normalized_amounts:
            normalized_total = round(sum(normalized_amounts.values()), 4)
        if normalized_total < 0:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="总资产金额不能为负数。",
            )

        self._repository.upsert_asset_snapshot(
            record_id=normalized_id,
            saved_at=normalized_saved_at,
            total_amount_wan=normalized_total,
            amounts=normalized_amounts,
        )
        self._repository.backup_database()
        return AssetSnapshotRecord(
            id=normalized_id,
            saved_at=normalized_saved_at,
            total_amount_wan=normalized_total,
            amounts=normalized_amounts,
        )

    def delete_snapshot(self, record_id: str) -> int:
        normalized_id = record_id.strip()
        if not normalized_id:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="历史记录 ID 不能为空。",
            )
        deleted = self._repository.delete_asset_snapshot(normalized_id)
        if deleted > 0:
            self._repository.backup_database()
        return deleted

    def _normalize_amounts(self, amounts: dict[str, float]) -> dict[str, float]:
        if not isinstance(amounts, dict):
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="资产分类金额格式不合法。",
            )

        normalized: dict[str, float] = {}
        allowed_keys = set(ASSET_CATEGORY_KEYS)
        for key, value in amounts.items():
            normalized_key = str(key).strip()
            if normalized_key not in allowed_keys:
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"未知资产分类：{normalized_key or key}",
                )
            try:
                amount = float(value)
            except (TypeError, ValueError):
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"资产分类 {normalized_key} 金额格式不合法。",
                ) from None
            if amount < 0:
                raise AppError(
                    code=ErrorCode.INVALID_INPUT,
                    message=f"资产分类 {normalized_key} 金额不能为负数。",
                )
            normalized[normalized_key] = round(amount, 4)
        return normalized
