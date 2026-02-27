from __future__ import annotations

from pathlib import Path

from app.core.config import clear_settings_cache
from app.services.editable_config import EditableConfigService


def test_update_editable_config_atomic_write_and_cleanup(tmp_path, monkeypatch) -> None:
    source = Path(__file__).resolve().parent / "config.test.yaml"
    config_path = tmp_path / "config.yaml"
    default_path = tmp_path / "config.example.yaml"
    config_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    default_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("MIDAS_CONFIG_PATH", str(config_path))
    clear_settings_cache()

    service = EditableConfigService(config_path=config_path, default_path=default_path)
    result = service.update_editable_settings({"runtime": {"log_level": "DEBUG"}})

    assert result["runtime"]["log_level"] == "DEBUG"
    leftovers = [
        path
        for path in tmp_path.iterdir()
        if path.name.startswith(f".{config_path.name}.") and path.name.endswith(".tmp")
    ]
    assert leftovers == []
