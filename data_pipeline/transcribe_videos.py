import os
import subprocess
import sys
import tempfile
from pathlib import Path
 
from faster_whisper import WhisperModel
 
from data_pipeline.minioutils import (
    download_from_bronze,
    ensure_buckets_exist,
    get_minio_client,
    list_bronze_files,
    silver_key_exists,
    upload_to_silver
)
 
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
 
 
def extract_audio(video_path: Path, tmp_dir: Path) -> Path:
    """Usa o FFmpeg para converter o vídeo em um arquivo .wav de áudio."""
    audio_path = tmp_dir / (video_path.stem + ".wav")
 
    command = [
        "ffmpeg",
        "-y",  # sobrescreve o arquivo de saída se já existir
        "-i", str(video_path),
        "-ac", "1",         # áudio mono (suficiente para transcrição de voz)
        "-ar", "16000",     # taxa de amostragem que o Whisper espera
        str(audio_path),
    ]
 
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao extrair áudio com FFmpeg: {result.stderr}")
 
    return audio_path
 
 
def format_timestamp(seconds: float) -> str:
    """Converte segundos (ex: 125.4) em algo legível (ex: '02:05')."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"
 
 
def transcribe_audio(audio_path: Path, model: WhisperModel):
    """Roda o faster-whisper e retorna uma lista de segmentos com texto e timestamps."""
    segments, _info = model.transcribe(str(audio_path), language="pt")
 
    transcribed_segments = []
    for segment in segments:
        transcribed_segments.append(
            {
                "inicio": segment.start,
                "fim": segment.end,
                "texto": segment.text.strip(),
            }
        )
    return transcribed_segments
 
 
def build_markdown(video_name: str, segments: list) -> str:
    """Monta um Markdown com o texto transcrito e os timestamps de cada trecho."""
    lines = [f"# Transcrição — {video_name}\n"]
 
    for seg in segments:
        inicio_fmt = format_timestamp(seg["inicio"])
        fim_fmt = format_timestamp(seg["fim"])
        lines.append(f"**[{inicio_fmt} - {fim_fmt}]** {seg['texto']}\n")
 
    return "\n".join(lines)
 
 
def process_video(client, key: str, tmp_dir: Path, model: WhisperModel):
    print(f"\n[transcribe_videos] Processando: {key}")
 
    local_video = download_from_bronze(client, key, tmp_dir)
    audio_path = extract_audio(local_video, tmp_dir)
    segments = transcribe_audio(audio_path, model)
 
    if not segments:
        print(f"[transcribe_videos] AVISO: nenhuma fala detectada em '{key}'.")
 
    video_name = local_video.stem
    markdown_text = build_markdown(video_name, segments)
 
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
 
    # Transcrever é a etapa mais lenta: só processa o que ainda não foi transcrito
    # (use --force para refazer tudo).
    if "--force" not in sys.argv:
        ja_transcritos = [k for k in video_keys if silver_key_exists(client, f"videos/{Path(k).stem}.md")]
        video_keys = [k for k in video_keys if k not in ja_transcritos]
        if ja_transcritos:
            print(f"[transcribe_videos] {len(ja_transcritos)} vídeo(s) já transcrito(s), pulando (use --force para refazer).")
        if not video_keys:
            print("[transcribe_videos] Nada novo para transcrever.")
            return
 
    print(f"[transcribe_videos] {len(video_keys)} vídeo(s) a transcrever: {video_keys}")
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