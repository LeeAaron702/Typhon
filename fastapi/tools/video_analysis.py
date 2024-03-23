from fastapi import APIRouter, HTTPException, Form
from pathlib import Path
import os
import cv2
from typing import List
import shutil

# Import relevant modules and functions
from tools.audio_video_separator import determine_source_type
from tools.youtube_downloader import download_youtube_video_util
from tools.instagram_downloader import download_instagram_content_for_processing

router = APIRouter()

# Updated constants as per the new requirement
TOKENS_PER_IMAGE = 85  # Estimated tokens per image at low detail
TOKENS_PER_IMAGE_PROMPT = 210  # Estimated tokens for generating the prompt for each image
TOKENS_PER_IMAGE_RESPONSE = 75  # Estimated tokens for the model's response to each image
TOKENS_PER_SUMMARY_PROMPT = 240  # Estimated tokens for generating the final summary prompt
TOKENS_PER_SUMMARY_RESPONSE = 500  # Estimated tokens for the model's final summary response


async def download_and_extract_video(url: str, processed_dir: str) -> str:
    """Download video from Instagram or YouTube and return its local path."""
    source_type = determine_source_type(url)
    if source_type == "youtube":
        download_info = download_youtube_video_util(url, processed_dir)
        title = get_safe_title(download_info["title"])
        video_dir = Path(processed_dir) / title
        video_dir.mkdir(parents=True, exist_ok=True)
        video_path = video_dir / (title + ".mp4")
        shutil.move(download_info["video_path"], video_path)
        return str(video_path)
    elif source_type == "instagram":
        content_dir, shortcode = download_instagram_content_for_processing(url, processed_dir)
        title = get_safe_title(shortcode)
        new_content_dir = Path(processed_dir) / title
        new_content_dir.mkdir(parents=True, exist_ok=True)
        for item in Path(content_dir).iterdir():
            shutil.move(str(item), str(new_content_dir / item.name))
        video_files = list(new_content_dir.glob("*.mp4"))
        if not video_files:
            raise HTTPException(status_code=400, detail="No video file found in downloaded Instagram content.")
        return str(video_files[0])  # Return path to the video file
    else:
        raise HTTPException(status_code=400, detail="Unsupported URL type.")

def extract_frames(video_path: str, output_folder: str) -> List[str]:
    """Extract frames from a video file."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Video at {video_path} cannot be opened.")

    fps = cap.get(cv2.CAP_PROP_FPS)  # Get the frames per second of the video
    success, frame_count = True, 0
    frames = []
    
    # We want to extract 1 frame every second, so we check if the current frame
    # count is a multiple of the FPS (rounded to the nearest whole number)
    while success:
        success, frame = cap.read()
        if success and frame_count % round(fps) == 0:
            frame_path = Path(output_folder) / f"frame_{frame_count // round(fps)}.jpg"
            cv2.imwrite(str(frame_path), frame)
            frames.append(str(frame_path))
        frame_count += 1

    cap.release()
    return frames

def get_safe_title(title: str) -> str:
    """Generate a filesystem-safe title by removing or replacing invalid characters."""
    return "".join([c if c.isalnum() or c in " _-." else "_" for c in title])


@router.post("/video-analysis-token-estimator/", tags=['Video Token Estimator'])
async def video_analysis_token_counter(url: str = Form(...)):
    processed_dir = "processed"
    video_path = await download_and_extract_video(url, processed_dir)

    video_dir = Path(video_path).parent
    frames_dir = video_dir / "extracted_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frames = extract_frames(video_path, str(frames_dir))

    # Calculate the estimated token usage for the given operation
    estimated_total_token_usage = (
        len(frames) * (TOKENS_PER_IMAGE + TOKENS_PER_IMAGE_PROMPT + TOKENS_PER_IMAGE_RESPONSE)
        + TOKENS_PER_SUMMARY_PROMPT + TOKENS_PER_SUMMARY_RESPONSE
    )

    return {
        "estimated_total_token_usage": estimated_total_token_usage,
        "detail": {
            "total_frames": len(frames),
            "tokens_per_image": TOKENS_PER_IMAGE,
            "tokens_per_image_prompt": TOKENS_PER_IMAGE_PROMPT,
            "tokens_per_image_response": TOKENS_PER_IMAGE_RESPONSE,
            "tokens_per_summary_prompt": TOKENS_PER_SUMMARY_PROMPT,
            "tokens_per_summary_response": TOKENS_PER_SUMMARY_RESPONSE
        }
    }


# now that the token counter is working, we can focus on the other apiend point which is going to actually do the calls to openai after confirmation. 
