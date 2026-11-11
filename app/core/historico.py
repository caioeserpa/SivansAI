import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional
 
TAMANHO_MAX_TITULO = 60
 
 
def _db_path() -> str:
    return os.getenv("HISTORICO_DB_PATH", "historico.db")
 
 
@contextmanager
def _conexao():
    # Uma conexão por operação: simples e seguro, já que o FastAPI atende requisições
    # em várias threads e uma conexão SQLite não deve ser compartilhada entre elas.
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
 
 
def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
 
 
def init_db():
    """Cria as tabelas se ainda não existirem. Pode ser chamada quantas vezes quiser."""
    with _conexao() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversas (
                id TEXT PRIMARY KEY,
                titulo TEXT NOT NULL,
                criada_em TEXT NOT NULL,
                atualizada_em TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversa_id TEXT NOT NULL REFERENCES conversas(id) ON DELETE CASCADE,
                papel TEXT NOT NULL CHECK (papel IN ('usuario', 'assistente')),
                conteudo TEXT NOT NULL,
                fontes TEXT NOT NULL DEFAULT '[]',
                criada_em TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mensagens_conversa ON mensagens(conversa_id, id);
            """
        )
 
 
def _titulo_a_partir_da_pergunta(pergunta: str) -> str:
    titulo = " ".join(pergunta.split())
    if len(titulo) > TAMANHO_MAX_TITULO:
        titulo = titulo[: TAMANHO_MAX_TITULO - 1].rstrip() + "…"
    return titulo or "Nova conversa"
 
 
def salvar_troca(conversa_id: str, pergunta: str, resposta: str, fontes: list):
    """Grava a pergunta e a resposta. Cria a conversa se ela ainda não existir."""
    agora = _agora()
    with _conexao() as conn:
        existe = conn.execute("SELECT 1 FROM conversas WHERE id = ?", (conversa_id,)).fetchone()
        if not existe:
            conn.execute(
                "INSERT INTO conversas (id, titulo, criada_em, atualizada_em) VALUES (?, ?, ?, ?)",
                (conversa_id, _titulo_a_partir_da_pergunta(pergunta), agora, agora),
            )
        conn.execute(
            "INSERT INTO mensagens (conversa_id, papel, conteudo, fontes, criada_em) VALUES (?, 'usuario', ?, '[]', ?)",
            (conversa_id, pergunta, agora),
        )
        conn.execute(
            "INSERT INTO mensagens (conversa_id, papel, conteudo, fontes, criada_em) VALUES (?, 'assistente', ?, ?, ?)",
            (conversa_id, resposta, json.dumps(fontes, ensure_ascii=False), agora),
        )
        conn.execute("UPDATE conversas SET atualizada_em = ? WHERE id = ?", (agora, conversa_id))
 
 
def ultimas_trocas(conversa_id: str, n: int = 3) -> list:
    """Devolve as últimas n trocas (pergunta + resposta), da mais antiga para a mais recente."""
    with _conexao() as conn:
        linhas = conn.execute(
            "SELECT papel, conteudo FROM mensagens WHERE conversa_id = ? ORDER BY id DESC LIMIT ?",
            (conversa_id, n * 2),
        ).fetchall()
 
    linhas = list(reversed(linhas))
    trocas = []
    for i in range(0, len(linhas) - 1, 2):
        if linhas[i]["papel"] == "usuario" and linhas[i + 1]["papel"] == "assistente":
            trocas.append({"pergunta": linhas[i]["conteudo"], "resposta": linhas[i + 1]["conteudo"]})
    return trocas
 
 
def listar_conversas() -> list:
    """Conversas da mais recente para a mais antiga."""
    with _conexao() as conn:
        linhas = conn.execute(
            "SELECT id, titulo, criada_em, atualizada_em FROM conversas ORDER BY atualizada_em DESC, rowid DESC"
        ).fetchall()
    return [dict(linha) for linha in linhas]
 
 
def obter_conversa(conversa_id: str) -> Optional[dict]:
    """Devolve a conversa com todas as mensagens, ou None se não existir."""
    with _conexao() as conn:
        conversa = conn.execute(
            "SELECT id, titulo, criada_em, atualizada_em FROM conversas WHERE id = ?", (conversa_id,)
        ).fetchone()
        if conversa is None:
            return None
        mensagens = conn.execute(
            "SELECT papel, conteudo, fontes, criada_em FROM mensagens WHERE conversa_id = ? ORDER BY id",
            (conversa_id,),
        ).fetchall()
 
    resultado = dict(conversa)
    resultado["mensagens"] = [
        {
            "papel": m["papel"],
            "conteudo": m["conteudo"],
            "fontes": json.loads(m["fontes"]),
            "criada_em": m["criada_em"],
        }
        for m in mensagens
    ]
    return resultado
 
 
def apagar_conversa(conversa_id: str) -> bool:
    """Apaga a conversa e suas mensagens. Retorna False se ela não existia."""
    with _conexao() as conn:
        cursor = conn.execute("DELETE FROM conversas WHERE id = ?", (conversa_id,))
        return cursor.rowcount > 0