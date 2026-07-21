import os

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.documents import STATIC_DOCS

EXPRESS_BASE_URL = os.environ.get("EXPRESS_BASE_URL", "http://localhost:3000")

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = None  # Will be initialized elsewhere or passed in


async def initialize_rag():
    global vectorstore

    documents = list(STATIC_DOCS)

    # Try to load public FAQ page from the web app (optional, graceful fallback)
    try:
        loader = WebBaseLoader(
            [f"{EXPRESS_BASE_URL}/faq"],
            requests_kwargs={"timeout": 10},
        )
        web_docs = loader.load()
        if web_docs:
            documents.extend(web_docs)
    except Exception:
        pass

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(documents)

    vectorstore = FAISS.from_documents(chunks, embeddings)
    return vectorstore


def get_vectorstore():
    return vectorstore
