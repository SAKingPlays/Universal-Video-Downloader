"""
Unified metadata model bridging extractors → on-disk sidecar files.

UltraDL writes a companion ``.info.json`` next to finished media containing
title, description, uploader, and source URL. The GUI/CLI read the same model
for progress display and history.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..extractors.base_extractor import ExtractedVideo
from ..utils.file_utils import safe_filename, write_atomic


@dataclass
class UnifiedMetadata:
    title: str
    description: str = ""
    uploader: str = ""
    upload_date: Optional[str] = None
    canonical_url: str = ""
    extractor: str = ""
    thumbnail_paths: List[str] = field(default_factory=list)
    subtitle_paths: List[str] = field(default_factory=list)
    saved_at: str = ""

    def to_json_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_extracted(cls, ev: ExtractedVideo) -> "UnifiedMetadata":
        return cls(
            title=ev.title,
            description=ev.description,
            uploader=ev.uploader,
            upload_date=ev.upload_date,
            canonical_url=ev.canonical_url,
            extractor=ev.extractor_id,
            saved_at=datetime.now(timezone.utc).isoformat(),
        )


class MetadataExtractor:
    """Persistence helpers for metadata sidecars."""

    @staticmethod
    def build_sidecar_path(media_path: Path) -> Path:
        return media_path.with_suffix(media_path.suffix + ".info.json")

    @staticmethod
    def write_sidecar(media_path: Path, meta: UnifiedMetadata) -> Path:
        path = MetadataExtractor.build_sidecar_path(media_path)
        write_atomic(path, json.dumps(meta.to_json_dict(), indent=2, ensure_ascii=False))
        return path

    @staticmethod
    def suggested_output_basename(meta: UnifiedMetadata) -> str:
        return safe_filename(meta.title or "video")
