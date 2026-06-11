from __future__ import annotations

import glob
import logging
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


class LocalFileSource:
    """Ingest regularly downloaded official CSV/XLS files, such as CSLB exports."""

    def __init__(self, name: str, cfg: dict[str, Any], project_root: str | Path = "."):
        self.name = name
        self.cfg = cfg
        self.project_root = Path(project_root)
        self.input_glob = cfg.get("input_glob", "data/manual_inputs/*.csv")

    def fetch(self, days_back: int | None = None) -> pd.DataFrame:  # noqa: ARG002
        pattern = str(self.project_root / self.input_glob)
        files = sorted(glob.glob(pattern))
        if not files:
            log.warning("No local files matched %s for %s", pattern, self.name)
            return pd.DataFrame()
        frames = []
        for path in files:
            p = Path(path)
            try:
                if p.suffix.lower() in {".xlsx", ".xls"}:
                    df = pd.read_excel(p)
                else:
                    df = pd.read_csv(p, dtype=str, encoding_errors="ignore")
                df["_local_file"] = str(p.name)
                frames.append(df)
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed reading %s: %s", p, exc)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
