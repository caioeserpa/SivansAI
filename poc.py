#deve ler op pdf e o txt com llama index
#deve usar um modelo de embedding via huggingface para indexar os textos no chroma db
# deve conectar o llama index ao ollma como LLM
# faz uma pergunta teste e imprime a resposta
 
#por fim, devemos rodar o arquivo no terminal, se a resposta fizer sentido e citar o conteúdo certo está certa a arquitetura.
 
import os
import shutil
import chromadb
import logging 
import warnings

from dotenv import load_dotenv

from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    Settings,
)
 
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.ollama import Ollama
from llama_index.readers.file import PyMuPDFReader
 
 
# Oculta barras de progresso e avisos de depreciação
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"
warnings.filterwarnings("ignore")

# Silencia logs informativos de bibliotecas externas
logging.basicConfig(level=logging.ERROR)
for logger_name in ["httpx", "httpcore", "huggingface_hub", "sentence_transformers", "llama_index"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

 
PERGUNTA_TESTE = "Do que se trata o acervo carregado nesses documentos? Responda em português, de forma resumida, e cite os documentos que serviram de base para a resposta."

#PARAM Usado para resetar índice do chromadb
RESET_INDICE = False
 
# Variables de configuração carregadas do .env com fallbacks seguros

load_dotenv()
DATA_DIR = os.getenv("DATA_DIR")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
CHROMA_DIR = os.getenv("CHROMA_DIR")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME")

 
def montar_indice():
    # 1. Leitura dos documentos em PDF e TXT ----------------------------
    print(f"[1/4] Lendo documentos do diretório {DATA_DIR}...")
    documentos = SimpleDirectoryReader(
        input_dir=DATA_DIR,
        required_exts=[".pdf", ".txt"],
        file_extractor={".pdf": PyMuPDFReader()},
        recursive=True,
    ).load_data()
    print(f"    -> {len(documentos)} documento(s) carregado(s).")
 
    # 2. Modelo de embedding via HuggingFace -----------------------------
    print(f"[2/4] Criando embeddings com o modelo {EMBED_MODEL_NAME}...")
    # query_instruction/text_instruction: modelos da família E5 esperam
    # esses prefixos para gerar embeddings de melhor qualidade.
    embed_model = HuggingFaceEmbedding(
        model_name=EMBED_MODEL_NAME,
        query_instruction="query: ",
        text_instruction="passage: ",
    )
 
    # 3. LLM via Ollama ---------------------------------------------------
    print(f"[3/4] Conectando ao modelo LLM {OLLAMA_MODEL} via Ollama...")
    llm = Ollama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        request_timeout=600,
    )
 
    # Define os padrões globais do LlamaIndex
    Settings.embed_model = embed_model
    Settings.llm = llm
 
    # 4. ChromaDB como vector store, persistente em disco -----------------
    print(f"[4/4] Criando o índice com ChromaDB no diretório {CHROMA_DIR}...")
 
    if RESET_INDICE and os.path.isdir(CHROMA_DIR):
        print(f"    -> RESET_INDICE=True: apagando índice antigo em {CHROMA_DIR}")
        shutil.rmtree(CHROMA_DIR)
 
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME
    )
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
 
    index = VectorStoreIndex.from_documents(
        documentos,
        storage_context=storage_context,
    )
    return index
 
 
def main():
    if not os.path.isdir(DATA_DIR):
        raise FileNotFoundError(
            f"Diretório {DATA_DIR} não encontrado. "
            "Certifique-se de que os documentos estão no local correto."
        )
 
    index = montar_indice()
 
    print("\n=== Pergunta teste ===")
    print(f"Pergunta: {PERGUNTA_TESTE}")
 
    query_engine = index.as_query_engine(similarity_top_k=5)
    resposta = query_engine.query(PERGUNTA_TESTE)
 
    print(f"Resposta: {resposta.response}")
 
    print("\n=== Fontes citadas ===")
    for i, node in enumerate(resposta.source_nodes, start=1):
        origem = node.node.metadata.get("file_name", "Unknown File")
        trecho = node.node.get_content()[:200].replace("\n", " ")
        print(f"    {i}. Origem - {origem}: \n\nTrecho - {trecho}...")
 
 
if __name__ == "__main__":
    main()
 