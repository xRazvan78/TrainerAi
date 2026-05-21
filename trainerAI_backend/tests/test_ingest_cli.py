import pytest
from unittest.mock import patch, AsyncMock
from pathlib import Path


def test_argparse_rejects_both_video_and_videos_dir():
    from app.training.ingest import main
    with patch("sys.argv", ["ingest", "--video", "a.mp4", "--videos-dir", "/some/dir"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


def test_argparse_requires_one_of_video_or_videos_dir():
    from app.training.ingest import main
    with patch("sys.argv", ["ingest"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


def test_argparse_video_flag_calls_ingest_video():
    from app.training.ingest import main
    mock_coro = AsyncMock(return_value=5)
    with patch("sys.argv", ["ingest", "--video", "foo.mp4", "--dry-run"]):
        with patch("app.training.ingest.ingest_video", mock_coro):
            main()
    mock_coro.assert_awaited_once()
    call_args = mock_coro.call_args
    assert call_args.args[0] == Path("foo.mp4")
    assert call_args.args[2] is True  # dry_run


def test_argparse_videos_dir_flag_calls_ingest_directory():
    from app.training.ingest import main
    mock_coro = AsyncMock(return_value=None)
    with patch("sys.argv", ["ingest", "--videos-dir", "/some/dir"]):
        with patch("app.training.ingest.ingest_directory", mock_coro):
            main()
    mock_coro.assert_awaited_once()
    call_args = mock_coro.call_args
    assert call_args.args[0] == Path("/some/dir")
