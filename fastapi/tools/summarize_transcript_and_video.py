from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
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
    estimate_token_count: int
    summary: str
    zip_file_path: str

async def summarize_text(transcript: str, aggregated_frame_descriptions: str) -> (str, int):
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
    prompt_message = {
        "role": "user",
        "content": prompt,
    }
    params = {
        "model": "gpt-4",
        "messages": [prompt_message],
        "max_tokens": 600,
        "temperature": 0,
    }
    result = openai.ChatCompletion.create(**params)
    summary = result.choices[0].message.content
    final_summary_token_estimate = calculate_token_count(prompt) + 600
    return summary, final_summary_token_estimate

async def process_summary(request: SummaryRequest) -> SummaryResponse:
    source_type = determine_source_type(request.source_url)
    if source_type == "unsupported":
        raise HTTPException(status_code=400, detail="Unsupported URL type provided.")
    
    transcription, content_dir = await process_media_transcription(request.source_url, source_type)
    print(transcription)
    video_path = await download_and_extract_video(request.source_url, PROCESSED_DIR)
    frames_dir = Path(video_path).parent / "extracted_frames"
    if not frames_dir.exists():
        frames_dir.mkdir(parents=True, exist_ok=True)

    transcription_file_path = Path(content_dir) / "transcription.txt"
    with open(transcription_file_path, "w", encoding="utf-8") as f:
        f.write(transcription)

    frames = extract_frames(video_path, str(frames_dir))
    frame_descriptions = []
    token_counter = 0
    summary = ""
    zip_file_path = ""

    for frame in frames:
        frame_total_tokens = 280  # Assume a base token count per frame for estimation
        if request.confirm_summary:
            description, tokens_from_description = await asyncio.to_thread(get_frame_description, frame)
            frame_descriptions.append(description)
            token_counter += tokens_from_description  # Add the actual tokens from description
        else:
            token_counter += frame_total_tokens  # Add the estimated tokens if not confirming summary

    if request.confirm_summary:
        aggregated_frame_descriptions = " ".join(frame_descriptions)
        summary, final_summary_token_estimate = await summarize_text(transcription, aggregated_frame_descriptions)
        token_counter += final_summary_token_estimate

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
        zip_file_path = str(zip_file_path)  # Convert Path object to string for JSON serialization

    # Calculate the estimated token count based on frames and other elements
    estimate_token_count = token_counter

    return SummaryResponse(
        token_count=calculate_token_count(summary) if summary else 0,
        estimate_token_count=estimate_token_count,
        summary=summary,
        zip_file_path=zip_file_path
    )

@router.post("/summarize_transcript_and_video/", tags=['Summarize Audio & Video'], response_model=SummaryResponse)
async def summarize_transcript_and_video(request: SummaryRequest, user: dict = Depends(get_current_user)) -> SummaryResponse:
    return await process_summary(request)