from __future__ import annotations

from typing import Any


def assess_media(content: bytes, filename: str, content_type: str | None) -> dict[str, Any]:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    expected = {"jpg", "jpeg", "png", "webp"}
    warnings: list[str] = []
    errors: list[str] = []
    if extension not in expected:
        errors.append("unsupported file extension")
    if not content:
        errors.append("empty upload")
    if len(content) > 25 * 1024 * 1024:
        errors.append("file exceeds 25 MB demo policy")
    if content_type and not content_type.startswith("image/"):
        errors.append("MIME type is not an image")
    if len(content) < 512:
        warnings.append("small test image; dimensions inferred in demo mode")
    return {
        "state": "Failed" if errors else ("Warning" if warnings else "Healthy"),
        "errors": errors,
        "warnings": warnings,
        "mime_verified": bool(content_type and content_type.startswith("image/")),
        "duplicate_check": "pending",
        "blur_score": 0.18 if len(content) < 512 else 0.82,
        "brightness_score": 0.72,
        "resolution_score": 0.91,
        "coverage_score": 0.88,
    }
