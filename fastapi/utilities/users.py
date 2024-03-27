from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from database import SessionLocal 
from models import Users  
from typing import Optional

from utilities.auth import get_current_user

router = APIRouter()


class UserResponse(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    stripe_customer_id: Optional[str] = None
    ai_api_counter: int

    class Config:
        from_attributes = True  # Updated from 'orm_mode' to 'from_attributes'


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/users/{username}", response_model=UserResponse)
async def get_user(
    username: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    user = db.query(Users).filter(Users.username == username.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        stripe_customer_id=user.stripe_customer_id,
        ai_api_counter=user.ai_api_counter,
    )
