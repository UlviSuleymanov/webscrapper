# WordPress Product Scraper Bot

Multithread dəstəkli, tam konfigurasiya edilə bilən WordPress məhsul scraper.

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
# Default config ilə (həm fayl həm database)
python main.py

# Yalnız JSON fayl
python main.py --format json

# Yalnız database-ə saxla
python main.py --db-only

# Database olmadan, yalnız fayl
python main.py --no-db

# Custom config ilə
python main.py --config custom_config.json

# Output formatları
python main.py --format json      # Yalnız JSON
python main.py --format csv       # Yalnız CSV
python main.py --format both      # Həm JSON həm CSV
python main.py --format none      # Heç bir fayl (yalnız DB)
```

## 🗄️ Database Setup

1. **MySQL database yarat:**
```sql
CREATE DATABASE scraped_products CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. **Config.json-da database parametrlərini düzəlt:**
```json
{
  "database": {
    "enabled": true,
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "scraped_products",
    "table_prefix": "wp_"
  }
}
```

3. **Cədvəllər avtomatik yaradılacaq:**
   - `wp_products` - Məhsul məlumatları
   - `wp_product_images` - Məhsul şəkilləri
   - `wp_categories` - Kateqoriyalar
   - `wp_product_categories` - Məhsul-Kateqoriya əlaqələri

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
