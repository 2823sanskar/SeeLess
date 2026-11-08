import os
import zipfile
import pytest
from app.database import SessionLocal, init_db
from app.models import Video, Description, SpeechSegment
from app.services.video_service import (
    format_timestamp,
    generate_vtt_content,
    generate_srt_content,
    list_videos,
    create_bulk_export_zip,
)


@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def test_timestamp_formatting():
    # WebVTT test (period separator)
    vtt_ts = format_timestamp(65.432, srt=False)
    assert vtt_ts == "00:01:05.432"

    # SRT test (comma separator)
    srt_ts = format_timestamp(3665.050, srt=True)
    assert srt_ts == "01:01:05,050"


def test_generate_vtt_content():
    desc = [
        Description(
            id="desc_1",
            video_id="vid_1",
            start_time=2.0,
            end_time=5.0,
            text="Man walks into the room.",
            priority=0.8,
            status="VALIDATED",
        )
    ]
    speech = [
        SpeechSegment(
            id="sp_1",
            video_id="vid_1",
            start_time=6.0,
            end_time=8.5,
            transcript="Hello there!",
        )
    ]
    vtt = generate_vtt_content(desc, speech)
    assert "WEBVTT" in vtt
    assert "00:00:02.000 --> 00:00:05.000" in vtt
    assert "[Audio Description] Man walks into the room." in vtt
    assert "00:00:06.000 --> 00:00:08.500" in vtt
    assert "Hello there!" in vtt


def test_generate_srt_content():
    desc = [
        Description(
            id="desc_1",
            video_id="vid_1",
            start_time=1.5,
            end_time=4.0,
            text="Door opens softly.",
            priority=0.7,
            status="VALIDATED",
        )
    ]
    speech = [
        SpeechSegment(
            id="sp_1",
            video_id="vid_1",
            start_time=4.5,
            end_time=6.0,
            transcript="Who is it?",
        )
    ]
    srt = generate_srt_content(desc, speech)
    assert "1" in srt
    assert "00:00:01,500 --> 00:00:04,000" in srt
    assert "[Audio Description] Door opens softly." in srt
    assert "2" in srt
    assert "00:00:04,500 --> 00:00:06,000" in srt
    assert "Who is it?" in srt


def test_list_videos_query(db):
    res = list_videos(db=db, page=1, page_size=10)
    assert res.total >= 0
    assert isinstance(res.items, list)


def test_create_bulk_export_zip(db):
    zip_path, count = create_bulk_export_zip(
        db=db,
        video_ids=[],
        export_types=["vtt", "srt"],
    )
    assert os.path.exists(zip_path)
    assert count == 0
    os.remove(zip_path)

