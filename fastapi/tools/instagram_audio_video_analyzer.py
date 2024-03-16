from fastapi import FastAPI, BackgroundTasks, HTTPException, APIRouter, UploadFile, File, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
import shutil
from typing import List, Tuple, Optional
import asyncio
import instaloader
from moviepy.editor import VideoFileClip
from faster_whisper import WhisperModel
import cv2
import base64
import openai
import os
from pathlib import Path
import datetime
import re
import zipfile
from auth import get_current_user
from dotenv import load_dotenv


# Initialize FastAPI app and router
app = FastAPI()
router = APIRouter()
load_dotenv()  # This loads the environment variables from .env

# Configuration and global variables
L = instaloader.Instaloader(download_pictures=False, download_videos=True, download_video_thumbnails=False, download_comments=False, save_metadata=True, post_metadata_txt_pattern="")
openai.api_key = os.getenv("OPENAI_API_KEY")  # Use the environment variable, or replace with your actual OpenAI API key if not set
PROCESSED_DIR = "processed/ig"
os.makedirs(PROCESSED_DIR, exist_ok=True)

class InstagramContentRequest(BaseModel):
    url: str

async def download_instagram_content(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Download an Instagram reel or post video."""
    content_pattern = re.compile(r"https?://www.instagram.com/(reel|p)/([^/?#&]+)")
    match = content_pattern.search(url)
    if not match:
        return None, None

    shortcode = match.group(2)
    content_specific_dir = Path(PROCESSED_DIR) / shortcode
    content_specific_dir.mkdir(parents=True, exist_ok=True)

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=content_specific_dir)
        video_files = list(content_specific_dir.glob("*.mp4"))
        video_file = video_files[0] if video_files else None
        
        if video_file:
            # Optionally save caption as well if needed.
            caption_file_path = content_specific_dir / f"{shortcode}_caption.txt"
            with open(caption_file_path, "w", encoding="utf-8") as f:
                f.write(post.caption if post.caption else "No caption")
            return str(content_specific_dir), str(video_file)
        else:
            print("No video file found after download.")
            return str(content_specific_dir), None

    except Exception as e:
        print(f"Exception while downloading content: {e}")
        return None, None

def transcribe_audio_from_video(video_path: str) -> str:
    """Transcribe audio from a video file using faster whisper."""
    clip = VideoFileClip(video_path)
    audio_path = video_path.replace(".mp4", "_audio.mp3")
    clip.audio.write_audiofile(audio_path)

    model = WhisperModel("base.en")
    transcription = " ".join([seg.text for seg in model.transcribe(audio_path)[0]])

    transcript_file_path = video_path.replace(".mp4", "_transcription.txt")
    with open(transcript_file_path, "w") as text_file:
        text_file.write(transcription)

    return transcription


async def extract_frames(video_path: str, output_folder: str) -> List[str]:
    """Extract frames from a video file."""
    cap = cv2.VideoCapture(video_path)
    success, frame_count = True, 0
    frames = []
    while success:
        success, frame = cap.read()
        if success and frame_count % 60 == 0:  # Change this value based on desired frame extraction frequency
            frame_path = f"{output_folder}/frame_{frame_count}.jpg"
            cv2.imwrite(frame_path, frame)
            frames.append(frame_path)
        frame_count += 1
    cap.release()
    return frames

def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

async def get_frame_description(frame_path: str) -> str:
    """Generate a description of an image frame using OpenAI's GPT model."""
    base64_image = image_to_base64(frame_path)
    image_prompt = """
    Provide a concise overview focusing on visible words, technical elements, software, tools, or coding practices. Highlight the technology's purpose, its application, name, text, and any visible interfaces or code snippets. Include: 'Technology/Software: [name/version, if visible]. Functionality & Details: [use, purpose, or specific technical elements or coding practices shown].' Include 'URL Link: [URL]' only if visible. 
    Guidelines: **350 character Max Response Length**, Spartan language, avoid filler, no mention of limitations or non-technical elements, no youtube links, 75 token max. Omit URL Link section if not applicable.
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
        "max_tokens": 50,
        "temperature": 0.5,
    }
    result = openai.ChatCompletion.create(**params)
    description = result.choices[0].message.content
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] Description obtained: {description}")

    return description

async def generate_final_summary(descriptions: List[str], transcription: str, vid_dir: str, url: str) -> (str, str):
    """Generate a final summary based on frame descriptions and transcription."""



    aggregated_descriptions = " ".join(descriptions)
    prompt = f"""
    "Construct a structured summary of the video based on the audio transcription and image descriptions provided, focusing specifically on technical content. Follow this organization:

    1. **Summary:** Offer a concise overview of the main theme, concentrating on crucial technological concepts, tools, or advancements discussed or shown. Emphasize the technological significance and potential impact, if there is text about a software or AI mention it.

    2. **Important Names or Software Name:** Catalog any significant technologies, programming languages, software, or tools featured, noting version numbers if mentioned. Highlight the relevance of each technology or tool in the context of the video.

    3. **Associated URLs:** Provide URLs for official software documentation, repositories, or additional resources referenced in the video. Only include URLs directly related to the discussed technologies.

    Guidelines for Construction:
    - Focus solely on extracting and summarizing relevant technical information. 
    - Strive for precision and clarity, tailoring the summary for a technical audience and ensuring it highlights the most innovative and pertinent aspects of the technology presented.
    - 500 tokens or 2000 characters max
    Frame Descriptions: {aggregated_descriptions}
    The audio transcription might be lyrics, if they are disregard. 
    Audio Transcription: {transcription}

    """
    #     Summarize the video content based on the frame descriptions and audio transcription.
    # Begin with a one-paragraph overview that encapsulates the main points from the descriptions and transcription.
    # Then list any mentioned software names followed by their respective URLs, if available.
    # Frame Descriptions: {aggregated_descriptions}
    # Audio Transcription: {transcription}
    
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
    # Define the summary file path within the reel_specific_dir
    summary_file_path = os.path.join(vid_dir, "final_summary.txt")
    
    # Write the final summary to the file
    with open(summary_file_path, "w", encoding="utf-8") as file:
        file.write(f"URL: {url}\n\n")
        file.write(summary)

    return summary, summary_file_path 

def zip_directory(folder_path: str, zip_name: str) -> str:
    zip_file_path = os.path.join(PROCESSED_DIR, zip_name)
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        len_dir_path = len(folder_path)
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Use the relative path for arcname to avoid the redundant folder structure
                arcname = file_path[len_dir_path:].lstrip(os.sep)  
                zipf.write(file_path, arcname=arcname)
    return zip_file_path

async def process_instagram_content(url: str) -> Tuple[str, str, str]:
    content_dir, video_path = await download_instagram_content(url)
    if not video_path:
        raise HTTPException(status_code=400, detail="Failed to download Instagram content.")

    transcription = transcribe_audio_from_video(video_path)
    
    output_folder = os.path.join(content_dir, "frames")
    os.makedirs(output_folder, exist_ok=True)
    
    frame_paths = await extract_frames(video_path, output_folder)
    
    descriptions = await asyncio.gather(*[get_frame_description(frame) for frame in frame_paths])
    
    summary, summary_file_path = await generate_final_summary(descriptions, transcription, content_dir, url)
    print("🚀 ~ summary:", summary)
    
    # ZIP the entire directory now that all processing is complete
    zip_name = f"{Path(content_dir).name}.zip"
    zip_file_path = zip_directory(content_dir, zip_name)
    
    return summary, summary_file_path, zip_file_path

@router.post("/analyze-instagram/", tags=['IG Audio & Video Analyzer'], response_class=FileResponse)
async def analyze_instagram(
                    request: InstagramContentRequest,     
                    user: dict = Depends(get_current_user)
):
    if not request.url:
        raise HTTPException(status_code=400, detail="Instagram URL must be provided.")
    
    summary, summary_file_path, zip_file_path = await process_instagram_content(request.url)
    
    # Return the zip file path for auto-download
    return FileResponse(path=zip_file_path, media_type='application/zip', filename=f"{Path(zip_file_path).name}")
app.include_router(router)
