import os
from functools import lru_cache
 
 
@lru_cache(maxsize=1)
def get_embedding_model():
    # Import feito aqui dentro (e não no topo do arquivo) para que o restante do
    from sentence_transformers import SentenceTransformer
 
    model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    return SentenceTransformer(model_name)
 
 
def embed_passage(text: str):
    model = get_embedding_model()
    vector = model.encode(f"passage: {text}", normalize_embeddings=True)
    return vector.tolist()
 
 
def embed_query(text: str):
    model = get_embedding_model()
    vector = model.encode(f"query: {text}", normalize_embeddings=True)
    return vector.tolist()
 
 
def embedding_dimension() -> int:
    """multilingual-e5-small produz vetores de 384 dimensões."""
    return 384