import os
 
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)
 
from app.core.embeddings import embedding_dimension
 
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "vale_amanhecer")
 
 
def get_qdrant_client() -> QdrantClient:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)
 
 
def ensure_collection(client: QdrantClient):
    """Cria a coleção no Qdrant caso ainda não exista."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=embedding_dimension(), distance=Distance.COSINE),
        )
        print(f"[qdrant_utils] Coleção '{COLLECTION_NAME}' criada.")
 
 
def upsert_chunk(client: QdrantClient, chunk_id: str, vector: list, payload: dict):
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=chunk_id, vector=vector, payload=payload)],
    )
 
 
def vector_search(client: QdrantClient, query_vector: list, top_k: int = 20):
    """Retorna os top_k pontos mais próximos por similaridade de cosseno."""
    return client.search(collection_name=COLLECTION_NAME, query_vector=query_vector, limit=top_k)
 
 
def scroll_all_points(client: QdrantClient, batch_size: int = 256):
    """Percorre TODOS os pontos da coleção (usado para montar o índice BM25 em memória)."""
    all_points = []
    next_offset = None
 
    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(points)
        if next_offset is None:
            break
 
    return all_points
 
 
def collection_count(client: QdrantClient) -> int:
    info = client.get_collection(COLLECTION_NAME)
    return info.points_count
 
 
def _filtro_por_fonte(fonte: str, tipo_midia: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="fonte", match=MatchValue(value=fonte)),
            FieldCondition(key="tipo_midia", match=MatchValue(value=tipo_midia)),
        ]
    )
 
 
def count_by_fonte(client: QdrantClient, fonte: str, tipo_midia: str) -> int:
    """Quantos chunks deste arquivo já estão indexados (0 = arquivo ainda não indexado)."""
    result = client.count(
        collection_name=COLLECTION_NAME,
        count_filter=_filtro_por_fonte(fonte, tipo_midia),
        exact=True,
    )
    return result.count
 
 
def delete_by_fonte(client: QdrantClient, fonte: str, tipo_midia: str):
    """Apaga todos os chunks de um arquivo (usado ao reindexar um arquivo que mudou)."""
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(filter=_filtro_por_fonte(fonte, tipo_midia)),
    )
 