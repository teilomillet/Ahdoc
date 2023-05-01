from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from pydantic import BaseModel

import uvicorn
import json
import logging
import os
import tempfile
import time
from abc import ABC
from io import StringIO
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlparse

from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.llms import OpenAI
from langchain.chains import VectorDBQA
from langchain.document_loaders import TextLoader, UnstructuredPDFLoader, PyPDFLoader
from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader
from langchain.document_loaders.unstructured import UnstructuredFileLoader
from langchain.utils import get_from_dict_or_env
from langchain.chains import RetrievalQA

os.environ.update({
    'OPENAI_API_KEY': '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'
})

# FastAPI app
app = FastAPI()

# Temporary file to store the uploaded PDF
temp_pdf = tempfile.NamedTemporaryFile(delete=False)

class FileUpload(BaseModel):
    name: str
    size: int

# Background task to indicate that the file has been received
def process_file_upload(upload: FileUpload):
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
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    contents = await file.read()
    with open(temp_pdf.name, mode="wb") as f:
        f.write(contents)
        background_tasks.add_task(process_file_upload, FileUpload(name=file.filename, size=len(contents)))
    return {"filename": file.filename}

# Endpoint to ask a question based on the uploaded PDF
@app.post("/question")
def ask_question(question: str):
    qa = load_pdf()
    answer = qa.run(question)
    return {"answer": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
