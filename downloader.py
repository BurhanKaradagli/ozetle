# downloader.py
import yt_dlp
import os
import time
import logging # Hata ayıklama için logging ekleyelim

# Logger kurulumu (isteğe bağlı ama faydalı)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_audio_yt_dlp(url, output_path="temp_audio"):
    """
    YouTube videosunun sesini yt-dlp kullanarak indirir.
    Belirtilen output_path klasörüne '{video_id}.{ext}' formatında kaydeder.
    Başarılı olursa indirilen dosyanın tam yolunu döndürür.
    """
    if not os.path.exists(output_path):
        try:
            os.makedirs(output_path)
            logging.info(f"Geçici klasör oluşturuldu: {output_path}")
        except OSError as e:
            error_msg = f"Geçici klasör oluşturulamadı: {e}"
            logging.error(error_msg)
            return None, error_msg

    # Geçici dosya adı için video ID'sini kullanalım
    # yt-dlp dosya adını otomatik olarak temizler
    # En iyi sesi m4a veya webm olarak indirmeye çalışalım (Whisper bunları sever)
    output_template = os.path.join(output_path, '%(id)s.%(ext)s')

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best', # Öncelikli formatlar
        'outtmpl': output_template,
        'noplaylist': True, # Sadece tek video indir
        'quiet': True, # Konsol çıktısını azalt
        'no_warnings': True, # Uyarıları gizle
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a', # Tercihen m4a, yoksa yt-dlp en iyisini seçer
            'preferredquality': '128', # Kalite (isteğe bağlı)
        }],
        'logger': logging.getLogger('yt_dlp'), # yt-dlp loglarını yakala
         # 'verbose': True, # Daha detaylı hata ayıklama için açılabilir
    }

    downloaded_file_path = None
    error_message = None

    try:
        logging.info(f"yt-dlp ile ses indiriliyor: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info ile hem bilgi alıp hem indirebiliriz
            info_dict = ydl.extract_info(url, download=True)
            # İndirme sonrası dosya yolunu kesin olarak alalım
            # prepare_filename, şablona göre dosya adını oluşturur
            downloaded_file_path = ydl.prepare_filename(info_dict)

            # Dosyanın gerçekten var olduğunu kontrol et
            if not os.path.exists(downloaded_file_path):
                 # Bazen uzantı değişebilir, klasördeki dosyayı bulmayı dene
                 possible_files = [os.path.join(output_path, f) for f in os.listdir(output_path) if f.startswith(info_dict['id'])]
                 if possible_files:
                      downloaded_file_path = max(possible_files, key=os.path.getctime) # en yenisi
                      if not os.path.exists(downloaded_file_path):
                           downloaded_file_path = None # Hala bulunamadıysa
                 else:
                     downloaded_file_path = None

            if downloaded_file_path:
                logging.info(f"Ses başarıyla indirildi: {downloaded_file_path}")
            else:
                error_message = f"İndirme sonrası dosya bulunamadı. Video ID: {info_dict.get('id', 'N/A')}"
                logging.error(error_message)

    except yt_dlp.utils.DownloadError as e:
        error_message = f"yt-dlp İndirme Hatası: {e}"
        logging.error(error_message, exc_info=True) # Hata detayını logla
    except Exception as e:
        error_message = f"Ses indirme sırasında beklenmedik hata: {e}"
        logging.error(error_message, exc_info=True)

    return downloaded_file_path, error_message