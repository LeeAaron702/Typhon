from fastapi import APIRouter, HTTPException
from typing import Optional
import tiktoken
from pydantic import BaseModel
from tools.audio_video_separator import determine_source_type
from tools.transcribe_media import process_media_transcription

router = APIRouter()

class TokenCountResponse(BaseModel):  # Response model defined above
    model_name: str
    token_count: int
    transcription: str

def calculate_token_count(text: str, model_name: str = "gpt-4") -> int:
    """
    Calculate the number of tokens in a given text using the specified model.

    Parameters:
    text (str): The input text to tokenize.
    model_name (str): The name of the model to use for encoding. Default is "gpt-4".

    Returns:
    int: The number of tokens in the text.
    """
    enc = tiktoken.encoding_for_model(model_name)
    token_count = len(enc.encode(text))
    return token_count

@router.post("/count-tokens/", tags=['Count Tokens'], response_model=TokenCountResponse)
async def count_tokens(source_url: str, model_name: Optional[str] = "gpt-4") -> TokenCountResponse:
    """
    Receive a source URL, transcribe media to text, and return the token count.
    """
    source_type = determine_source_type(source_url)
    if source_type == "unsupported":
        raise HTTPException(status_code=400, detail="Unsupported URL type provided.")
    
    transcription, _ = await process_media_transcription(source_url, source_type)
    try:
        token_count = calculate_token_count(transcription, model_name)
        return TokenCountResponse(model_name=model_name, token_count=token_count, transcription=transcription)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

