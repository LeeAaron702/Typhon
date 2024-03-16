from fastapi import FastAPI, status, Depends, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import models 
from database import engine, SessionLocal
from typing import Annotated
from sqlalchemy.orm import Session
import os
from starlette.exceptions import HTTPException as StarletteHTTPException

import auth 
from auth import get_current_user
from utils.logger import log_user_activity, DISCORD_WEBHOOK_URL

from tools.audio_video_separator import router as av_router
from tools.youtube_downloader import router as yt_router
from tools.transcribe_media import router as tm_router
from tools.bulk_image_compressor import router as bic_router
from tools.instagram_reel_downloader import router as ir_router  # Import the Instagram reel downloader router
from tools.instagram_audio_video_analyzer import router as iava_router

app = FastAPI()

origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(av_router, prefix="/tools")
app.include_router(yt_router, prefix="/tools")
app.include_router(tm_router, prefix="/tools")
app.include_router(bic_router, prefix="/tools")
app.include_router(ir_router, prefix="/tools") 
app.include_router(iava_router, prefix="/tools") 

models.Base.metadata.create_all(bind=engine)

PROCESSED_DIR = "processed"

@app.on_event("startup")
def on_startup():
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code != status.HTTP_200_OK:
        message = f"Error: {exc.detail} (Status code: {exc.status_code}, Path: {request.url.path})"
        async with httpx.AsyncClient() as client:
            data = {"content": message}
            await client.post(DISCORD_WEBHOOK_URL, json=data)
    return JSONResponse(content={"detail": exc.detail}, status_code=exc.status_code)

@app.get("/", tags=['Authentication'], status_code=status.HTTP_200_OK)
async def user(request: Request, background_tasks: BackgroundTasks, user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed')
    
    log_user_activity(request, background_tasks, user['username'], "accessed the auth function")
    
    return {"User": user}
