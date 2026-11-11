import os
from typing import Optional
 
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
 
from app.core import historico
from app.core.rag_engine import RagEngine
 
router = APIRouter()
 
historico.init_db()
rag_engine = RagEngine()
 
REFORMULAR_PERGUNTAS = os.getenv("REFORMULAR_PERGUNTAS", "true").lower() == "true"
TROCAS_PARA_REFORMULAR = int(os.getenv("TROCAS_PARA_REFORMULAR", "3"))
 
 
class ChatRequest(BaseModel):
    pergunta: str = Field(min_length=1)
    conversa_id: Optional[str] = Field(default=None, max_length=100)
 
 
class ChatResponse(BaseModel):
    resposta: str
    fontes: list[str]
    contextos: list[str]
    conversa_id: Optional[str] = None
    pergunta_reescrita: Optional[str] = None  # só preenchido se a pergunta foi reformulada
    historico_salvo: Optional[bool] = None  # None = sem conversa_id (nada a salvar)
 
 
@router.get("/health")
def health():
    return {
        "status": "ok",
        "chunks_indexados": rag_engine.bm25_index.size,
        "termos_no_glossario": len(rag_engine.glossario),
        "conversas_salvas": len(historico.listar_conversas()),
    }
 
 
@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    pergunta_busca = request.pergunta
    pergunta_reescrita = None
 
    if request.conversa_id and REFORMULAR_PERGUNTAS:
        trocas = historico.ultimas_trocas(request.conversa_id, n=TROCAS_PARA_REFORMULAR)
        if trocas:
            candidata = rag_engine.reformular_pergunta(request.pergunta, trocas)
            if candidata != request.pergunta:
                pergunta_busca = candidata
                pergunta_reescrita = candidata
 
    try:
        resposta, chunks_usados = rag_engine.answer_question(pergunta_busca)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta: {exc}")
 
    fontes = []
    contextos = []
    for chunk in chunks_usados:
        contextos.append((chunk.get("texto") or "")[:2500])
        if chunk.get("tipo_midia") == "video":
            fontes.append(f"Vídeo {chunk.get('fonte')} — Minuto {chunk.get('timestamp_inicio')}")
        else:
            fontes.append(f"{chunk.get('fonte')} — Seção: {chunk.get('secao', '—')}")
 
    historico_salvo = None
    if request.conversa_id:
        try:
            # Grava a pergunta ORIGINAL do usuário (não a reescrita), como ele digitou.
            historico.salvar_troca(request.conversa_id, request.pergunta, resposta, fontes)
            historico_salvo = True
        except Exception as exc:
            # Não joga fora uma resposta que levou tempo para gerar: devolve e avisa.
            print(f"[endpoints] ERRO ao salvar histórico: {exc}")
            historico_salvo = False
 
    return ChatResponse(
        resposta=resposta,
        fontes=fontes,
        contextos=contextos,
        conversa_id=request.conversa_id,
        pergunta_reescrita=pergunta_reescrita,
        historico_salvo=historico_salvo,
    )
 
 
@router.get("/conversas")
def listar_conversas():
    return historico.listar_conversas()
 
 
@router.get("/conversas/{conversa_id}")
def obter_conversa(conversa_id: str):
    conversa = historico.obter_conversa(conversa_id)
    if conversa is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return conversa
 
 
@router.delete("/conversas/{conversa_id}")
def apagar_conversa(conversa_id: str):
    if not historico.apagar_conversa(conversa_id):
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return {"status": "ok"}
 
 
@router.post("/reindexar-bm25")
def reindexar_bm25():
    rag_engine.reload_bm25_index()
    return {"status": "ok", "chunks_indexados": rag_engine.bm25_index.size}
 
 
@router.post("/recarregar-glossario")
def recarregar_glossario():
    """Chame depois de editar data_pipeline/glossario.json."""
    rag_engine.reload_glossario()
    return {"status": "ok", "termos_no_glossario": len(rag_engine.glossario)}