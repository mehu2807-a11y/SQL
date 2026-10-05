"""
Olist E-Commerce Analytics Dashboard
=====================================
Interactive Streamlit dashboard for Customer Retention & Product Performance Analysis.

Usage: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import altair as alt
import mysql.connector
from mysql.connector import Error
import numpy as np

# ─── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Olist E-Commerce Analytics",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stMetric > div { padding: 12px 16px; border-radius: 8px; }
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.4rem !important; border-bottom: 2px solid #e0e0e0; padding-bottom: 6px; }
</style>
""", unsafe_allow_html=True)

# ─── Database Connection ─────────────────────────────────────────────────────
DB_CONFIG = {
    'host': st.secrets.get("MYSQL_HOST", 'localhost'),
    'user': st.secrets.get("MYSQL_USER", 'root'),
    'password': st.secrets.get("MYSQL_PASSWORD", 'Mehul@2807'),
    'database': st.secrets.get("MYSQL_DATABASE", 'olist_ecommerce'),
    'port': int(st.secrets.get("MYSQL_PORT", 3306)),
    'charset': 'utf8mb4',
    'use_unicode': True,
}


@st.cache_data(ttl=600)
def run_query(query: str) -> pd.DataFrame:
    """Run a SQL query and return results as a DataFrame."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Error as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()


def check_connection():
    """Verify database connectivity."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders")
        count = cursor.fetchone()[0]
        conn.close()
        return True, count
    except Error as e:
        return False, str(e)


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shopping-cart.png", width=60)
    st.title(" Olist Analytics")
    st.markdown("---")

    page = st.radio(
        "**Navigate**",
        [" Overview", " Order Funnel", " Cohort Retention",
         " RFM Segmentation", " Satisfaction Drivers",
         " Insights & Recommendations"],
        index=0,
    )

    st.markdown("---")
    st.caption("Data: Olist Brazilian E-Commerce (2016–2018)")
    st.caption("Built with Streamlit + MySQL")

    # Connection status
    connected, info = check_connection()
    if connected:
        st.success(f"v Connected ({info:,} orders)")
    else:
        st.error(f"x {info}")
        st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
if page == " Overview":
    st.title(" Olist E-Commerce — Executive Overview")

    # KPI Cards
    kpi = run_query("""
        SELECT
            COUNT(DISTINCT o.order_id) AS total_orders,
            COUNT(DISTINCT c.customer_unique_id) AS total_customers,
            COUNT(DISTINCT oi.seller_id) AS total_sellers,
            ROUND(SUM(oi.price + oi.freight_value), 0) AS total_revenue,
            ROUND(AVG(oi.price + oi.freight_value), 2) AS avg_order_value
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status NOT IN ('canceled', 'unavailable')
    """)

    review_kpi = run_query("SELECT ROUND(AVG(review_score), 2) AS avg_score FROM order_reviews")

    delivery_kpi = run_query("""
        SELECT ROUND(
            SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 1
        ) AS late_pct
        FROM orders
        WHERE order_delivered_customer_date IS NOT NULL
          AND order_estimated_delivery_date IS NOT NULL
    """)

    repeat_kpi = run_query("""
        SELECT ROUND(
            SUM(CASE WHEN cnt >= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
        ) AS repeat_rate
        FROM (
            SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS cnt
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id
        ) t
    """)

    if not kpi.empty:
        c1, c2, c3 = st.columns(3)
        st.write('')
        c4, c5, c6 = st.columns(3)
        c1.metric(" Total Orders", f"{kpi['total_orders'].iloc[0]/1000:.1f}K")
        c2.metric(" Unique Customers", f"{kpi['total_customers'].iloc[0]/1000:.1f}K")
        c3.metric(" Active Sellers", f"{kpi['total_sellers'].iloc[0]/1000:.1f}K")
        c4.metric(" Total Revenue", f"R${kpi['total_revenue'].iloc[0]/1000000:.1f}M")
        c5.metric(" Avg Review", f"{review_kpi['avg_score'].iloc[0]}/5")
        c6.metric(" Repeat Rate", f"{repeat_kpi['repeat_rate'].iloc[0]}%")

    st.markdown("---")

    # Monthly Revenue Trend
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(" Monthly Revenue Trend")
        monthly_rev = run_query("""
            SELECT
                DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS month,
                ROUND(SUM(oi.price + oi.freight_value), 0) AS revenue,
                COUNT(DISTINCT o.order_id) AS orders
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status NOT IN ('canceled', 'unavailable')
            GROUP BY month ORDER BY month
        """)
        if not monthly_rev.empty:
            st.line_chart(monthly_rev.set_index('month')[['orders', 'revenue']])

    with col2:
        st.subheader(" Orders by State")
        state_orders = run_query("""
            SELECT c.customer_state AS state, COUNT(DISTINCT o.order_id) AS orders
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            GROUP BY c.customer_state ORDER BY orders DESC
        """)
        if not state_orders.empty:
            st.bar_chart(state_orders, x='state', y='orders', color='#3498db')

    # Top categories
    col3, col4 = st.columns(2)

    with col3:
        st.subheader(" Top 10 Product Categories")
        categories = run_query("""
            SELECT
                COALESCE(pct.product_category_name_english, 'Other') AS category,
                COUNT(DISTINCT o.order_id) AS orders,
                ROUND(SUM(oi.price), 0) AS revenue
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN products p ON oi.product_id = p.product_id
            LEFT JOIN product_category_translation pct ON p.product_category_name = pct.product_category_name
            WHERE o.order_status NOT IN ('canceled', 'unavailable')
            GROUP BY category ORDER BY revenue DESC LIMIT 10
        """)
        if not categories.empty:
            st.bar_chart(categories, x='category', y='revenue', color='#2ecc71')

    with col4:
        st.subheader(" Payment Methods")
        payments = run_query("""
            SELECT payment_type, COUNT(*) AS count,
                   ROUND(SUM(payment_value), 0) AS total_value
            FROM order_payments
            GROUP BY payment_type ORDER BY count DESC
        """)
        if not payments.empty:
            st.bar_chart(payments.set_index('payment_type')['count'])


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ORDER FUNNEL
# ═══════════════════════════════════════════════════════════════════════════════
elif page == " Order Funnel":
    st.title(" Order Funnel Analysis")

    # Funnel chart
    st.subheader("Order Stage Progression")
    funnel = run_query("""
        SELECT
            COUNT(CASE WHEN order_purchase_timestamp IS NOT NULL THEN 1 END) AS `Placed`,
            COUNT(CASE WHEN order_approved_at IS NOT NULL THEN 1 END) AS `Approved`,
            COUNT(CASE WHEN order_delivered_carrier_date IS NOT NULL THEN 1 END) AS `Shipped`,
            COUNT(CASE WHEN order_delivered_customer_date IS NOT NULL THEN 1 END) AS `Delivered`
        FROM orders
    """)
    if not funnel.empty:
        stages = ['Placed', 'Approved', 'Shipped', 'Delivered']
        values = [funnel[s].iloc[0] for s in stages]
        conversions = [100.0] + [round(values[i]/values[i-1]*100, 1) for i in range(1, len(values))]

        st.dataframe(pd.DataFrame({'Stage': stages, 'Orders': values, 'Conversion (%)': conversions}), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        # Order status distribution
        st.subheader(" Order Status Distribution")
        status_dist = run_query("""
            SELECT order_status, COUNT(*) AS count,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM orders), 2) AS pct
            FROM orders GROUP BY order_status ORDER BY count DESC
        """)
        if not status_dist.empty:
            st.bar_chart(status_dist, x='order_status', y='count', color='#e67e22')

    with col2:
        # Cancellation rate over time
        st.subheader(" Monthly Cancellation Rate")
        cancel_trend = run_query("""
            SELECT
                DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS month,
                COUNT(*) AS total,
                SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) AS canceled,
                ROUND(SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS cancel_rate
            FROM orders
            WHERE order_purchase_timestamp IS NOT NULL
            GROUP BY month ORDER BY month
        """)
        if not cancel_trend.empty:
            st.line_chart(cancel_trend, x='month', y='cancel_rate', color='#e74c3c')

    # Delivery delay analysis
    st.subheader(" Delivery Delay Distribution")
    delay_dist = run_query("""
        SELECT
            CASE
                WHEN DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date) <= -5 THEN 'Early (>5 days)'
                WHEN DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date) BETWEEN -5 AND -1 THEN 'Early (1-5 days)'
                WHEN DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date) = 0 THEN 'On Time'
                WHEN DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date) BETWEEN 1 AND 7 THEN 'Late (1-7 days)'
                WHEN DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date) BETWEEN 8 AND 14 THEN 'Late (8-14 days)'
                ELSE 'Late (15+ days)'
            END AS delay_bucket,
            COUNT(*) AS orders,
            ROUND(COUNT(*) * 100.0 / (
                SELECT COUNT(*) FROM orders
                WHERE order_delivered_customer_date IS NOT NULL
                  AND order_estimated_delivery_date IS NOT NULL
            ), 1) AS pct
        FROM orders
        WHERE order_delivered_customer_date IS NOT NULL
          AND order_estimated_delivery_date IS NOT NULL
        GROUP BY delay_bucket
        ORDER BY FIELD(delay_bucket, 'Early (>5 days)', 'Early (1-5 days)', 'On Time',
                       'Late (1-7 days)', 'Late (8-14 days)', 'Late (15+ days)')
    """)
    if not delay_dist.empty:
        st.bar_chart(delay_dist, x='delay_bucket', y='orders')

    # Delivery time by state
    st.subheader(" Average Delivery Time by State")
    state_delivery = run_query("""
        SELECT c.customer_state AS state,
               ROUND(AVG(DATEDIFF(o.order_delivered_customer_date, o.order_purchase_timestamp)), 1) AS avg_days,
               ROUND(SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END)
                     * 100.0 / COUNT(*), 1) AS late_pct
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_delivered_customer_date IS NOT NULL
        GROUP BY c.customer_state
        ORDER BY avg_days DESC
    """)
    if not state_delivery.empty:
        st.bar_chart(state_delivery.set_index('customer_state')[['avg_days', 'late_pct']])


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: COHORT RETENTION
# ═══════════════════════════════════════════════════════════════════════════════
elif page == " Cohort Retention":
    st.title(" Cohort Retention Analysis")

    # Overall repeat rate
    repeat_stats = run_query("""
        WITH customer_orders AS (
            SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_count
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id
        )
        SELECT
            COUNT(*) AS total_customers,
            SUM(CASE WHEN order_count = 1 THEN 1 ELSE 0 END) AS one_time,
            SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) AS repeat_buyers,
            ROUND(SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS repeat_rate,
            MAX(order_count) AS max_orders
        FROM customer_orders
    """)

    if not repeat_stats.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Customers", f"{repeat_stats['total_customers'].iloc[0]/1000:.1f}K")
        c2.metric("One-Time Buyers", f"{repeat_stats['one_time'].iloc[0]/1000:.1f}K")
        c3.metric("Repeat Buyers", f"{repeat_stats['repeat_buyers'].iloc[0]:,}")
        c4.metric("Repeat Rate", f"{repeat_stats['repeat_rate'].iloc[0]}%", delta=f"Max: {repeat_stats['max_orders'].iloc[0]} orders")

    st.markdown("---")

    # Cohort retention heatmap
    st.subheader(" Monthly Cohort Retention Heatmap")

    cohort_data = run_query("""
        WITH customer_first_purchase AS (
            SELECT c.customer_unique_id,
                   MIN(o.order_purchase_timestamp) AS first_purchase_date
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            GROUP BY c.customer_unique_id
        ),
        customer_purchases AS (
            SELECT c.customer_unique_id,
                   o.order_purchase_timestamp,
                   cfp.first_purchase_date,
                   TIMESTAMPDIFF(MONTH, cfp.first_purchase_date, o.order_purchase_timestamp) AS months_since_first
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            JOIN customer_first_purchase cfp ON c.customer_unique_id = cfp.customer_unique_id
        ),
        cohort_sizes AS (
            SELECT DATE_FORMAT(first_purchase_date, '%Y-%m') AS cohort_month,
                   COUNT(DISTINCT customer_unique_id) AS cohort_size
            FROM customer_first_purchase
            GROUP BY cohort_month
        ),
        retention_data AS (
            SELECT DATE_FORMAT(first_purchase_date, '%Y-%m') AS cohort_month,
                   months_since_first,
                   COUNT(DISTINCT customer_unique_id) AS returning_customers
            FROM customer_purchases
            GROUP BY cohort_month, months_since_first
        )
        SELECT r.cohort_month,
               r.months_since_first,
               cs.cohort_size,
               r.returning_customers,
               ROUND(r.returning_customers * 100.0 / cs.cohort_size, 2) AS retention_pct
        FROM retention_data r
        JOIN cohort_sizes cs ON r.cohort_month = cs.cohort_month
        WHERE r.months_since_first BETWEEN 0 AND 12
        ORDER BY r.cohort_month, r.months_since_first
    """)

    if not cohort_data.empty:
        # Pivot for heatmap
        pivot = cohort_data.pivot_table(
            index='cohort_month', columns='months_since_first',
            values='retention_pct', aggfunc='first'
        ).fillna(0)

        st.dataframe(pivot.style.background_gradient(cmap='YlGnBu', axis=None, vmin=0, vmax=20).format('{:.1f}%', na_rep=''))

        st.info("""
         **Key Finding**: The retention heatmap reveals extremely low repeat purchase rates 
        across all cohorts. Most cohorts show <3% retention after just 1 month, indicating 
        that Olist functions primarily as a one-time marketplace rather than a repeat-purchase platform.
        """)

    # Customer order frequency distribution
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(" Order Frequency Distribution")
        freq = run_query("""
            SELECT order_count, COUNT(*) AS customers FROM (
                SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_count
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                WHERE o.order_status = 'delivered'
                GROUP BY c.customer_unique_id
            ) t GROUP BY order_count ORDER BY order_count LIMIT 10
        """)
        if not freq.empty:
            st.bar_chart(freq, x='order_count', y='customers', color='#3498db')

    with col2:
        st.subheader(" Cohort Size Over Time")
        cohort_sizes = run_query("""
            SELECT DATE_FORMAT(MIN(o.order_purchase_timestamp), '%Y-%m') AS cohort_month,
                   COUNT(DISTINCT c.customer_unique_id) AS new_customers
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            GROUP BY c.customer_unique_id
            HAVING cohort_month IS NOT NULL
            ORDER BY cohort_month
        """)
        if not cohort_sizes.empty:
            # Aggregate by month
            cohort_agg = cohort_sizes.groupby('cohort_month')['new_customers'].sum().reset_index()
            st.area_chart(cohort_agg, x='cohort_month', y='new_customers', color='#2ecc71')


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: RFM SEGMENTATION
# ═══════════════════════════════════════════════════════════════════════════════
elif page == " RFM Segmentation":
    st.title(" RFM Customer Segmentation")

    rfm_data = run_query("""
        WITH customer_rfm AS (
            SELECT
                c.customer_unique_id,
                DATEDIFF('2018-10-17', MAX(o.order_purchase_timestamp)) AS recency_days,
                COUNT(DISTINCT o.order_id) AS frequency,
                ROUND(SUM(oi.price + oi.freight_value), 2) AS monetary
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id
        ),
        rfm_scored AS (
            SELECT *,
                NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
                NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
                NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
            FROM customer_rfm
        )
        SELECT *,
            CASE
                WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
                WHEN f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
                WHEN r_score >= 3 AND f_score >= 2 THEN 'Potential Loyalists'
                WHEN r_score >= 4 AND f_score = 1 THEN 'Recent Customers'
                WHEN r_score >= 3 AND f_score = 1 AND m_score >= 2 THEN 'Promising'
                WHEN r_score = 2 AND f_score >= 2 AND m_score >= 2 THEN 'Need Attention'
                WHEN r_score = 2 AND f_score <= 2 THEN 'About to Sleep'
                WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
                WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'Cant Lose Them'
                WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Hibernating'
                WHEN r_score = 1 AND f_score = 1 THEN 'Lost'
                ELSE 'Other'
            END AS segment
        FROM rfm_scored
    """)

    if not rfm_data.empty:
        # Segment summary
        segment_summary = rfm_data.groupby('segment').agg(
            customers=('customer_unique_id', 'count'),
            avg_recency=('recency_days', 'mean'),
            avg_frequency=('frequency', 'mean'),
            avg_monetary=('monetary', 'mean'),
            total_revenue=('monetary', 'sum')
        ).reset_index().sort_values('total_revenue', ascending=False)

        segment_summary['pct'] = (segment_summary['customers'] / segment_summary['customers'].sum() * 100).round(1)

        # KPI row
        c1, c2, c3 = st.columns(3)
        c1.metric(" Total Segments", len(segment_summary))
        c2.metric(" Top Segment", segment_summary.iloc[0]['segment'])
        c3.metric(" Revenue Concentration",
                  f"Top 20% = {rfm_data.nlargest(int(len(rfm_data)*0.2), 'monetary')['monetary'].sum() / rfm_data['monetary'].sum() * 100:.0f}%")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(" Segment Distribution")
            st.bar_chart(segment_summary, x='segment', y='customers')

        with col2:
            st.subheader(" Revenue by Segment")
            st.bar_chart(segment_summary.head(10), x='segment', y='total_revenue')

        # RFM scatter plot
        st.subheader(" RFM Scatter: Recency vs Monetary (sized by Frequency)")
        sample = rfm_data.sample(min(2000, len(rfm_data)), random_state=42)
        st.scatter_chart(sample, x='recency_days', y='monetary', color='segment', size='frequency')

        # Segment detail table
        st.subheader(" Segment Details")
        display_df = segment_summary.copy()
        display_df.columns = ['Segment', 'Customers', 'Avg Recency (days)',
                              'Avg Frequency', 'Avg Monetary (R$)', 'Total Revenue (R$)', '% of Total']
        display_df['Avg Recency (days)'] = display_df['Avg Recency (days)'].round(0)
        display_df['Avg Frequency'] = display_df['Avg Frequency'].round(2)
        display_df['Avg Monetary (R$)'] = display_df['Avg Monetary (R$)'].round(2)
        display_df['Total Revenue (R$)'] = display_df['Total Revenue (R$)'].round(0)
        st.dataframe(display_df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SATISFACTION DRIVERS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == " Satisfaction Drivers":
    st.title(" Customer Satisfaction Drivers")

    col1, col2 = st.columns(2)

    with col1:
        # Review score distribution
        st.subheader(" Review Score Distribution")
        scores = run_query("""
            SELECT review_score, COUNT(*) AS count,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM order_reviews), 1) AS pct
            FROM order_reviews GROUP BY review_score ORDER BY review_score
        """)
        if not scores.empty:
            st.bar_chart(scores, x='review_score', y='count')

    with col2:
        # Delivery delay vs review score — THE KEY CHART
        st.subheader(" Delivery Delay → Review Score (Key Finding)")
        delay_score = run_query("""
            SELECT
                CASE
                    WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) < -5 THEN '1. Early >5d'
                    WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) BETWEEN -5 AND -1 THEN '2. Early 1-5d'
                    WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) = 0 THEN '3. On Time'
                    WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) BETWEEN 1 AND 7 THEN '4. Late 1-7d'
                    WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) BETWEEN 8 AND 14 THEN '5. Late 8-14d'
                    ELSE '6. Late 15+d'
                END AS delay_bucket,
                ROUND(AVG(r.review_score), 2) AS avg_score,
                COUNT(*) AS orders
            FROM orders o
            JOIN order_reviews r ON o.order_id = r.order_id
            WHERE o.order_delivered_customer_date IS NOT NULL
              AND o.order_estimated_delivery_date IS NOT NULL
            GROUP BY delay_bucket
            ORDER BY delay_bucket
        """)
        if not delay_score.empty:
            st.bar_chart(delay_score, x='delay_bucket', y='avg_score')

    # Score drop callout
    if not delay_score.empty:
        early_score = delay_score[delay_score['delay_bucket'].str.contains('Early|On Time')]['avg_score'].mean()
        late_score = delay_score[delay_score['delay_bucket'].str.contains('Late')]['avg_score'].mean()
        drop = round(early_score - late_score, 2)
        st.error(f"""
         **Key Finding**: Late deliveries cause a **{drop}-point drop** in review scores 
        (avg {early_score:.2f} for on-time vs {late_score:.2f} for late). 
        This is the single strongest driver of negative reviews.
        """)

    # Category satisfaction
    st.subheader(" Satisfaction by Product Category (Top 15)")
    cat_sat = run_query("""
        SELECT
            COALESCE(pct.product_category_name_english, 'Other') AS category,
            COUNT(*) AS orders,
            ROUND(AVG(r.review_score), 2) AS avg_score,
            ROUND(SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS negative_pct,
            ROUND(AVG(DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date)), 1) AS avg_delay
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN product_category_translation pct ON p.product_category_name = pct.product_category_name
        JOIN order_reviews r ON o.order_id = r.order_id
        WHERE o.order_delivered_customer_date IS NOT NULL
        GROUP BY category
        HAVING orders >= 50
        ORDER BY avg_score ASC LIMIT 15
    """)
    if not cat_sat.empty:
        st.bar_chart(cat_sat.set_index('category')['avg_score'])

    # Monthly satisfaction trend
    st.subheader(" Monthly Satisfaction Trend")
    monthly_sat = run_query("""
        SELECT DATE_FORMAT(review_creation_date, '%Y-%m') AS month,
               ROUND(AVG(review_score), 2) AS avg_score,
               COUNT(*) AS reviews
        FROM order_reviews
        GROUP BY month ORDER BY month
    """)
    if not monthly_sat.empty:
        st.line_chart(monthly_sat.set_index('month')['avg_score'])


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: INSIGHTS & RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == " Insights & Recommendations":
    st.title(" Key Insights & Product Recommendations")

    # Pull real numbers for the recommendations
    delay_impact = run_query("""
        SELECT
            ROUND(AVG(CASE WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) <= 0
                           THEN r.review_score END), 2) AS ontime_score,
            ROUND(AVG(CASE WHEN DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date) > 0
                           THEN r.review_score END), 2) AS late_score,
            ROUND(SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END)
                  * 100.0 / COUNT(*), 1) AS late_pct
        FROM orders o
        JOIN order_reviews r ON o.order_id = r.order_id
        WHERE o.order_delivered_customer_date IS NOT NULL
          AND o.order_estimated_delivery_date IS NOT NULL
    """)

    repeat_rate_data = run_query("""
        SELECT ROUND(SUM(CASE WHEN cnt >= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS rate FROM (
            SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS cnt
            FROM customers c JOIN orders o ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered' GROUP BY c.customer_unique_id
        ) t
    """)

    if not delay_impact.empty:
        ontime = delay_impact['ontime_score'].iloc[0]
        late = delay_impact['late_score'].iloc[0]
        drop = round(ontime - late, 2)
        late_pct = delay_impact['late_pct'].iloc[0]
        repeat_rate = repeat_rate_data['rate'].iloc[0] if not repeat_rate_data.empty else 'N/A'

    # Recommendation 1
    st.markdown("---")
    st.subheader(" Recommendation 1: Improve Delivery Promise Accuracy")
    c1, c2, c3 = st.columns(3)
    c1.metric("On-Time Score", f"{ontime}/5")
    c2.metric("Late Score", f"{late}/5", delta=f"-{drop} points")
    c3.metric("Late Delivery Rate", f"{late_pct}%")
    st.markdown(f"""
    **Finding**: Late deliveries cause a **{drop}-point drop** in review scores. 
    Currently **{late_pct}%** of orders arrive after the promised date.

    **Action**: Add a 2-3 day buffer to delivery estimates, especially for orders shipped 
    to Northern/Northeastern states. Under-promise and over-deliver.

    **Expected Impact**: If half of currently-late orders perceived as "on time" with better estimates, 
    the platform-wide average review score would increase by ~0.3 points.
    """)

    # Recommendation 2
    st.markdown("---")
    st.subheader(" Recommendation 2: Drive Repeat Purchases")
    c1, c2, c3 = st.columns(3)
    c1.metric("Repeat Rate", f"{repeat_rate}%")
    c2.metric("Industry Benchmark", "20-30%")
    c3.metric("Gap", f"{round(20 - float(repeat_rate), 1)}pp")
    st.markdown(f"""
    **Finding**: Only **{repeat_rate}%** of customers make a repeat purchase — far below 
    the e-commerce industry benchmark of 20-30%.

    **Action**: 
    - Implement automated post-purchase email sequences (30/60/90 days)
    - Offer first-repeat-purchase discount codes to "Recent Customer" RFM segments
    - Create product recommendation engine based on first purchase category

    **Expected Impact**: Even a 1-2 percentage point increase in repeat rate at current AOV 
    would generate significant incremental revenue.
    """)

    # Recommendation 3
    st.markdown("---")
    st.subheader(" Recommendation 3: Fix High-Delay Product Categories")
    worst_cats = run_query("""
        SELECT COALESCE(pct.product_category_name_english, 'Other') AS category,
               COUNT(*) AS orders,
               ROUND(AVG(r.review_score), 2) AS avg_score,
               ROUND(AVG(DATEDIFF(o.order_delivered_customer_date, o.order_estimated_delivery_date)), 1) AS avg_delay
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN product_category_translation pct ON p.product_category_name = pct.product_category_name
        JOIN order_reviews r ON o.order_id = r.order_id
        WHERE o.order_delivered_customer_date IS NOT NULL
        GROUP BY category HAVING orders >= 100
        ORDER BY avg_delay DESC LIMIT 5
    """)
    if not worst_cats.empty:
        st.dataframe(worst_cats, use_container_width=True, hide_index=True)
        st.markdown("""
        **Finding**: Certain product categories consistently have higher delivery delays 
        and corresponding lower review scores.

        **Action**: 
        - Work with sellers in these categories to set realistic shipping SLAs
        - Consider category-specific delivery estimate buffers
        - Prioritize seller onboarding for categories with fastest fulfillment
        """)

    # Recommendation 4
    st.markdown("---")
    st.subheader(" Recommendation 4: Geographic Logistics Optimization")
    state_gap = run_query("""
        SELECT c.customer_state,
               ROUND(AVG(DATEDIFF(o.order_delivered_customer_date, o.order_purchase_timestamp)), 1) AS avg_days,
               ROUND(SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END)
                     * 100.0 / COUNT(*), 1) AS late_pct,
               COUNT(*) AS orders
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_delivered_customer_date IS NOT NULL
          AND o.order_estimated_delivery_date IS NOT NULL
        GROUP BY c.customer_state HAVING orders >= 100
        ORDER BY late_pct DESC LIMIT 5
    """)
    if not state_gap.empty:
        st.dataframe(state_gap, use_container_width=True, hide_index=True)
        st.markdown("""
        **Finding**: Northern/Northeastern states experience 2-3x higher late delivery rates 
        than Southern states like SP and PR.

        **Action**: 
        - Open regional fulfillment centers in underserved regions
        - Partner with local carriers for last-mile delivery
        - Adjust delivery estimates by region to set accurate expectations
        """)

    # Resume bullets
    st.markdown("---")
    st.subheader(" Resume Bullets")
    st.code(f"""
• Designed a relational schema in MySQL for 100K+ orders across 8 tables 
  and wrote CTE/window-function queries to analyse the order funnel, 
  cancellations and delivery delays.

• Built monthly cohort retention and RFM segmentation models, finding 
  that only {repeat_rate}% of customers made a repeat purchase and 
  identifying high-value segments for targeting.

• Quantified the impact of delivery delay on review scores ({drop}-point 
  drop for late orders) and recommended 4 product changes, presented 
  through a Streamlit dashboard.
    """, language="text")


# ─── Footer ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Olist E-Commerce Analytics Dashboard | Data: Kaggle Olist Dataset | Built with Python, MySQL, Streamlit")
