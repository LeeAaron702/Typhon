from fastapi import APIRouter, HTTPException, Form, Depends
from pydantic import BaseModel
from pathlib import Path
import os
import cv2
import shutil
import openai
import base64
import datetime
import asyncio
from typing import List

from tools.audio_video_separator import determine_source_type
from tools.youtube_downloader import download_youtube_video_util
from tools.instagram_downloader import download_instagram_content_for_processing

from auth import get_current_user


router = APIRouter()
openai.api_key = os.getenv("OPENAI_API_KEY")

processed_dir= "processed"

# Constants for token estimation
TOKENS_PER_IMAGE = 280
TOKENS_PER_SUMMARY_PROMPT = 250
TOKENS_PER_SUMMARY_RESPONSE = 750

class VideoAnalysisRequest(BaseModel):
    url: str
    confirm_analysis: bool = False

class VideoAnalysisResponse(BaseModel):
    estimated_total_token_usage: int
    frame_descriptions: list = None
    video_summary: str = None
    open_ai_token_counter: int

def get_safe_title(title: str) -> str:
    """Generate a filesystem-safe title."""
    return "".join([c if c.isalnum() or c in " _-." else "_" for c in title])

async def download_and_extract_video(url: str, processed_dir: str) -> str:
    """Download and extract video from Instagram or YouTube."""
    source_type = determine_source_type(url)
    if source_type == "youtube":
        download_info = download_youtube_video_util(url, processed_dir)
        title = get_safe_title(download_info["title"])
        video_dir = Path(processed_dir) / title
        video_path = video_dir / (title + ".mp4")
        if not video_dir.exists():
            video_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(download_info["video_path"], video_path)
    elif source_type == "instagram":
        content_dir, shortcode = download_instagram_content_for_processing(url, processed_dir)
        title = get_safe_title(shortcode)
        new_content_dir = Path(processed_dir) / title
        if not new_content_dir.exists():
            new_content_dir.mkdir(parents=True, exist_ok=True)
            for item in Path(content_dir).iterdir():
                shutil.move(str(item), str(new_content_dir / item.name))
        video_files = list(new_content_dir.glob("*.mp4"))
        if video_files:
            video_path = str(video_files[0])
        else:
            raise HTTPException(status_code=400, detail="No video file found in downloaded content.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported URL type.")
    return str(video_path)

def extract_frames(video_path: str, output_folder: str) -> list:
    """Extract frames from a video file."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    success, frame_count = True, 0
    while success:
        success, frame = cap.read()
        if success and frame_count % round(fps) == 0:
            frame_path = Path(output_folder) / f"frame_{frame_count // round(fps)}.jpg"
            cv2.imwrite(str(frame_path), frame)
            frames.append(str(frame_path))
        frame_count += 1
    cap.release()
    return frames

def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    
def get_frame_description(frame_path: str) -> str:
    """Generate a description of an image frame using OpenAI's GPT model."""
    base64_image = image_to_base64(frame_path)
    image_prompt = """
    Describe the scene captured in this frame, focusing on key elements such as actions, objects, settings, and any text. Mention the main activity, characters, and mood, if discernible. Include text details: 'Visible Text: [text]'. Note any significant symbols or signs.
    Guidelines: **250 character Max Response Length**, concise language, prioritize visual elements and text, if any.
    """
    
    prompt_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": image_prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "low",
                    "resize": 768
                }
            }
        ]
    }

    params = {
        "model": "gpt-4-vision-preview",
        "messages": [prompt_message],
        "max_tokens": 70,
        "temperature": 0.5,
    }
    result = openai.ChatCompletion.create(**params)
    print(result)
    description = result.choices[0].message.content
    total_tokens = result.usage['total_tokens']  
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] Description obtained: {description}, {total_tokens}")
    return description, total_tokens


async def generate_final_summary(descriptions: List[str], transcription: str, vid_dir: str, url: str) -> (str, str):
    """Generate a final summary based on frame descriptions"""
    aggregated_descriptions = " ".join(descriptions)
    prompt = f"""
    "Create a comprehensive summary of the video combining the provided image descriptions. Focus on the overarching story, key events, and important details:

    1. **Summary:** Deliver a clear overview of the video's content, emphasizing major points, storyline, and critical details captured in the descriptions and transcription.

    2. **Key Elements:** Identify and list main characters, significant events, and any pivotal moments or messages portrayed, integrating both audio and visual elements.

    3. **Notable Visuals and Texts:** Highlight any significant visual symbols, texts, or elements that add to the understanding or narrative of the video.

    Guidelines for Construction:
    - Ensure the summary is informative and accessible, catering to a broad audience, including those who are deaf.
    - Maintain clarity and succinctness, focusing on elements that contribute to a comprehensive understanding of the video's content.
    - 500 tokens or 1500 characters max
    Frame Descriptions: {aggregated_descriptions}
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
    final_summary_total_tokens = result.usage['total_tokens']  
    print("final_summary_total_tokens: ", final_summary_total_tokens)
    # Define the summary file path within the reel_specific_dir
    summary_file_path = os.path.join(vid_dir, "final_summary.txt")
    
    # Write the final summary to the file
    with open(summary_file_path, "w", encoding="utf-8") as file:
        file.write(f"URL: {url}\n\n")
        file.write(summary)

    return summary, summary_file_path, final_summary_total_tokens



@router.post("/video-summary/", tags=['Summarize Video'], response_model=VideoAnalysisResponse)
async def video_summary(
    request: VideoAnalysisRequest,
    user: dict = Depends(get_current_user)
    ):
    video_path = await download_and_extract_video(request.url, processed_dir)
    video_dir = Path(video_path).parent
    frames_dir = video_dir / "extracted_frames"
    if not frames_dir.exists():
        frames_dir.mkdir(parents=True, exist_ok=True)

    frames = extract_frames(video_path, str(frames_dir))
    total_tokens_used = 0  # Ensure this variable is initialized at the start of the function
    print(len(frames))
    estimated_tokens = len(frames) * TOKENS_PER_IMAGE + TOKENS_PER_SUMMARY_PROMPT + TOKENS_PER_SUMMARY_RESPONSE

    if request.confirm_analysis:
        frame_descriptions = []
        for frame in frames:
            description, tokens = await asyncio.to_thread(get_frame_description, frame)
            frame_descriptions.append(description)
            total_tokens_used += tokens  # Accumulate tokens used for each frame
            await asyncio.sleep(0.2)  # Delay to avoid hitting token limits
        
        # Here you should correctly calculate or adjust the estimated tokens if necessary
        # For example, you might want to add the actual tokens used for frame analysis to the initial estimate
          # Adjust this line as per your logic

        video_summary, summary_file_path, final_summary_total_tokens = await generate_final_summary(frame_descriptions, "", str(video_dir), request.url)
        total_tokens_used += final_summary_total_tokens
        
        # Optionally, you can log or use total_tokens_used as needed
        print(f"Total OpenAI API tokens used: {total_tokens_used}")  # Print the total tokens used if needed
        return VideoAnalysisResponse(
            estimated_total_token_usage=estimated_tokens, 
            frame_descriptions=frame_descriptions, 
            video_summary=video_summary, 
            open_ai_token_counter=total_tokens_used
        )
    else:
        return VideoAnalysisResponse(
            estimated_total_token_usage=estimated_tokens, 
            open_ai_token_counter=0  # Provide a default value for cases where no analysis is performed
        )
