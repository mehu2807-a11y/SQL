-- ==============================================================================
-- Olist E-commerce Order Funnel Analysis
-- Database: olist_ecommerce
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Order Status Distribution
-- Description: Count and percentage of orders by status
-- ------------------------------------------------------------------------------
WITH total_orders AS (
    SELECT COUNT(*) AS total_count
    FROM orders
)
SELECT 
    order_status,
    COUNT(order_id) AS order_count,
    ROUND(COUNT(order_id) * 100.0 / t.total_count, 2) AS percentage
FROM orders
CROSS JOIN total_orders t
GROUP BY order_status, t.total_count
ORDER BY order_count DESC;

-- ------------------------------------------------------------------------------
-- 2. Funnel Progression
-- Description: Track orders through stages and show conversion rate
-- ------------------------------------------------------------------------------
WITH funnel_stages AS (
    SELECT
        COUNT(CASE WHEN order_purchase_timestamp IS NOT NULL THEN order_id END) AS total_placed,
        COUNT(CASE WHEN order_approved_at IS NOT NULL THEN order_id END) AS total_approved,
        COUNT(CASE WHEN order_delivered_carrier_date IS NOT NULL THEN order_id END) AS total_shipped,
        COUNT(CASE WHEN order_delivered_customer_date IS NOT NULL THEN order_id END) AS total_delivered
    FROM orders
)
SELECT
    'Placed' AS stage,
    total_placed AS order_count,
    100.00 AS conversion_from_placed,
    NULL AS step_conversion
FROM funnel_stages

UNION ALL

SELECT
    'Approved' AS stage,
    total_approved AS order_count,
    ROUND(total_approved * 100.0 / total_placed, 2) AS conversion_from_placed,
    ROUND(total_approved * 100.0 / total_placed, 2) AS step_conversion
FROM funnel_stages

UNION ALL

SELECT
    'Shipped' AS stage,
    total_shipped AS order_count,
    ROUND(total_shipped * 100.0 / total_placed, 2) AS conversion_from_placed,
    ROUND(total_shipped * 100.0 / total_approved, 2) AS step_conversion
FROM funnel_stages

UNION ALL

SELECT
    'Delivered' AS stage,
    total_delivered AS order_count,
    ROUND(total_delivered * 100.0 / total_placed, 2) AS conversion_from_placed,
    ROUND(total_delivered * 100.0 / total_shipped, 2) AS step_conversion
FROM funnel_stages;

-- ------------------------------------------------------------------------------
-- 3. Cancellation Analysis
-- ------------------------------------------------------------------------------

-- 3a. Cancellation rate by month
WITH monthly_orders AS (
    SELECT 
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS order_month,
        COUNT(order_id) AS total_orders,
        COUNT(CASE WHEN order_status = 'canceled' THEN order_id END) AS canceled_orders
    FROM orders
    WHERE order_purchase_timestamp IS NOT NULL
    GROUP BY order_month
)
SELECT 
    order_month,
    total_orders,
    canceled_orders,
    ROUND(canceled_orders * 100.0 / total_orders, 2) AS cancellation_rate_pct
FROM monthly_orders
ORDER BY order_month;

-- 3b. Average time to cancellation
WITH canceled_orders AS (
    SELECT
        order_id,
        TIMESTAMPDIFF(DAY, order_purchase_timestamp, COALESCE(order_delivered_carrier_date, order_approved_at, order_purchase_timestamp)) AS days_to_cancel
    FROM orders
    WHERE order_status = 'canceled'
)
SELECT 
    AVG(days_to_cancel) AS avg_days_to_cancellation
FROM canceled_orders
WHERE days_to_cancel > 0;

-- 3c. Top product categories with highest cancellation rates
WITH category_orders AS (
    SELECT 
        pct.product_category_name_english,
        COUNT(DISTINCT o.order_id) AS total_category_orders,
        COUNT(DISTINCT CASE WHEN o.order_status = 'canceled' THEN o.order_id END) AS canceled_category_orders
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN product_category_translation pct ON p.product_category_name = pct.product_category_name
    GROUP BY pct.product_category_name_english
)
SELECT 
    product_category_name_english,
    total_category_orders,
    canceled_category_orders,
    ROUND(canceled_category_orders * 100.0 / total_category_orders, 2) AS cancellation_rate_pct
FROM category_orders
WHERE total_category_orders >= 50 -- Filter for categories with meaningful volume
ORDER BY cancellation_rate_pct DESC
LIMIT 10;

-- 3d. Cancellation by payment type
WITH payment_cancellations AS (
    SELECT 
        op.payment_type,
        COUNT(DISTINCT o.order_id) AS total_orders,
        COUNT(DISTINCT CASE WHEN o.order_status = 'canceled' THEN o.order_id END) AS canceled_orders
    FROM orders o
    JOIN order_payments op ON o.order_id = op.order_id
    GROUP BY op.payment_type
)
SELECT 
    payment_type,
    total_orders,
    canceled_orders,
    ROUND(canceled_orders * 100.0 / total_orders, 2) AS cancellation_rate_pct
FROM payment_cancellations
ORDER BY cancellation_rate_pct DESC;

-- ------------------------------------------------------------------------------
-- 4. Delivery Delay Analysis
-- ------------------------------------------------------------------------------

-- 4a & 4b. Percentage of orders delivered late & Average delivery delay in days
WITH delivery_stats AS (
    SELECT
        order_id,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 ELSE 0 END AS is_late,
        CASE WHEN order_delivered_customer_date > order_estimated_delivery_date 
             THEN TIMESTAMPDIFF(DAY, order_estimated_delivery_date, order_delivered_customer_date)
             ELSE 0 END AS delay_days
    FROM orders
    WHERE order_status = 'delivered' 
      AND order_delivered_customer_date IS NOT NULL 
      AND order_estimated_delivery_date IS NOT NULL
)
SELECT 
    COUNT(*) AS total_delivered_orders,
    SUM(is_late) AS late_orders,
    ROUND(SUM(is_late) * 100.0 / COUNT(*), 2) AS late_delivery_pct,
    ROUND(AVG(NULLIF(delay_days, 0)), 2) AS avg_delay_days_for_late_orders
FROM delivery_stats;

-- 4c. Delivery delay by state
WITH state_delays AS (
    SELECT
        c.customer_state,
        COUNT(o.order_id) AS delivered_orders,
        SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS late_orders,
        AVG(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date 
                 THEN TIMESTAMPDIFF(DAY, o.order_estimated_delivery_date, o.order_delivered_customer_date) 
                 ELSE NULL END) AS avg_delay_days
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
    GROUP BY c.customer_state
)
SELECT 
    customer_state,
    delivered_orders,
    late_orders,
    ROUND(late_orders * 100.0 / delivered_orders, 2) AS late_delivery_pct,
    ROUND(avg_delay_days, 2) AS avg_delay_days
FROM state_delays
ORDER BY late_delivery_pct DESC;

-- 4d. Delivery delay trend over time (monthly)
WITH monthly_delays AS (
    SELECT
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS order_month,
        COUNT(order_id) AS delivered_orders,
        SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 ELSE 0 END) AS late_orders,
        AVG(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date 
                 THEN TIMESTAMPDIFF(DAY, order_estimated_delivery_date, order_delivered_customer_date) 
                 ELSE NULL END) AS avg_delay_days
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL
    GROUP BY order_month
)
SELECT 
    order_month,
    delivered_orders,
    late_orders,
    ROUND(late_orders * 100.0 / delivered_orders, 2) AS late_delivery_pct,
    ROUND(avg_delay_days, 2) AS avg_delay_days
FROM monthly_delays
ORDER BY order_month;

-- 4e. Distribution of delay buckets
WITH delay_buckets AS (
    SELECT 
        order_id,
        TIMESTAMPDIFF(DAY, order_estimated_delivery_date, order_delivered_customer_date) AS diff_days
    FROM orders
    WHERE order_status = 'delivered'
      AND order_delivered_customer_date IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL
)
SELECT 
    CASE 
        WHEN diff_days <= 0 THEN 'On Time or Early'
        WHEN diff_days BETWEEN 1 AND 7 THEN '1-7 days late'
        WHEN diff_days BETWEEN 8 AND 14 THEN '8-14 days late'
        ELSE '14+ days late'
    END AS delay_bucket,
    COUNT(order_id) AS order_count,
    ROUND(COUNT(order_id) * 100.0 / (SELECT COUNT(*) FROM delay_buckets), 2) AS pct_total
FROM delay_buckets
GROUP BY delay_bucket
ORDER BY 
    CASE delay_bucket 
        WHEN 'On Time or Early' THEN 1
        WHEN '1-7 days late' THEN 2
        WHEN '8-14 days late' THEN 3
        ELSE 4
    END;

-- ------------------------------------------------------------------------------
-- 5. Time-to-Deliver Analysis
-- ------------------------------------------------------------------------------

-- 5a & 5b. Average days from purchase to delivery by month and estimate vs actual
WITH monthly_delivery_times AS (
    SELECT 
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS order_month,
        TIMESTAMPDIFF(DAY, order_purchase_timestamp, order_delivered_customer_date) AS actual_delivery_days,
        TIMESTAMPDIFF(DAY, order_purchase_timestamp, order_estimated_delivery_date) AS estimated_delivery_days
    FROM orders
    WHERE order_status = 'delivered'
      AND order_purchase_timestamp IS NOT NULL
      AND order_delivered_customer_date IS NOT NULL
      AND order_estimated_delivery_date IS NOT NULL
)
SELECT 
    order_month,
    COUNT(*) AS total_delivered,
    ROUND(AVG(actual_delivery_days), 2) AS avg_actual_delivery_days,
    ROUND(AVG(estimated_delivery_days), 2) AS avg_estimated_delivery_days,
    ROUND(AVG(estimated_delivery_days) - AVG(actual_delivery_days), 2) AS avg_days_beaten_estimate
FROM monthly_delivery_times
GROUP BY order_month
ORDER BY order_month;

-- 5c. Fastest and slowest states by delivery time
WITH state_delivery_times AS (
    SELECT 
        c.customer_state,
        COUNT(o.order_id) AS total_delivered,
        AVG(TIMESTAMPDIFF(DAY, o.order_purchase_timestamp, o.order_delivered_customer_date)) AS avg_delivery_days
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp IS NOT NULL
      AND o.order_delivered_customer_date IS NOT NULL
    GROUP BY c.customer_state
)
SELECT 
    customer_state,
    total_delivered,
    ROUND(avg_delivery_days, 2) AS avg_delivery_days,
    RANK() OVER (ORDER BY avg_delivery_days ASC) AS fastest_rank,
    RANK() OVER (ORDER BY avg_delivery_days DESC) AS slowest_rank
FROM state_delivery_times
ORDER BY avg_delivery_days ASC;

-- ------------------------------------------------------------------------------
-- 6. Create VIEW v_order_funnel
-- Description: Summarizes the overall funnel metrics 
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_order_funnel AS
SELECT
    DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS order_month,
    COUNT(order_id) AS total_orders_placed,
    COUNT(order_approved_at) AS total_orders_approved,
    COUNT(order_delivered_carrier_date) AS total_orders_shipped,
    COUNT(order_delivered_customer_date) AS total_orders_delivered,
    COUNT(CASE WHEN order_status = 'canceled' THEN order_id END) AS total_orders_canceled,
    -- Funnel conversion rates
    ROUND(COUNT(order_approved_at) * 100.0 / NULLIF(COUNT(order_id), 0), 2) AS pct_approved,
    ROUND(COUNT(order_delivered_carrier_date) * 100.0 / NULLIF(COUNT(order_approved_at), 0), 2) AS pct_shipped,
    ROUND(COUNT(order_delivered_customer_date) * 100.0 / NULLIF(COUNT(order_delivered_carrier_date), 0), 2) AS pct_delivered,
    -- Cancellation rate
    ROUND(COUNT(CASE WHEN order_status = 'canceled' THEN order_id END) * 100.0 / NULLIF(COUNT(order_id), 0), 2) AS pct_canceled
FROM orders
GROUP BY order_month
ORDER BY order_month;
