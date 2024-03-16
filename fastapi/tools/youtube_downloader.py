from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from fastapi.responses import FileResponse
from pytube import YouTube, exceptions as pytube_exceptions
import os
import re
from pathlib import Path

from auth import get_current_user
from utils.logger import log_user_activity  # Ensure this is imported

router = APIRouter()

PROCESSED_DIR = "processed"


def safe_filename(filename: str) -> str:
    """Generate a safe filename by removing invalid characters."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)


@router.post("/download_youtube_video/", tags=["Download Youtube Video"])
async def download_youtube_video(
    request: Request,
    background_tasks: BackgroundTasks,
    youtube_url: str,
    user: dict = Depends(get_current_user),
):
    if not youtube_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YouTube URL must be provided.",
        )

    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    try:
        yt = YouTube(youtube_url)
    except pytube_exceptions.PytubeError as e:
        action = f"failed to process YouTube URL: {youtube_url} with error: {str(e)}"
        log_user_activity(request, background_tasks, user["username"], action)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process YouTube URL.",
        ) from e

    try:
        video = (
            yt.streams.filter(file_extension="mp4", progressive=True)
            .order_by("resolution")
            .desc()
            .first()
        )
        if not video:
            raise HTTPException(status_code=404, detail="No suitable video found.")

        video_title = yt.title  # Fetch the title for logging
        file_name = safe_filename(Path(video_title).with_suffix(".mp4").name)
        video_path = os.path.join(PROCESSED_DIR, file_name)
        video.download(filename=video_path)
    except (
        Exception
    ) as e:  # Catch generic exceptions related to downloading or file handling
        action = f"error occurred while downloading or saving YouTube video: {video_title} with error: {str(e)}"
        log_user_activity(request, background_tasks, user["username"], action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error downloading or saving video.",
        ) from e

    # Log the successful download
    action = f"successfully downloaded YouTube video '{video_title}'"
    log_user_activity(request, background_tasks, user["username"], action)

    response = FileResponse(
        path=video_path,
        media_type="application/octet-stream",
        filename=file_name,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
        },
    )

    return response
