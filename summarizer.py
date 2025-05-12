# summarizer.py
import google.generativeai as genai
import logging
import os

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Fonksiyon imzasına 'detected_language' parametresini ekleyin
def summarize_text(text_to_summarize, api_key, detected_language):
    """
    Verilen metni (kaynak dili belirtilerek) Google Gemini API kullanarak
    Türkçe olarak özetler.
    """
    if not api_key:
        error_msg = "Gemini API anahtarı girilmedi."
        logging.error(error_msg)
        return None, error_msg
    if not text_to_summarize:
        error_msg = "Özetlenecek metin boş."
        logging.warning(error_msg)
        return None, error_msg
    if not detected_language:
        # Eğer dil algılanamazsa varsayılan olarak İngilizce kabul edilebilir veya hata verilebilir.
        # Şimdilik bir uyarı verip devam edelim, prompt'ta belirtmeyiz.
        logging.warning("Kaynak dil algılanamadı, prompt buna göre ayarlanacak.")
        # Alternatif: error_msg = "Kaynak dil belirtilmedi."; return None, error_msg

    summary = None
    error_message = None

    try:
        # Log mesajına kaynak dili ekle
        logging.info(f"Gemini API ile özetleme işlemi başlatılıyor... (Kaynak Dil: {detected_language or 'Bilinmiyor'})")
        genai.configure(api_key=api_key)

        # Kullanılacak model (Hata alırsanız 'gemini-1.0-pro' deneyin)
        # Önceki hatayı gidermek için bunu kullanabilirsiniz:
        model_name = 'gemini-2.0-flash'
        # model_name = 'gemini-pro' # Veya bu
        model = genai.GenerativeModel(model_name)
        logging.info(f"Kullanılan Gemini Modeli: {model_name}")

        # --- Dinamik Prompt Oluşturma ---
        # Kaynak dili İngilizce ise prompt'u buna göre ayarla
        # Diğer diller için de benzer bir mantık kurulabilir
        source_lang_name_map = {
            'en': 'İngilizce',
            'tr': 'Türkçe',
            'de': 'Almanca',
            'fr': 'Fransızca',
            'es': 'İspanyolca',
            # Diğer yaygın dilleri ekleyebilirsiniz
        }
        # Algılanan dil kodunu okunabilir isme çevir, yoksa kodu kullan
        source_lang_display = source_lang_name_map.get(detected_language, detected_language)

        # Prompt'u oluştururken kaynak dili belirt
        prompt = (
            f"Lütfen aşağıdaki '{source_lang_display}' dilindeki metni alıp, "
            f"bu metnin ana fikirlerini içeren anlaşılır bir paragraf olarak **Türkçe** dilinde özetle:\n\n"
            f"--- Kaynak Metin ({source_lang_display}) ---\n"
            f"{text_to_summarize}\n"
            f"--- Bitti ---\n\n"
            f"**Türkçe Özet:**"
        )
        # ---------------------------------

        logging.debug(f"Gemini API'ye gönderilecek Prompt (ilk 200 karakter):\n{prompt[:200]}...")

        response = model.generate_content(prompt)

        # response.text yerine daha güvenli erişim
        if response.parts:
             summary = "".join(part.text for part in response.parts)
             logging.info("Özetleme başarıyla tamamlandı.")
        else:
             # İçerik filtreleme veya başka bir sorun
             feedback = response.prompt_feedback
             error_message = f"Gemini API'den geçerli bir özet alınamadı. Geri bildirim: {feedback}"
             logging.warning(error_message)
             summary = None # Hata olarak işaretle

    except Exception as e:
        error_message = f"Gemini API Hatası: {e}"
        logging.error(error_message, exc_info=True)
        # Önceki 404 hatası için spesifik kontrol
        if "404" in str(e) and "models/" in str(e):
             error_message = (f"Gemini API Hatası: Belirtilen model ('{model_name}') bulunamadı veya "
                              f"API anahtarınızla kullanılamıyor. Lütfen Google Cloud Console'da "
                              f"'Generative Language API'nin etkin olduğundan ve doğru modeli "
                              f"kullandığınızdan emin olun.\n\nOrijinal Hata: {e}")
        elif "API key not valid" in str(e):
            error_message = "Girilen Gemini API anahtarı geçersiz veya gerekli API (Generative Language API) etkin değil. Lütfen kontrol edin."

    return summary, error_message

# save_summary fonksiyonu aynı kalabilir
def save_summary(summary, filename="video_ozeti.txt"):
    """Özeti belirtilen dosyaya kaydeder."""
    if not summary:
        error_msg = "Kaydedilecek özet içeriği boş."
        logging.warning(error_msg)
        return False, error_msg

    success = False
    error_message = None
    try:
        logging.info(f"Özet '{filename}' dosyasına kaydediliyor...")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(summary)
        logging.info("Dosyaya kaydetme başarılı.")
        success = True
    except IOError as e:
        error_message = f"Dosyaya yazma hatası: {e}"
        logging.error(error_message, exc_info=True)
    except Exception as e:
        error_message = f"Özeti kaydederken beklenmedik hata: {e}"
        logging.error(error_message, exc_info=True)

    return success, error_message