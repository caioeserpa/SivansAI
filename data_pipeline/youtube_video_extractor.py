import ssl
from pytubefix import YouTube
from pytubefix.cli import on_progress

ssl._create_default_https_context = ssl._create_unverified_context

urls = [
    "https://www.youtube.com/watch?v=Om_XKR1rwmc",
    "https://www.youtube.com/watch?v=G-O8fyR32SQ",
    "https://www.youtube.com/watch?v=81MKrCwd9n8"
]

for url in urls:
    print(f"Iniciando: {url}")
    
    yt = YouTube(url, on_progress_callback=on_progress, client='ANDROID') #CLIENT = WEB
    
    print(f"Título: {yt.title}")
    
    ys = yt.streams.get_highest_resolution()
    
    if ys is None:
        print("Stream progressivo padrão não encontrado. Buscando alternativa...")
        # Pega a melhor opção de vídeo disponível
        ys = yt.streams.filter(file_extension='mp4').order_by('resolution').desc().first()
        
    if ys is None:
        print(f"⚠️ Não foi possível encontrar streams para o vídeo: {yt.title}. Pulando...")
        continue
        
    print(f"Baixando em: {ys.resolution or 'resolução desconhecida'}...")
    
    ys.download(output_path="/Volumes/SSD_CAIO/SivansAI/acervo")
    
    print("Download concluído com sucesso!\n")