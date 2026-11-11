import json
import re
from pathlib import Path
 
_GLOSSARIO_PATH = Path(__file__).resolve().parent.parent.parent / "data_pipeline" / "glossario.json"
 
 
def load_glossario() -> dict:
    """Lê o glossário do disco. Se o arquivo não existir ou estiver vazio, retorna {}
    (o sistema continua funcionando normalmente, só sem a expansão de termos)."""
    if not _GLOSSARIO_PATH.exists() or _GLOSSARIO_PATH.stat().st_size == 0:
        return {}

    try:
        with open(_GLOSSARIO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return {}

    # Ignora chaves de instrução/comentário (começam com "_"), só ficam os termos de verdade.
    return {termo: sinonimos for termo, sinonimos in data.items() if not termo.startswith("_")}
 
 
def expand_query(query: str, glossario: dict) -> str:
    """
    Para cada palavra da query que bater com um termo do glossário (seja o termo
    principal ou um dos sinônimos), adiciona os outros termos relacionados ao final
    da query. Isso aumenta a chance do BM25 encontrar um chunk que usa uma variação
    diferente da mesma palavra.
    """
    if not glossario:
        return query
 
    # Remove pontuação antes de comparar (ex: "Doutrinador?" precisa bater com "doutrinador").
    palavras_da_query = re.findall(r"\w+", query.lower())
    termos_para_adicionar = set()
 
    for termo_principal, sinonimos in glossario.items():
        grupo_completo = [termo_principal.lower()] + [s.lower() for s in sinonimos]
 
        # Se QUALQUER palavra do grupo apareceu na pergunta, adiciona o resto do grupo.
        if any(palavra in grupo_completo for palavra in palavras_da_query):
            termos_para_adicionar.update(grupo_completo)
 
    if not termos_para_adicionar:
        return query
 
    return query + " " + " ".join(sorted(termos_para_adicionar))