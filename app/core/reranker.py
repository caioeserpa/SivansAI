import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_reranker():
    from sentence_transformers import CrossEncoder

    model_name = os.getenv("RERANKER_MODEL", "unicamp-dl/mMiniLM-L6-v2-pt-v2")
    return CrossEncoder(model_name, max_length=512)


def rerank(query: str, candidates: list, top_k: int = 4):
    """
    candidates: lista de dicts, cada um precisa ter a chave 'texto'.
    Retorna os top_k candidatos reordenados por relevância (mais relevante primeiro).
    """
    if not candidates:
        return []

    try:
        reranker = get_reranker()
        pairs = [(query, (c.get("texto") or "")[:2000]) for c in candidates]
        scores = reranker.predict(pairs)

        scored_candidates = list(zip(candidates, scores))
        scored_candidates.sort(key=lambda pair: pair[1], reverse=True)

        return [candidate for candidate, _score in scored_candidates[:top_k]]
    except Exception as exc:
        print(f"[reranker] Aviso: falha no rerank ({exc}). Usando ordem da busca híbrida.")
        return candidates[:top_k]
