import json
import logging
from contextlib import contextmanager
from threading import Lock
from typing import List, Optional

import mysql.connector
from mysql.connector import Error, pooling

from app.dto import ProductData


class DatabaseRepository:
    """
    MySQL database repository.
    Handles strict CRUD operations using Connection Pooling.
    """

    def __init__(self, db_config):
        self.config = db_config
        self.db_lock = Lock()
        self.connection_pool = None

        if self.config.enabled:
            self._create_connection_pool()
            self._create_tables()

    def _create_connection_pool(self) -> None:
        """Initializes the MySQL connection pool."""
        try:
            self.connection_pool = pooling.MySQLConnectionPool(
                pool_name="scraper_pool",
                pool_size=10,  # Increased for multi-threading
                pool_reset_session=True,
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
            )
            logging.info("Database connection pool initialized.")
        except Error as e:
            logging.critical(f"Failed to create connection pool: {str(e)}")
            raise

    @contextmanager
    def _get_connection(self):
        """Context manager for acquiring and releasing connections."""
        connection = None
        try:
            connection = self.connection_pool.get_connection()
            yield connection
        except Error as e:
            logging.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()

    def _create_tables(self) -> None:
        """
        Creates necessary tables.
        Note: SKU is NOT unique here as per requirement. wp_id is the unique key.
        Attributes and Tags are stored as JSON to catch all dynamic fields.
        """

        # Products Table
        # wp_id: WordPress post ID (Unique identifier)
        # attributes: JSON field for "Ölçüləri", "Digər adı", etc.
        products_table = f"""
        CREATE TABLE IF NOT EXISTS {self.config.table_prefix}products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            wp_id VARCHAR(50) UNIQUE,
            title VARCHAR(500),
            price VARCHAR(100),
            description TEXT,
            sku VARCHAR(100),
            oem VARCHAR(200),
            attributes JSON,
            tags JSON,
            url TEXT,
            scraped_at DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_sku (sku),
            INDEX idx_oem (oem),
            INDEX idx_wp_id (wp_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        # Images Table
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

        # Categories Table
        categories_table = f"""
        CREATE TABLE IF NOT EXISTS {self.config.table_prefix}categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """

        # Pivot Table for Categories
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
                logging.info("Database tables verified/created.")
        except Error as e:
            logging.error(f"Table creation failed: {str(e)}")
            raise

    def save_product(self, product: ProductData) -> Optional[int]:
        """
        Saves or updates a product.
        Uses wp_id for uniqueness.
        """
        if not self.config.enabled:
            return None

        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()

                # Prepare JSON data
                # DTO properties ensure these are valid JSON strings or None
                tags_data = (
                    json.dumps(product.tags, ensure_ascii=False)
                    if product.tags
                    else None
                )
                attributes_data = (
                    json.dumps(product.attributes, ensure_ascii=False)
                    if product.attributes
                    else None
                )

                # Insert or Update Logic based on wp_id
                insert_query = f"""
                INSERT INTO {self.config.table_prefix}products
                (wp_id, title, price, description, sku, oem, attributes, tags, url, scraped_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                price = VALUES(price),
                description = VALUES(description),
                sku = VALUES(sku),
                oem = VALUES(oem),
                attributes = VALUES(attributes),
                tags = VALUES(tags),
                url = VALUES(url),
                scraped_at = VALUES(scraped_at)
                """

                cursor.execute(
                    insert_query,
                    (
                        product.wp_id,
                        product.title,
                        product.price,
                        product.description,
                        product.sku,
                        product.oem,
                        attributes_data,  # Contains "Ölçüləri", "Digər adı" etc.
                        tags_data,
                        product.url,
                        product.scraped_at,
                    ),
                )

                # Get the internal DB ID
                product_id = cursor.lastrowid

                # If it was an update, lastrowid might be 0, so fetch ID by wp_id
                if product_id == 0:
                    cursor.execute(
                        f"SELECT id FROM {self.config.table_prefix}products WHERE wp_id = %s",
                        (product.wp_id,),
                    )
                    result = cursor.fetchone()
                    product_id = result[0] if result else None

                if product_id:
                    self._save_related_data(cursor, product_id, product)

                connection.commit()
                cursor.close()

                logging.info(f"Product saved: {product.title} (WP_ID: {product.wp_id})")
                return product_id

        except Error as e:
            logging.error(f"Failed to save product {product.title}: {str(e)}")
            return None

    def _save_related_data(self, cursor, product_id: int, product: ProductData):
        """Helper to save images and categories."""

        # 1. Handle Images
        cursor.execute(
            f"DELETE FROM {self.config.table_prefix}product_images WHERE product_id = %s",
            (product_id,),
        )
        if product.images:
            images_query = f"""
            INSERT INTO {self.config.table_prefix}product_images
            (product_id, image_url, image_order) VALUES (%s, %s, %s)
            """
            images_data = [
                (product_id, img, idx) for idx, img in enumerate(product.images)
            ]
            cursor.executemany(images_query, images_data)

        # 2. Handle Categories
        cursor.execute(
            f"DELETE FROM {self.config.table_prefix}product_categories WHERE product_id = %s",
            (product_id,),
        )
        if product.categories:
            for category_name in product.categories:
                # Find or Create Category
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

                # Link Product to Category
                cursor.execute(
                    f"INSERT IGNORE INTO {self.config.table_prefix}product_categories (product_id, category_id) VALUES (%s, %s)",
                    (product_id, category_id),
                )

    def save_products_batch(self, products: List[ProductData]) -> int:
        """Batch processing wrapper."""
        if not self.config.enabled:
            return 0

        saved_count = 0
        with self.db_lock:
            for product in products:
                if self.save_product(product):
                    saved_count += 1
        return saved_count

    def clear_all_data(self) -> bool:
        """Truncates all tables."""
        if not self.config.enabled:
            return False

        try:
            with self._get_connection() as connection:
                cursor = connection.cursor()
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                cursor.execute(
                    f"TRUNCATE TABLE {self.config.table_prefix}product_categories"
                )
                cursor.execute(
                    f"TRUNCATE TABLE {self.config.table_prefix}product_images"
                )
                cursor.execute(f"TRUNCATE TABLE {self.config.table_prefix}categories")
                cursor.execute(f"TRUNCATE TABLE {self.config.table_prefix}products")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                connection.commit()
                cursor.close()
                logging.warning("All database data cleared.")
                return True
        except Error as e:
            logging.error(f"Failed to clear data: {str(e)}")
            return False
