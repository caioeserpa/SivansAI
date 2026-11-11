from rank_bm25 import BM25Okapi
 
 
def _tokenize(text: str):
    # Tokenização simples por espaço, em minúsculas. É uma simplificação: não trata
    # plural/singular nem variações de palavra (isso seria "stemming"), mas já funciona
    # bem para achar termos exatos da doutrina.
    return text.lower().split()
 
 
class Bm25Index:
    def __init__(self, doc_ids: list, doc_texts: list, doc_payloads: list):
        self.doc_ids = doc_ids
        self.id_to_payload = dict(zip(doc_ids, doc_payloads))
        
        # Trava de segurança: se não houver documentos (banco vazio), não inicializa o BM25
        if not doc_texts:
            self._bm25 = None
            return

        tokenized_corpus = [_tokenize(text) for text in doc_texts]
        self._bm25 = BM25Okapi(tokenized_corpus)
 
    @property
    def size(self) -> int:
        return len(self.doc_ids)
 
    def top_k_ids(self, query: str, k: int = 20):
        """Retorna os IDs dos k documentos com maior score BM25 para a query."""
        # Se o índice BM25 não foi inicializado (banco vazio), retorna lista vazia
        if self._bm25 is None:
            return []

        tokenized_query = _tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)
 
        ranked_positions = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [self.doc_ids[i] for i in ranked_positions]
 
    @classmethod
    def from_qdrant_points(cls, points):
        """Constrói o índice a partir dos pontos retornados por qdrant_utils.scroll_all_points."""
        doc_ids = [p.id for p in points]
        doc_texts = [p.payload.get("texto", "") for p in points]
        doc_payloads = [p.payload for p in points]
        return cls(doc_ids, doc_texts, doc_payloads)
 