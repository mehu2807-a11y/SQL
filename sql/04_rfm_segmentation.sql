-- 04_rfm_segmentation.sql
-- Database: olist_ecommerce

-- ============================================================================
-- 1 & 2. RFM Score Calculation and Segment Labels (Views)
-- ============================================================================

-- View: v_rfm_scores
-- Calculates the base Recency, Frequency, and Monetary values and their 1-5 quintile scores.
CREATE OR REPLACE VIEW v_rfm_scores AS
WITH customer_rfm_metrics AS (
    SELECT 
        c.customer_unique_id,
        MAX(o.order_purchase_timestamp) AS last_purchase_date,
        DATEDIFF('2018-10-17', MAX(o.order_purchase_timestamp)) AS recency_days,
        COUNT(DISTINCT o.order_id) AS frequency,
        SUM(oi.price + oi.freight_value) AS monetary
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered' -- Consider only completed orders for monetary value
    GROUP BY c.customer_unique_id
)
SELECT 
    customer_unique_id,
    recency_days,
    frequency,
    CAST(monetary AS DECIMAL(10,2)) AS monetary,
    -- Recency score: lower days = higher score (5 is best)
    NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
    -- Frequency score: higher = higher score (5 is best)
    NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
    -- Monetary score: higher = higher score (5 is best)
    NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
FROM customer_rfm_metrics;

-- View: v_rfm_segments
-- Applies business rules to classify customers into actionable segments based on RFM scores.
CREATE OR REPLACE VIEW v_rfm_segments AS
SELECT 
    customer_unique_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    CONCAT(r_score, f_score, m_score) AS rfm_cell,
    CASE 
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
        WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'Can''t Lose Them'
        WHEN f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
        WHEN r_score >= 3 AND f_score >= 2 THEN 'Potential Loyalists'
        WHEN r_score >= 4 AND f_score = 1 THEN 'Recent Customers'
        WHEN r_score >= 3 AND f_score = 1 AND m_score >= 2 THEN 'Promising'
        WHEN r_score = 2 AND f_score >= 2 AND m_score >= 2 THEN 'Need Attention'
        WHEN r_score = 2 AND f_score <= 2 THEN 'About to Sleep'
        WHEN r_score = 1 AND f_score = 1 THEN 'Lost'
        WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Hibernating'
        ELSE 'Other'
    END AS rfm_segment
FROM v_rfm_scores;

-- ============================================================================
-- 3. Segment Summary Statistics
-- ============================================================================
-- Analyzes the overall composition and value of each customer segment
SELECT 
    rfm_segment,
    COUNT(customer_unique_id) AS customer_count,
    ROUND(COUNT(customer_unique_id) * 100.0 / SUM(COUNT(customer_unique_id)) OVER (), 2) AS pct_of_total_customers,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency), 2) AS avg_frequency,
    CAST(AVG(monetary) AS DECIMAL(10,2)) AS avg_monetary,
    CAST(SUM(monetary) AS DECIMAL(12,2)) AS total_segment_revenue,
    ROUND(SUM(monetary) * 100.0 / SUM(SUM(monetary)) OVER (), 2) AS pct_of_total_revenue,
    RANK() OVER (ORDER BY SUM(monetary) DESC) AS revenue_rank
FROM v_rfm_segments
GROUP BY rfm_segment
ORDER BY revenue_rank;


-- ============================================================================
-- 4. Top Customers Analysis
-- ============================================================================
-- 4a. Top 20 Customers by Monetary Value
SELECT 
    customer_unique_id,
    rfm_segment,
    recency_days,
    frequency,
    monetary,
    r_score, f_score, m_score
FROM v_rfm_segments
ORDER BY monetary DESC
LIMIT 20;

-- 4b. Revenue Concentration (Pareto Principle / Decile Analysis)
-- What % of revenue comes from the top 10%, 20% of customers?
WITH ranked_customers AS (
    SELECT 
        customer_unique_id,
        monetary,
        NTILE(10) OVER (ORDER BY monetary DESC) AS spending_decile
    FROM v_rfm_segments
),
decile_summary AS (
    SELECT 
        spending_decile,
        COUNT(customer_unique_id) AS customers_in_decile,
        SUM(monetary) AS decile_revenue
    FROM ranked_customers
    GROUP BY spending_decile
)
SELECT 
    spending_decile,
    customers_in_decile,
    CAST(decile_revenue AS DECIMAL(12,2)) AS decile_revenue,
    CAST(SUM(decile_revenue) OVER (ORDER BY spending_decile ASC) AS DECIMAL(12,2)) AS cumulative_revenue,
    ROUND(decile_revenue * 100.0 / SUM(decile_revenue) OVER (), 2) AS pct_of_total_revenue,
    ROUND(SUM(decile_revenue) OVER (ORDER BY spending_decile ASC) * 100.0 / SUM(decile_revenue) OVER (), 2) AS cumulative_pct_of_total
FROM decile_summary
ORDER BY spending_decile;


-- ============================================================================
-- 5. Segment Recommendations
-- ============================================================================
-- Computes actionable metrics and basic recommendations for marketing per segment
SELECT 
    rfm_segment,
    COUNT(customer_unique_id) AS segment_size,
    CAST(SUM(monetary) AS DECIMAL(12,2)) AS segment_value,
    CASE
        WHEN rfm_segment = 'Champions' THEN 'Reward them. They can be early adopters for new products.'
        WHEN rfm_segment = 'Loyal Customers' THEN 'Offer higher value products. Ask for reviews.'
        WHEN rfm_segment = 'Potential Loyalists' THEN 'Offer membership or loyalty programs.'
        WHEN rfm_segment = 'Recent Customers' THEN 'Provide onboarding support and early discounts.'
        WHEN rfm_segment = 'Promising' THEN 'Offer free trials or welcome bonuses.'
        WHEN rfm_segment = 'Need Attention' THEN 'Make limited time offers, recommend based on past purchases.'
        WHEN rfm_segment = 'About to Sleep' THEN 'Share valuable resources, recommend popular products.'
        WHEN rfm_segment = 'At Risk' THEN 'Send personalized emails to reconnect, offer renewals.'
        WHEN rfm_segment = 'Can''t Lose Them' THEN 'Win them back via renewals or newer products, don''t lose them to competitors.'
        WHEN rfm_segment = 'Hibernating' THEN 'Offer other relevant products and special discounts.'
        WHEN rfm_segment = 'Lost' THEN 'Revive interest with reach out campaign, otherwise ignore.'
        ELSE 'General targeted marketing.'
    END AS marketing_action
FROM v_rfm_segments
GROUP BY rfm_segment
ORDER BY segment_value DESC;
