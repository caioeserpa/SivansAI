import os
 
import requests
 
from app.core.bm25_index import Bm25Index
from app.core.embeddings import embed_query
from app.core.glossario import expand_query, load_glossario
from app.core.qdrant_utils import ensure_collection, get_qdrant_client, scroll_all_points, vector_search
from app.core.reranker import rerank
 
TOP_K_CANDIDATES = int(os.getenv("TOP_K_RETRIEVE", "20"))
TOP_K_FINAL = int(os.getenv("TOP_K_RERANK", "4"))
RRF_K = 60  # constante padrão usada em Reciprocal Rank Fusion
 
SYSTEM_PROMPT_TEMPLATE = """Você é um assistente especialista, analítico e altamente respeitoso encarregado de
sanar dúvidas sobre a doutrina, rituais e história do Vale do Amanhecer.
Sua resposta deve ser estritamente baseada nos trechos de contexto fornecidos abaixo.
 
Diretrizes Operacionais:
1. Se a resposta não puder ser extraída do contexto fornecido, responda rigorosamente:
   "Infelizmente, não localizei essa informação nos documentos oficiais disponíveis no acervo atual."
2. Não tente inventar fatos, especular ou extrapolar dados fora do contexto.
3. Para cada afirmação feita, cite explicitamente a fonte correspondente contida nas
   tags de metadados do contexto (Ex: [Fonte: Livro de Leis, Pág. 45] ou [Fonte: Vídeo Trinos, Minuto 12:34]).
---
CONTEXTO RECUPERADO:
{context_str}
---
PERGUNTA DO USUÁRIO: {query_str}
RESPOSTA DO ASSISTENTE:"""
 
 
PROMPT_REFORMULAR = """Você reescreve perguntas de acompanhamento para que fiquem compreensíveis sozinhas, sem depender da conversa anterior.
 
Conversa anterior:
{historico}
 
Nova pergunta: {pergunta}
 
Reescreva a nova pergunta de forma completa e independente, em português, preservando o sentido. Se ela já for compreensível sozinha, repita-a sem alterações. Responda APENAS com a pergunta reescrita, sem explicações."""
 
TAMANHO_MAX_PERGUNTA_REESCRITA = 400
 
 
class RagEngine:
    def __init__(self):
        self.qdrant_client = get_qdrant_client()
        ensure_collection(self.qdrant_client)
        self.bm25_index = self._build_bm25_index()
        self.glossario = load_glossario()
        print(f"[rag_engine] Glossário carregado com {len(self.glossario)} termo(s).")
 
    def _build_bm25_index(self) -> Bm25Index:
        points = scroll_all_points(self.qdrant_client)
        print(f"[rag_engine] Índice BM25 construído com {len(points)} chunks.")
        return Bm25Index.from_qdrant_points(points)
 
    def reload_bm25_index(self):
        """Chame isso depois de rodar chunking_indexing.py de novo, sem reiniciar a API."""
        self.bm25_index = self._build_bm25_index()
 
    def reload_glossario(self):
        """Chame isso depois de editar data_pipeline/glossario.json, sem reiniciar a API."""
        self.glossario = load_glossario()
        print(f"[rag_engine] Glossário recarregado com {len(self.glossario)} termo(s).")
 
    def hybrid_search(self, query: str) -> list:
        query_vector = embed_query(query)  # busca vetorial usa a pergunta ORIGINAL
        vector_hits = vector_search(self.qdrant_client, query_vector, top_k=TOP_K_CANDIDATES)
 
        query_expandida = expand_query(query, self.glossario)  # BM25 usa a versão EXPANDIDA
        bm25_ids = self.bm25_index.top_k_ids(query_expandida, k=TOP_K_CANDIDATES)
 
        fused_scores = {}
        payload_by_id = {}
 
        for rank, hit in enumerate(vector_hits):
            fused_scores[hit.id] = fused_scores.get(hit.id, 0.0) + 1.0 / (RRF_K + rank + 1)
            payload_by_id[hit.id] = hit.payload
 
        for rank, doc_id in enumerate(bm25_ids):
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)
            if doc_id not in payload_by_id:
                payload_by_id[doc_id] = self.bm25_index.id_to_payload.get(doc_id, {})
 
        ranked_ids = sorted(fused_scores, key=lambda doc_id: fused_scores[doc_id], reverse=True)
        candidates = [payload_by_id[doc_id] for doc_id in ranked_ids[:TOP_K_CANDIDATES]]
 
        return rerank(query, candidates, top_k=TOP_K_FINAL)
 
    @staticmethod
    def build_context_string(chunks: list) -> str:
        parts = []
        for chunk in chunks:
            if chunk.get("tipo_midia") == "video":
                fonte = f"[Fonte: Vídeo {chunk.get('fonte')}, Minuto {chunk.get('timestamp_inicio')}]"
            else:
                fonte = f"[Fonte: {chunk.get('fonte')}, Seção: {chunk.get('secao', '—')}]"
            texto = (chunk.get("texto") or "")[:2500]
            parts.append(f"{fonte}\n{texto}")
        return "\n\n".join(parts)
 
    @staticmethod
    def call_ollama(prompt: str, num_predict: int = None) -> str:
        import time

        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()
        host = (os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).strip().rstrip("/").replace("localhost", "127.0.0.1")

        options = {
            "temperature": 0.1,  # baixa, para priorizar fidelidade ao contexto
            "num_predict": num_predict or int(os.getenv("OLLAMA_MAX_TOKENS", "400")),
            "num_ctx": 4096,
            "repeat_penalty": 1.15,
        }

        last_exc = None
        for attempt in range(1, 4):
            try:
                response = requests.post(
                    f"{host}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": options,
                    },
                    timeout=300,
                )
                if not response.ok:
                    print(f"[rag_engine] Ollama HTTP {response.status_code}: {response.text}")
                response.raise_for_status()
                return response.json()["response"]
            except Exception as exc:
                last_exc = exc
                print(f"[rag_engine] Tentativa {attempt}/3 no Ollama falhou: {exc}")
                if attempt < 3:
                    time.sleep(3)
        raise last_exc
 
    def reformular_pergunta(self, pergunta: str, trocas_anteriores: list) -> str:
        """
        Transforma uma pergunta de acompanhamento ("e a cor?") numa pergunta completa,
        usando as últimas trocas da conversa. Se algo der errado (resposta vazia, longa
        demais, Ollama falhou), devolve a pergunta ORIGINAL — a conversa nunca quebra
        por causa dessa etapa.
        """
        if not trocas_anteriores:
            return pergunta
 
        linhas = []
        for troca in trocas_anteriores:
            linhas.append(f"Usuário: {troca['pergunta']}")
            linhas.append(f"Assistente: {troca['resposta'][:300]}")
        prompt = PROMPT_REFORMULAR.format(historico="\n".join(linhas), pergunta=pergunta)
 
        try:
            bruta = self.call_ollama(prompt, num_predict=100)
        except Exception as exc:
            print(f"[rag_engine] Reformulação falhou ({exc}); usando a pergunta original.")
            return pergunta
 
        linhas_resposta = [linha.strip() for linha in bruta.strip().splitlines() if linha.strip()]
        if not linhas_resposta:
            return pergunta
        reescrita = linhas_resposta[0].strip().strip('"').strip("“”").strip()
 
        if not reescrita or len(reescrita) > TAMANHO_MAX_PERGUNTA_REESCRITA:
            return pergunta
        return reescrita
 
    def answer_question(self, query: str):
        top_chunks = self.hybrid_search(query)
        context_str = self.build_context_string(top_chunks)
        prompt = SYSTEM_PROMPT_TEMPLATE.format(context_str=context_str, query_str=query)
        resposta = self.call_ollama(prompt)
        return resposta, top_chunks
 