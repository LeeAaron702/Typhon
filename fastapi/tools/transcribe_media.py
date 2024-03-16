from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks, Request
from fastapi.responses import FileResponse
from moviepy.editor import VideoFileClip
from pytube import YouTube
from faster_whisper import WhisperModel
import os
import shutil
from auth import get_current_user
from utils.logger import log_user_activity, send_log_to_discord
from pathlib import Path
import re
import zipfile
from starlette.concurrency import run_in_threadpool

router = APIRouter()

PROCESSED_DIR = "processed"

def safe_filename(filename: str) -> str:
    """Sanitize the filename by removing unsupported characters and truncating."""
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Truncate to 100 characters to avoid filesystem limitations
    return filename[:100]

async def download_video(youtube_url: str, save_path: str):
    """Download video using YouTube URL."""
    def blocking_download():
        yt = YouTube(youtube_url)
        video = yt.streams.filter(file_extension='mp4', progressive=True).order_by('resolution').desc().first()
        if not video:
            raise HTTPException(status_code=404, detail="No suitable video found.")
        video.download(output_path=save_path, filename="video.mp4")
    await run_in_threadpool(blocking_download)

async def save_upload_file(upload_file: UploadFile, save_path: str):
    """Save uploaded file to disk."""
    with open(os.path.join(save_path, "video.mp4"), "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

async def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio file to text using WhisperModel."""
    def blocking_transcribe():
        model = WhisperModel("base.en")
        return " ".join([seg.text for seg in model.transcribe(audio_path)[0]])
    return await run_in_threadpool(blocking_transcribe)

@router.post("/transcribe_media/", tags=['Transcribe Media'])
async def transcribe_media(
    request: Request,
    background_tasks: BackgroundTasks,
    youtube_url: str = None,
    file: UploadFile = File(None),
    user: dict = Depends(get_current_user)
):
    # Ensure the base processed directory exists
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    video_title, video_filename = None, None
    task_folder_name = None

    # Handle input from YouTube URL or file upload
    if youtube_url and file:
        raise HTTPException(status_code=400, detail="Provide either a YouTube URL or a file, not both.")
    elif youtube_url:
        yt = YouTube(youtube_url)
        video_title = safe_filename(yt.title)
    elif file:
        video_title = safe_filename(file.filename)
    else:
        raise HTTPException(status_code=400, detail="No YouTube URL or file provided.")

    # Create a unique directory for this task based on the sanitized video title
    task_folder_name = video_title
    task_folder_path = os.path.join(PROCESSED_DIR, task_folder_name)
    os.makedirs(task_folder_path, exist_ok=True)

    if youtube_url:
        await download_video(youtube_url, task_folder_path)
    elif file:
        await save_upload_file(file, task_folder_path)

    video_path = os.path.join(task_folder_path, "video.mp4")
    audio_path = os.path.join(task_folder_path, "audio.mp3")
    transcript_path = os.path.join(task_folder_path, "transcription.txt")

    # Process video to extract audio
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path)

    # Transcribe audio
    transcription = await transcribe_audio(audio_path)
    with open(transcript_path, "w") as text_file:
        text_file.write(transcription)

    # Zip the task folder
    zip_filename = f"{task_folder_name}_transcription"  # Removed '.zip' from here
    zip_file_path = shutil.make_archive(base_name=os.path.join(PROCESSED_DIR, zip_filename), format='zip', root_dir=task_folder_path)
    # `shutil.make_archive` automatically appends '.zip', so 'zip_file_path' now correctly ends with '.zip'

    # Cleanup: Remove the task folder after zipping to save space
    # shutil.rmtree(task_folder_path)

    log_message_end = f"{user['username']} completed transcription successfully for '{video_title}'."
    background_tasks.add_task(send_log_to_discord, log_message_end)

    return FileResponse(path=zip_file_path, media_type='application/zip', filename=zip_filename)
