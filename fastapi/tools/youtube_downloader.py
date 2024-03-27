from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from fastapi.responses import FileResponse
from pytube import YouTube, exceptions as pytube_exceptions
import os
import re
from pathlib import Path

from utilities.auth import get_current_user
from utilities.logger import log_user_activity  # Ensure this is imported

router = APIRouter()

PROCESSED_DIR = "processed"


def safe_filename(filename: str) -> str:
    """Generate a safe filename by removing invalid characters."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def download_youtube_video_util(youtube_url: str, processed_dir: str) -> dict:
    """
    Downloads a YouTube video and returns information about the downloaded file.
    The video is stored in a subdirectory within 'processed_dir' named after the video title.
    """
    try:
        yt = YouTube(youtube_url)
        video = yt.streams.get_highest_resolution()
        if not video:
            raise ValueError("No suitable video found.")
        
        video_title = safe_filename(yt.title)
        video_dir = os.path.join(processed_dir, video_title)  # Create a directory named after the video
        os.makedirs(video_dir, exist_ok=True)  # Ensure the directory exists

        file_name = f"{video_title}.mp4"
        video_path = os.path.join(video_dir, file_name)
        video.download(output_path=video_dir, filename=file_name)
        return {"video_path": video_path, "video_dir": video_dir, "title": yt.title}
    except pytube_exceptions.PytubeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        download_info = download_youtube_video_util(youtube_url, PROCESSED_DIR)
        video_path = download_info["video_path"]  # Correctly extracting the video_path from the dictionary
        video_title = download_info["title"]
        action = f"successfully downloaded YouTube video '{video_title}'"
    except Exception as e:
        action = f"failed to download YouTube video from URL: {youtube_url} with error: {str(e)}"
        log_user_activity(request, background_tasks, user["username"], action)
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if isinstance(e, pytube_exceptions.PytubeError):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(e, ValueError):
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=str(e),
        ) from e

    log_user_activity(request, background_tasks, user["username"], action)

    response = FileResponse(
        path=video_path,  # Use the correctly extracted path here
        media_type="application/octet-stream",
        filename=os.path.basename(video_path),
        headers={"Content-Disposition": f'attachment; filename="{os.path.basename(video_path)}"'},
    )

    return response
