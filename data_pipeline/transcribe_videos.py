"""
transcribe_videos.py
 
O que este script faz, passo a passo:
1. Conecta no MinIO e garante que os buckets bronze/silver existem.
2. Lista todos os arquivos .mp4 que estão no bucket bronze.
3. Baixa cada vídeo para uma pasta temporária local.
4. Usa o FFmpeg (via subprocess) para extrair o áudio em .wav.
5. Usa o faster-whisper para transcrever o áudio, capturando o timestamp de início e
   fim de cada trecho falado.
6. Salva o resultado como um arquivo .md (texto corrido + metadados de tempo) e envia
   para o bucket silver.
 
Pré-requisito: o FFmpeg precisa estar instalado no sistema (não é uma biblioteca Python).
Verifique rodando `ffmpeg -version` no terminal antes de continuar.
 
Como rodar:
    python data_pipeline/transcribe_videos.py
"""

import os
import subprocess
import tempfile
import pathlib as Path

from faster_whisper import WhisperModel

from minioutils import(
    download_from_bronze,
    ensure_buckets_exist,
    get_minio_client,
    list_bronze_files,
    upload_to_silver,
    
)

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")

def extract_audio(video_path: Path, tmp_dir: Path) -> Path:
    "Usa o FFmpeg para converter o vídeo em um arquivo .wav de áudio"
    audio_path = tmp_dir / (video_path.stem + ".wav")
    
    command = [
        "ffmpeg",
        "-y", #sobrescreve a saída caso existente
        "-i", str(video_path),
        "-ac", "1", #audio mono
        "-ar", "16000", #taxa de amostragem do whisper
        str(audio_path) 
    ]
    
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao extrair áudio com FFmpeg: {result.stderr}")
    return audio_path


def format_timestap(seconds: float) -> str:
    "Converte segundos em algo legível. Ex 125.4 em 02:05"
    
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def transcribe_audio(audio_path: Path, model:WhisperModel):
    "Roda o faster-whisper e retorna uma lsita de segmentos com texto e timestamps"
    
    segments, _info = model.transcribe(str(audio_path), language="pt-br")
    
    transcribed_segments = []
    for segment in segments:
        transcribed_segments.append(
            {
                "inicio": segment.start,
                "fim": segment.end,
                "texto": segment.text.strip()
            }
        )
    return transcribed_segments

def build_markdown(video_name: str, segments: list) -> str:
    "Monta um Markdown com o texto transcrito e os timestamps de cada trecho."
    lines = [f"# Transcrição - {video_name} \n"]
             
    for seg in segments:
        inicio_fmt = format_timestap(seg["inicio"])
        fim_fmt  = format_timestap(seg["fim"])
        lines.append(f"**[{inicio_fmt} - {fim_fmt}]** {seg["texto"]}\n")

    return "\n".join(lines)



def process_video(client, key: str, tmp_dir: Path, model: WhisperModel):
    print(f"\n[transcribe_videos] Processando: {key}")
 
    local_video = download_from_bronze(client, key, tmp_dir)
    audio_path = extract_audio(local_video, tmp_dir)
    segments = transcribe_audio(audio_path, model)
 
    if not segments:
        print(f"[transcribe_videos] AVISO: nenhuma fala detectada em '{key}'.")
 
    video_name = local_video.stem
    markdown_text = buil_markdown(video_name, segments)
 
    output_name = video_name + ".md"
    local_output = tmp_dir / output_name
    local_output.write_text(markdown_text, encoding="utf-8")
 
    silver_key = f"videos/{output_name}"
    upload_to_silver(client, local_output, silver_key)
 
 
def main():
    client = get_minio_client()
    ensure_buckets_exist(client)
 
    video_keys = list_bronze_files(client, ".mp4")
    if not video_keys:
        print("[transcribe_videos] Nenhum vídeo encontrado no bucket bronze. Suba alguns arquivos e rode de novo.")
        return
 
    print(f"[transcribe_videos] {len(video_keys)} vídeo(s) encontrado(s): {video_keys}")
    print(f"[transcribe_videos] Carregando modelo Whisper '{WHISPER_MODEL_SIZE}' (pode demorar na primeira vez)...")
 
    # compute_type="int8" deixa a transcrição mais rápida em CPU (Mac sem GPU dedicada).
    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
 
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for key in video_keys:
            try:
                process_video(client, key, tmp_dir, model)
            except Exception as exc:
                print(f"[transcribe_videos] ERRO ao processar '{key}': {exc}")
 
    print("\n[transcribe_videos] Concluído.")
 
 
if __name__ == "__main__":
    main()