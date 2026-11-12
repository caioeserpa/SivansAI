import os
import re
import uuid
import requests
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_CHAT = 300
TIMEOUT_CURTO = 5

st.set_page_config(
    page_title="SivansAI · Estudo da Doutrina",
    page_icon="☀️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------------
# Função utilitária para renderizar HTML/SVG sem risco de bloco de código no Markdown
# ----------------------------------------------------------------------------------
def render_html(html_str: str):
    """
    Remove quebras de linha com espaços em branco e comentários para que o
    CommonMark do Streamlit nunca confunda o HTML com bloco de código (indented code block).
    """
    sem_comentarios = re.sub(r"<!--.*?-->", "", html_str, flags=re.DOTALL)
    linhas_limpas = [linha.strip() for linha in sem_comentarios.splitlines() if linha.strip()]
    st.markdown("".join(linhas_limpas), unsafe_allow_html=True)


# ----------------------------------------------------------------------------------
# Identidade Visual, Tipografia e Paleta Sagrada
# Cores Oficiais:
#   - Azul Índigo Profundo: #11254A (Base institucional, textos, céu noturno)
#   - Amarelo Solar:        #F2B705 (Luz do amanhecer, destaque primário)
#   - Laranja Amanhecer:    #E87A1E (Calor, raios solares, saudação)
#   - Verde Matas:          #1B6B46 (Cura, natureza, badges PDF)
#   - Roxo Místico:         #4A2574 (Transmutação, lua, badges Vídeo)
#   - Vermelho Carmim:      #C1272D (Força, fitas e bordados)
#   - Creme Pergaminho:     #EAE6DF (Fundo neutro, papelaria)
# ----------------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Cormorant+Garamond:ital,wght@0,600;0,700;1,600&family=Lora:ital,wght@0,500;0,600;1,500&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

:root {
    --azul-indigo: #11254A;
    --amarelo-solar: #F2B705;
    --laranja-sol: #E87A1E;
    --verde-matas: #1B6B46;
    --roxo-mistico: #4A2574;
    --vermelho-carmim: #C1272D;
    --creme-pergaminho: #EAE6DF;
    --creme-fundo: #F5F2EB;
    --creme-card: #FFFFFF;
    --borda-suave: #D8D2C5;
}

/* Fundo Geral da Aplicação */
.stApp {
    background-color: var(--creme-fundo) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
    color: var(--azul-indigo) !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

/* ------------------------------------------------------------------ */
/* BARRA LATERAL (SIDEBAR)                                            */
/* ------------------------------------------------------------------ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0c1a35 0%, var(--azul-indigo) 55%, #131e33 100%) !important;
    border-right: 2px solid rgba(242, 183, 5, 0.3) !important;
}

[data-testid="stSidebar"] h1, 
[data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3 {
    font-family: 'Cinzel', serif !important;
    color: var(--amarelo-solar) !important;
    letter-spacing: 1.5px !important;
}

[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {
    color: #E6E1D8 !important;
}

[data-testid="stSidebar"] hr {
    border-color: rgba(242, 183, 5, 0.25) !important;
}

/* Botões na Barra Lateral */
[data-testid="stSidebar"] .stButton > button {
    background-color: rgba(255, 255, 255, 0.06) !important;
    color: #F8F6F1 !important;
    border: 1px solid rgba(242, 183, 5, 0.32) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    text-align: left !important;
    transition: all 0.2s ease-in-out !important;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: linear-gradient(135deg, rgba(232, 122, 30, 0.35), rgba(242, 183, 5, 0.25)) !important;
    border-color: var(--amarelo-solar) !important;
    color: #FFFFFF !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(242, 183, 5, 0.18) !important;
}

/* Botão de Destaque 'Nova Conversa' */
.btn-nova-conversa button {
    background: linear-gradient(135deg, var(--laranja-sol) 0%, var(--amarelo-solar) 100%) !important;
    color: var(--azul-indigo) !important;
    border: none !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(232, 122, 30, 0.4) !important;
}

.btn-nova-conversa button:hover {
    background: linear-gradient(135deg, #d36810 0%, #e2a400 100%) !important;
    color: #07101e !important;
    box-shadow: 0 6px 18px rgba(232, 122, 30, 0.55) !important;
}

/* ------------------------------------------------------------------ */
/* CONTEÚDO PRINCIPAL E BOTÕES DE SUGESTÃO                            */
/* ------------------------------------------------------------------ */
.main .stButton > button {
    background-color: #FFFFFF !important;
    color: var(--azul-indigo) !important;
    border: 1.5px solid var(--borda-suave) !important;
    border-left: 4px solid var(--amarelo-solar) !important;
    border-radius: 10px !important;
    padding: 14px 18px !important;
    text-align: left !important;
    box-shadow: 0 2px 8px rgba(17, 37, 74, 0.05) !important;
    transition: all 0.2s ease-in-out !important;
}

.main .stButton > button:hover {
    background-color: #FFFFFF !important;
    border-color: var(--laranja-sol) !important;
    border-left: 4px solid var(--laranja-sol) !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(232, 122, 30, 0.16) !important;
}

.main .stButton > button p,
.main .stButton > button span,
.main .stButton > button strong {
    color: var(--azul-indigo) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

/* Faixa Sagrada Multicor */
.faixa-sagrada {
    display: flex;
    height: 7px;
    width: 100%;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 20px;
    box-shadow: 0 2px 8px rgba(17, 37, 74, 0.12);
}
.faixa-sagrada .cor-1 { flex: 1; background-color: var(--azul-indigo); }
.faixa-sagrada .cor-2 { flex: 1; background-color: var(--amarelo-solar); }
.faixa-sagrada .cor-3 { flex: 1; background-color: var(--laranja-sol); }
.faixa-sagrada .cor-4 { flex: 1; background-color: var(--verde-matas); }
.faixa-sagrada .cor-5 { flex: 1; background-color: var(--vermelho-carmim); }
.faixa-sagrada .cor-6 { flex: 1; background-color: var(--roxo-mistico); }

/* Borda Decorativa Inspirada nos Bordados das Ruanas */
.borda-bordado {
    height: 12px;
    width: 100%;
    background-color: var(--azul-indigo);
    background-image: 
        radial-gradient(var(--amarelo-solar) 18%, transparent 22%),
        radial-gradient(var(--laranja-sol) 14%, transparent 18%);
    background-size: 24px 12px, 24px 12px;
    background-position: 0 0, 12px 6px;
    border-top: 1.5px solid var(--amarelo-solar);
    border-bottom: 1.5px solid var(--laranja-sol);
    border-radius: 3px;
    margin: 16px 0 24px 0;
    opacity: 0.95;
}

/* Cabeçalho Institucional */
.header-templo {
    text-align: center;
    padding: 8px 0 14px 0;
}

.header-titulo {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 2.4rem;
    font-weight: 800;
    color: var(--azul-indigo);
    letter-spacing: -0.5px;
    margin: 10px 0 2px 0;
}

.header-saudacao {
    font-family: 'Lora', 'Cormorant Garamond', serif;
    font-size: 1.45rem;
    font-weight: 600;
    color: var(--laranja-sol);
    letter-spacing: 3.5px;
    margin: 0 0 10px 0;
    text-transform: uppercase;
}

.header-descricao {
    font-size: 0.96rem;
    color: #4A5568;
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.55;
}

/* ------------------------------------------------------------------ */
/* BALÕES DE CHAT                                                     */
/* ------------------------------------------------------------------ */
[data-testid="stChatMessage"] {
    background-color: transparent !important;
    padding: 8px 0 !important;
}

/* Balão do Usuário */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: linear-gradient(135deg, var(--azul-indigo) 0%, #1e3b6e 100%) !important;
    border-radius: 14px 14px 2px 14px !important;
    padding: 14px 18px !important;
    margin: 10px 0 10px auto !important;
    max-width: 86% !important;
    box-shadow: 0 4px 14px rgba(17, 37, 74, 0.16) !important;
    border-left: 3px solid var(--amarelo-solar) !important;
}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) span {
    color: #F8F6F1 !important;
    font-size: 1rem !important;
}

/* Balão do Assistente */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background-color: var(--creme-card) !important;
    border: 1px solid var(--borda-suave) !important;
    border-left: 4px solid var(--laranja-sol) !important;
    border-radius: 14px 14px 14px 2px !important;
    padding: 16px 20px !important;
    margin: 10px 0 !important;
    box-shadow: 0 4px 16px rgba(17, 37, 74, 0.06) !important;
}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) p {
    color: #1F2937 !important;
    line-height: 1.65 !important;
}

/* Badges de Citação de Fontes */
.badge-fonte {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.82rem;
    font-weight: 600;
    margin: 3px 0;
}

.badge-pdf {
    background-color: rgba(27, 107, 70, 0.12);
    color: var(--verde-matas);
    border: 1px solid rgba(27, 107, 70, 0.3);
}

.badge-video {
    background-color: rgba(74, 37, 116, 0.12);
    color: var(--roxo-mistico);
    border: 1px solid rgba(74, 37, 116, 0.3);
}

/* ------------------------------------------------------------------ */
/* ÁREA FIXA DE ENTRADA DO CHAT (RODAPÉ)                              */
/* ------------------------------------------------------------------ */
[data-testid="stBottom"],
[data-testid="stBottom"] > div {
    background-color: var(--creme-fundo) !important;
}

[data-testid="stChatInput"] {
    background-color: #FFFFFF !important;
    border-radius: 12px !important;
    border: 1.5px solid var(--borda-suave) !important;
    box-shadow: 0 4px 16px rgba(17, 37, 74, 0.08) !important;
}

[data-testid="stChatInput"]:focus-within {
    border-color: var(--amarelo-solar) !important;
    box-shadow: 0 0 0 2px rgba(242, 183, 5, 0.35) !important;
}

[data-testid="stChatInput"] textarea {
    color: var(--azul-indigo) !important;
    background-color: #FFFFFF !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #718096 !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------------------------
# Função geradora do Logotipo Vetorial Oficial
# ----------------------------------------------------------------------------------
def get_logo_svg(prefix: str, width: int = 150, height: int = 80) -> str:
    sun_id = f"sunGrad_{prefix}"
    moon_id = f"moonGrad_{prefix}"
    return f"""<svg viewBox="0 0 340 180" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" style="display:block; margin: 0 auto;"><defs><linearGradient id="{sun_id}" x1="0%" y1="100%" x2="0%" y2="0%"><stop offset="0%" stop-color="#E87A1E" /><stop offset="100%" stop-color="#F2B705" /></linearGradient><linearGradient id="{moon_id}" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#11254A" /><stop offset="100%" stop-color="#4A2574" /></linearGradient></defs><g fill="#E87A1E"><polygon points="166,105 166,22 174,22 174,105" /><polygon points="167,105 194,27 201,32 173,105" /><polygon points="167,105 220,44 225,51 173,105" /><polygon points="167,105 241,69 244,77 173,105" /><polygon points="167,105 252,99 252,107 173,105" /><polygon points="173,105 146,27 139,32 167,105" /><polygon points="173,105 120,44 115,51 167,105" /><polygon points="173,105 99,69 96,77 167,105" /><polygon points="173,105 88,99 88,107 167,105" /></g><path d="M 106,105 A 64,64 0 0,1 234,105 Z" fill="url(#{sun_id})" /><path d="M 230,84 C 242,118 226,158 184,167 C 142,176 102,146 102,118 C 114,150 156,158 191,147 C 218,139 233,113 224,88 Z" fill="url(#{moon_id})" /><g fill="#11254A"><polygon points="26,105 48,89 54,105" /><polygon points="26,105 48,121 54,105" /><polygon points="40,105 58,91 62,105" /><polygon points="40,105 58,119 62,105" /><rect x="54" y="102" width="232" height="6" rx="2.5" /><polygon points="282,92 314,105 282,118 290,105" /></g></svg>"""


# ----------------------------------------------------------------------------------
# Estado da Sessão
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
        st.session_state.aviso = "Não foi possível abrir essa conversa. A API está rodando?"
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
        st.session_state.aviso = "Não foi possível apagar a conversa da base de dados."
        st.session_state.confirmando_exclusao = False
        return
    nova_conversa()


# ----------------------------------------------------------------------------------
# Barra Lateral (Sidebar)
# ----------------------------------------------------------------------------------
saude = api_saude()
conversas = api_listar_conversas() if saude else []

with st.sidebar:
    render_html(get_logo_svg("sidebar", width=115, height=62))
    render_html(
        """
        <div style="text-align: center; margin-top: 6px; margin-bottom: 16px;">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.3rem; font-weight: 800; color: #F2B705; letter-spacing: -0.3px;">SivansAI</div>
            <div style="font-family: 'Lora', 'Cormorant Garamond', serif; font-size: 0.92rem; font-weight: 600; color: #E87A1E; letter-spacing: 2.2px;">SALVE DEUS!</div>
        </div>
        """
    )

    st.markdown('<div class="btn-nova-conversa">', unsafe_allow_html=True)
    st.button("☀️ Nova Conversa", on_click=nova_conversa, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if saude:
        trechos = saude.get('chunks_indexados', 0)
        termos = saude.get('termos_no_glossario', 0)
        render_html(
            f"""
            <div style="background: rgba(27,107,70,0.22); border: 1px solid rgba(27,107,70,0.45); padding: 9px 12px; border-radius: 8px; margin: 12px 0; font-size: 0.8rem; color: #EAE6DF;">
                🟢 <b>Acervo Doutrinário Conectado</b><br>
                • {trechos:,} trechos indexados (Qdrant)<br>
                • {termos} termos no glossário oficial
            </div>
            """
        )
    else:
        st.error("⚠️ API offline. Inicie com: uvicorn app.main:app")

    ids_salvos = {c["id"] for c in conversas}
    if st.session_state.conversa_id in ids_salvos:
        if st.session_state.confirmando_exclusao:
            st.warning("Apagar esta conversa permanentemente?")
            c1, c2 = st.columns(2)
            c1.button("Sim, apagar", on_click=apagar_conversa_atual, type="primary", use_container_width=True)
            c2.button("Cancelar", on_click=cancelar_exclusao, use_container_width=True)
        else:
            st.button("🗑️ Apagar conversa atual", on_click=pedir_confirmacao_exclusao, use_container_width=True)

    st.divider()
    render_html("<div style='font-family: \"Cinzel\", serif; font-size: 0.85rem; font-weight: 700; color: #F2B705; margin-bottom: 8px; letter-spacing: 0.8px;'>HISTÓRICO DE DIÁLOGOS</div>")
    
    if conversas:
        for conversa in conversas:
            atual = conversa["id"] == st.session_state.conversa_id
            marcador = "🔶 " if atual else "💬 "
            rotulo = f"{marcador}{conversa['titulo']}"
            st.button(
                rotulo,
                key=f"conv_{conversa['id']}",
                on_click=abrir_conversa,
                args=(conversa["id"],),
                use_container_width=True,
            )
    elif saude:
        st.caption("Nenhum histórico salvo ainda.")

    render_html(
        """
        <div style="margin-top: 28px; padding-top: 14px; border-top: 1px solid rgba(242,183,5,0.22); text-align: center; font-size: 0.8rem; color: #E6E1D8;">
            <b style="color: #F8F6F1; letter-spacing: 0.5px;">Caio Serpa</b><br>
            <a href="https://github.com/caioeserpa/SivansAI" target="_blank" rel="noopener noreferrer" style="color: #F2B705; text-decoration: none; font-size: 0.74rem; display: inline-flex; align-items: center; justify-content: center; gap: 4px; margin-top: 4px;">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                github.com/caioeserpa/SivansAI
            </a><br>
            <span style="font-size: 0.72rem; color: #C4BDAD; display: inline-block; margin-top: 3px;">Projeto realizado para portfólio</span>
        </div>
        """
    )


# ----------------------------------------------------------------------------------
# Área Principal
# ----------------------------------------------------------------------------------

# Faixa Sagrada com as 6 Cores da Doutrina
render_html(
    """
    <div class="faixa-sagrada">
        <div class="cor-1" title="Azul Índigo Profundo (#11254A)"></div>
        <div class="cor-2" title="Amarelo Solar (#F2B705)"></div>
        <div class="cor-3" title="Laranja Amanhecer (#E87A1E)"></div>
        <div class="cor-4" title="Verde Matas (#1B6B46)"></div>
        <div class="cor-5" title="Vermelho Carmim (#C1272D)"></div>
        <div class="cor-6" title="Roxo Místico (#4A2574)"></div>
    </div>
    """
)

# Cabeçalho Institucional Oficial
render_html(
    f"""
    <div class="header-templo">
        {get_logo_svg("main", width=155, height=82)}
        <div class="header-titulo">SivansAI</div>
        <div class="header-saudacao">VALE DO AMANHECER · SALVE DEUS!</div>
        <div class="header-descricao">
            IA desenvolvida para uso pessoal no intuito de auxiliar o estudo da doutrina.<br>
            Respostas estritamente fundamentadas no acervo oficial de leis, cartas, rituais e gravações.
        </div>
    </div>
    <div class="borda-bordado"></div>
    """
)

if st.session_state.aviso:
    st.warning(st.session_state.aviso)

# Mensagens Iniciais Sugeridas (quando a conversa está vazia)
pergunta_clicada = None
if len(st.session_state.mensagens) == 0:
    render_html("<p style='font-size: 0.88rem; font-weight: 700; color: #11254A; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;'>Sugestões para iniciar sua pesquisa doutrinária:</p>")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎗️ **Significado da Fita**\n\nCores, símbolos e função protetora magnética dos médiuns.", key="sug_1", use_container_width=True):
            pergunta_clicada = "Qual é o significado e a função da fita usada pelos médiuns do Vale do Amanhecer?"
        if st.button("🏛️ **Fundação da UESB (1959)**\n\nOrigem na Serra do Ouro por Tia Neiva e seus filhos.", key="sug_2", use_container_width=True):
            pergunta_clicada = "O que foi a UESB e em que data e local ela foi fundada?"
    with col2:
        if st.button("⚖️ **Doutrinador vs. Apará**\n\nComo é realizado o teste mediúnico da Chamada do Mentor.", key="sug_3", use_container_width=True):
            pergunta_clicada = "Como é realizado o teste mediúnico inicial para definir se o aspirante é Doutrinador ou Apará?"
        if st.button("🛡️ **Armas das Indumentárias**\n\nPlexos, proteção e irradiação das falanges missionárias.", key="sug_4", use_container_width=True):
            pergunta_clicada = "Qual é o papel e o significado das 'armas' bordadas nas indumentárias dos médiuns?"

# Histórico de Mensagens
PAPEL_STREAMLIT = {"usuario": "user", "assistente": "assistant"}

for mensagem in st.session_state.mensagens:
    papel = PAPEL_STREAMLIT[mensagem["papel"]]
    avatar = "🏹" if papel == "user" else "☀️"
    with st.chat_message(papel, avatar=avatar):
        st.markdown(mensagem["conteudo"])

        if mensagem["papel"] != "assistente":
            continue

        if mensagem.get("pergunta_reescrita"):
            st.caption(f"🔄 Pergunta interpretada no contexto como: *{mensagem['pergunta_reescrita']}*")

        fontes = list(dict.fromkeys(mensagem.get("fontes", [])))
        if fontes:
            with st.expander(f"📚 Fontes Oficiais Citadas ({len(fontes)})"):
                for fonte in fontes:
                    if "Vídeo" in fonte or "Minuto" in fonte:
                        render_html(f"<span class='badge-fonte badge-video'>🎬 {fonte}</span>")
                    else:
                        render_html(f"<span class='badge-fonte badge-pdf'>📖 {fonte}</span>")

        if mensagem.get("historico_salvo") is False:
            st.caption("⚠️ Esta troca não foi gravada no histórico.")

# Entrada de Pergunta (seja digitada ou via sugestão)
pergunta_digitada = st.chat_input("Faça sua pergunta sobre as leis, rituais ou história da doutrina...")
pergunta_final = pergunta_clicada or pergunta_digitada

if pergunta_final:
    st.session_state.aviso = None
    with st.chat_message("user", avatar="🏹"):
        st.markdown(pergunta_final)

    dados = None
    with st.chat_message("assistant", avatar="☀️"):
        with st.spinner("Consultando o acervo doutrinário e gerando resposta fundamentada..."):
            try:
                resposta_http = requests.post(
                    f"{API_URL}/chat",
                    json={"pergunta": pergunta_final, "conversa_id": st.session_state.conversa_id},
                    timeout=TIMEOUT_CHAT,
                )
                resposta_http.raise_for_status()
                dados = resposta_http.json()
            except requests.exceptions.ConnectionError:
                st.error("Não foi possível conectar à API. Verifique se o servidor está ativo (`uvicorn app.main:app`).")
            except requests.exceptions.Timeout:
                st.error("A busca demorou mais que o esperado. Tente reformular de forma mais objetiva.")
            except requests.exceptions.RequestException as exc:
                st.error(f"Erro ao processar consulta: {exc}")

    if dados is not None:
        st.session_state.mensagens.append(
            {"papel": "usuario", "conteudo": pergunta_final, "fontes": [], "pergunta_reescrita": None, "historico_salvo": True}
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
        st.rerun()
