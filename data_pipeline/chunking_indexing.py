import sys
import tempfile
import uuid
from pathlib import Path
 
# Permite importar os módulos de app/core mesmo rodando este script direto da pasta data_pipeline/
sys.path.append(str(Path(__file__).resolve().parent.parent))
 
from app.core.embeddings import embed_passage
from app.core.qdrant_utils import (
    count_by_fonte,
    delete_by_fonte,
    ensure_collection,
    get_qdrant_client,
    upsert_chunk,
)
from data_pipeline.chunking import chunk_pdf_markdown, chunk_video_markdown
from data_pipeline.minioutils import download_from_bronze, get_minio_client, BUCKET_SILVER
 
 
def list_silver_files(client, prefix: str):
    response = client.list_objects_v2(Bucket=BUCKET_SILVER, Prefix=prefix)
    return [obj["Key"] for obj in response.get("Contents", [])]
 
 
def download_from_silver(client, key: str, local_dir: Path) -> Path:
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / Path(key).name
    client.download_file(BUCKET_SILVER, key, str(local_path))
    return local_path
 
 
# Namespace fixo: garante que o mesmo (arquivo, posição do chunk) sempre gere o MESMO id.
_NAMESPACE_IDS = uuid.UUID("6f1b6c3e-0d4a-4a53-9a57-2b0f6c7d1e11")
 
FORCE = "--force" in sys.argv
 
 
def index_chunks(qdrant_client, chunks: list, fonte: str, tipo_midia: str):
    """
    Indexa os chunks de UM arquivo. Antes, apaga o que já existia desse arquivo, e os ids
    são determinísticos — assim reindexar NUNCA duplica (nem deixa chunks velhos de uma
    versão anterior do arquivo para trás).
    """
    delete_by_fonte(qdrant_client, fonte, tipo_midia)
    for posicao, chunk in enumerate(chunks):
        vector = embed_passage(chunk["texto"])
        chunk_id = str(uuid.uuid5(_NAMESPACE_IDS, f"{tipo_midia}:{fonte}:{posicao}"))
        upsert_chunk(qdrant_client, chunk_id, vector, chunk)
 
 
def ja_indexado(qdrant_client, fonte: str, tipo_midia: str) -> bool:
    return count_by_fonte(qdrant_client, fonte, tipo_midia) > 0
 
 
def process_pdfs(minio_client, qdrant_client, tmp_dir: Path):
    keys = list_silver_files(minio_client, "pdfs/")
    print(f"[chunking_indexing] {len(keys)} PDF(s) processado(s) encontrados em silver/pdfs/.")
 
    total_chunks = 0
    for key in keys:
        fonte = Path(key).stem
        if not FORCE and ja_indexado(qdrant_client, fonte, "pdf"):
            print(f"  -> {key}: já indexado, pulando (use --force para reindexar)")
            continue
        local_path = download_from_silver(minio_client, key, tmp_dir)
        markdown_text = local_path.read_text(encoding="utf-8")
        chunks = chunk_pdf_markdown(markdown_text, fonte=fonte)
        index_chunks(qdrant_client, chunks, fonte, "pdf")
        total_chunks += len(chunks)
        print(f"  -> {key}: {len(chunks)} chunks indexados")
 
    return total_chunks
 
 
def process_videos(minio_client, qdrant_client, tmp_dir: Path):
    keys = list_silver_files(minio_client, "videos/")
    print(f"[chunking_indexing] {len(keys)} vídeo(s) transcrito(s) encontrado(s) em silver/videos/.")
 
    total_chunks = 0
    for key in keys:
        fonte = Path(key).stem
        if not FORCE and ja_indexado(qdrant_client, fonte, "video"):
            print(f"  -> {key}: já indexado, pulando (use --force para reindexar)")
            continue
        local_path = download_from_silver(minio_client, key, tmp_dir)
        markdown_text = local_path.read_text(encoding="utf-8")
        chunks = chunk_video_markdown(markdown_text, fonte=fonte)
        index_chunks(qdrant_client, chunks, fonte, "video")
        total_chunks += len(chunks)
        print(f"  -> {key}: {len(chunks)} chunks indexados")
 
    return total_chunks
 
 
def main():
    minio_client = get_minio_client()
    qdrant_client = get_qdrant_client()
    ensure_collection(qdrant_client)
 
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        total_pdf_chunks = process_pdfs(minio_client, qdrant_client, tmp_dir)
        total_video_chunks = process_videos(minio_client, qdrant_client, tmp_dir)
 
    print(f"\n[chunking_indexing] Concluído. Chunks novos indexados nesta rodada: {total_pdf_chunks + total_video_chunks}.")
    print("[chunking_indexing] Com a API rodando, chame POST /reindexar-bm25 para ela enxergar os novos chunks.")
 
 
if __name__ == "__main__":
    main()
 