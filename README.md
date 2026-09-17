# DO.MBA - Pull Manager

**DO.MBA - Pull Manager** adalah aplikasi GUI berbasis Python (CustomTkinter) yang dirancang untuk mengelola dan mengeksekusi perintah `git pull` secara otomatis di banyak server remote (SSH) sekaligus (*bulk/blast deployment*).

---

## 🚀 Fitur Utama

* **Multi-Host Management**: Simpan dan kelola kredensial server target (SSH/SFTP) dalam satu tempat.
* **Group Filtering**: Pengelompokan host (misal: *Production*, *Staging*, *All Groups*) untuk mengeksekusi perintah secara spesifik.
* **Instant Search**: Pencarian cepat server berdasarkan nama, IP, atau label host.
* **Pull Blast / Run All**: Jalankan otomasi `git pull` secara serentak (*asynchronous*) di semua server tanpa membuat UI *freeze*.
* **Live Console Output**: Tampilan terminal bawaan untuk memantau log stdout/stderr eksekusi perintah secara *real-time*.
* **Import & Export Data**: Cadangkan (*backup*) atau pulihkan (*restore*) daftar konfigurasi server dengan mudah.
* **Modern Dark UI**: Antarmuka bersih beradaptasi dengan gaya macOS/Windows berbasis CustomTkinter.

---

## 🛠️ Prasyarat & Instalasi

### 1. Kebutuhan Sistem
* **Python 3.9+**
* Operating System: macOS, Windows, atau Linux

### 2. Ketergantungan Library

Install seluruh library yang dibutuhkan dengan menjalankan perintah berikut di terminal:

```bash
pip install customtkinter asyncssh pillow
