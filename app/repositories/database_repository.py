import json
import logging
from contextlib import contextmanager
from threading import Lock
from typing import List, Optional

import mysql.connector
from mysql.connector import Error, pooling

from app.dto import ProductData


class DatabaseRepository:
    """MySQL database əməliyyatları üçün repository"""

    def __init__(self, db_config):
        self.config = db_config
        self.db_lock = Lock()
        self.connection_pool = None

        if self.config.enabled:
            self._create_connection_pool()
            self._create_tables()

    def _create_connection_pool(self) -> None:
        """Connection pool yarat"""
        try:
            self.connection_pool = pooling.MySQLConnectionPool(
                pool_name="scraper_pool",
                pool_size=5,
                pool_reset_session=True,
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
            )
            logging.info("Database connection pool yaradıldı")
        except Error as e:
            logging.error(f"Connection pool xətası: {str(e)}")
            raise

    @contextmanager
    def _get_connection(self):
        """Connection pool-dan connection al"""
        connection = None
        try:
            connection = self.connection_pool.get_connection()
            yield connection
        except Error as e:
            logging.error(f"Database connection xətası: {str(e)}")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()

    def _create_tables(self) -> None:
        """Lazımi cədvəlləri yarat"""
        products_table = f"""
        CREATE TABLE IF NOT EXISTS {self.config.table_prefix}products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(500),
            price VARCHAR(100),
            description TEXT,
            sku VARCHAR(100) UNIQUE,
            url TEXT,
            scraped_at DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_sku (sku),
            INDEX idx_title (title(255))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        images_table = f"""
        CREATE TABLE IF NOT EXISTS {self.config.table_prefix}product_images (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            image_url TEXT,
            image_order INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES {self.config.table_prefix}products(id) ON DELETE CASCADE,
            INDEX idx_product_id (product_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        categories_table = f"""
        CREATE TABLE IF NOT EXISTS {self.config.table_prefix}categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        product_categories_table = f"""
        CREATE TABLE IF NOT EXISTS {self.config.table_prefix}product_categories (
            product_id INT NOT NULL,
            category_id INT NOT NULL,
            PRIMARY KEY (product_id, category_id),
            FOREIGN KEY (product_id) REFERENCES {self.config.table_prefix}products(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES {self.config.table_prefix}categories(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()

                cursor.execute(products_table)
                cursor.execute(images_table)
                cursor.execute(categories_table)
                cursor.execute(product_categories_table)

                connection.commit()
                cursor.close()

                logging.info("Database cədvəlləri yaradıldı")
        except Error as e:
            logging.error(f"Cədvəl yaratma xətası: {str(e)}")
            raise

    def save_product(self, product: ProductData) -> Optional[int]:
        """Tək məhsulu database-ə saxla"""
        if not self.config.enabled:
            return None

        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()

                # Məhsulu insert et və ya update et
                insert_query = f"""
                INSERT INTO {self.config.table_prefix}products
                (title, price, description, sku, url, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                price = VALUES(price),
                description = VALUES(description),
                url = VALUES(url),
                scraped_at = VALUES(scraped_at)
                """

                cursor.execute(
                    insert_query,
                    (
                        product.title,
                        product.price,
                        product.description,
                        product.sku,
                        product.url,
                        product.scraped_at,
                    ),
                )

                product_id = cursor.lastrowid

                # Əgər update idisə, product_id-ni əl ilə tap
                if product_id == 0:
                    cursor.execute(
                        f"SELECT id FROM {self.config.table_prefix}products WHERE sku = %s",
                        (product.sku,),
                    )
                    result = cursor.fetchone()
                    product_id = result[0] if result else None

                if product_id:
                    # Köhnə şəkilləri sil
                    cursor.execute(
                        f"DELETE FROM {self.config.table_prefix}product_images WHERE product_id = %s",
                        (product_id,),
                    )

                    # Yeni şəkilləri əlavə et
                    if product.images:
                        images_query = f"""
                        INSERT INTO {self.config.table_prefix}product_images
                        (product_id, image_url, image_order)
                        VALUES (%s, %s, %s)
                        """
                        images_data = [
                            (product_id, img, idx)
                            for idx, img in enumerate(product.images)
                        ]
                        cursor.executemany(images_query, images_data)

                    # Kateqoriyaları əlavə et
                    if product.categories:
                        for category_name in product.categories:
                            # Kateqoriyanı tap və ya yarat
                            cursor.execute(
                                f"SELECT id FROM {self.config.table_prefix}categories WHERE name = %s",
                                (category_name,),
                            )
                            result = cursor.fetchone()

                            if result:
                                category_id = result[0]
                            else:
                                cursor.execute(
                                    f"INSERT INTO {self.config.table_prefix}categories (name) VALUES (%s)",
                                    (category_name,),
                                )
                                category_id = cursor.lastrowid

                            # Məhsula kateqoriya əlavə et
                            cursor.execute(
                                f"""
                                INSERT IGNORE INTO {self.config.table_prefix}product_categories
                                (product_id, category_id) VALUES (%s, %s)
                                """,
                                (product_id, category_id),
                            )

                connection.commit()
                cursor.close()

                logging.info(
                    f"Database-ə saxlanıldı: {product.title} (ID: {product_id})"
                )
                return product_id

        except Error as e:
            logging.error(f"Database saxlama xətası: {str(e)}")
            return None

    def save_products_batch(self, products: List[ProductData]) -> int:
        """Bir neçə məhsulu batch olaraq saxla"""
        if not self.config.enabled:
            return 0

        saved_count = 0

        with self.db_lock:
            for product in products:
                if self.save_product(product):
                    saved_count += 1

        logging.info(f"Database-ə cəmi {saved_count}/{len(products)} məhsul saxlanıldı")
        return saved_count

    def get_product_by_sku(self, sku: str) -> Optional[ProductData]:
        """SKU-ya görə məhsul tap"""
        if not self.config.enabled:
            return None

        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)

                cursor.execute(
                    f"SELECT * FROM {self.config.table_prefix}products WHERE sku = %s",
                    (sku,),
                )

                result = cursor.fetchone()
                cursor.close()

                if result:
                    return ProductData(
                        title=result["title"],
                        price=result["price"],
                        description=result["description"],
                        sku=result["sku"],
                        url=result["url"],
                        scraped_at=str(result["scraped_at"]),
                    )

                return None

        except Error as e:
            logging.error(f"Məhsul axtarış xətası: {str(e)}")
            return None

    def get_all_products(self, limit: Optional[int] = None) -> List[ProductData]:
        """Bütün məhsulları al"""
        if not self.config.enabled:
            return []

        try:
            with self._get_connection() as connection:
                cursor = connection.cursor(dictionary=True)

                query = (
                    f"SELECT * FROM {self.config.table_prefix}products ORDER BY id DESC"
                )
                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query)
                results = cursor.fetchall()
                cursor.close()

                products = []
                for row in results:
                    products.append(
                        ProductData(
                            title=row["title"],
                            price=row["price"],
                            description=row["description"],
                            sku=row["sku"],
                            url=row["url"],
                            scraped_at=str(row["scraped_at"]),
                        )
                    )

                return products

        except Error as e:
            logging.error(f"Məhsullar alma xətası: {str(e)}")
            return []

    def clear_all_data(self) -> bool:
        """Bütün məlumatları təmizlə (DİQQƏT!)"""
        if not self.config.enabled:
            return False

        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()

                cursor.execute(
                    f"DELETE FROM {self.config.table_prefix}product_categories"
                )
                cursor.execute(f"DELETE FROM {self.config.table_prefix}product_images")
                cursor.execute(f"DELETE FROM {self.config.table_prefix}categories")
                cursor.execute(f"DELETE FROM {self.config.table_prefix}products")

                connection.commit()
                cursor.close()

                logging.info("Database məlumatları təmizləndi")
                return True

        except Error as e:
            logging.error(f"Database təmizləmə xətası: {str(e)}")
            return False
