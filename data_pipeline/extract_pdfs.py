""" 
O que este script faz, passo a passo:
1. Conecta no MinIO e garante que os buckets bronze/silver existem.
2. Lista todos os arquivos .pdf que estão no bucket bronze.
3. Baixa cada PDF para uma pasta temporária local.
4. Usa o PyMuPDF (fitz) para ler o texto de cada página, tentando identificar
   títulos (com base no tamanho da fonte) e transformá-los em cabeçalhos Markdown.
5. Remove cabeçalhos/rodapés repetidos (linhas que aparecem em quase todas as páginas
   costumam ser ruído, como numeração de página ou nome da coleção).
6. Salva o resultado como um arquivo .md e envia para o bucket silver.
 
 """

import shutil 
import tempfile
from collections import Counter
from pathlib import Path

import pymupdf as fitz

from minioutils import (
    download_from_bronze,
    ensure_buckets_exist,
    get_minio_client,
    list_bronze_files,
    upload_to_silver
)

TITLE_FONT_SIZE_THRESHOLD = 13.5

def extract_lines_with_font_size(pdf_path: Path):
    #Retorna uma lista de páginas, cada uma com uma lsita de te4xtos e tamanho de fonte
    doc = fitz.open(pdf_path)
    pages_lines = []
    
    for page in doc:
        page_dict = page.get_text("dict")
        lines_on_page = []
        
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                spans =line.get("spans", [])
                if not spans:
                    continue #junta os pedaçoes (spans) da linha em um texto único
                
                text = "".join(span["text"] for span in spans).strip()
                if not text:
                    continue
                #usa o maior tamanho da fonte entre os spans de linha
                font_size = max(span["size"] for span in spans)
                lines_on_page.append((text,font_size))
        
        pages_lines.append(lines_on_page)
        
        doc.close()
        return pages_lines
    
def detect_repeated_noise_lines(pages_lines, min_repetition_ratio=0.6):
    #Identifica linhas que se repetem em muitas páginas (candidatas a cabeçalho/rodapé)
    total_pages = len(pages_lines)
    if total_pages ==0:
        return set()
    
    line_counter = Counter()
    for lines_on_page in pages_lines:
        #conta cada linha só uma vez por página, mesmo que se repita na mesma página
        unique_lines_this_page = {text for text, _ in lines_on_page}
        line_counter.update(unique_lines_this_page)
        
    threshold = max(2, int(total_pages * min_repetition_ratio))
    noise_lines = {text for text, _ in line_counter.items() if count >= threshold}
    return noise_lines

def convert_to_markdown(pages_lines, noise_lines) -> str:
    "Transforma as linhas extraídas em texto KM, marcando títulos com '#'"
    
    mk_parts = []
    
    for lines_on_page in pages_lines:
        for text, font_size in lines_on_page:
            if text in noise_lines:
                continue #pula cabeçalho e rodapé
            
            if font_size >= TITLE_FONT_SIZE_THRESHOLD:
                mk_parts.append(f"\n## {text}\n")
            else:
                mk_parts.append(text)
                
    return "\n".join(mk_parts)

def process_df(client, key: str, tmp_dir: Path):
    print(f"\n[extract_pdfs] Processando: {key}")
    
    local_pdf = download_from_bronze(client, key, tmp_dir)
    pages_lines = extract_lines_with_font_size(local_pdf)
    noise_lines = detect_repeated_noise_lines(pages_lines)
    markdown_text = convert_to_markdown(pages_lines, noise_lines)
    
    output_name = Path(key).stem + ".md"
    local_output = tmp_dir / output_name
    local_output.write_text(markdown_text, encoding="utf-8")
    
    silver_key = f"pdfs/{output_name}"
    upload_to_silver(client, local_output, silver_key)
    


def main():
    client = get_minio_client()
    ensure_buckets_exist(client)
    
    pdf_keys = list_bronze_files(client, ".pdf")
    if not pdf_keys:
        print("[extract_pdfs] Nenhum PDF encontrado no bucket bronze. Suba arquivos e rode novamente")
        
        return
    
    print(f"[extract_pdfs] {len(pdf_keys)} PDF(s) encontrado(s): {pdf_keys}")
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for key in pdf_keys:
            try:
                process_df(client, key, tmp_dir)
            except Exception as exc:
                print(f"[extract_pdfs] ERRO ao processar '{key}': {exc}")
                
    print("\n[extract_pdfs] Conluído.")
    
    
if __name__ == "__main__":
    main()