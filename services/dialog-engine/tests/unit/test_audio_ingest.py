import pytest

from dialog_engine.audio.ingest import AudioIngestor, IngestLimits


@pytest.mark.asyncio
async def test_audio_ingestor_allows_within_limit():
    ingestor = AudioIngestor(limits=IngestLimits(max_bytes=10, max_duration_seconds=60))

    payload = await ingestor.from_bytes(data=b"12345", content_type="audio/wav")

    assert payload.content_type == "audio/wav"
    assert payload.data == b"12345"


@pytest.mark.asyncio
async def test_audio_ingestor_enforces_size_limit():
    ingestor = AudioIngestor(limits=IngestLimits(max_bytes=3, max_duration_seconds=60))

    with pytest.raises(ValueError):
        await ingestor.from_bytes(data=b"1234", content_type="audio/wav")
