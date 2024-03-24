from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from fastapi.responses import FileResponse
from typing import List
import openai
from dotenv import load_dotenv
import os
import asyncio
import zipfile
from pathlib import Path
import shutil

from tools.summarize_video import download_and_extract_video, get_frame_description, extract_frames
from tools.transcribe_media import process_media_transcription, determine_source_type
from tools.token_counter import calculate_token_count
from auth import get_current_user

router = APIRouter()
load_dotenv()  # Load environment variables from .env file

openai.api_key = os.getenv("OPENAI_API_KEY")  # Set your OpenAI API key
PROCESSED_DIR = "processed"

class SummaryRequest(BaseModel):
    source_url: str
    confirm_summary: bool = False

class SummaryResponse(BaseModel):
    token_count: int
    summary: str
    zip_file_path: str

async def summarize_text(transcript: str, aggregated_frame_descriptions: str) -> str:
    """
    Summarize the provided transcript and frame descriptions using GPT-4.
    """
    prompt = f"""
    Create a comprehensive summary combining the provided audio transcription and image frame descriptions:
    
    Audio Transcription:
    {transcript}
    
    Frame Descriptions:
    {aggregated_frame_descriptions}
    
    Please provide a structured summary of the video's content, focusing on key themes, narratives, and visual elements.
    """
    result = openai.Completion.create(
        model="gpt-4",
        prompt=prompt,
        max_tokens=800,
        temperature=0.5,
    )
    summary = result.choices[0].text.strip()
    return summary

async def process_summary(request: SummaryRequest) -> SummaryResponse:
    source_type = determine_source_type(request.source_url)
    if source_type == "unsupported":
        raise HTTPException(status_code=400, detail="Unsupported URL type provided.")
    
    transcription, content_dir = await process_media_transcription(request.source_url, source_type)
    video_path = await download_and_extract_video(request.source_url, PROCESSED_DIR)
    frames_dir = Path(video_path).parent / "extracted_frames"
    if not frames_dir.exists():
        frames_dir.mkdir(parents=True, exist_ok=True)

    frames = extract_frames(video_path, str(frames_dir))
    frame_descriptions = []
    for frame in frames:
        description, _ = await asyncio.to_thread(get_frame_description, frame)  # Assuming implementation provided in your context
        frame_descriptions.append(description)
        await asyncio.sleep(0.1)  # Avoid overwhelming the API

    aggregated_frame_descriptions = " ".join(frame_descriptions)
    
    if request.confirm_summary:
        summary = await summarize_text(transcription, aggregated_frame_descriptions)
        
        # Save the summary to a text file
        summary_file_path = Path(content_dir) / "final_summary.txt"
        with open(summary_file_path, "w", encoding="utf-8") as f:
            f.write(summary)
        
        # Zip the content directory
        zip_filename = f"{Path(content_dir).name}.zip"
        zip_file_path = Path(PROCESSED_DIR) / zip_filename
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(content_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, arcname=os.path.relpath(file_path, start=content_dir))
            
        # Add the summary to the response
        token_count = calculate_token_count(summary)  # Assuming implementation provided in your context
        return SummaryResponse(token_count=token_count, summary=summary, zip_file_path=str(zip_file_path))
    else:
        return SummaryResponse(token_count=0, summary="", zip_file_path="")

@router.post("/summarize_transcript_and_video/", tags=['Summarize Audio & Video'], response_model=SummaryResponse)
async def summarize_transcript_and_video(request: SummaryRequest, user: dict = Depends(get_current_user)) -> SummaryResponse:
    return await process_summary(request)
