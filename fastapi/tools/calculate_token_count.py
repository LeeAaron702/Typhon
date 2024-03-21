from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
import tiktoken

app = FastAPI()
router = APIRouter()

class TokenCountRequest(BaseModel):
    text: str
    model_name: str = "gpt-4"  # Default model name; adjust as necessary

def calculate_token_count(text: str, model_name: str = "gpt-4") -> int:
    """
    Calculate the token count of a given text using a specified model's encoding from tiktoken.

    Parameters:
    text (str): The text to calculate the token count for.
    model_name (str): The model name to select the appropriate encoding. Defaults to "gpt-4".

    Returns:
    int: The total token count of the text.
    """
    # Get the encoding for the specified model
    enc = tiktoken.encoding_for_model(model_name)
    
    # Encode the text and calculate the token count
    token_count = len(enc.encode(text))
    
    return token_count

@router.post("/calculate-tokens/", tags=["Utility"])
async def calculate_tokens(request: TokenCountRequest):
    """
    Endpoint to calculate the token count of the provided text for a specific model's encoding.

    Parameters:
    request (TokenCountRequest): A request model containing the text and the model name.

    Returns:
    dict: A dictionary containing the total token count and the model used.
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="Text must be provided.")

    token_count = calculate_token_count(request.text, request.model_name)
    return {"model_name": request.model_name, "token_count": token_count}

app.include_router(router)
