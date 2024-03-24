import shutil
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
import instaloader
import re
import os
import zipfile
from pathlib import Path
from pydantic import BaseModel

from auth import get_current_user
from utils.logger import log_user_activity

router = APIRouter()

class InstagramContentRequest(BaseModel):
    content_url: str

PROCESSED_DIR = "processed"

# Configure Instaloader for a wider range of content
L = instaloader.Instaloader(download_pictures=True, download_videos=True, download_video_thumbnails=True, download_comments=False, save_metadata=True, post_metadata_txt_pattern='')

def download_instagram_content_util(content_url, shortcode):
    """
    Downloads Instagram content to a directory named after the shortcode and creates a zip file.
    
    :param content_url: The full URL of the Instagram content to download.
    :param shortcode: The shortcode extracted from the content URL.
    :return: Path to the created zip file.
    """
    content_specific_dir = os.path.join(PROCESSED_DIR, shortcode)
    os.makedirs(content_specific_dir, exist_ok=True)  # Ensure the directory exists
    
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=Path(content_specific_dir))

        caption_file_path = os.path.join(content_specific_dir, f"{shortcode}_caption.txt")
        with open(caption_file_path, "w", encoding="utf-8") as f:
            f.write(post.caption if post.caption else "No caption")

        zip_file_path = os.path.join(PROCESSED_DIR, f"{shortcode}.zip")
        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            for item in Path(content_specific_dir).iterdir():
                if item.is_file():
                    zipf.write(item, arcname=item.name)
        return zip_file_path
    except Exception as e:
        raise e
    


def download_instagram_content_for_processing(content_url: str, output_dir: str) -> (str, str):
    """
    Downloads Instagram content to a specified directory for further processing.

    Args:
    content_url (str): The full URL of the Instagram content to download.
    output_dir (str): The directory where the content should be downloaded.

    Returns:
    Tuple[str, str]: A tuple containing the path to the directory where the content was downloaded, and the shortcode of the Instagram content.
    """
    # Pattern to match Instagram content URLs and extract the shortcode
    content_pattern = re.compile(r'https?://www.instagram.com/(reel|p)/([^/?#&]+)')
    match = content_pattern.search(content_url)
    if not match:
        raise ValueError("Invalid Instagram URL format.")
    
    shortcode = match.group(2)
    content_specific_dir = os.path.join(output_dir, shortcode)
    
    # Ensure the output directory exists
    os.makedirs(content_specific_dir, exist_ok=True)
    
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=Path(content_specific_dir))

        # Optionally, write the caption to a file
        caption_file_path = os.path.join(content_specific_dir, f"{shortcode}_caption.txt")
        with open(caption_file_path, "w", encoding="utf-8") as f:
            f.write(post.caption if post.caption else "No caption")
        
        return (content_specific_dir, shortcode)
    except Exception as e:
        raise Exception(f"Failed to download Instagram content: {str(e)}")


@router.post("/download_instagram_content/", tags=["Download Instagram Content"], response_class=FileResponse)
async def download_instagram_content(
    request: Request,
    background_tasks: BackgroundTasks,
    content_request: InstagramContentRequest,
    user: dict = Depends(get_current_user),
):
    content_url_str = content_request.content_url
    if not content_url_str:
        raise HTTPException(status_code=400, detail="Instagram content URL must be provided.")

    # Extract the shortcode directly in this function
    content_pattern = re.compile(r'https?://www.instagram.com/(reel|p)/([^/?#&]+)')
    match = content_pattern.search(content_url_str)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Instagram URL format.")
    shortcode = match.group(2)

    try:
        zip_file_path = download_instagram_content_util(content_url_str, shortcode)
        action = f"successfully downloaded Instagram content and caption: {content_url_str}"
    except Exception as e:
        action = f"failed to download Instagram content and caption: {content_url_str} with error: {str(e)}"
        log_user_activity(request, background_tasks, user["username"], action)
        raise HTTPException(status_code=500, detail="Failed to download Instagram content.") from e

    log_user_activity(request, background_tasks, user["username"], action)
    return FileResponse(path=zip_file_path, media_type='application/zip', filename=f"{shortcode}.zip")
