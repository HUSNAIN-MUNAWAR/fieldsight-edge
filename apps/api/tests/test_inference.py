from app.services.inference import DeterministicDemoProvider


def test_deterministic_demo_uses_media_bytes_when_available():
    provider = DeterministicDemoProvider()
    first = provider.run("same-media-id", content=b"image-a")
    second = provider.run("same-media-id", content=b"image-b")
    assert (first.defect_class, first.bbox, first.confidence) != (second.defect_class, second.bbox, second.confidence)
    assert not any("media identity" in warning for warning in first.quality_warnings)


def test_missing_media_bytes_are_explicitly_qualified():
    result = DeterministicDemoProvider().run("same-media-id")
    assert any("input bytes unavailable" in warning for warning in result.quality_warnings)
