from fastapi import FastAPI, File, UploadFile, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter, WebSocketRateLimiter
from pydantic import BaseModel

from jose import jwt, JWTError
from passlib.context import CryptContext


import uuid
import time
import uvicorn
import json
import os
import tempfile
import io
import threading
import asyncio

from io import BytesIO
from typing import Optional
from copy import copy
from functools import lru_cache
from datetime import datetime, timedelta

from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.llms import OpenAI
from langchain.chains import RetrievalQA
from langchain.callbacks import get_openai_callback
from langchain.document_loaders import PyPDFLoader, UnstructuredPDFLoader, PyMuPDFLoader


os.environ.update({
    'OPENAI_API_KEY': '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'
})

SECRET_KEY = "4f37c493e65289aed7abe7b0df5b807dbd8c4e6b5998e749e0a31cf9d355d255"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

UPLOAD_DIR = "data"

db = {
    "test": {
        "username": "test",
        "full_name": "Test Test",
        "email": "test@gmail.com",
        "hashed_password": "$2b$12$R.75BWLXy8XiU7FPBKJlYeF3Af82KZeYicY1HajFLJv.elVW8f/YS",
        "disabled": False
    }
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="token")

room_list = []

# Temporary file to store the uploaded PDF
temp_pdf = io.BytesIO()


# Pydantic models for input and output data
class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class UserOut(BaseModel):
    username: str
    email: str

class UserInCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None


class FileUpload(BaseModel):
    name: str
    size: int

# FastAPI app
app = FastAPI()

# Functions for password hashing and verification
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_hash_password(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_data = db[username]
        return UserInDB(**user_data)
    
def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta or None=None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else: 
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth_2_scheme)):
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                                         detail="Could not validate credential", 
                                         headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        if username is None:
            raise credential_exception
        
        token_data = TokenData(username=username)
    except JWTError:
        raise credential_exception
    
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credential_exception
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Inactive user')
    return current_user

# Endpoint to upload token
@app.post("/token", response_model=Token)
async def login_for_access_token(data_form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db, data_form.username, data_form.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail='Mauvais identifiant ou mot de passe',
                            headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={'sub': user.username}, expires_delta=access_token_expires)
    return {'access_token': access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
    
@app.get("/users/me/items")
async def read_own_items(current_user: User = Depends(get_current_active_user)):
    return [{"item_id": 1, "owner": current_user}]

# Endpoit to sign up a new user
@app.post("/users/signup", response_model=UserOut)
async def create_user(user: UserInCreate):
    if user.username in db:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_hash_password(user.password)
    db[user.username] = {"username": user.username, "hashed_password": hashed_password, "disabled": False}
    return UserOut(**db[user.username])

# Background task to indicate that the file has been received
def process_file_upload(upload: FileUpload) -> None:
    print(f"Received file {upload.name} of size {upload.size} bytes")

# Generate a unique filename based on timestamp and random string
def generate_filename(file_name):
    timestamp = int(time.time())
    random_string = uuid.uuid4().hex
    return f"{file_name}-{timestamp}-{random_string}"

@lru_cache(maxsize=1)
def load_pdf(user_id):
    # Construct the path to the PDF file
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}.pdf")

    # Load the document
    loader = PyMuPDFLoader(file_path)
    documents = loader.load()

    # Document splitter
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_documents(documents)

    # Create embeddings
    embeddings = OpenAIEmbeddings()
    vectordb = Chroma.from_documents(texts, embeddings)

    # Create the chain
    llm = OpenAI()
    retriever = vectordb.as_retriever()
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)

    return qa

# Endpoint to upload a PDF file
@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks,
                      file: UploadFile = File(...),
                      max_size: Optional[int] = 100000000,
                      user_id: str = Form(...)):
    global temp_pdf
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}.pdf")
    temp_pdf = io.BytesIO(await file.read())
    if len(temp_pdf.getvalue()) > max_size:
        return {"error": "File size exceeds the maximum limit."}
    with open(file_path, "wb") as pdf_file:
        pdf_file.write(temp_pdf.getvalue())

    # Set timer to delete file after 10 minutes of inactivity
    def delete_file():
        os.remove(file_path)
    timer = threading.Timer(10 * 60, delete_file)
    timer.start()

    background_tasks.add_task(process_file_upload, FileUpload(name=file.filename, size=len(temp_pdf.getvalue())))
    return {"filename": file.filename}



# Endpoint to ask a question based on the uploaded PDF
@app.post("/question")
def ask_question(question: str, user_id: str):
    file_path = os.path.join(UPLOAD_DIR, f"{user_id}.pdf")
    if not os.path.isfile(file_path):
        return {"error": f"PDF file not found at {file_path}.pdf"}
    qa = load_pdf(user_id)
    answer = qa.run(question)
    return {"answer": answer}

# Create websocket
async def send_message(websocket: WebSocket, message: str):
    await websocket.send_text(json.dumps({'msg': message}))

# Create websocket
@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    try:
        await websocket.accept()
        print('Connection established, socket - ', websocket)
        
        # Set the inactivity timeout (in seconds)
        inactivity_timeout = 600
        
        # Start the timer
        async def timer():
            while True:
                await asyncio.sleep(inactivity_timeout)
                try:
                    await send_message(websocket, "Error: Inactivity timeout reached.")
                    await websocket.close()
                except:
                    pass
        
        task = asyncio.create_task(timer())
        
        while True:
            data = await websocket.receive_text()
            # Reset the timer on each incoming message
            task.cancel()
            task = asyncio.create_task(timer())
            response = ask_question(data, user_id)
            if "answer" in response:
                await send_message(websocket, response["answer"])
            else:
                await send_message(websocket, "Error: " + response["error"])
    except WebSocketDisconnect as e:
        print('Connection closed.')
        print(e)
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)