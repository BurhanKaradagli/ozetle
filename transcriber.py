# transcriber.py
import whisper # openai-whisper kütüphanesi
import os
import logging

# Logger (downloader.py ile aynı formatı kullanabilir)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def transcribe_audio(audio_path, model_name="base", delete_audio=True):
    """
    Verilen ses dosyasını Whisper kullanarak yazıya döker.
    İşlem sonrası ses dosyasını silebilir (varsayılan: True).
    """
    if not audio_path or not os.path.exists(audio_path):
        error_msg = f"Transkript için ses dosyası bulunamadı: {audio_path}"
        logging.error(error_msg)
        return None, None, error_msg

    transcript = None
    detected_language = None
    error_message = None

    try:
        logging.info(f"Transkript oluşturuluyor (Model: {1})... Dosya: {audio_path}")
        # Modeli yükle (ilk kullanımda indirir)
        # Cihaz belirtilebilir: model = whisper.load_model(model_name, device="cuda") # GPU varsa
        model = whisper.load_model(model_name)

        # Transkripsiyon yap (fp16=False CPU'da daha uyumlu olabilir)
        result = model.transcribe(audio_path, fp16=False)

        transcript = result["text"]
        detected_language = result["language"]
        logging.info(f"Transkript oluşturuldu. Algılanan Dil: {detected_language}")

    except Exception as e:
        error_message = f"Transkript sırasında hata: {e}"
        logging.error(error_message, exc_info=True) # Hata detayını logla
    finally:
        # Geçici ses dosyasını silme (eğer isteniyorsa ve dosya varsa)
        if delete_audio and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logging.info(f"Geçici ses dosyası silindi: {audio_path}")
            except OSError as e:
                logging.warning(f"Geçici ses dosyası silinemedi: {e}")

    return transcript, detected_language, error_message