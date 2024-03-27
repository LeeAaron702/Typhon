from datetime import timedelta, datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from database import SessionLocal
from models import Users
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from .logger import log_user_activity
import os
from dotenv import load_dotenv
from fastapi import Form
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])

load_dotenv()  # Load environment variables from .env file

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")


class CreateUserForm(BaseModel):
    username: str
    password: str
    first_name: str
    last_name: str
    email: str

    # Use a method to preprocess inputs if needed, like making the username lowercase
    def __init__(self, **data):
        super().__init__(**data)
        self.username = self.username.lower()
        self.email = self.email.lower()


class Token(BaseModel):
    access_token: str
    token_type: str
    username: str



async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    background_tasks: BackgroundTasks,
    db: db_dependency,
    form_data: CreateUserForm,  # This now expects JSON data
):
    create_user_model = Users(
        username=form_data.username,
        hashed_password=bcrypt_context.hash(form_data.password),
        first_name=form_data.first_name,
        last_name=form_data.last_name,
        email=form_data.email,
    )
    db.add(create_user_model)
    db.commit()

    action_message = "been created"
    log_user_activity(
        request, background_tasks, create_user_model.username, action_message
    )

    return {"msg": "User created successfully."}
    # need to add error handling to this


@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    background_tasks: BackgroundTasks,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: db_dependency,
):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )

    token = create_access_token(user.username, user.id, timedelta(minutes=60))

    # Here we are logging the username who has obtained the token
    action_message = "logged in and obtained a token."
    log_user_activity(request, background_tasks, form_data.username, action_message)

    return {"access_token": token, "token_type": "bearer", "username": user.username}


def authenticate_user(username: str, password: str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user:
        return False
    if not bcrypt_context.verify(password, user.hashed_password):
        return False
    return user


def create_access_token(username: str, user_id: int, expires_delta: timedelta):
    encode = {"sub": username, "id": user_id}
    expires = datetime.utcnow() + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate user.",
            )
        return {"username": username, "id": user_id}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user."
        )
