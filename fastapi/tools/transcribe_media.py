from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import FileResponse
import os
from pathlib import Path
import zipfile
from auth import get_current_user
from utils.logger import log_user_activity
from .audio_video_separator import extract_audio, determine_source_type
from faster_whisper import WhisperModel
from starlette.concurrency import run_in_threadpool

router = APIRouter()
PROCESSED_DIR = "processed"

async def transcribe_audio(audio_path: str) -> str:
    def blocking_transcribe():
        model = WhisperModel("base.en")
        return " ".join([seg.text for seg in model.transcribe(audio_path)[0]])
    return await run_in_threadpool(blocking_transcribe)

async def process_media(source_url: str, source_type: str) -> Path:
    audio_path, content_dir = await run_in_threadpool(extract_audio, source_url, source_type, PROCESSED_DIR)
    transcription = await transcribe_audio(audio_path)

    # Save transcription to a text file inside the content directory
    transcript_path = Path(content_dir) / (Path(audio_path).stem + '_transcription.txt')
    transcript_path.write_text(transcription)

    return content_dir

async def process_media_transcription(source_url: str, source_type: str) -> Path:
    audio_path, content_dir = await run_in_threadpool(extract_audio, source_url, source_type, PROCESSED_DIR)
    transcription = await transcribe_audio(audio_path)
    # Instead of saving to a text file, return the transcription directly
    return transcription, content_dir


@router.post("/transcribe_media/", tags=['Download Youtube or Instagram Video & Audio & Create Transcription'])
async def transcribe_media_download(
    request: Request,
    background_tasks: BackgroundTasks,
    source_url: str,
    user: dict = Depends(get_current_user)
):
    source_type = determine_source_type(source_url)
    if source_type == "unsupported":
        raise HTTPException(status_code=400, detail="Unsupported URL type provided.")
    
    content_dir = await process_media(source_url, source_type)

    # Create a zip file of the entire content directory
    zip_filename = f"{Path(content_dir).name}.zip"
    zip_file_path = os.path.join(PROCESSED_DIR, zip_filename)
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in Path(content_dir).rglob('*'):
            zipf.write(item, arcname=item.relative_to(content_dir))

    action = f"Transcribed and packaged media from {source_type}: {source_url}"
    log_user_activity(request, background_tasks, user['username'], action)

    return FileResponse(path=zip_file_path, media_type='application/zip', filename=zip_filename)
