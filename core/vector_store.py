import os
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate



CHROMA_DIR = "vector_db"
COLLECTION_NAME = "meeting_transcripts"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def get_embedding():

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

def build_vector_store(transcript: str)-> Chroma:
    """Build a vector store from the transcript for semantic search."""
    # Split the transcript into smaller chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap= 50,
    )
    chunks = splitter.split_text(transcript)

    # Create Document objects for each chunk
    doc = [Document(page_content=chunk , metadata={"chunk_index": i }) for i, chunk in enumerate(chunks)]


    embeddings = get_embedding()
    vector_store = Chroma.from_documents(
        documents=doc,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME
    )
    return vector_store

def load_vector_store()-> Chroma:
    """Load the existing vector store from disk."""
    embeddings = get_embedding()
    vector_store = Chroma(
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings
    )
    return vector_store

def get_retriver(vector_store: Chroma , k: int = 4):
    """Get a retriever for semantic search from the vector store."""
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k}
    )


