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

import utilities.auth as auth 
from utilities.auth import get_current_user
from utilities.logger import log_user_activity, DISCORD_WEBHOOK_URL

# from tools.youtube_download_transcribe_media import router as tm_router
# from tools.bulk_image_compressor import router as bic_router
# from tools.instagram_audio_video_analyzer import router as iava_router
# from tools.calculate_token_count import router as tc_router
# from tools.youtube_download_transcribe_and_count_tokens import router as ydtact_router

from utilities.users import router as user_router

# from tools.youtube_downloader import router as yt_router
# from tools.instagram_downloader import router as id_router 
from tools.downloader import router as dl_router

from tools.audio_video_separator import router as av_router
from tools.transcribe_media import router as tm_router 
# from tools.token_counter import router as tc_router
from tools.summarize_transcript import router as st_router
from tools.summarize_video import router as sv_router
from tools.summarize_transcript_and_video import router as stv_router

from tools.stripe import router as stripe_router

# from tools.video_analysis import router as va_router

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

app.include_router(user_router, prefix="/tools")

# app.include_router(yt_router, prefix="/tools")
app.include_router(dl_router, prefix="/tools")
app.include_router(av_router, prefix="/tools")



# app.include_router(id_router, prefix="/tools") 
app.include_router(tm_router, prefix="/tools") 
# app.include_router(tc_router, prefix="/tools") 
app.include_router(st_router, prefix="/tools") 
app.include_router(sv_router, prefix="/tools") 
app.include_router(stv_router, prefix="/tools") 

app.include_router(stripe_router, prefix="/tools") 

# app.include_router(va_router, prefix="/tools") 

# app.include_router(tm_router, prefix="/tools")
# app.include_router(bic_router, prefix="/tools")
# app.include_router(iava_router, prefix="/tools") 
# app.include_router(ydtact_router, prefix="/tools") 
# app.include_router(ct_router, prefix="/tools") 

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

# @app.get("/", tags=['Authentication'], status_code=status.HTTP_200_OK)
# async def user(request: Request, background_tasks: BackgroundTasks, user: user_dependency, db: db_dependency):
#     if user is None:
#         raise HTTPException(status_code=401, detail='Authentication Failed')
    
#     log_user_activity(request, background_tasks, user['username'], "accessed the auth function")
    
#     return {"User": user}
