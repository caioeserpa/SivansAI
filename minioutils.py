import os
from pathlib import Path

import boto3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD")
BUCKET_BRONZE = os.getenv("MINIO_BUCKET_BRONZE", "bronze")
BUCKET_SILVER = os.getenv("MINIO_BUCKET_SILVER", "silver")


def get_minio_client():
    
    # Aplica strip() para garantir que não há espaços invisíveis
    access_key = MINIO_ROOT_USER.strip() if MINIO_ROOT_USER else None
    secret_key = MINIO_ROOT_PASSWORD.strip() if MINIO_ROOT_PASSWORD else None
    
    #Cria o cliente que fala com o MinIO usando a mesma API do S3
    return boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={'addressing_style': 'path'}),
        region_name="us-east-1",
    )
    
   
def ensure_buckets_exist(client):
    #Cria os buckets bronze e silver caso ainda não exisam
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
    for bucket in (BUCKET_BRONZE, BUCKET_SILVER):
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
            print(f"[minio_utils] Bucket '{bucket}' criado.")
            

def list_bronze_files(client, extension: str):
    #lista os arquivos do bucket bronze que terminam com a extensão dada
    response = client.list_objects_v2(Bucket=BUCKET_BRONZE)
    contents = response.get("Contents", [])
    return [obj["Key"] for obj in contents if obj["Key"].lower().endswith(extension.lower())]

def download_from_bronze(client, key: str, local_dir: Path) -> Path: 
    #Baixa um arquivo do bucket bronze para uma pasta temporária local
    local_dir.mkdir(parents=True, exist_ok=True)    
    local_path = local_dir / Path(key).name
    client.download_file(BUCKET_BRONZE, key, str(local_path))
    return local_path
    
def upload_to_silver(client, local_path: Path, key: str):
    #Envia um arquivo processado para o bucket silver
    client.upload_file(str(local_path), BUCKET_SILVER, key)
    print(f"[minio_utils] Enviado para silver: {key}")