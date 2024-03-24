from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import os

from tools.transcribe_media import process_media_transcription, determine_source_type
from tools.token_counter import calculate_token_count

from auth import get_current_user

router = APIRouter()
load_dotenv()  # Load environment variables from .env file

openai.api_key = os.getenv("OPENAI_API_KEY")  # Set your OpenAI API key


class TranscriptProcessRequest(BaseModel):
    source_url: str
    confirm_summary: bool = (
        False  # Indicates whether the user confirms summarization after seeing the token count
    )


class TranscriptProcessResponse(BaseModel):
    transcript: str
    token_count: int
    summary: str = (
        ""  # This will contain the summary if the user confirms the summarization process
    )


async def summarize_text(transcript: str) -> str:
    """
    Summarize the provided transcript using GPT-4 without offering a model choice.
    This function assumes you have a valid OpenAI API key.
    """
    try:
        prompt = f"""
        Construct a structured summary of the video based on the audio transcription:\n{transcript}
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
        print(result)
        summary = result.choices[0].message.content
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to summarize the text: {str(e)}"
        )


# Define a function to calculate the total tokens, including the prompt and summary
async def total_prompt_transcript_token_count(transcript: str) -> int:
    # Calculate the tokens for the given transcript
    # transcript_tokens = calculate_token_count(transcript)

    # Define the prompt used for the summarization
    prompt = f"""
    Construct a structured summary of the video based on the audio transcription:\n{transcript}
    """
    # Calculate the tokens for the prompt
    prompt_tokens = calculate_token_count(prompt)

    # Add 600 tokens to account for the maximum response size
    max_response_tokens = 600

    # Sum up the tokens
    total_transcript_tokens = prompt_tokens + max_response_tokens
    return total_transcript_tokens


@router.post("/audio-summary/", tags=["Summarize Audio from a Video"])
async def audio_summary(
    request: TranscriptProcessRequest, 
    user: dict = Depends(get_current_user)
) -> TranscriptProcessResponse:
    source_type = determine_source_type(request.source_url)
    if source_type == "unsupported":
        raise HTTPException(status_code=400, detail="Unsupported URL type provided.")

    transcription, _ = await process_media_transcription(
        request.source_url, source_type
    )

    # Calculate the total tokens
    total_transcript_tokens = await total_prompt_transcript_token_count(transcription)

    summary = ""
    if request.confirm_summary:
        summary = await summarize_text(transcription)

    return TranscriptProcessResponse(
        transcript=transcription, token_count=total_transcript_tokens, summary=summary
    )
