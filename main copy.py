from fastapi import FastAPI, File, UploadFile, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

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

# FastAPI app
app = FastAPI()

room_list = []

# Temporary file to store the uploaded PDF
temp_pdf = io.BytesIO()

class FileUpload(BaseModel):
    name: str
    size: int

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


# Endpoint to upload a PDF file
@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), max_size: Optional[int] = 1000000):
    global temp_pdf
    file_name = generate_filename(file.filename)
    temp_pdf = io.BytesIO(await file.read())
    if len(temp_pdf.getvalue()) > max_size:
        return {"error": "File size exceeds the maximum limit."}
    background_tasks.add_task(process_file_upload, FileUpload(name=file.filename, size=len(temp_pdf.getvalue())))
    return {"filename": file.filename}
    

# Endpoint to ask a question based on the uploaded PDF
@app.post("/question")
def ask_question(question: str):
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
