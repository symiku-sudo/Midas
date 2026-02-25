from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SERVER_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SchemaIssue:
    path: str
    message: str


def load_yaml_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"配置文件不是 YAML 对象: {path}")
    return raw


def validate_config_key_schema(
    example_path: Path,
    config_path: Path,
) -> list[SchemaIssue]:
    example = load_yaml_object(example_path)
    config = load_yaml_object(config_path)
    issues: list[SchemaIssue] = []
    _compare_structure(expected=example, actual=config, path="", issues=issues)
    return issues


def _compare_structure(
    *,
    expected: Any,
    actual: Any,
    path: str,
    issues: list[SchemaIssue],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            issues.append(
                SchemaIssue(
                    path=path or "<root>",
                    message=f"类型不一致，期望 object，实际为 {type_name(actual)}。",
                )
            )
            return

        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())

        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)

        for key in missing:
            issues.append(
                SchemaIssue(
                    path=join_path(path, key),
                    message="缺少该键。",
                )
            )
        for key in extra:
            issues.append(
                SchemaIssue(
                    path=join_path(path, key),
                    message="存在额外键（config.example.yaml 中不存在）。",
                )
            )

        for key in sorted(expected_keys & actual_keys):
            _compare_structure(
                expected=expected[key],
                actual=actual[key],
                path=join_path(path, key),
                issues=issues,
            )
        return

    if isinstance(expected, list):
        if not isinstance(actual, list):
            issues.append(
                SchemaIssue(
                    path=path or "<root>",
                    message=f"类型不一致，期望 list，实际为 {type_name(actual)}。",
                )
            )
        return

    if isinstance(actual, (dict, list)):
        issues.append(
            SchemaIssue(
                path=path or "<root>",
                message=(
                    f"类型不一致，期望标量({type_name(expected)})，"
                    f"实际为 {type_name(actual)}。"
                ),
            )
        )


def join_path(base: str, key: str) -> str:
    return key if not base else f"{base}.{key}"


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验 config.yaml 与 config.example.yaml 的键结构是否一致。"
    )
    parser.add_argument(
        "--example",
        default=str(SERVER_ROOT / "config.example.yaml"),
        help="默认配置模板路径（默认: server/config.example.yaml）",
    )
    parser.add_argument(
        "--config",
        default=str(SERVER_ROOT / "config.yaml"),
        help="本地配置路径（默认: server/config.yaml）",
    )
    parser.add_argument(
        "--allow-missing-config",
        action="store_true",
        help="若 config 文件不存在则直接通过（常用于 CI 无本地配置场景）。",
    )
    args = parser.parse_args()

    example_path = Path(args.example).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()

    if not config_path.exists() and args.allow_missing_config:
        print(f"[PASS] config 文件不存在，已按 --allow-missing-config 跳过: {config_path}")
        return 0

    try:
        issues = validate_config_key_schema(example_path, config_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    if not issues:
        print("[PASS] config 键结构校验通过（仅值可不同）。")
        return 0

    print(f"[FAIL] 发现 {len(issues)} 处结构差异：")
    for issue in issues:
        print(f"  - {issue.path}: {issue.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
