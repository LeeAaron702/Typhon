import shutil
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
import instaloader
import re
import os
import zipfile
from pathlib import Path

from auth import get_current_user
from utils.logger import log_user_activity

router = APIRouter()

PROCESSED_DIR = "processed/reels"
reel_pattern = re.compile(r'https?://www.instagram.com/reel/([^/?#&]+)')

# Configure Instaloader to not download videos
L = instaloader.Instaloader(download_pictures=True, download_videos=True, download_video_thumbnails=True, download_comments=False, save_metadata=True, post_metadata_txt_pattern='')

@router.post("/download_instagram_reel/", tags=["Download Instagram Reel"], response_class=FileResponse)
async def download_instagram_reel(
    request: Request,
    background_tasks: BackgroundTasks,
    reel_url: str,
    user: dict = Depends(get_current_user),
):
    if not reel_url:
        raise HTTPException(status_code=400, detail="Instagram reel URL must be provided.")

    reel_match = reel_pattern.search(reel_url)
    if not reel_match:
        raise HTTPException(status_code=400, detail="Invalid Instagram reel URL.")

    shortcode = reel_match.group(1)
    reel_specific_dir = os.path.join(PROCESSED_DIR, shortcode)

    if not os.path.exists(reel_specific_dir):
        os.makedirs(reel_specific_dir, exist_ok=True)

    try:
        # Download the post using Instaloader
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=Path(reel_specific_dir))

        # Save the caption text of the reel to a .txt file in the same directory
        caption_file_path = os.path.join(reel_specific_dir, f"{shortcode}_caption.txt")
        with open(caption_file_path, "w", encoding="utf-8") as f:
            f.write(post.caption if post.caption else "No caption")

        # Include the caption file in the zip file
        zip_file_path = os.path.join(PROCESSED_DIR, f"{shortcode}.zip")
        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            for item in Path(reel_specific_dir).iterdir():
                if item.is_file():
                    zipf.write(item, arcname=item.name)

        # Log the successful download along with the caption
        action = f"successfully downloaded Instagram reel and caption: {reel_url}"
        log_user_activity(request, background_tasks, user["username"], action)

    except Exception as e:
        # If an error occurs during download or zipping, log the error
        action = f"failed to download Instagram reel and caption: {reel_url} with error: {str(e)}"
        log_user_activity(request, background_tasks, user["username"], action)
        raise HTTPException(status_code=500, detail="Failed to download Instagram reel.") from e

    return FileResponse(path=zip_file_path, media_type='application/zip', filename=f"{shortcode}.zip")
