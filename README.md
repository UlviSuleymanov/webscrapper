# WordPress Scraper Bot

Multithread dəstəkli, tam konfigurasiya edilə bilən WordPress scraper.

## 🚀 Setup

```bash
# Virtual environment yarat
python -m venv venv

# Activate
# Windows:
venv\\Scripts\\activate
# Linux/Mac:
source venv/bin/activate

# Paketləri yüklə
pip install -r requirements.txt

# Config faylını yarad
cp config.json.example config.json
```

## 📝 İstifadə

```bash
# Default config ilə
python main.py

# Custom config ilə
python main.py --config custom_config.json

# Output formatı seç
python main.py --format json
python main.py --format csv
python main.py --format both
```

## 🏗️ Struktur

```
wordpress_scraper/
├── app/
│   ├── config/          # Konfiqurasiya
│   ├── dto/             # Data Transfer Objects
│   ├── repositories/    # Data saxlama
│   ├── services/        # Business logic
│   ├── formatters/      # Output formatlaşdırma
│   └── scraper.py       # Ana scraper class
├── output/              # Nəticələr
└── main.py              # Entry point
```

## ⚙️ Konfiqurasiya

`config.json` faylında:
- `base_url`: Scrape ediləcək sayt
- `max_threads`: Thread sayı
- `fields`: Scrape ediləcək field-lər
- `selectors`: CSS selektorlar
- `download_images`: Şəkil yükləmə

## 🔧 Custom Selektorlar

Əgər standart WooCommerce deyilsə, `config.json`-da selektorları dəyiş:

```json
{
  "selectors": {
    "product_links": ".custom-product a",
    "title": ".custom-title",
    "price": ".custom-price"
  }
}
```
