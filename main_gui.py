# main_gui.py
import customtkinter as ctk
from tkinter import messagebox, PhotoImage
import threading
import os
import sys
import logging
import subprocess

# Modülleri içe aktar
from downloader import download_audio_yt_dlp
from transcriber import transcribe_audio
from summarizer import summarize_text, save_summary

# Logger kurulumu
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- GUI İşlemleri ve Yardımcı Fonksiyonlar ---

# GUI'yi farklı thread'den güvenli bir şekilde güncellemek için
def update_status(message):
    # Use after(0, ...) for safe thread updates
    if root: # Pencere kapatıldıysa hata vermemesi için kontrol
        root.after(0, lambda: status_label.configure(text=f"Durum: {message}"))

def update_summary_text(summary_content):
    if root:
        def update_widget():
            summary_text.configure(state=ctk.NORMAL)
            summary_text.delete("1.0", ctk.END)
            summary_text.insert(ctk.END, summary_content)
            summary_text.configure(state=ctk.DISABLED)
        # Use after(0, ...) for safe thread updates
        root.after(0, update_widget)

# These already use root.after(0, ...) which is correct
def show_error_async(title, message):
     if root:
        root.after(0, lambda: messagebox.showerror(title, message))
        # Update status also needs to be thread-safe
        update_status("Hata oluştu.") # Genel durum

def show_info_async(title, message):
    if root:
        root.after(0, lambda: messagebox.showinfo(title, message))


# Ana işlem fonksiyonu (Thread içinde çalışacak)
def run_processing(url, api_key):
    audio_file = None
    try:
        # 1. Adım: Ses İndirme
        update_status("Video sesi indiriliyor (yt-dlp)...")
        temp_dir = "temp_audio_yt"
        os.makedirs(temp_dir, exist_ok=True)
        audio_file, error = download_audio_yt_dlp(url, output_path=temp_dir)

        if error or not audio_file:
            msg = f"Ses indirilemedi: {error}" if error else "Ses indirilemedi (bilinmeyen hata)."
            logging.error(msg)
            show_error_async("İndirme Hatası", msg)
            # No need for update_status here, show_error_async already calls it
            return

        update_status(f"Ses indirildi: {os.path.basename(audio_file)}")

        # 2. Adım: Transkript Oluşturma
        whisper_model = "base"
        update_status(f"Transkript oluşturuluyor (Whisper Model: {whisper_model} - Bu işlem uzun sürebilir)...")
        transcript, lang, error = transcribe_audio(audio_file, model_name=whisper_model, delete_audio=True)
        # audio_file is now None because delete_audio=True

        if error or not transcript:
            msg = f"Transkript oluşturulamadı: {error}" if error else "Transkript oluşturulamadı (bilinmeyen hata)."
            logging.error(msg)
            show_error_async("Transkript Hatası", msg)
            # Clean up the potentially undeleted audio file if transcription failed early
            # Check existence *before* trying to remove
            if audio_file and os.path.exists(audio_file):
                 try:
                     os.remove(audio_file)
                     logging.info(f"Temizlik: Başarısız transkript sonrası '{audio_file}' silindi.")
                 except OSError as e:
                     logging.warning(f"Temizlik: '{audio_file}' silinemedi: {e}")
            return

        logging.info(f"Transkript tamamlandı. Algılanan dil: {lang}")
        update_status(f"Transkript tamamlandı (Algılanan Dil: {lang}). Özetleme başlıyor...")

        # 3. Adım: Özetleme
        update_status(f"Metin Gemini API ile '{lang}' dilinden Türkçe'ye özetleniyor...")
        summary, error = summarize_text(transcript, api_key, detected_language=lang)

        if error or not summary:
            err_msg = f"Metin özetlenemedi.\n\nHata: {error}"
            logging.error(f"Özetleme hatası: {error}")
            show_error_async("Özetleme Hatası", err_msg)
            # No need for update_status here, show_error_async already calls it
            return

        # 4. Adım: Sonuçları Gösterme ve Kaydetme
        update_status("Özet GUI'de gösteriliyor...")
        update_summary_text(summary)

        update_status("Özet dosyaya kaydediliyor...")
        output_summary_file = "video_ozeti.txt"
        saved, save_error = save_summary(summary, filename=output_summary_file)

        if save_error:
            logging.warning(f"Özet kaydedilemedi: {save_error}")
            # Use show_info_async for consistency
            show_info_async("Kaydetme Uyarısı", f"Özet başarıyla oluşturuldu ancak '{output_summary_file}' dosyasına kaydedilemedi: {save_error}")
        else:
             logging.info(f"Özet başarıyla kaydedildi: {output_summary_file}")
             show_info_async("Başarılı", f"Video özeti başarıyla oluşturuldu ve '{output_summary_file}' dosyasına kaydedildi.")

        update_status("İşlem başarıyla tamamlandı!")

    except Exception as e:
        logging.error(f"Ana işlem sırasında beklenmedik hata: {e}", exc_info=True)
        show_error_async("Genel Hata", f"Beklenmedik bir hata oluştu: {e}")
        # No need for update_status here, show_error_async already calls it

    finally:
        # Re-enable button using after(0, ...)
        if root:
            # Ensure the button is re-enabled on the main thread
            root.after(0, lambda: process_button.configure(state=ctk.NORMAL)) # CORRECTED LINE

        # Clean up audio file if it still exists
        # Check existence *before* trying to remove
        if audio_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
                logging.info(f"Temizlik: İşlem sonu artık '{audio_file}' silindi.")
            except OSError as e:
                logging.warning(f"Temizlik: İşlem sonu '{audio_file}' silinemedi: {e}")

        # Clean up temp directory if empty
        temp_dir = "temp_audio_yt"
        # Check existence and listdir
        if os.path.exists(temp_dir) and os.path.isdir(temp_dir) and not os.listdir(temp_dir):
             try:
                 os.rmdir(temp_dir)
                 logging.info(f"Temizlik: Boş geçici dizin '{temp_dir}' silindi.")
             except OSError as e:
                 logging.warning(f"Temizlik: Geçici dizin '{temp_dir}' silinemedi: {e}")


# Butona basılınca çalışacak fonksiyon
def start_processing_thread():
    url = url_entry.get().strip()
    api_key = api_key_entry.get().strip()

    if not url:
        # Use show_error_async for consistency, it handles the status update
        show_error_async("Giriş Hatası", "Lütfen geçerli bir YouTube video URL'si girin.")
        return
    if not ("youtube.com/watch?v=" in url or "youtu.be/" in url):
         show_error_async("Giriş Hatası", "Geçersiz YouTube URL formatı.")
         return

    if not api_key:
         # Use show_error_async, but also provide specific status
         update_status("Lütfen Gemini API anahtarınızı girin.")
         show_error_async("Giriş Hatası", "Lütfen Google Gemini API anahtarınızı girin.")
         return

    # Inform user and disable button
    update_status("İşlem başlatılıyor...")
    update_summary_text("İşleniyor...") # Clear summary box and inform
    process_button.configure(state=ctk.DISABLED)

    # Start processing in a separate thread
    thread = threading.Thread(target=run_processing, args=(url, api_key), daemon=True)
    thread.start()

# --- Theme Switching ---
def toggle_theme():
    current_mode = ctk.get_appearance_mode()
    new_mode = "Light" if current_mode == "Dark" else "Dark"
    ctk.set_appearance_mode(new_mode)
    logging.info(f"Tema değiştirildi: {new_mode}")
    # Update status safely from the main thread event handler
    update_status(f"Tema: {new_mode}")


# --- Check FFmpeg ---
def check_ffmpeg():
    try:
        startupinfo = None
        creation_flags = 0 # Default for non-Windows
        if os.name == 'nt':
             startupinfo = subprocess.STARTUPINFO()
             startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
             # startupinfo.wShowWindow = subprocess.SW_HIDE # Alternative way
             creation_flags = subprocess.CREATE_NO_WINDOW # More common way

        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, check=True,
            startupinfo=startupinfo,
            creationflags=creation_flags
        )
        logging.info("ffmpeg bulundu ve çalıştırılabiliyor.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logging.warning(f"ffmpeg bulunamadı veya çalıştırılamadı: {e}")
        # Use root.after to ensure messagebox runs in the main thread
        # Check if root exists before scheduling
        if root:
            root.after(100, lambda: messagebox.showwarning("FFmpeg Eksikliği Uyarısı",
                                   "Sisteminizde FFmpeg kurulu değil veya PATH içinde bulunamıyor.\n\n"
                                   "yt-dlp ile ses dönüştürme ve Whisper ile bazı ses formatlarının işlenmesi için FFmpeg gereklidir.\n\n"
                                   "Lütfen FFmpeg'i kurun ve sistem PATH'ine ekleyin.\n"
                                   "İndirme linki: https://ffmpeg.org/download.html\n\n"
                                   "Program çalışmaya devam edecek ancak hatalarla karşılaşabilirsiniz."))
        return False
    except Exception as e: # Catch other potential errors
        logging.error(f"ffmpeg kontrolü sırasında beklenmedik hata: {e}", exc_info=True)
        if root:
            root.after(100, lambda: messagebox.showerror("FFmpeg Kontrol Hatası",
                                   f"FFmpeg kontrol edilirken bir hata oluştu: {e}"))
        return False


# --- GUI Kurulumu ---

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("YouTube Video Özetleyici (yt-dlp & Whisper & Gemini)")
root.geometry("700x650")

# Center the window
window_width = 700
window_height = 650
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
center_x = int(screen_width/2 - window_width / 2)
center_y = int(screen_height/2 - window_height / 2)
root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

# Configure grid layout
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(3, weight=1)

# --- Top Frame for Theme Switch ---
top_frame = ctk.CTkFrame(root, corner_radius=0)
top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
top_frame.grid_columnconfigure(0, weight=1)

theme_button = ctk.CTkButton(top_frame, text="Temayı Değiştir", command=toggle_theme, width=150)
theme_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")


# --- Input Frame ---
input_frame = ctk.CTkFrame(root)
input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
input_frame.grid_columnconfigure(1, weight=1)

url_label = ctk.CTkLabel(input_frame, text="YouTube Video URL:")
url_label.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
url_entry = ctk.CTkEntry(input_frame, placeholder_text="https://www.youtube.com/watch?v=...")
url_entry.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")

api_key_label = ctk.CTkLabel(input_frame, text="Gemini API Anahtarı:")
api_key_label.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="w")
api_key_entry = ctk.CTkEntry(input_frame, placeholder_text="API Anahtarınızı buraya girin", show="*")
api_key_entry.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="ew")

# --- Process Button ---
process_button = ctk.CTkButton(root, text="Video Özeti Çıkar", command=start_processing_thread, height=40)
process_button.grid(row=2, column=0, padx=10, pady=10)

# --- Summary Area ---
summary_frame = ctk.CTkFrame(root)
summary_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 5))
summary_frame.grid_rowconfigure(1, weight=1)
summary_frame.grid_columnconfigure(0, weight=1)

summary_label = ctk.CTkLabel(summary_frame, text="Video Özeti:", anchor="w")
summary_label.grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")

summary_text = ctk.CTkTextbox(summary_frame, wrap=ctk.WORD, state=ctk.DISABLED, corner_radius=5)
summary_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

# --- Status Label ---
status_label = ctk.CTkLabel(root, text="Durum: Bekleniyor...", anchor="w")
status_label.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 10))


# --- Ana Döngüyü Başlat ---
if __name__ == "__main__":
    # Set console encoding (best effort)
    try:
        # Check if stdout/stderr are connected to a terminal (isatty)
        # before attempting to reconfigure. Avoids errors in environments
        # where sys.stdout/stderr might not be standard streams (like some IDEs).
        if sys.stdout is not None and sys.stdout.encoding != 'utf-8' and sys.stdout.isatty():
           sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr is not None and sys.stderr.encoding != 'utf-8' and sys.stderr.isatty():
           sys.stderr.reconfigure(encoding='utf-8')
        logging.info(f"Konsol kodlaması ayarlandı (denendi): stdout={getattr(sys.stdout, 'encoding', 'N/A')}, stderr={getattr(sys.stderr, 'encoding', 'N/A')}")
    except Exception as e:
        logging.warning(f"Konsol kodlaması ayarlanamadı: {e}")
        print(f"Warning: Could not set console encoding: {e}", file=sys.stderr) # Print to stderr

    # Check for FFmpeg after root is created but before mainloop
    check_ffmpeg() # It uses root.after internally if root exists

    root.mainloop()