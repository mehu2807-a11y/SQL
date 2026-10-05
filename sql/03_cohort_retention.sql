-- 1. First Purchase Cohort Assignment
WITH customer_first_purchase AS (
    SELECT 
        c.customer_unique_id,
        MIN(o.order_purchase_timestamp) AS first_purchase_date
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
)
SELECT 
    DATE_FORMAT(first_purchase_date, '%Y-%m') AS cohort_month,
    COUNT(DISTINCT customer_unique_id) AS cohort_size
FROM customer_first_purchase
GROUP BY cohort_month
ORDER BY cohort_month;

-- 2. Monthly Cohort Retention Table
-- 6. Create a VIEW called v_cohort_retention with the retention matrix
CREATE OR REPLACE VIEW v_cohort_retention AS
WITH customer_first_purchase AS (
    SELECT 
        c.customer_unique_id,
        MIN(o.order_purchase_timestamp) AS first_purchase_date
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
),
customer_purchases AS (
    SELECT 
        c.customer_unique_id,
        o.order_purchase_timestamp,
        cfp.first_purchase_date,
        TIMESTAMPDIFF(MONTH, cfp.first_purchase_date, o.order_purchase_timestamp) AS months_since_first
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN customer_first_purchase cfp ON c.customer_unique_id = cfp.customer_unique_id
),
cohort_sizes AS (
    SELECT 
        DATE_FORMAT(first_purchase_date, '%Y-%m') AS cohort_month,
        COUNT(DISTINCT customer_unique_id) AS cohort_size
    FROM customer_first_purchase
    GROUP BY cohort_month
),
retention_data AS (
    SELECT 
        DATE_FORMAT(first_purchase_date, '%Y-%m') AS cohort_month,
        months_since_first,
        COUNT(DISTINCT customer_unique_id) AS returning_customers
    FROM customer_purchases
    GROUP BY cohort_month, months_since_first
)
SELECT 
    r.cohort_month,
    s.cohort_size,
    r.months_since_first,
    r.returning_customers,
    ROUND((r.returning_customers / s.cohort_size) * 100, 2) AS retention_rate
FROM retention_data r
JOIN cohort_sizes s ON r.cohort_month = s.cohort_month
ORDER BY r.cohort_month, r.months_since_first;

-- 3. Overall Repeat Purchase Rate
WITH customer_order_counts AS (
    SELECT 
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
)
SELECT 
    COUNT(customer_unique_id) AS total_customers,
    SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) AS returning_customers,
    ROUND(SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) / COUNT(customer_unique_id) * 100, 2) AS repeat_purchase_rate,
    ROUND(AVG(CASE WHEN order_count >= 2 THEN order_count ELSE NULL END), 2) AS avg_orders_per_repeating_customer
FROM customer_order_counts;

-- 4. Time Between Purchases
WITH customer_orders AS (
    SELECT 
        c.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        LAG(o.order_purchase_timestamp) OVER (PARTITION BY c.customer_unique_id ORDER BY o.order_purchase_timestamp) AS previous_order_date
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
),
inter_purchase_intervals AS (
    SELECT 
        customer_unique_id,
        DATEDIFF(order_purchase_timestamp, previous_order_date) AS days_between_orders
    FROM customer_orders
    WHERE previous_order_date IS NOT NULL
)
SELECT 
    ROUND(AVG(days_between_orders), 2) AS avg_days_between_orders,
    MIN(days_between_orders) AS min_days_between_orders,
    MAX(days_between_orders) AS max_days_between_orders
FROM inter_purchase_intervals;

-- 5. Cohort Revenue Analysis
WITH customer_first_purchase AS (
    SELECT 
        c.customer_unique_id,
        MIN(o.order_purchase_timestamp) AS first_purchase_date
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
),
customer_purchases AS (
    SELECT 
        c.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        cfp.first_purchase_date,
        TIMESTAMPDIFF(MONTH, cfp.first_purchase_date, o.order_purchase_timestamp) AS months_since_first
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN customer_first_purchase cfp ON c.customer_unique_id = cfp.customer_unique_id
),
order_revenue AS (
    SELECT 
        order_id,
        SUM(price + freight_value) AS total_order_value
    FROM order_items
    GROUP BY order_id
)
SELECT 
    DATE_FORMAT(cp.first_purchase_date, '%Y-%m') AS cohort_month,
    cp.months_since_first,
    SUM(r.total_order_value) AS cohort_revenue,
    ROUND(AVG(r.total_order_value), 2) AS avg_order_value
FROM customer_purchases cp
JOIN order_revenue r ON cp.order_id = r.order_id
GROUP BY cohort_month, cp.months_since_first
ORDER BY cohort_month, cp.months_since_first;
