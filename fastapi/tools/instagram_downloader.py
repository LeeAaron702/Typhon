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

PROCESSED_DIR = "processed/content"
content_pattern = re.compile(r'https?://www.instagram.com/(reel|p)/([^/?#&]+)')

# Configure Instaloader for a wider range of content
L = instaloader.Instaloader(download_pictures=True, download_videos=True, download_video_thumbnails=True, download_comments=False, save_metadata=True, post_metadata_txt_pattern='')

@router.post("/download_instagram_content/", tags=["Download Instagram Content"], response_class=FileResponse)
async def download_instagram_content(
    request: Request,
    background_tasks: BackgroundTasks,
    content_request: InstagramContentRequest,  # Renamed for clarity
    user: dict = Depends(get_current_user),
):
    # Access the content_url string within the InstagramContentRequest object
    content_url_str = content_request.content_url

    if not content_url_str:  # Check if the URL string is empty or not provided
        raise HTTPException(status_code=400, detail="Instagram content URL must be provided.")

    content_match = content_pattern.search(content_url_str)  # Use the string for searching
    if not content_match:
        raise HTTPException(status_code=400, detail="Invalid Instagram content URL.")

    shortcode = content_match.group(2)
    content_specific_dir = os.path.join(PROCESSED_DIR, shortcode)

    if not os.path.exists(content_specific_dir):
        os.makedirs(content_specific_dir, exist_ok=True)

    try:
        # Download the post or reel using Instaloader
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=Path(content_specific_dir))

        # Save the caption text to a .txt file in the same directory
        caption_file_path = os.path.join(content_specific_dir, f"{shortcode}_caption.txt")
        with open(caption_file_path, "w", encoding="utf-8") as f:
            f.write(post.caption if post.caption else "No caption")

        # Include the downloaded content and the caption file in a zip file
        zip_file_path = os.path.join(PROCESSED_DIR, f"{shortcode}.zip")
        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            for item in Path(content_specific_dir).iterdir():
                if item.is_file():
                    zipf.write(item, arcname=item.name)

        # Log the successful download along with the caption
        action = f"successfully downloaded Instagram content and caption: {content_url_str}"
        log_user_activity(request, background_tasks, user["username"], action)

    except Exception as e:
        # If an error occurs during download or zipping, log the error
        action = f"failed to download Instagram content and caption: {content_url_str} with error: {str(e)}"
        log_user_activity(request, background_tasks, user["username"], action)
        raise HTTPException(status_code=500, detail="Failed to download Instagram content.") from e

    return FileResponse(path=zip_file_path, media_type='application/zip', filename=f"{shortcode}.zip")
