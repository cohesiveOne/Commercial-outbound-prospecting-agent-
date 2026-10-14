"""Load and validate config/icp.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_ICP_PATH = Path(__file__).resolve().parent.parent / "config" / "icp.yaml"

REQUIRED_TOP_LEVEL = ("company", "run_defaults", "personas", "scoring", "signals", "segments")
REQUIRED_SEGMENT_KEYS = ("label", "sub_segments", "zoominfo", "personas", "value_props")


class ICPError(ValueError):
    """Raised when icp.yaml is missing required structure."""


def load_icp(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else DEFAULT_ICP_PATH
    with open(path, encoding="utf-8") as fh:
        icp = yaml.safe_load(fh)
    validate_icp(icp)
    return icp


def validate_icp(icp: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_TOP_LEVEL if k not in icp]
    if missing:
        raise ICPError(f"icp.yaml missing top-level keys: {missing}")

    weights = icp["scoring"]["weights"]
    total = sum(weights.values())
    if total != 100:
        raise ICPError(f"scoring.weights must sum to 100, got {total}")

    persona_keys = set(icp["personas"])
    for seg_key, seg in icp["segments"].items():
        seg_missing = [k for k in REQUIRED_SEGMENT_KEYS if k not in seg]
        if seg_missing:
            raise ICPError(f"segment {seg_key!r} missing keys: {seg_missing}")
        unknown = set(seg["personas"]) - persona_keys
        if unknown:
            raise ICPError(f"segment {seg_key!r} references unknown personas: {sorted(unknown)}")
        for sub_key, sub in seg["sub_segments"].items():
            if not sub.get("description_keywords"):
                raise ICPError(f"sub-segment {seg_key}.{sub_key} has no description_keywords")
        lo, hi = seg["zoominfo"]["sweet_spot"]
        if lo > hi:
            raise ICPError(f"segment {seg_key!r} sweet_spot is inverted: {lo} > {hi}")


def get_segment(icp: dict[str, Any], segment_key: str) -> dict[str, Any]:
    try:
        return icp["segments"][segment_key]
    except KeyError as exc:
        valid = ", ".join(icp["segments"])
        raise ICPError(f"unknown segment {segment_key!r}; valid: {valid}") from exc
