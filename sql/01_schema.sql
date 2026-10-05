-- Create Database
DROP DATABASE IF EXISTS olist_ecommerce;
CREATE DATABASE olist_ecommerce DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE olist_ecommerce;

-- Table: customers
CREATE TABLE customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    customer_unique_id VARCHAR(32),
    customer_zip_code_prefix INT,
    customer_city VARCHAR(100),
    customer_state CHAR(2),
    INDEX idx_customer_unique_id (customer_unique_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Customer demographics and locations';

-- Table: geolocation
CREATE TABLE geolocation (
    geo_id INT AUTO_INCREMENT PRIMARY KEY,
    geolocation_zip_code_prefix INT,
    geolocation_lat DECIMAL(10,8),
    geolocation_lng DECIMAL(11,8),
    geolocation_city VARCHAR(100),
    geolocation_state CHAR(2),
    INDEX idx_geo_zip (geolocation_zip_code_prefix)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Geolocation details for zip codes';

-- Table: sellers
CREATE TABLE sellers (
    seller_id VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix INT,
    seller_city VARCHAR(100),
    seller_state CHAR(2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Seller demographics and locations';

-- Table: product_category_translation
CREATE TABLE product_category_translation (
    product_category_name VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Translation of product categories to English';

-- Table: products
CREATE TABLE products (
    product_id VARCHAR(32) PRIMARY KEY,
    product_category_name VARCHAR(100),
    product_name_lenght INT,
    product_description_lenght INT,
    product_photos_qty INT,
    product_weight_g INT,
    product_length_cm INT,
    product_height_cm INT,
    product_width_cm INT,
    FOREIGN KEY (product_category_name) REFERENCES product_category_translation(product_category_name) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_product_category (product_category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Product catalog details';

-- Table: orders
CREATE TABLE orders (
    order_id VARCHAR(32) PRIMARY KEY,
    customer_id VARCHAR(32),
    order_status VARCHAR(20),
    order_purchase_timestamp DATETIME,
    order_approved_at DATETIME,
    order_delivered_carrier_date DATETIME,
    order_delivered_customer_date DATETIME,
    order_estimated_delivery_date DATETIME,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_order_status (order_status),
    INDEX idx_order_purchase_timestamp (order_purchase_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Main orders information';

-- Table: order_items
CREATE TABLE order_items (
    order_id VARCHAR(32),
    order_item_id INT,
    product_id VARCHAR(32),
    seller_id VARCHAR(32),
    shipping_limit_date DATETIME,
    price DECIMAL(10,2),
    freight_value DECIMAL(10,2),
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (seller_id) REFERENCES sellers(seller_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Individual items in each order';

-- Table: order_payments
CREATE TABLE order_payments (
    order_id VARCHAR(32),
    payment_sequential INT,
    payment_type VARCHAR(20),
    payment_installments INT,
    payment_value DECIMAL(10,2),
    PRIMARY KEY (order_id, payment_sequential),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Payment details for orders';

-- Table: order_reviews
CREATE TABLE order_reviews (
    review_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32),
    review_score TINYINT,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date DATETIME,
    review_answer_timestamp DATETIME,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_review_score (review_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Customer reviews for orders';

-- =======================================================
-- Data Cleaning & Views Section
-- =======================================================

-- 1. Remove exact duplicate rows from geolocation
-- (Run this after data import)
/*
DELETE g1 FROM geolocation g1
INNER JOIN geolocation g2 
WHERE 
    g1.geo_id > g2.geo_id AND
    g1.geolocation_zip_code_prefix = g2.geolocation_zip_code_prefix AND
    g1.geolocation_lat = g2.geolocation_lat AND
    g1.geolocation_lng = g2.geolocation_lng;
*/

-- 2. Update empty strings to NULL across text columns
-- (Run this after data import)
/*
UPDATE customers SET customer_city = NULL WHERE customer_city = '';
UPDATE geolocation SET geolocation_city = NULL WHERE geolocation_city = '';
UPDATE sellers SET seller_city = NULL WHERE seller_city = '';
UPDATE order_reviews SET review_comment_title = NULL WHERE review_comment_title = '';
UPDATE order_reviews SET review_comment_message = NULL WHERE review_comment_message = '';
*/

-- 3. View: v_orders_enriched
CREATE OR REPLACE VIEW v_orders_enriched AS
SELECT 
    o.order_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    oi.order_item_id,
    oi.price,
    oi.freight_value,
    p.product_id,
    pct.product_category_name_english,
    r.review_score
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN product_category_translation pct ON p.product_category_name = pct.product_category_name
LEFT JOIN order_reviews r ON o.order_id = r.order_id;

-- 4. View: v_delivery_performance
CREATE OR REPLACE VIEW v_delivery_performance AS
SELECT 
    order_id,
    customer_id,
    order_purchase_timestamp,
    order_estimated_delivery_date,
    order_delivered_customer_date,
    DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date) AS delivery_delay_days,
    CASE 
        WHEN order_delivered_customer_date IS NULL THEN 'Not Delivered'
        WHEN order_delivered_customer_date <= order_estimated_delivery_date THEN 'On Time'
        ELSE 'Delayed'
    END AS delivery_status
FROM orders;
