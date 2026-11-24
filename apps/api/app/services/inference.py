from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

TAXONOMY = {
    "damaged_panel": {"label": "Damaged panel", "severity": "critical"},
    "soiling": {"label": "Soiling", "severity": "medium"},
    "vegetation_obstruction": {"label": "Vegetation obstruction", "severity": "high"},
    "hotspot_risk": {"label": "Hotspot-risk marker", "severity": "high"},
    "frame_corrosion": {"label": "Frame corrosion", "severity": "medium"},
    "missing_panel": {"label": "Missing panel", "severity": "critical"},
    "inverter_issue": {"label": "Inverter cabinet issue", "severity": "high"},
}


@dataclass
class InferenceResult:
    defect_class: str
    label: str
    severity: str
    confidence: float
    bbox: dict[str, int]
    mask: list[list[int]]
    quality_warnings: list[str]
    duration_ms: int


class DeterministicDemoProvider:
    name = "deterministic-demo"

    def run(self, media_id: str, quality: dict[str, Any] | None = None, content: bytes | None = None) -> InferenceResult:
        started = time.perf_counter()
        warnings = list((quality or {}).get("warnings", []))
        if content:
            seed = int.from_bytes(hashlib.sha256(content).digest()[:4], "big")
        else:
            seed = int.from_bytes(hashlib.sha256(media_id.encode("utf-8")).digest()[:4], "big")
            warnings.append("input bytes unavailable; deterministic fallback used media identity")
        classes = list(TAXONOMY)
        defect_class = classes[seed % len(classes)]
        tax = TAXONOMY[defect_class]
        confidence = round(0.58 + ((seed * 13) % 37) / 100, 2)
        if confidence < 0.70:
            warnings.append("medium-confidence candidate")
        return InferenceResult(
            defect_class=defect_class,
            label=tax["label"],
            severity=tax["severity"],
            confidence=confidence,
            bbox={"x": 18 + seed % 30, "y": 13 + seed % 29, "w": 25 + seed % 19, "h": 18 + seed % 17},
            mask=[[22, 20], [54, 18], [63, 39], [47, 52], [24, 43]],
            quality_warnings=warnings,
            duration_ms=max(8, int((time.perf_counter() - started) * 1000) + 14),
        )


class OptionalUltralyticsProvider:
    name = "ultralytics-optional"

    def run(self, *_: Any, **__: Any) -> InferenceResult:
        raise RuntimeError(
            "Ultralytics adapter is optional; no model weights are bundled or downloaded in demo mode."
        )


class OptionalONNXProvider:
    name = "onnx-optional"

    def run(self, *_: Any, **__: Any) -> InferenceResult:
        raise RuntimeError("ONNX Runtime adapter is optional; configure a local model path in production.")
