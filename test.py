from fastapi import FastAPI, File, UploadFile, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

import uvicorn
import json
import os
import tempfile
from typing import Optional
from copy import copy

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
temp_pdf = tempfile.NamedTemporaryFile()

class FileUpload(BaseModel):
    name: str
    size: int

# Background task to indicate that the file has been received
def process_file_upload(upload: FileUpload) -> None:
    print(f"Received file {upload.name} of size {upload.size} bytes")

def load_pdf():
    # Document loader
    loader = PyPDFLoader(temp_pdf.name)
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
    contents = await file.read()
    if len(contents) > max_size:
        return {"error": "File size exceeds the maximum limit."}
    with open(temp_pdf.name, mode="wb") as f:
        f.write(contents)
        background_tasks.add_task(process_file_upload, FileUpload(name=file.filename, size=len(contents)))
    return {"filename": file.filename}

# Endpoint to ask a question based on the uploaded PDF
@app.post("/question")
def ask_question(question: str):
    with get_openai_callback() as cb, open(temp_pdf.name, mode="rb") as pdf_file:
        qa = load_pdf()
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
