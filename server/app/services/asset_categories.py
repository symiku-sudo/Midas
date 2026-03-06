from __future__ import annotations

ASSET_CATEGORY_SPECS: list[tuple[str, str]] = [
    ("stock", "股票"),
    ("equity_fund", "股票基金"),
    ("gold", "黄金"),
    ("bond_and_bond_fund", "债券/债券基金"),
    ("money_market_fund", "货币基金"),
    ("bank_fixed_deposit", "银行定期存款"),
    ("bank_current_deposit", "银行活期存款"),
    ("housing_fund", "公积金"),
]

ASSET_CATEGORY_KEYS: list[str] = [key for key, _ in ASSET_CATEGORY_SPECS]
ASSET_CATEGORY_LABEL_MAP: dict[str, str] = {
    key: label for key, label in ASSET_CATEGORY_SPECS
}
