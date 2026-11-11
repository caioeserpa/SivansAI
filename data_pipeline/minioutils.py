"""
Funções compartilhadas para conectar e trocar arquivos com o MinIO.
Usado tanto por extract_pdfs.py quanto por transcribe_videos.py.
"""
 
import os
from pathlib import Path
 
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
 
load_dotenv()
 
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "")
BUCKET_BRONZE = os.getenv("MINIO_BUCKET_BRONZE", "bronze")
BUCKET_SILVER = os.getenv("MINIO_BUCKET_SILVER", "silver")
 
 
def get_minio_client():
    """Cria o cliente que fala com o MinIO usando a mesma API do S3."""
    return boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
 
 
def ensure_buckets_exist(client):
    """Cria os buckets bronze e silver caso ainda não existam."""
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
    for bucket in (BUCKET_BRONZE, BUCKET_SILVER):
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
            print(f"[minio_utils] Bucket '{bucket}' criado.")
 
 
def list_bronze_files(client, extension: str):
    """Lista os arquivos do bucket bronze que terminam com a extensão dada (ex: '.pdf')."""
    response = client.list_objects_v2(Bucket=BUCKET_BRONZE)
    contents = response.get("Contents", [])
    return [obj["Key"] for obj in contents if obj["Key"].lower().endswith(extension.lower())]
 
 
def download_from_bronze(client, key: str, local_dir: Path) -> Path:
    """Baixa um arquivo do bucket bronze para uma pasta temporária local."""
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / Path(key).name
    client.download_file(BUCKET_BRONZE, key, str(local_path))
    return local_path
 
 
def upload_to_silver(client, local_path: Path, key: str):
    """Envia um arquivo processado para o bucket silver."""
    client.upload_file(str(local_path), BUCKET_SILVER, key)
    print(f"[minio_utils] Enviado para silver: {key}")
 
 
def silver_key_exists(client, key: str) -> bool:
    """Retorna True se o arquivo já existe no bucket silver (ou seja, já foi processado)."""
    try:
        client.head_object(Bucket=BUCKET_SILVER, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
 