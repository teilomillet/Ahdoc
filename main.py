from fastapi import FastAPI, File, UploadFile, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
from io import BytesIO
from typing import Optional
from copy import copy
from functools import lru_cache
from datetime import datetime, timedelta

from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.llms import OpenAI
from langchain.chains import VectorDBQA
from langchain.callbacks import get_openai_callback
from langchain.document_loaders import PyPDFLoader


os.environ.update({
    'OPENAI_API_KEY': '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'
})

SECRET_KEY = "4f37c493e65289aed7abe7b0df5b807dbd8c4e6b5998e749e0a31cf9d355d255"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


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


# Background task to indicate that the file has been received
def process_file_upload(upload: FileUpload) -> None:
    print(f"Received file {upload.name} of size {upload.size} bytes")

# Generate a unique filename based on timestamp and random string
def generate_filename(file_name):
    timestamp = int(time.time())
    random_string = uuid.uuid4().hex
    return f"{file_name}-{timestamp}-{random_string}"

@lru_cache(maxsize=1)
def load_pdf(file_name):
    # Document loader
    loader = PyPDFLoader(file_name)
    documents = loader.load()

    # Document splitter
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_documents(documents)

    # Create embeddings
    embeddings = OpenAIEmbeddings()
    vectordb = Chroma.from_documents(texts, embeddings)

    # Create the chain
    qa = VectorDBQA.from_chain_type(llm=OpenAI(), chain_type="stuff", vectorstore=vectordb)
    return qa


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

# Endpoint to upload a PDF file
@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, 
                      file: UploadFile = File(...), 
                      max_size: Optional[int] = 1000000): # , current_user: User = Depends(get_current_active_user)
    global temp_pdf
    file_name = generate_filename(file.filename)
    temp_pdf = io.BytesIO(await file.read())
    if len(temp_pdf.getvalue()) > max_size:
        return {"error": "File size exceeds the maximum limit."}
    background_tasks.add_task(process_file_upload, FileUpload(name=file.filename, size=len(temp_pdf.getvalue())))
    return {"filename": file.filename}
    

# Endpoint to ask a question based on the uploaded PDF
@app.post("/question")
def ask_question(question: str): #, current_user: UserInDB = Depends(get_current_active_user)
    global temp_pdf
    with get_openai_callback() as cb, BytesIO(temp_pdf.getvalue()) as pdf_file:
        # Save the contents of the BytesIO object to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(pdf_file.read())
        temp_file.close()
        qa = load_pdf(temp_file.name)
        answer = qa.run(question)
        print(f"Total Tokens: {cb.total_tokens}")
        print(f"Prompt Tokens: {cb.prompt_tokens}")
        print(f"Completion Tokens: {cb.completion_tokens}")
        print(f"Total Cost (USD): ${cb.total_cost}")
        return {"answer": answer}
    
async def broadcast_to_room(question: str, except_user):
    res = list(filter(lambda i: i['socket'] == except_user, room_list))
    for room in room_list:
        if except_user != room['socket']:
            await room['socket'].send_text(json.dumps({'msg': question, 'userId': res[0]['client_id']}))
        else:
            # If the message is from the user, call the ask_question endpoint and send the answer back
            answer = ask_question(question)["answer"]
            await room['socket'].send_text(json.dumps({'msg': answer, 'userId': res[0]['client_id']}))

def remove_room(except_room):
    new_room_list = copy(room_list)
    room_list.clear()
    for room in new_room_list:
        if except_room != room['socket']:
            room_list.append(room)
    print("room_list append - ", room_list)


# Create websocket
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    try:
        await websocket.accept()
        print('connection is establish, socket - ', websocket)
        client = {
                'client_id': client_id,
                'socket': websocket
            }
        room_list.append(client)
        while True:
            data = await websocket.receive_text()
            # print(data)
            # await websocket.send_text(data)
            await broadcast_to_room(data, websocket)

    except WebSocketDisconnect as e:
        print('Connection closed.')
        print(e)
        remove_room(websocket)
    

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
