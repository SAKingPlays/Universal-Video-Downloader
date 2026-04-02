"""
Application configuration loaded from YAML or JSON.

Search order:
1. Path passed explicitly
2. ``ULTRADL_CONFIG`` environment variable
3. User config: ``~/.config/ultradl/config.yaml`` (Windows: ``%APPDATA%\\ultradl\\config.yaml``)
4. Built-in defaults
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .logger import get_logger

log = get_logger("config")


def default_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "ultradl" / "config.yaml"
    return Path.home() / ".config" / "ultradl" / "config.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dep
        raise RuntimeError("PyYAML is required to read YAML configs.") from exc
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


@dataclass
class AppConfig:
    download_dir: Path = field(default_factory=lambda: Path.home() / "Videos" / "UltraDL")
    preferred_height: int = 1080
    max_concurrent_downloads: int = 4
    max_segment_workers: int = 8
    chunk_size_bytes: int = 1024 * 1024
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    timeout_seconds: float = 60.0
    retry_attempts: int = 5
    retry_backoff_base: float = 0.75
    ffmpeg_path: str = "ffmpeg"
    cache_dir: Optional[Path] = None
    enable_metadata_cache: bool = True
    cache_ttl_seconds: int = 3600
    live_poll_interval: float = 2.0

    def effective_cache_dir(self) -> Path:
        if self.cache_dir is not None:
            return self.cache_dir
        return self.download_dir / ".ultradl_cache"

    @classmethod
    def from_mapping(cls, m: Dict[str, Any]) -> "AppConfig":
        data: Dict[str, Any] = {}
        for key, default in asdict(cls()).items():
            if key not in m:
                continue
            val = m[key]
            if key in ("download_dir", "cache_dir") and val is not None:
                data[key] = Path(val)
            else:
                data[key] = val
        return cls(**{**asdict(cls()), **data})


def load_config(path: Optional[Path] = None) -> AppConfig:
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    env = os.environ.get("ULTRADL_CONFIG")
    if env:
        candidates.append(Path(env))
    candidates.append(default_config_path())

    for p in candidates:
        try:
            if not p.exists():
                continue
            if p.suffix.lower() in {".yaml", ".yml"}:
                m = _load_yaml(p)
            elif p.suffix.lower() == ".json":
                m = _load_json(p)
            else:
                log.warning("Unknown config extension for %s, skipping", p)
                continue
            log.info("Loaded configuration from %s", p)
            return AppConfig.from_mapping(m)
        except Exception as exc:  # pragma: no cover - user files vary
            log.error("Failed to load config %s: %s", p, exc)
    return AppConfig()


def save_example_config(path: Path) -> None:
    """Write a commented example as JSON (no YAML write dependency)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    example = {
        "download_dir": str(Path.home() / "Videos" / "UltraDL"),
        "preferred_height": 1080,
        "max_concurrent_downloads": 4,
        "max_segment_workers": 8,
        "chunk_size_bytes": 1048576,
        "timeout_seconds": 60.0,
        "retry_attempts": 5,
        "ffmpeg_path": "ffmpeg",
        "enable_metadata_cache": True,
        "cache_ttl_seconds": 3600,
        "live_poll_interval": 2.0,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(example, f, indent=2)
        f.write("\n")
