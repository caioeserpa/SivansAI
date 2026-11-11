
 
import re
import tiktoken
 
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 50
 
# Usamos o tokenizer do tiktoken só para MEDIR o tamanho do chunk em tokens.
# Não precisa ser o tokenizer exato do LLM que você vai usar — é só uma régua consistente.
_ENCODING = tiktoken.get_encoding("cl100k_base")
 
 
def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))
 
 
def split_by_markdown_headers(markdown_text: str):
    """
    Divide o texto em seções, cada uma começando num cabeçalho '## Título'.
    Retorna uma lista de tuplas (titulo_da_secao, texto_da_secao).
    Texto antes do primeiro cabeçalho vira uma seção com título None.
    """
    header_pattern = re.compile(r"^##\s+(.*)$", re.MULTILINE)
    matches = list(header_pattern.finditer(markdown_text))
 
    if not matches:
        return [(None, markdown_text.strip())]
 
    sections = []
 
    # Texto antes do primeiro cabeçalho (se houver)
    if matches[0].start() > 0:
        preamble = markdown_text[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))
 
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        section_text = markdown_text[start:end].strip()
        sections.append((title, section_text))
 
    return sections
 
 
def split_text_recursive_by_tokens(text: str, chunk_size=CHUNK_SIZE_TOKENS, overlap=CHUNK_OVERLAP_TOKENS):
    """
    Divide um texto em pedaços de até `chunk_size` tokens, tentando quebrar em
    parágrafos ou frases (não no meio de uma palavra), com sobreposição entre pedaços
    consecutivos para manter continuidade do contexto.
    """
    # Separadores em ordem de preferência: parágrafo > linha > frase > espaço.
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_chunk = ""
 
    def flush_current():
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
 
    for paragraph in paragraphs:
        candidate = (current_chunk + "\n\n" + paragraph).strip() if current_chunk else paragraph
 
        if count_tokens(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            # O parágrafo sozinho já é grande demais ou o chunk atual está cheio.
            flush_current()
 
            if count_tokens(paragraph) <= chunk_size:
                current_chunk = paragraph
            else:
                # Parágrafo muito grande: quebra por frases.
                sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                current_chunk = ""
                for sentence in sentences:
                    candidate_sentence = (current_chunk + " " + sentence).strip() if current_chunk else sentence
                    if count_tokens(candidate_sentence) <= chunk_size:
                        current_chunk = candidate_sentence
                    else:
                        flush_current()
                        current_chunk = sentence
 
    flush_current()
 
    # Aplica sobreposição: pega o final de cada chunk e prepende no próximo.
    if overlap > 0 and len(chunks) > 1:
        overlapped_chunks = [chunks[0]]
        for chunk in chunks[1:]:
            previous_tokens = _ENCODING.encode(overlapped_chunks[-1])
            overlap_text = _ENCODING.decode(previous_tokens[-overlap:])
            overlapped_chunks.append((overlap_text + "\n\n" + chunk).strip())
        return overlapped_chunks
 
    return chunks
 
 
def chunk_pdf_markdown(markdown_text: str, fonte: str):
    """Retorna uma lista de dicts prontos para indexar, a partir de um PDF em Markdown."""
    sections = split_by_markdown_headers(markdown_text)
    result = []
 
    for title, section_text in sections:
        if not section_text:
            continue
        for piece in split_text_recursive_by_tokens(section_text):
            result.append(
                {
                    "texto": piece,
                    "tipo_midia": "pdf",
                    "fonte": fonte,
                    "secao": title or "Introdução",
                }
            )
 
    return result
 
 
_VIDEO_LINE_PATTERN = re.compile(r"\*\*\[(\d{2}:\d{2}) - (\d{2}:\d{2})\]\*\*\s*(.*)")
 
 
def parse_video_segments(markdown_text: str):
    """Extrai (inicio, fim, texto) de cada linha do formato '**[mm:ss - mm:ss]** texto'."""
    segments = []
    for line in markdown_text.splitlines():
        match = _VIDEO_LINE_PATTERN.match(line.strip())
        if match:
            inicio, fim, texto = match.groups()
            if texto.strip():
                segments.append((inicio, fim, texto.strip()))
    return segments
 
 
def chunk_video_markdown(markdown_text: str, fonte: str, chunk_size=CHUNK_SIZE_TOKENS):
    """
    Agrupa segmentos de transcrição consecutivos em chunks de até `chunk_size` tokens,
    guardando o timestamp de início (do primeiro segmento) e fim (do último) de cada chunk.
    """
    segments = parse_video_segments(markdown_text)
    if not segments:
        return []
 
    result = []
    current_texts = []
    current_start = segments[0][0]
 
    def flush(end_timestamp):
        if current_texts:
            result.append(
                {
                    "texto": " ".join(current_texts),
                    "tipo_midia": "video",
                    "fonte": fonte,
                    "timestamp_inicio": current_start,
                    "timestamp_fim": end_timestamp,
                }
            )
 
    for inicio, fim, texto in segments:
        candidate = " ".join(current_texts + [texto])
        if count_tokens(candidate) <= chunk_size or not current_texts:
            current_texts.append(texto)
        else:
            flush(fim_anterior)
            current_texts = [texto]
            current_start = inicio
        fim_anterior = fim
 
    flush(fim_anterior)
    return result
 