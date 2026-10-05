-- ============================================================================
-- SATISFACTION DRIVERS ANALYSIS
-- Database: olist_ecommerce
-- Focus: Understanding what drives customer satisfaction (review scores)
-- ============================================================================

-- ============================================================================
-- 1. Review Score Distribution
-- ============================================================================
-- Overview of review scores across the platform and monthly trends

-- Overall Distribution
WITH total_reviews AS (
    SELECT COUNT(*) AS total_cnt FROM order_reviews
)
SELECT 
    review_score,
    COUNT(*) AS review_count,
    ROUND(COUNT(*) * 100.0 / (SELECT total_cnt FROM total_reviews), 2) AS percentage,
    (SELECT ROUND(AVG(review_score), 2) FROM order_reviews) AS overall_avg_score
FROM 
    order_reviews
GROUP BY 
    review_score
ORDER BY 
    review_score DESC;

-- Monthly Trend
SELECT 
    DATE_FORMAT(review_creation_date, '%Y-%m') AS review_month,
    COUNT(*) AS review_count,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    SUM(CASE WHEN review_score >= 4 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS positive_review_pct
FROM 
    order_reviews
GROUP BY 
    DATE_FORMAT(review_creation_date, '%Y-%m')
ORDER BY 
    review_month;

-- ============================================================================
-- 2. Delivery Delay vs Review Score
-- ============================================================================
-- Quantifying the impact of delivery delays on customer satisfaction

-- View for Delivery Satisfaction
CREATE OR REPLACE VIEW v_delivery_satisfaction AS
WITH delivery_metrics AS (
    SELECT 
        o.order_id,
        r.review_score,
        o.order_estimated_delivery_date,
        o.order_delivered_customer_date,
        DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) AS delivery_delay_days
    FROM 
        orders o
    JOIN 
        order_reviews r ON o.order_id = r.order_id
    WHERE 
        o.order_status = 'delivered'
        AND o.order_delivered_customer_date IS NOT NULL
        AND o.order_estimated_delivery_date IS NOT NULL
),
delay_buckets AS (
    SELECT 
        order_id,
        review_score,
        delivery_delay_days,
        CASE 
            WHEN delivery_delay_days < -5 THEN 'Early (>5 days)'
            WHEN delivery_delay_days BETWEEN -5 AND -1 THEN 'Early (1-5 days)'
            WHEN delivery_delay_days = 0 THEN 'On Time'
            WHEN delivery_delay_days BETWEEN 1 AND 7 THEN 'Late (1-7 days)'
            WHEN delivery_delay_days BETWEEN 8 AND 14 THEN 'Late (8-14 days)'
            ELSE 'Late (15+ days)'
        END AS delivery_performance
    FROM 
        delivery_metrics
)
SELECT 
    delivery_performance,
    COUNT(*) AS total_reviews,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    SUM(CASE WHEN review_score IN (1, 2) THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS negative_review_pct
FROM 
    delay_buckets
GROUP BY 
    delivery_performance
ORDER BY 
    -- Custom ordering logic
    CASE delivery_performance
        WHEN 'Early (>5 days)' THEN 1
        WHEN 'Early (1-5 days)' THEN 2
        WHEN 'On Time' THEN 3
        WHEN 'Late (1-7 days)' THEN 4
        WHEN 'Late (8-14 days)' THEN 5
        WHEN 'Late (15+ days)' THEN 6
    END;

SELECT * FROM v_delivery_satisfaction;

-- ============================================================================
-- 3. Satisfaction by Product Category
-- ============================================================================

CREATE OR REPLACE VIEW v_category_satisfaction AS
WITH order_item_reviews AS (
    SELECT 
        oi.order_id,
        oi.product_id,
        p.product_category_name,
        r.review_score,
        o.order_estimated_delivery_date,
        o.order_delivered_customer_date
    FROM 
        order_items oi
    JOIN 
        orders o ON oi.order_id = o.order_id
    JOIN 
        products p ON oi.product_id = p.product_id
    LEFT JOIN 
        order_reviews r ON oi.order_id = r.order_id
    WHERE 
        o.order_status = 'delivered'
)
SELECT 
    COALESCE(t.product_category_name_english, oir.product_category_name) AS category_name,
    COUNT(DISTINCT oir.order_id) AS total_orders,
    ROUND(AVG(oir.review_score), 2) AS avg_review_score,
    SUM(CASE WHEN DATEDIFF(oir.order_delivered_customer_date, oir.order_estimated_delivery_date) > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT oir.order_id) AS late_delivery_rate
FROM 
    order_item_reviews oir
LEFT JOIN 
    product_category_translation t ON oir.product_category_name = t.product_category_name
GROUP BY 
    category_name
HAVING 
    total_orders >= 100 -- Focus on categories with significant volume
ORDER BY 
    total_orders DESC;

-- Top 20 categories by volume and their satisfaction
SELECT * FROM v_category_satisfaction LIMIT 20;

-- Highest satisfaction categories
SELECT * FROM v_category_satisfaction ORDER BY avg_review_score DESC LIMIT 10;

-- Lowest satisfaction categories
SELECT * FROM v_category_satisfaction ORDER BY avg_review_score ASC LIMIT 10;

-- ============================================================================
-- 4. Satisfaction by Seller
-- ============================================================================
-- Analyzing seller performance and its relation to review scores

WITH seller_performance AS (
    SELECT 
        oi.seller_id,
        COUNT(DISTINCT oi.order_id) AS total_orders,
        ROUND(AVG(r.review_score), 2) AS avg_review_score,
        SUM(CASE WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT oi.order_id) AS late_delivery_rate
    FROM 
        order_items oi
    JOIN 
        orders o ON oi.order_id = o.order_id
    LEFT JOIN 
        order_reviews r ON oi.order_id = r.order_id
    WHERE 
        o.order_status = 'delivered'
    GROUP BY 
        oi.seller_id
    HAVING 
        total_orders >= 10
)
-- Best Sellers
SELECT 'Best Sellers' AS category, seller_performance.* FROM seller_performance ORDER BY avg_review_score DESC, total_orders DESC LIMIT 10;

WITH seller_performance AS (
    SELECT 
        oi.seller_id,
        COUNT(DISTINCT oi.order_id) AS total_orders,
        ROUND(AVG(r.review_score), 2) AS avg_review_score,
        SUM(CASE WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT oi.order_id) AS late_delivery_rate
    FROM 
        order_items oi
    JOIN 
        orders o ON oi.order_id = o.order_id
    LEFT JOIN 
        order_reviews r ON oi.order_id = r.order_id
    WHERE 
        o.order_status = 'delivered'
    GROUP BY 
        oi.seller_id
    HAVING 
        total_orders >= 10
)
-- Worst Sellers
SELECT 'Worst Sellers' AS category, seller_performance.* FROM seller_performance ORDER BY avg_review_score ASC, total_orders DESC LIMIT 10;

-- ============================================================================
-- 5. Delivery Promise Accuracy
-- ============================================================================
-- How accurate are estimated delivery dates by state?

SELECT 
    c.customer_state,
    COUNT(*) AS total_delivered_orders,
    ROUND(AVG(DATEDIFF(o.order_estimated_delivery_date, o.order_delivered_customer_date)), 2) AS avg_days_early,
    ROUND(AVG(CASE WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) > 0 
             THEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) 
             ELSE NULL END), 2) AS avg_under_estimation_days_when_late,
    SUM(CASE WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS late_percentage
FROM 
    orders o
JOIN 
    customers c ON o.customer_id = c.customer_id
WHERE 
    o.order_status = 'delivered'
    AND o.order_estimated_delivery_date IS NOT NULL
    AND o.order_delivered_customer_date IS NOT NULL
GROUP BY 
    c.customer_state
ORDER BY 
    avg_days_early DESC;

-- ============================================================================
-- 6. Payment and Satisfaction
-- ============================================================================

-- Satisfaction by Payment Type
SELECT 
    op.payment_type,
    COUNT(DISTINCT op.order_id) AS total_orders,
    ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM 
    order_payments op
JOIN 
    order_reviews r ON op.order_id = r.order_id
GROUP BY 
    op.payment_type
ORDER BY 
    total_orders DESC;

-- Satisfaction by Installments
WITH installment_buckets AS (
    SELECT 
        order_id,
        CASE 
            WHEN payment_installments = 1 THEN '1 Installment'
            WHEN payment_installments BETWEEN 2 AND 3 THEN '2-3 Installments'
            WHEN payment_installments BETWEEN 4 AND 6 THEN '4-6 Installments'
            WHEN payment_installments BETWEEN 7 AND 10 THEN '7-10 Installments'
            ELSE '11+ Installments'
        END AS installment_group
    FROM 
        order_payments
    WHERE 
        payment_installments > 0
    GROUP BY 
        order_id, installment_group
)
SELECT 
    i.installment_group,
    COUNT(i.order_id) AS total_orders,
    ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM 
    installment_buckets i
JOIN 
    order_reviews r ON i.order_id = r.order_id
GROUP BY 
    i.installment_group
ORDER BY 
    CASE i.installment_group
        WHEN '1 Installment' THEN 1
        WHEN '2-3 Installments' THEN 2
        WHEN '4-6 Installments' THEN 3
        WHEN '7-10 Installments' THEN 4
        WHEN '11+ Installments' THEN 5
    END;

-- Order Value vs Satisfaction
WITH order_value AS (
    SELECT 
        order_id,
        SUM(payment_value) AS total_value
    FROM 
        order_payments
    GROUP BY 
        order_id
),
value_buckets AS (
    SELECT 
        order_id,
        total_value,
        NTILE(5) OVER(ORDER BY total_value) AS value_quintile
    FROM 
        order_value
)
SELECT 
    vb.value_quintile,
    ROUND(MIN(vb.total_value), 2) AS min_value,
    ROUND(MAX(vb.total_value), 2) AS max_value,
    COUNT(vb.order_id) AS total_orders,
    ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM 
    value_buckets vb
JOIN 
    order_reviews r ON vb.order_id = r.order_id
GROUP BY 
    vb.value_quintile
ORDER BY 
    vb.value_quintile;
