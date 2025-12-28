"""
================================================================================
PORTFOLIO MONITOR - STREAMLIT DASHBOARD
================================================================================
Free web dashboard for your portfolio
Deploy on Streamlit Cloud for free!
================================================================================
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import os

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Portfolio Monitor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS
# ============================================================================

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .positive { color: #28a745; font-weight: bold; }
    .negative { color: #dc3545; font-weight: bold; }
    .status-ok { 
        background-color: #d4edda; 
        color: #155724; 
        padding: 0.25rem 0.5rem; 
        border-radius: 5px; 
    }
    .status-warning { 
        background-color: #fff3cd; 
        color: #856404; 
        padding: 0.25rem 0.5rem; 
        border-radius: 5px; 
    }
    .status-critical { 
        background-color: #f8d7da; 
        color: #721c24; 
        padding: 0.25rem 0.5rem; 
        border-radius: 5px; 
    }
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ist_now():
    """Get current IST time"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_hours():
    """Check if market is open"""
    ist_now = get_ist_now()
    if ist_now.weekday() >= 5:
        return False
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    return market_open <= ist_now.time() <= market_close

def get_market_status():
    """Get market status"""
    ist_now = get_ist_now()
    if ist_now.weekday() >= 5:
        return "🔴 WEEKEND", "Markets closed"
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    current_time = ist_now.time()
    
    if current_time < market_open:
        return "🟡 PRE-MARKET", f"Opens at 09:15 IST"
    elif current_time > market_close:
        return "🔴 CLOSED", "Market closed"
    else:
        return "🟢 OPEN", f"Closes at 15:30 IST"

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    """Calculate MACD"""
    exp12 = prices.ewm(span=12, adjust=False).mean()
    exp26 = prices.ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal

def calculate_trend(prices, period=20):
    """Calculate trend"""
    sma = prices.rolling(window=period).mean()
    above_sma = (prices > sma).astype(int)
    trend_consistency = above_sma.rolling(window=period).mean().iloc[-1]
    direction = "BULLISH" if trend_consistency > 0.5 else "BEARISH"
    strength = trend_consistency * 100 if direction == "BULLISH" else (1 - trend_consistency) * 100
    return direction, strength

@st.cache_data(ttl=60)  # Cache for 60 seconds
def fetch_stock_data(symbol):
    """Fetch stock data with caching"""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="3mo")
        if df.empty:
            symbol = symbol.replace('.NS', '.BO')
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
        return df
    except:
        return None

def analyze_position(row):
    """Analyze a single position"""
    ticker = str(row['Ticker'])
    symbol = ticker if '.NS' in ticker else f"{ticker}.NS"
    position_type = str(row['Position']).upper()
    entry_price = float(row['Entry_Price'])
    quantity = int(row.get('Quantity', 1))
    stop_loss = float(row['Stop_Loss'])
    target1 = float(row['Target_1'])
    target2 = float(row.get('Target_2', target1 * 1.1))
    
    df = fetch_stock_data(symbol)
    if df is None or df.empty:
        return None
    
    df.reset_index(inplace=True)
    current_price = float(df['Close'].iloc[-1])
    
    # Calculate P&L
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
        distance_to_sl = ((current_price - stop_loss) / current_price) * 100
        distance_to_t1 = ((target1 - current_price) / current_price) * 100
    else:
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
        distance_to_sl = ((stop_loss - current_price) / current_price) * 100
        distance_to_t1 = ((current_price - target1) / current_price) * 100
    
    # Technical indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    trend_dir, trend_str = calculate_trend(df['Close'])
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1])
    
    # Generate alerts
    alerts = []
    
    # Stop loss check
    sl_hit = (position_type == "LONG" and current_price <= stop_loss) or \
             (position_type == "SHORT" and current_price >= stop_loss)
    if sl_hit:
        alerts.append(("CRITICAL", "STOP LOSS HIT", "Exit immediately"))
    
    # Target checks
    if position_type == "LONG":
        if current_price >= target2:
            alerts.append(("HIGH", "TARGET 2 HIT", "Book full profits"))
        elif current_price >= target1:
            alerts.append(("MEDIUM", "TARGET 1 HIT", "Book 50% profits"))
    else:
        if current_price <= target2:
            alerts.append(("HIGH", "TARGET 2 HIT", "Book full profits"))
        elif current_price <= target1:
            alerts.append(("MEDIUM", "TARGET 1 HIT", "Book 50% profits"))
    
    # RSI alerts
    if rsi > 70:
        alerts.append(("MEDIUM", "RSI OVERBOUGHT", "Consider taking profits"))
    elif rsi < 30:
        alerts.append(("MEDIUM", "RSI OVERSOLD", "Watch for bounce"))
    
    # Determine status
    if any(a[0] == 'CRITICAL' for a in alerts):
        status = 'CRITICAL'
    elif any(a[0] == 'HIGH' for a in alerts):
        status = 'WARNING'
    elif alerts:
        status = 'INFO'
    else:
        status = 'OK'
    
    return {
        'ticker': ticker,
        'position_type': position_type,
        'entry_price': entry_price,
        'current_price': current_price,
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        'quantity': quantity,
        'pnl_percent': pnl_percent,
        'pnl_amount': pnl_amount,
        'distance_to_sl': distance_to_sl,
        'distance_to_t1': distance_to_t1,
        'rsi': rsi,
        'trend': trend_dir,
        'trend_strength': trend_str,
        'macd_histogram': macd_hist,
        'alerts': alerts,
        'status': status,
        'df': df  # For chart
    }

def load_portfolio():
    """Load portfolio from Excel or create sample"""
    try:
        if os.path.exists('my_portfolio.xlsx'):
            df = pd.read_excel('my_portfolio.xlsx', sheet_name='Portfolio')
            if 'Status' in df.columns:
                df = df[df['Status'].str.upper() == 'ACTIVE']
            return df
    except:
        pass
    
    # Return sample data if file not found
    return pd.DataFrame({
        'Ticker': ['RELIANCE', 'TCS', 'INFY'],
        'Position': ['LONG', 'LONG', 'SHORT'],
        'Entry_Price': [1550.00, 3280.00, 1650.00],
        'Quantity': [10, 5, 8],
        'Stop_Loss': [1500.00, 3200.00, 1720.00],
        'Target_1': [1650.00, 3400.00, 1550.00],
        'Target_2': [1750.00, 3500.00, 1450.00],
        'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE']
    })

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">📊 Portfolio Monitor</h1>', unsafe_allow_html=True)
    
    # Market status and time
    market_status, market_msg = get_market_status()
    ist_now = get_ist_now()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.markdown(f"### {market_status}")
        st.caption(market_msg)
    with col2:
        st.markdown(f"### 🕐 {ist_now.strftime('%H:%M:%S')} IST")
        st.caption(ist_now.strftime('%A, %B %d, %Y'))
    with col3:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()
    
    st.divider()
    
    # Load portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.warning("No positions found. Please add positions to my_portfolio.xlsx")
        return
    
    # Analyze all positions
    with st.spinner("Analyzing positions..."):
        results = []
        for _, row in portfolio.iterrows():
            result = analyze_position(row)
            if result:
                results.append(result)
    
    if not results:
        st.error("Could not fetch stock data. Please try again later.")
        return
    
    # Summary metrics
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['entry_price'] * r['quantity'] for r in results)
    total_alerts = sum(len(r['alerts']) for r in results)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric(
            label="💰 Total P&L",
            value=f"₹{total_pnl:+,.2f}",
            delta=f"{(total_pnl/total_invested*100):+.2f}%" if total_invested > 0 else "0%"
        )
    
    with col2:
        st.metric(
            label="📊 Positions",
            value=len(results)
        )
    
    with col3:
        st.metric(
            label="🔔 Alerts",
            value=total_alerts,
            delta="Action needed" if total_alerts > 0 else "All clear"
        )
    
    with col4:
        winning = sum(1 for r in results if r['pnl_percent'] > 0)
        st.metric(
            label="📈 Win Rate",
            value=f"{winning}/{len(results)}",
            delta=f"{winning/len(results)*100:.0f}%"
        )
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Positions", "📈 Charts", "🔔 Alerts", "⚙️ Settings"])
    
    # ============ POSITIONS TAB ============
    with tab1:
        st.subheader("Your Positions")
        
        for result in results:
            with st.expander(
                f"{'🟢' if result['status'] == 'OK' else '🟡' if result['status'] == 'INFO' else '🔴'} "
                f"**{result['ticker']}** | "
                f"{'LONG 📈' if result['position_type'] == 'LONG' else 'SHORT 📉'} | "
                f"P&L: {result['pnl_percent']:+.2f}%",
                expanded=result['status'] in ['CRITICAL', 'WARNING']
            ):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("##### Price Info")
                    st.write(f"**Entry:** ₹{result['entry_price']:,.2f}")
                    st.write(f"**Current:** ₹{result['current_price']:,.2f}")
                    st.write(f"**Quantity:** {result['quantity']}")
                    
                    pnl_color = "green" if result['pnl_percent'] >= 0 else "red"
                    st.markdown(f"**P&L:** <span style='color:{pnl_color};font-weight:bold;'>"
                               f"₹{result['pnl_amount']:+,.2f} ({result['pnl_percent']:+.2f}%)</span>",
                               unsafe_allow_html=True)
                
                with col2:
                    st.markdown("##### Levels")
                    st.write(f"**Stop Loss:** ₹{result['stop_loss']:,.2f} ({result['distance_to_sl']:.1f}% away)")
                    st.write(f"**Target 1:** ₹{result['target1']:,.2f} ({result['distance_to_t1']:.1f}% away)")
                    st.write(f"**Target 2:** ₹{result['target2']:,.2f}")
                    
                    # Progress bar to target
                    if result['position_type'] == 'LONG':
                        progress = (result['current_price'] - result['stop_loss']) / (result['target1'] - result['stop_loss'])
                    else:
                        progress = (result['stop_loss'] - result['current_price']) / (result['stop_loss'] - result['target1'])
                    progress = max(0, min(1, progress))
                    st.progress(progress, text=f"Progress to Target 1: {progress*100:.0f}%")
                
                with col3:
                    st.markdown("##### Indicators")
                    
                    # RSI with color
                    rsi_color = "🔴" if result['rsi'] > 70 else "🟢" if result['rsi'] < 30 else "🟡"
                    st.write(f"**RSI:** {rsi_color} {result['rsi']:.1f}")
                    
                    # Trend
                    trend_icon = "📈" if result['trend'] == 'BULLISH' else "📉"
                    st.write(f"**Trend:** {trend_icon} {result['trend']} ({result['trend_strength']:.0f}%)")
                    
                    # MACD
                    macd_icon = "🟢" if result['macd_histogram'] > 0 else "🔴"
                    st.write(f"**MACD:** {macd_icon} {result['macd_histogram']:.2f}")
                
                # Alerts for this position
                if result['alerts']:
                    st.markdown("##### ⚠️ Alerts")
                    for priority, alert_type, action in result['alerts']:
                        if priority == 'CRITICAL':
                            st.error(f"**{alert_type}**: {action}")
                        elif priority == 'HIGH':
                            st.warning(f"**{alert_type}**: {action}")
                        else:
                            st.info(f"**{alert_type}**: {action}")
    
    # ============ CHARTS TAB ============
    with tab2:
        st.subheader("Price Charts")
        
        selected_stock = st.selectbox(
            "Select Stock",
            options=[r['ticker'] for r in results]
        )
        
        # Find selected result
        selected_result = next((r for r in results if r['ticker'] == selected_stock), None)
        
        if selected_result and 'df' in selected_result:
            df = selected_result['df']
            
            # Create candlestick chart
            fig = go.Figure()
            
            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df['Date'],
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Price'
            ))
            
            # Add entry price line
            fig.add_hline(
                y=selected_result['entry_price'],
                line_dash="dash",
                line_color="blue",
                annotation_text=f"Entry: ₹{selected_result['entry_price']:.2f}"
            )
            
            # Add stop loss line
            fig.add_hline(
                y=selected_result['stop_loss'],
                line_dash="dash",
                line_color="red",
                annotation_text=f"SL: ₹{selected_result['stop_loss']:.2f}"
            )
            
            # Add target line
            fig.add_hline(
                y=selected_result['target1'],
                line_dash="dash",
                line_color="green",
                annotation_text=f"T1: ₹{selected_result['target1']:.2f}"
            )
            
            fig.update_layout(
                title=f"{selected_stock} - Price Chart",
                yaxis_title="Price (₹)",
                xaxis_title="Date",
                height=500,
                xaxis_rangeslider_visible=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # RSI Chart
            rsi_series = calculate_rsi(df['Close'])
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=df['Date'], y=rsi_series, mode='lines', name='RSI'))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
            fig_rsi.update_layout(title="RSI (14)", height=200, yaxis_range=[0, 100])
            st.plotly_chart(fig_rsi, use_container_width=True)
    
    # ============ ALERTS TAB ============
    with tab3:
        st.subheader("All Alerts")
        
        all_alerts = []
        for r in results:
            for priority, alert_type, action in r['alerts']:
                all_alerts.append({
                    'Ticker': r['ticker'],
                    'Priority': priority,
                    'Alert': alert_type,
                    'Action': action,
                    'P&L': f"{r['pnl_percent']:+.2f}%"
                })
        
        if all_alerts:
            df_alerts = pd.DataFrame(all_alerts)
            st.dataframe(df_alerts, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No alerts! All positions are healthy.")
    
    # ============ SETTINGS TAB ============
    with tab4:
        st.subheader("Portfolio Settings")
        
        st.markdown("### Current Positions")
        st.dataframe(portfolio, use_container_width=True, hide_index=True)
        
        st.markdown("### Add/Edit Positions")
        st.info("To add or edit positions, update the `my_portfolio.xlsx` file in your repository.")
        
        # Sample format
        st.markdown("### Excel Format")
        sample_df = pd.DataFrame({
            'Ticker': ['RELIANCE'],
            'Position': ['LONG'],
            'Entry_Price': [1550.00],
            'Quantity': [10],
            'Stop_Loss': [1500.00],
            'Target_1': [1650.00],
            'Target_2': [1750.00],
            'Status': ['ACTIVE']
        })
        st.dataframe(sample_df, use_container_width=True, hide_index=True)
        
        st.markdown("### Auto-Refresh")
        auto_refresh = st.checkbox("Enable auto-refresh (every 60 seconds)", value=False)
        
        if auto_refresh:
            st.caption("Page will refresh automatically...")
            import time
            time.sleep(60)
            st.rerun()

# ============================================================================
# RUN APP
# ============================================================================

if __name__ == "__main__":
    main()
