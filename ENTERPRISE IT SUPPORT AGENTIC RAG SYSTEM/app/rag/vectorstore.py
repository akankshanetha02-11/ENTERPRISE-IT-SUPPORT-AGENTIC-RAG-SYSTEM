import time

from pinecone import Pinecone, ServerlessSpec
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

from app.core.config import get_settings


settings = get_settings()

_embeddings = None
_vectorstore = None


# Embedding model dimensions
EMBEDDING_DIMENSIONS = {
    "sentence-transformers/all-minilm-l6-v2": 384,
    "all-minilm-l6-v2": 384,
}


# Get embedding dimension
def get_embedding_dimension(model_name: str | None = None) -> int:

    name = (model_name or settings.embedding_model).strip().lower()

    if name in EMBEDDING_DIMENSIONS:
        return EMBEDDING_DIMENSIONS[name]

    if "all-minilm-l6-v2" in name:
        return 384

    raise ValueError(
        f"Unsupported embedding model: {name}"
    )


# Initialize HuggingFace embeddings
def get_embeddings():

    global _embeddings

    if _embeddings is None:

        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    return _embeddings


# Create or connect Pinecone index
def ensure_index():

    if not settings.pinecone_api_key:
        raise RuntimeError("PINECONE_API_KEY is missing")

    desired_dimension = get_embedding_dimension()

    pc = Pinecone(api_key=settings.pinecone_api_key)

    existing_indexes = pc.list_indexes().names()

    if settings.pinecone_index_name in existing_indexes:

        index_info = pc.describe_index(
            settings.pinecone_index_name
        )

        current_dimension = index_info.dimension

        if current_dimension != desired_dimension:

            raise ValueError(
                f"Dimension mismatch: Existing index = "
                f"{current_dimension}, Required = {desired_dimension}. "
                "Please create a new Pinecone index with dimension 384."
            )

    else:

        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=desired_dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            ),
        )

        while True:

            index_info = pc.describe_index(
                settings.pinecone_index_name
            )

            if index_info.status["ready"]:
                break

            time.sleep(1)

    return pc.Index(settings.pinecone_index_name)


# Initialize Pinecone Vector Store
def get_vectorstore():

    global _vectorstore

    if _vectorstore is None:

        index = ensure_index()

        _vectorstore = PineconeVectorStore(
            index=index,
            embedding=get_embeddings(),
            namespace=settings.pinecone_namespace,
        )

    return _vectorstore


# Create retriever
def get_retriever():

    return get_vectorstore().as_retriever(
        search_kwargs={"k": settings.top_k}
    )


# Add documents to Pinecone
def add_documents(chunks):

    if not chunks:
        raise ValueError("No documents found to insert")

    store = get_vectorstore()

    return store.add_documents(chunks)