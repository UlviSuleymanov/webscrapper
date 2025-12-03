# WordPress Product Scraper Bot

Multithread dəstəkli, tam konfiqurasiya edilə bilən WordPress məhsul scraper.

## 🚀 Setup

```bash
# Virtual environment yarat
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Paketləri yüklə
pip install -r requirements.txt

# Config faylını yarad
cp config.json.example config.json
```

## 📝 İstifadə


### Test Rejimi (Bir Neçə Məhsul)

Test üçün məhdud məhsul sayı ilə işləmək:

```bash
# 10 məhsul ilə test (default)
python main.py --test

# 50 məhsul ilə test
python main.py --test --limit 50

# 5 məhsul ilə test, yalnız JSON
python main.py --test --limit 5 --format json
```

### Dayandırma

Bot işləyərkən **CTRL+C** basın - aktiv thread-lər tamamlanacaq və data saxlanacaq.

### Tam Scrape (Bütün Məhsullar)

```bash
# Default config ilə (həm fayl həm database)
python main.py

# Yalnız JSON fayl
python main.py --format json

# Yalnız database-ə saxla
python main.py --db-only

# Database olmadan, yalnız fayl
python main.py --no-db
```

### Output formatları

```bash
python main.py --format json      # Yalnız JSON
python main.py --format csv       # Yalnız CSV
python main.py --format both      # Həm JSON həm CSV
python main.py --format none      # Heç bir fayl (yalnız DB)
```

### Custom config

```bash
python main.py --config custom_config.json
```

## 🔧 Problem Həllər

### Qiymət Düzgün Alınmır

Scraper indi bir neçə selector ilə qiyməti yoxlayır:
- `span.woocommerce-Price-amount.amount`
- `span.price .woocommerce-Price-amount`
- `.price ins .woocommerce-Price-amount` (endirimli)
- `.price .amount`
- `p.price`

Əgər hələ də problem varsa, məhsul səhifəsinin HTML kodunu yoxlayın və `config.json`-da `selectors.price` dəyişin.

### Məlumat Düzgün Alınmır

Bütün məlumatlar **olduğu kimi** alınır, heç bir format dəyişikliyi yoxdur. Əgər problem varsa:

1. `scraper.log` faylına baxın
2. Test mode ilə 1-2 məhsul scrape edin: `python main.py --test --limit 2`
3. Output JSON-a baxıb hansı field-lərin boş olduğunu yoxlayın

### Thread Sayı

Əgər kompüteriniz yavaşlayırsa, `config.json`-da `max_threads` azaldın (3-5 arası tövsiyə olunur).

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
- `max_threads`: Thread sayı (3-5 tövsiyə)
- `test_mode`: Test rejimi (true/false)
- `test_limit`: Test rejimində məhsul sayı
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

## 📊 Data Strukturu

Her məhsul üçün alınan məlumat:

```json
{
  "wp_id": "3785",
  "title": "Məhsul adı",
  "price": "100.00 ₼",
  "description": "Məhsul təsviri",
  "sku": "SKU123",
  "oem": "OEM456",
  "tags": ["tag1", "tag2"],
  "attributes": {
    "Ölçüləri": "10x20x30",
    "Digər adı": "Alternative Name"
  },
  "images": ["/path/to/image1.jpg"],
  "categories": ["Category 1"],
  "url": "https://...",
  "scraped_at": "2024-01-01T12:00:00"
}
```

## 💡 Məsləhətlər

1. **İlk dəfə test edin**: `python main.py --test --limit 5`
2. **Log faylını izləyin**: `tail -f scraper.log`
3. **CTRL+C ilə dayandırın**: Data itməyəcək
4. **Thread sayını optimizə edin**: Sisteminizdən asılı olaraq 3-7 arası
5. **Headless mode**: Sürətli scrape üçün `"headless": true` istifadə edin
