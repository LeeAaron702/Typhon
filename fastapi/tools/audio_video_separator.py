from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import FileResponse
from moviepy.editor import VideoFileClip
from pytube import YouTube
from enum import Enum
import os
from auth import get_current_user
from pathlib import Path
import re
import shutil
from utils.logger import log_user_activity


class ReturnType(str, Enum):
    audio = "audio"

router = APIRouter()

# Change this to the directory where processed files will be stored
PROCESSED_DIR = "processed"

SUPPORTED_FILE_TYPES = ["mp4", "mov", "avi", "mkv"]

def safe_filename(filename: str) -> str:
    # Remove invalid characters from the filename
    return re.sub(r'[\\/*?:"<>|]', "", filename)

@router.post("/download_extract_audio/", tags=['Extract Audio From Youtube'])
async def extract_audio(request: Request, background_tasks: BackgroundTasks, return_type: ReturnType = ReturnType.audio, youtube_url: str = None, file: UploadFile = File(None), user: dict = Depends(get_current_user)):
    if youtube_url:
        source = "YouTube URL"
    elif file:
        source = "Uploaded File"
    else:
        raise HTTPException(status_code=400, detail="No input source provided.")
    
    file_name = None
    if youtube_url:
        yt = YouTube(youtube_url)
        video = yt.streams.filter(file_extension='mp4', progressive=True).order_by('resolution').desc().first()
        if not video:
            raise HTTPException(status_code=404, detail="No suitable video found.")
        # Use video title for the filename
        file_name = safe_filename(yt.title)
        video_path = os.path.join(PROCESSED_DIR, f"{file_name}.mp4")
        video.download(filename=video_path)
    elif file:
        if file.filename.split('.')[-1].lower() not in SUPPORTED_FILE_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type. Supported types: {', '.join(SUPPORTED_FILE_TYPES)}")
        file_name = Path(file.filename).stem
        video_path = os.path.join(PROCESSED_DIR, f"{file_name}.mp4")
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    else:
        raise HTTPException(status_code=400, detail="No input source provided.")

    if not file_name:
        raise HTTPException(status_code=500, detail="Failed to determine the file name.")

    clip = VideoFileClip(video_path)
    
    if return_type == ReturnType.audio:
        audio_filename = f"{file_name}.mp3"
        audio_path = os.path.join(PROCESSED_DIR, audio_filename)
        clip.audio.write_audiofile(audio_path)
        file_path = audio_path
        media_type = 'audio/mpeg'
    else:
        # If you ever want to support returning the video file itself
        media_type = 'video/mp4'
        audio_filename = f"{file_name}.mp4"
    
    if youtube_url:
        action = f"extracted audio from YouTube video: {yt.title}"
    elif file:
        action = f"extracted audio from uploaded file: {file.filename}"
    else:
        action = "attempted audio extraction but failed due to lack of input source"
        
    log_user_activity(request, background_tasks, user['username'], action)
    
    response = FileResponse(path=file_path, media_type=media_type, filename=audio_filename)

    return response


