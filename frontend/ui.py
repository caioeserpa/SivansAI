import os
import uuid
 
import requests
import streamlit as st
 
try:
    from dotenv import load_dotenv
 
    load_dotenv()
except ImportError:
    pass
 
API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_CHAT = 300  # modelo local em CPU pode demorar; melhor esperar do que dar erro cedo
TIMEOUT_CURTO = 5
 
st.set_page_config(page_title="SivansAI", page_icon="📚", layout="centered")
 
 
# ----------------------------------------------------------------------------------
# Estado da sessão
# ----------------------------------------------------------------------------------
def _novo_id() -> str:
    return str(uuid.uuid4())
 
 
if "conversa_id" not in st.session_state:
    st.session_state.conversa_id = _novo_id()
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "aviso" not in st.session_state:
    st.session_state.aviso = None
if "confirmando_exclusao" not in st.session_state:
    st.session_state.confirmando_exclusao = False
 
 
# ----------------------------------------------------------------------------------
# Chamadas à API
# ----------------------------------------------------------------------------------
def api_saude():
    """Devolve o JSON do /health, ou None se a API não respondeu."""
    try:
        resposta = requests.get(f"{API_URL}/health", timeout=TIMEOUT_CURTO)
        resposta.raise_for_status()
        return resposta.json()
    except requests.exceptions.RequestException:
        return None
 
 
def api_listar_conversas() -> list:
    try:
        resposta = requests.get(f"{API_URL}/conversas", timeout=TIMEOUT_CURTO)
        resposta.raise_for_status()
        return resposta.json()
    except requests.exceptions.RequestException:
        return []
 
 
# ----------------------------------------------------------------------------------
# Ações dos botões (callbacks rodam antes da próxima renderização)
# ----------------------------------------------------------------------------------
def nova_conversa():
    st.session_state.conversa_id = _novo_id()
    st.session_state.mensagens = []
    st.session_state.aviso = None
    st.session_state.confirmando_exclusao = False
 
 
def abrir_conversa(conversa_id: str):
    try:
        resposta = requests.get(f"{API_URL}/conversas/{conversa_id}", timeout=TIMEOUT_CURTO)
        resposta.raise_for_status()
        dados = resposta.json()
    except requests.exceptions.RequestException:
        st.session_state.aviso = "Não consegui abrir essa conversa. A API está no ar?"
        return
 
    st.session_state.conversa_id = conversa_id
    st.session_state.mensagens = [
        {
            "papel": m["papel"],
            "conteudo": m["conteudo"],
            "fontes": m.get("fontes", []),
            "pergunta_reescrita": None,
            "historico_salvo": True,
        }
        for m in dados["mensagens"]
    ]
    st.session_state.aviso = None
    st.session_state.confirmando_exclusao = False
 
 
def pedir_confirmacao_exclusao():
    st.session_state.confirmando_exclusao = True
 
 
def cancelar_exclusao():
    st.session_state.confirmando_exclusao = False
 
 
def apagar_conversa_atual():
    try:
        resposta = requests.delete(f"{API_URL}/conversas/{st.session_state.conversa_id}", timeout=TIMEOUT_CURTO)
        resposta.raise_for_status()
    except requests.exceptions.RequestException:
        st.session_state.aviso = "Não consegui apagar a conversa. A API está no ar?"
        st.session_state.confirmando_exclusao = False
        return
    nova_conversa()
 
 
# ----------------------------------------------------------------------------------
# Barra lateral
# ----------------------------------------------------------------------------------
saude = api_saude()
conversas = api_listar_conversas() if saude else []
 
with st.sidebar:
    st.header("Conversas")
    st.button("➕ Nova conversa", on_click=nova_conversa, use_container_width=True)
 
    if saude:
        st.caption(f"API conectada · {saude.get('chunks_indexados', '?')} trechos no acervo")
    else:
        st.error("API offline. Suba com: uvicorn app.main:app")
 
    ids_salvos = {c["id"] for c in conversas}
    if st.session_state.conversa_id in ids_salvos:
        if st.session_state.confirmando_exclusao:
            st.warning("Apagar esta conversa? Não dá para desfazer.")
            col1, col2 = st.columns(2)
            col1.button("Apagar", on_click=apagar_conversa_atual, type="primary", use_container_width=True)
            col2.button("Cancelar", on_click=cancelar_exclusao, use_container_width=True)
        else:
            st.button("🗑 Apagar conversa atual", on_click=pedir_confirmacao_exclusao, use_container_width=True)
 
    st.divider()
    if conversas:
        for conversa in conversas:
            atual = conversa["id"] == st.session_state.conversa_id
            rotulo = ("▶ " if atual else "") + conversa["titulo"]
            st.button(
                rotulo,
                key=f"conv_{conversa['id']}",
                on_click=abrir_conversa,
                args=(conversa["id"],),
                use_container_width=True,
            )
    elif saude:
        st.caption("Nenhuma conversa salva ainda.")
 
 
# ----------------------------------------------------------------------------------
# Área principal
# ----------------------------------------------------------------------------------
st.title("SivansAI")
st.caption(
    "Pergunte sobre a doutrina Vale do Amanhecer, os rituais e a história. As respostas vêm apenas dos "
    "documentos e vídeos do acervo, sempre com a fonte citada."
)
 
if st.session_state.aviso:
    st.warning(st.session_state.aviso)
 
PAPEL_STREAMLIT = {"usuario": "user", "assistente": "assistant"}
 
for mensagem in st.session_state.mensagens:
    with st.chat_message(PAPEL_STREAMLIT[mensagem["papel"]]):
        st.markdown(mensagem["conteudo"])
 
        if mensagem["papel"] != "assistente":
            continue
        if mensagem.get("pergunta_reescrita"):
            st.caption(f"Pergunta interpretada como: {mensagem['pergunta_reescrita']}")
        fontes = list(dict.fromkeys(mensagem.get("fontes", [])))  # sem repetidas, na mesma ordem
        if fontes:
            with st.expander(f"Fontes ({len(fontes)})"):
                for fonte in fontes:
                    st.markdown(f"- {fonte}")
        if mensagem.get("historico_salvo") is False:
            st.caption("⚠️ Esta troca não foi salva no histórico.")
 
pergunta = st.chat_input("Pergunte sobre o acervo...")
 
if pergunta:
    st.session_state.aviso = None
    with st.chat_message("user"):
        st.markdown(pergunta)
 
    dados = None
    with st.chat_message("assistant"):
        with st.spinner("Buscando no acervo e gerando a resposta. Pode levar alguns segundos..."):
            try:
                resposta_http = requests.post(
                    f"{API_URL}/chat",
                    json={"pergunta": pergunta, "conversa_id": st.session_state.conversa_id},
                    timeout=TIMEOUT_CHAT,
                )
                resposta_http.raise_for_status()
                dados = resposta_http.json()
            except requests.exceptions.ConnectionError:
                st.error("Não consegui falar com a API. Ela está rodando? (uvicorn app.main:app)")
            except requests.exceptions.Timeout:
                st.error("A resposta demorou demais e foi interrompida. Tente de novo ou use uma pergunta mais curta.")
            except requests.exceptions.RequestException as exc:
                st.error(f"A API devolveu um erro ao processar a pergunta: {exc}")
 
    # Só entra no histórico da tela se a API respondeu; em caso de erro, a pergunta
    # não fica "pendurada" sem resposta.
    if dados is not None:
        st.session_state.mensagens.append(
            {"papel": "usuario", "conteudo": pergunta, "fontes": [], "pergunta_reescrita": None, "historico_salvo": True}
        )
        st.session_state.mensagens.append(
            {
                "papel": "assistente",
                "conteudo": dados["resposta"],
                "fontes": dados.get("fontes", []),
                "pergunta_reescrita": dados.get("pergunta_reescrita"),
                "historico_salvo": dados.get("historico_salvo"),
            }
        )
        st.rerun()  # redesenha tudo a partir do estado (e atualiza a lista lateral)
 