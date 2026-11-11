from dotenv import load_dotenv
 
load_dotenv()
 
from fastapi import FastAPI
 
from app.api.endpoints import router
 
app = FastAPI(
    title="RAG — Acervo Vale do Amanhecer",
    description="API de perguntas e respostas sobre o acervo, com busca híbrida e citação de fontes.",
    version="0.5.0", 
)
 
app.include_router(router)
 