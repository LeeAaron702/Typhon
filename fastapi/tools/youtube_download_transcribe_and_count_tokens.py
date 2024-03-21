from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
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
import tiktoken

router = APIRouter()

PROCESSED_DIR = "processed"

# Assuming you have the calculate_token_count function from previous steps
def calculate_token_count(text: str, model_name: str = "gpt-4") -> int:
    enc = tiktoken.encoding_for_model(model_name)
    token_count = len(enc.encode(text))
    return token_count

def safe_filename(filename: str) -> str:
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    return filename[:100]

async def download_video(youtube_url: str, save_path: str):
    def blocking_download():
        yt = YouTube(youtube_url)
        video = yt.streams.get_highest_resolution()
        if not video:
            raise HTTPException(status_code=404, detail="No suitable video found.")
        video.download(output_path=save_path, filename="video.mp4")
    await run_in_threadpool(blocking_download)

async def save_upload_file(upload_file: UploadFile, save_path: str):
    with open(os.path.join(save_path, "video.mp4"), "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

async def transcribe_audio(audio_path: str) -> str:
    def blocking_transcribe():
        model = WhisperModel("base.en")
        return " ".join([seg.text for seg in model.transcribe(audio_path)[0]])
    return await run_in_threadpool(blocking_transcribe)

@router.post("/transcribe-and-count-tokens/", tags=['Transcribe and Count Tokens'])
async def transcribe_and_count_tokens(
    request: Request,
    background_tasks: BackgroundTasks,
    youtube_url: str = None,
    file: UploadFile = File(None),
    user: dict = Depends(get_current_user)
):
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    if youtube_url and file:
        raise HTTPException(status_code=400, detail="Provide either a YouTube URL or a file, not both.")
    elif youtube_url:
        yt = YouTube(youtube_url)
        video_title = safe_filename(yt.title)
    elif file:
        video_title = safe_filename(file.filename)
    else:
        raise HTTPException(status_code=400, detail="No YouTube URL or file provided.")

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

    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path)

    transcription = await transcribe_audio(audio_path)
    with open(transcript_path, "w") as text_file:
        text_file.write(transcription)

    token_count = calculate_token_count(transcription)

    log_message_end = f"{user['username']} completed transcription successfully for '{video_title}' with {token_count} tokens."
    background_tasks.add_task(send_log_to_discord, log_message_end)

    return JSONResponse(content={"video_title": video_title, "token_count": token_count})
