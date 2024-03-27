import os
import re
from pathlib import Path
import shutil
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pytube import YouTube, exceptions as pytube_exceptions
import instaloader

from utilities.auth import get_current_user
from utilities.logger import log_user_activity

router = APIRouter()

PROCESSED_DIR = "processed"
L = instaloader.Instaloader(download_pictures=True, download_videos=True, download_video_thumbnails=True,
                             download_comments=False, save_metadata=True, post_metadata_txt_pattern='')


class ContentRequest(BaseModel):
    content_url: str


def safe_filename(filename: str) -> str:
    """Generate a safe filename by removing invalid characters."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)


def download_instagram_content_util(content_url: str, shortcode: str) -> str:
    """
    Downloads Instagram content to a directory named after the shortcode and creates a zip file.
    
    :param content_url: The full URL of the Instagram content to download.
    :param shortcode: The shortcode extracted from the content URL.
    :return: Path to the created zip file.
    """
    content_specific_dir = os.path.join(PROCESSED_DIR, shortcode)
    os.makedirs(content_specific_dir, exist_ok=True)  # Ensure the directory exists
    
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=Path(content_specific_dir))

        caption_file_path = os.path.join(content_specific_dir, f"{shortcode}_caption.txt")
        with open(caption_file_path, "w", encoding="utf-8") as f:
            f.write(post.caption if post.caption else "No caption")

        zip_file_path = os.path.join(PROCESSED_DIR, f"{shortcode}.zip")
        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            for item in Path(content_specific_dir).iterdir():
                if item.is_file():
                    zipf.write(item, arcname=item.name)
        return zip_file_path
    except Exception as e:
        raise e


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


def download_content(content_url: str, processed_dir: str) -> str:
    """
    Detects the type of content (Instagram or YouTube) and downloads it accordingly.
    
    :param content_url: The full URL of the content to download.
    :param processed_dir: The directory where the content should be stored.
    :return: Path to the downloaded content.
    """
    instagram_pattern = re.compile(r'https?://www.instagram.com/(reel|p)/([^/?#&]+)')
    youtube_pattern = re.compile(r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]+(&\S+)?')

    if instagram_pattern.match(content_url):
        shortcode = instagram_pattern.search(content_url).group(2)
        return download_instagram_content_util(content_url, shortcode)
    elif youtube_pattern.match(content_url):
        return download_youtube_video_util(content_url, processed_dir)["video_path"]
    else:
        raise HTTPException(status_code=400, detail="Unsupported content URL.")


@router.post("/download_content/", tags=["Download Content"], response_class=FileResponse)
async def download_content_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    content_request: ContentRequest,
    user: dict = Depends(get_current_user),
):
    content_url_str = content_request.content_url
    if not content_url_str:
        raise HTTPException(status_code=400, detail="Content URL must be provided.")

    try:
        content_path = download_content(content_url_str, PROCESSED_DIR)
        action = f"successfully downloaded content: {content_url_str}"
    except Exception as e:
        action = f"failed to download content: {content_url_str} with error: {str(e)}"
        log_user_activity(request, background_tasks, user["username"], action)
        raise HTTPException(status_code=500, detail="Failed to download content.") from e

    log_user_activity(request, background_tasks, user["username"], action)
    return FileResponse(path=content_path, media_type='application/octet-stream', filename=os.path.basename(content_path))
