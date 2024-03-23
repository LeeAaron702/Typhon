from enum import Enum
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from moviepy.editor import VideoFileClip
import os
from pathlib import Path
import zipfile

from auth import get_current_user
from utils.logger import log_user_activity
from .instagram_downloader import download_instagram_content_for_processing
from .youtube_downloader import download_youtube_video_util

router = APIRouter()

PROCESSED_DIR = "processed"

@router.post("/extract_and_package_media/", tags=['Download Youtube or Instagram Video & Audio'])
async def extract_and_package_media(
    request: Request,
    background_tasks: BackgroundTasks,
    source_url: str,
    user: dict = Depends(get_current_user),
):
    source_type = determine_source_type(source_url)
    if source_type == "unsupported":
        raise HTTPException(status_code=400, detail="Unsupported URL type provided.")

    audio_path, content_dir = extract_audio(source_url, source_type, PROCESSED_DIR)
    
    # Create a zip file of the content directory
    zip_file_path = os.path.join(PROCESSED_DIR, f"{Path(content_dir).stem}_media_package.zip")
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(content_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, arcname=os.path.relpath(file_path, content_dir))
    
    action = f"Packaged media from {source_type}: {source_url}"
    log_user_activity(request, background_tasks, user['username'], action)

    return FileResponse(path=zip_file_path, media_type='application/zip', filename=os.path.basename(zip_file_path))

def determine_source_type(url: str) -> str:
    if "instagram.com" in url:
        return "instagram"
    elif "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return "unsupported"

def extract_audio(url: str, source_type: str, output_dir: str) -> str:
    if source_type == "youtube":
        return extract_audio_from_youtube(url, output_dir)
    elif source_type == "instagram":
        return extract_audio_from_instagram(url, output_dir)

def extract_audio_from_youtube(url: str, output_dir: str) -> (str, str):
    download_info = download_youtube_video_util(url, output_dir)
    video_path = download_info["video_path"]
    video_dir = Path(video_path).parent  # This will be the directory containing the video file.
    clip = VideoFileClip(video_path)
    audio_path = video_path.replace(".mp4", ".mp3")
    clip.audio.write_audiofile(audio_path)
    return audio_path, str(video_dir)  # Return both the audio path and the directory.

def extract_audio_from_instagram(url: str, output_dir: str) -> (str, str):
    content_dir, _ = download_instagram_content_for_processing(url, output_dir)
    video_files = list(Path(content_dir).glob("*.mp4"))
    if not video_files:
        raise Exception("No video file found in downloaded Instagram content.")
    video_path = str(video_files[0])
    clip = VideoFileClip(video_path)
    audio_path = os.path.join(content_dir, Path(video_path).stem + ".mp3")
    clip.audio.write_audiofile(audio_path)
    return audio_path, content_dir  # Return both the audio path and the directory.
