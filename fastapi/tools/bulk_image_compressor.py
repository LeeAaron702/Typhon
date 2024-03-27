from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends, BackgroundTasks, Request
from fastapi.responses import FileResponse
from PIL import Image
import os
import shutil
import zipfile
from typing import List
from utilities.auth import get_current_user
from utilities.logger import log_user_activity  # Import the logging functions

router = APIRouter()

PROCESSED_DIR = "processed"
SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png']

quality_mapping = {
    "high": 80,
    "medium": 75,
    "low": 60,
    "very low": 50,
}

def compress_image(input_path, output_path, quality_setting):
    quality = quality_mapping.get(quality_setting, 80)
    with Image.open(input_path) as image:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(output_path, 'JPEG', quality=quality, optimize=True)

def is_large_file(file_path, size_threshold):
    file_size = os.path.getsize(file_path) / 1024  # in Kilobytes
    return file_size > size_threshold

def process_single_image(file_path, quality_value, size_threshold):
    if is_large_file(file_path, size_threshold):
        base, ext = os.path.splitext(file_path)
        optimized_file_path = f"{base}_optimize_{quality_value}.jpg"
        compress_image(file_path, optimized_file_path, quality_mapping[quality_value])
        return optimized_file_path
    return file_path

def process_image_files(directory, quality_value, size_threshold):
    processed_files = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if not filename.lower().endswith(tuple(SUPPORTED_IMAGE_FORMATS)):
                continue
            file_path = os.path.join(root, filename)
            processed_file_path = process_single_image(file_path, quality_value, size_threshold)
            processed_files.append((processed_file_path, os.path.relpath(processed_file_path, directory)))
    return processed_files

@router.post("/bulk_image_compressor/", tags=['Bulk Image Compressor'])
async def bulk_image_compressor(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    quality: str = Query(default="high", enum=["high", "medium", "low", "very low"]),
    size_threshold: int = Query(default=500),
    user: dict = Depends(get_current_user)
):
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

    user_action = f"compressed images with {quality} quality"
    log_user_activity(request, background_tasks, user['username'], user_action)

    compressed_zip_filename = f"{user['username']}_compressed_images.zip"
    compressed_zip_file_path = os.path.join(PROCESSED_DIR, compressed_zip_filename)

    with zipfile.ZipFile(compressed_zip_file_path, 'w') as zipf:
        for uploaded_file in files:
            temp_file_path = os.path.join(PROCESSED_DIR, uploaded_file.filename)
            with open(temp_file_path, 'wb') as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)

            if uploaded_file.filename.lower().endswith('.zip'):
                extraction_path = os.path.join(PROCESSED_DIR, uploaded_file.filename[:-4])
                os.makedirs(extraction_path, exist_ok=True)
                with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                    zip_ref.extractall(extraction_path)

                processed_files = process_image_files(extraction_path, quality, size_threshold)
                for processed_file_path, arcname in processed_files:
                    zipf.write(processed_file_path, arcname)
                    os.remove(processed_file_path)
                shutil.rmtree(extraction_path)
            else:
                if uploaded_file.filename.lower().endswith(tuple(SUPPORTED_IMAGE_FORMATS)):
                    optimized_file_path = process_single_image(temp_file_path, quality, size_threshold)
                    arcname = os.path.basename(optimized_file_path)
                    zipf.write(optimized_file_path, arcname)
                    os.remove(optimized_file_path)
            os.remove(temp_file_path)

    return FileResponse(path=compressed_zip_file_path, media_type='application/zip', filename=compressed_zip_filename)
