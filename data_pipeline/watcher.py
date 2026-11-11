
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
 
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
 
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))  # permite importar app.core e data_pipeline
 
from data_pipeline.minioutils import BUCKET_BRONZE, BUCKET_SILVER, ensure_buckets_exist, get_minio_client  # noqa: E402
 
load_dotenv()
 
# extensão -> (tipo no Qdrant, pasta no bucket silver)
EXTENSOES = {".pdf": ("pdf", "pdfs"), ".mp4": ("video", "videos")}
SUFIXOS_TEMPORARIOS = {".part", ".crdownload", ".tmp", ".download", ".swp"}
INTERVALO_VERIFICACAO = 5  # segundos entre verificações da fila
 
 
def _pasta_do_acervo() -> Path:
    pasta = Path(os.getenv("ACERVO_DIR", "acervo")).expanduser()
    return pasta if pasta.is_absolute() else PROJECT_ROOT / pasta
 
 
def _segundos_estavel() -> int:
    return int(os.getenv("WATCHER_SEGUNDOS_ESTAVEL", "10"))
 
 
def _api_url() -> str:
    return os.getenv("API_URL", "http://localhost:8000").rstrip("/")
 
 
# ----------------------------------------------------------------------------------
# Filtros
# ----------------------------------------------------------------------------------
def arquivo_oculto_ou_temporario(caminho: Path) -> bool:
    nome = caminho.name
    return nome.startswith((".", "~")) or caminho.suffix.lower() in SUFIXOS_TEMPORARIOS
 
 
def arquivo_valido(caminho: Path) -> bool:
    """True para PDFs e MP4 de verdade (ignora ocultos, temporários e outros formatos)."""
    return not arquivo_oculto_ou_temporario(caminho) and caminho.suffix.lower() in EXTENSOES
 
 
# ----------------------------------------------------------------------------------
# Fila: só libera um arquivo depois que ele parou de crescer
# ----------------------------------------------------------------------------------
class FilaEstavel:
    """
    Copiar um vídeo grande gera dezenas de eventos enquanto o arquivo ainda está
    incompleto. Enviar nessa hora mandaria um arquivo cortado. Por isso cada arquivo
    só fica "pronto" depois que o tamanho dele ficou igual por `segundos_estavel`.
    """
 
    def __init__(self, segundos_estavel: int = 10):
        self.segundos_estavel = segundos_estavel
        self._lock = threading.Lock()
        self._estado = {}  # caminho -> None (ainda não medido) ou (tamanho, desde_quando)
 
    def registrar(self, caminho: Path):
        with self._lock:
            self._estado.setdefault(str(caminho), None)
 
    def prontos(self, agora: float = None) -> list:
        agora = time.monotonic() if agora is None else agora
        liberados = []
        with self._lock:
            for chave, estado in list(self._estado.items()):
                caminho = Path(chave)
                try:
                    tamanho = caminho.stat().st_size
                except FileNotFoundError:
                    del self._estado[chave]  # foi removido/renomeado enquanto esperava
                    continue
 
                if estado is None or estado[0] != tamanho:
                    self._estado[chave] = (tamanho, agora)  # mudou: reinicia a contagem
                    continue
                if tamanho > 0 and agora - estado[1] >= self.segundos_estavel:
                    liberados.append(caminho)
                    del self._estado[chave]
        return liberados
 
 
class ManipuladorAcervo(FileSystemEventHandler):
    def __init__(self, fila: FilaEstavel):
        self.fila = fila
        self._avisados = set()
 
    def _tratar(self, caminho_str: str):
        caminho = Path(caminho_str)
        if arquivo_valido(caminho):
            self.fila.registrar(caminho)
        elif not arquivo_oculto_ou_temporario(caminho) and caminho_str not in self._avisados:
            self._avisados.add(caminho_str)
            print(f"[watcher] Ignorando '{caminho.name}': formato não suportado (use .pdf ou .mp4).")
 
    def on_created(self, event):
        if not event.is_directory:
            self._tratar(event.src_path)
 
    def on_modified(self, event):
        if not event.is_directory:
            self._tratar(event.src_path)
 
    def on_moved(self, event):
        if not event.is_directory:
            self._tratar(event.dest_path)
 
def enviar_para_bronze(minio_client, caminho: Path, limpar_derivados=None) -> str:
    """
    Envia o arquivo para o bucket bronze. Devolve:
    - "novo":         não existia no bronze, foi enviado;
    - "igual":        já existe no bronze (mesmo tamanho) E já tem o .md no silver;
    - "falta_silver": existe no bronze, mas o .md processado sumiu ou nunca terminou;
    - "atualizado":   existe no bronze mas com tamanho diferente: foi reenviado e limpo.
    """
    chave = caminho.name
    tamanho_local = caminho.stat().st_size
    tipo, pasta_silver = EXTENSOES[caminho.suffix.lower()]
    chave_silver = f"{pasta_silver}/{caminho.stem}.md"
 
    try:
        existente = minio_client.head_object(Bucket=BUCKET_BRONZE, Key=chave)
        tamanho_remoto = existente["ContentLength"]
        ja_existia = True
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
            raise
        ja_existia = False
 
    # Se já existia no bronze com o mesmo tamanho, verifica se o processamento terminou (Silver)
    if ja_existia and tamanho_remoto == tamanho_local:
        try:
            minio_client.head_object(Bucket=BUCKET_SILVER, Key=chave_silver)
            return "igual"  # Tudo certo em ambos os buckets
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return "falta_silver"  # Está no bronze, mas falta processar
            raise
 
    # Se é novo ou mudou de tamanho, faz o upload pro bronze
    minio_client.upload_file(str(caminho), BUCKET_BRONZE, chave)
 
    if not ja_existia:
        return "novo"
 
    # Se chegou aqui, é atualização (tamanho mudou). Limpa os resquícios velhos.
    try:
        minio_client.delete_object(Bucket=BUCKET_SILVER, Key=chave_silver)
    except Exception:
        pass
        
    if limpar_derivados:
        limpar_derivados(caminho.stem, tipo)
    return "atualizado"
 
def limpar_chunks_no_qdrant(fonte: str, tipo_midia: str):
    """Apaga do Qdrant os chunks de um arquivo que foi substituído."""
    try:
        from app.core.qdrant_utils import delete_by_fonte, get_qdrant_client
 
        delete_by_fonte(get_qdrant_client(), fonte, tipo_midia)
    except Exception as exc:
        print(f"[watcher] AVISO: não consegui limpar os chunks antigos de '{fonte}' no Qdrant ({exc}).")
        print("[watcher]        Rode 'python data_pipeline/chunking_indexing.py --force' para corrigir.")
 
 
# ----------------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------------
def _rodar_script(nome_script: str) -> bool:
    print(f"\n[watcher] >>> {nome_script}")
    # Cada etapa roda num processo separado: ao terminar, a memória (modelos, Whisper)
    # é devolvida ao sistema, o que importa num Mac de 8GB.
    resultado = subprocess.run([sys.executable, str(PROJECT_ROOT / "data_pipeline" / nome_script)], cwd=PROJECT_ROOT)
    if resultado.returncode != 0:
        print(f"[watcher] AVISO: {nome_script} terminou com erro (código {resultado.returncode}). Veja as mensagens acima.")
    return resultado.returncode == 0
 
 
def avisar_api():
    try:
        resposta = requests.post(f"{_api_url()}/reindexar-bm25", timeout=60)
        resposta.raise_for_status()
        print(f"[watcher] API atualizada: {resposta.json().get('chunks_indexados', '?')} trechos no índice.")
    except requests.exceptions.RequestException:
        print("[watcher] A API não respondeu (está fora do ar?). Sem problema: ela monta o índice sozinha quando subir.")
 
 
def executar_pipeline(tem_pdf: bool = True, tem_video: bool = True):
    if tem_pdf:
        _rodar_script("extract_pdfs.py")
    if tem_video:
        _rodar_script("transcribe_videos.py")
    _rodar_script("chunking_indexing.py")
    avisar_api()
 
def processar_lote(arquivos: list, minio_client, executar=executar_pipeline, limpar=limpar_chunks_no_qdrant, forcar_pipeline=False) -> dict:
    """Envia os arquivos ao bronze e, se algo mudou ou falta no silver, roda o pipeline."""
    resumo = {"novo": 0, "atualizado": 0, "falta_silver": 0, "igual": 0, "erro": 0}
    tem_pdf = tem_video = False
 
    for caminho in arquivos:
        try:
            status = enviar_para_bronze(minio_client, caminho, limpar)
        except Exception as exc:
            resumo["erro"] += 1
            print(f"[watcher] ERRO ao processar '{caminho.name}': {exc}")
            continue
 
        resumo[status] += 1
        print(f"[watcher] {caminho.name}: {status}")
        
        # O pipeline roda se for arquivo novo, atualizado OU se faltar no silver
        if status in ("novo", "atualizado", "falta_silver"):
            if caminho.suffix.lower() == ".pdf":
                tem_pdf = True
            else:
                tem_video = True
 
    if forcar_pipeline:
        executar(True, True)
    elif tem_pdf or tem_video:
        executar(tem_pdf, tem_video)
    return resumo
 
 
# ----------------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------------
def varrer_pasta(pasta: Path) -> list:
    """Lista PDFs e MP4 da pasta (e subpastas), sem repetir nomes de arquivo."""
    candidatos = sorted(p for p in pasta.rglob("*") if p.is_file() and arquivo_valido(p))
    vistos, unicos = set(), []
    for caminho in candidatos:
        if caminho.name in vistos:
            print(f"[watcher] AVISO: nome repetido '{caminho.name}' em {caminho.parent}; ignorando esta cópia (use nomes únicos).")
            continue
        vistos.add(caminho.name)
        unicos.append(caminho)
    return unicos
 
 
def main():
    pasta = _pasta_do_acervo()
    if not pasta.exists():
        print(f"[watcher] ERRO: a pasta do acervo não existe: {pasta}")
        print("[watcher] Confira o ACERVO_DIR no .env (e se o SSD está conectado).")
        sys.exit(1)
 
    try:
        minio_client = get_minio_client()
        ensure_buckets_exist(minio_client)
    except Exception as exc:
        print(f"[watcher] ERRO: não consegui falar com o MinIO ({exc}).")
        print("[watcher] Ele está no ar? (docker ps)")
        sys.exit(1)
 
    print(f"[watcher] Pasta do acervo: {pasta}")
    print("[watcher] Sincronização inicial...")
    processar_lote(varrer_pasta(pasta), minio_client, forcar_pipeline=True)
 
    if "--uma-vez" in sys.argv:
        print("\n[watcher] Sincronização concluída (--uma-vez).")
        return
 
    fila = FilaEstavel(_segundos_estavel())
    classe_observer = PollingObserver if os.getenv("WATCHER_POLLING", "false").lower() == "true" else Observer
    observer = classe_observer()
    observer.schedule(ManipuladorAcervo(fila), str(pasta), recursive=True)
    observer.start()
    print(f"\n[watcher] Vigiando {pasta}. Arquivos novos serão processados sozinhos. (Ctrl+C para sair)")
 
    try:
        while True:
            time.sleep(INTERVALO_VERIFICACAO)
            prontos = fila.prontos()
            if prontos:
                print(f"\n[watcher] {len(prontos)} arquivo(s) novo(s) detectado(s).")
                processar_lote(prontos, minio_client)
                print("\n[watcher] Voltando a vigiar...")
    except KeyboardInterrupt:
        print("\n[watcher] Encerrando...")
    finally:
        observer.stop()
        observer.join()
 
 
if __name__ == "__main__":
    main()
 