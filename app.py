"""
================================================================================
🧠 SMART PORTFOLIO MONITOR v5.1 - COMPLETE FIXED EDITION
================================================================================
ALL FEATURES INCLUDED & FIXED:
✅ Alert when SL hits
✅ Alert when target hits
✅ Warn BEFORE SL hits (Predictive)
✅ Hold recommendation after target
✅ Dynamic target calculation
✅ Momentum scoring (0-100)
✅ Volume confirmation
✅ Support/Resistance detection
✅ Trail stop suggestion (FIXED - uses sidebar threshold)
✅ Risk scoring (0-100)
✅ Auto-refresh during market hours (FIXED - non-blocking)
✅ Email alerts for critical events
✅ Multi-Timeframe Analysis (NEW - fully implemented)
✅ Better caching (FIXED - 15s TTL)
================================================================================
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json

# Try to import streamlit-autorefresh (optional but recommended)
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Smart Portfolio Monitor v5.1",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
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
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .critical-box {
        background: linear-gradient(135deg, #dc3545, #c82333);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .success-box {
        background: linear-gradient(135deg, #28a745, #218838);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .warning-box {
        background: linear-gradient(135deg, #ffc107, #e0a800);
        color: black;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .info-box {
        background: linear-gradient(135deg, #17a2b8, #138496);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .score-high { color: #28a745; font-weight: bold; }
    .score-medium { color: #ffc107; font-weight: bold; }
    .score-low { color: #dc3545; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR - SETTINGS
# ============================================================================

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    
    # Email Configuration
    st.markdown("### 📧 Email Alerts")
    email_enabled = st.checkbox("Enable Email Alerts", value=False)
    
    if email_enabled:
        sender_email = st.text_input("Your Gmail", placeholder="you@gmail.com")
        sender_password = st.text_input("App Password", type="password", 
                                        help="Use Gmail App Password, not regular password")
        recipient_email = st.text_input("Send Alerts To", value=sender_email)
    else:
        sender_email = ""
        sender_password = ""
        recipient_email = ""
    
    st.divider()
    
    # Auto-Refresh
    st.markdown("### 🔄 Auto-Refresh")
    auto_refresh = st.checkbox("Enable Auto-Refresh", value=True,
                              help="Auto-refresh during market hours")
    refresh_interval = st.slider("Refresh Interval (seconds)", 30, 300, 60)
    
    if not HAS_AUTOREFRESH:
        st.warning("⚠️ Install `streamlit-autorefresh` for better auto-refresh:\n`pip install streamlit-autorefresh`")
    
    st.divider()
    
    # Alert Thresholds
    st.markdown("### 🎯 Alert Thresholds")
    loss_threshold = st.slider("Alert on Loss %", -10.0, 0.0, -2.0, 
                               help="Alert when loss exceeds this")
    profit_threshold = st.slider("Alert on Profit %", 0.0, 20.0, 5.0,
                                help="Alert when profit exceeds this")
    trail_sl_trigger = st.slider("Trail SL after Profit %", 0.5, 10.0, 2.0, step=0.5,
                                help="Start trailing SL after this profit %")
    sl_risk_threshold = st.slider("SL Risk Alert Threshold", 30, 90, 50,
                                 help="Alert when SL risk score exceeds this")
    
    st.divider()
    
    # Analysis Settings
    st.markdown("### 📊 Analysis Settings")
    enable_volume_analysis = st.checkbox("Volume Confirmation", value=True)
    enable_sr_detection = st.checkbox("Support/Resistance", value=True)
    enable_multi_timeframe = st.checkbox("Multi-Timeframe Analysis", value=True,
                                        help="Analyze Daily, Weekly, Hourly trends")
    
    st.divider()
    
    # Debug Info
    with st.expander("🔧 Debug Info"):
        st.write(f"Auto-refresh library: {'✅ Installed' if HAS_AUTOREFRESH else '❌ Not installed'}")
        st.write(f"Refresh interval: {refresh_interval}s")
        st.write(f"Trail SL trigger: {trail_sl_trigger}%")
        st.write(f"SL Risk threshold: {sl_risk_threshold}%")

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
        return False, "WEEKEND", "Markets closed for weekend", "🔴"
    
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    current_time = ist_now.time()
    
    if current_time < market_open:
        return False, "PRE-MARKET", f"Opens at 09:15 IST", "🟡"
    elif current_time > market_close:
        return False, "CLOSED", "Market closed for today", "🔴"
    else:
        return True, "OPEN", f"Closes at 15:30 IST", "🟢"

def send_email_alert(subject, html_content, sender, password, recipient):
    """Send email alert"""
    if not sender or not password or not recipient:
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email failed: {e}")
        return False

# ============================================================================
# TECHNICAL ANALYSIS FUNCTIONS
# ============================================================================

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_atr(high, low, close, period=14):
    """Calculate Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_ema(prices, period):
    """Calculate EMA"""
    return prices.ewm(span=period, adjust=False).mean()

def calculate_sma(prices, period):
    """Calculate SMA"""
    return prices.rolling(window=period).mean()

def calculate_adx(high, low, close, period=14):
    """Calculate ADX (Average Directional Index)"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    up_move = high - high.shift()
    down_move = close.shift() - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx

# ============================================================================
# VOLUME ANALYSIS ✅
# ============================================================================

def analyze_volume(df):
    """
    Analyze volume to confirm price movements
    Returns: volume_signal, volume_ratio, description, volume_trend
    """
    if 'Volume' not in df.columns or df['Volume'].iloc[-1] == 0:
        return "NEUTRAL", 1.0, "Volume data not available", "NEUTRAL"
    
    # Calculate average volume (20-day)
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    # Get price direction
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    price_change_pct = (price_change / df['Close'].iloc[-2]) * 100
    
    # Volume trend (is volume increasing?)
    vol_5d = df['Volume'].tail(5).mean()
    vol_20d = df['Volume'].tail(20).mean()
    volume_trend = "INCREASING" if vol_5d > vol_20d else "DECREASING"
    
    # Determine signal
    if price_change > 0 and volume_ratio > 1.5:
        signal = "STRONG_BUYING"
        desc = f"Strong buying pressure ({volume_ratio:.1f}x avg volume)"
    elif price_change > 0 and volume_ratio > 1.0:
        signal = "BUYING"
        desc = f"Buying with good volume ({volume_ratio:.1f}x)"
    elif price_change > 0 and volume_ratio < 0.7:
        signal = "WEAK_BUYING"
        desc = f"Weak rally, low volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio > 1.5:
        signal = "STRONG_SELLING"
        desc = f"Strong selling pressure ({volume_ratio:.1f}x avg volume)"
    elif price_change < 0 and volume_ratio > 1.0:
        signal = "SELLING"
        desc = f"Selling with volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio < 0.7:
        signal = "WEAK_SELLING"
        desc = f"Weak decline, low volume ({volume_ratio:.1f}x)"
    else:
        signal = "NEUTRAL"
        desc = f"Normal volume ({volume_ratio:.1f}x)"
    
    return signal, volume_ratio, desc, volume_trend

# ============================================================================
# SUPPORT/RESISTANCE DETECTION ✅
# ============================================================================

def find_support_resistance(df, lookback=60):
    """
    Find key support and resistance levels
    Returns: dictionary with support/resistance info
    """
    if len(df) < lookback:
        lookback = len(df)
    
    if lookback < 10:
        current_price = df['Close'].iloc[-1]
        return {
            'support_levels': [],
            'resistance_levels': [],
            'nearest_support': current_price * 0.95,
            'nearest_resistance': current_price * 1.05,
            'distance_to_support': 5.0,
            'distance_to_resistance': 5.0
        }
    
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    close = df['Close'].tail(lookback)
    current_price = float(close.iloc[-1])
    
    # Find pivot highs and lows
    pivot_highs = []
    pivot_lows = []
    
    for i in range(2, len(high) - 2):
        # Pivot high (local maximum)
        if (high.iloc[i] > high.iloc[i-1] and high.iloc[i] > high.iloc[i-2] and 
            high.iloc[i] > high.iloc[i+1] and high.iloc[i] > high.iloc[i+2]):
            pivot_highs.append(float(high.iloc[i]))
        
        # Pivot low (local minimum)
        if (low.iloc[i] < low.iloc[i-1] and low.iloc[i] < low.iloc[i-2] and 
            low.iloc[i] < low.iloc[i+1] and low.iloc[i] < low.iloc[i+2]):
            pivot_lows.append(float(low.iloc[i]))
    
    # Cluster nearby levels
    def cluster_levels(levels, threshold_pct=1.0):
        if not levels:
            return []
        levels = sorted(levels)
        clustered = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if (level - current_cluster[0]) / current_cluster[0] * 100 < threshold_pct:
                current_cluster.append(level)
            else:
                clustered.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [level]
        clustered.append(sum(current_cluster) / len(current_cluster))
        return clustered
    
    support_levels = cluster_levels(pivot_lows)
    resistance_levels = cluster_levels(pivot_highs)
    
    # Find nearest support (below current price)
    supports_below = [s for s in support_levels if s < current_price]
    nearest_support = max(supports_below) if supports_below else current_price * 0.95
    
    # Find nearest resistance (above current price)
    resistances_above = [r for r in resistance_levels if r > current_price]
    nearest_resistance = min(resistances_above) if resistances_above else current_price * 1.05
    
    return {
        'support_levels': support_levels[-5:] if support_levels else [],
        'resistance_levels': resistance_levels[-5:] if resistance_levels else [],
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'distance_to_support': ((current_price - nearest_support) / current_price) * 100,
        'distance_to_resistance': ((nearest_resistance - current_price) / current_price) * 100
    }

# ============================================================================
# MULTI-TIMEFRAME ANALYSIS ✅ (NEW - FULLY IMPLEMENTED)
# ============================================================================

def multi_timeframe_analysis(ticker, position_type):
    """
    Analyze multiple timeframes for trend confirmation
    Returns: signals dict, alignment_score, recommendation
    """
    symbol = ticker if '.NS' in str(ticker) else f"{ticker}.NS"
    
    try:
        stock = yf.Ticker(symbol)
        
        timeframes = {}
        
        # Daily timeframe (3 months)
        try:
            daily_df = stock.history(period="3mo", interval="1d")
            if len(daily_df) >= 20:
                timeframes['Daily'] = daily_df
        except:
            pass
        
        # Weekly timeframe (1 year)
        try:
            weekly_df = stock.history(period="1y", interval="1wk")
            if len(weekly_df) >= 10:
                timeframes['Weekly'] = weekly_df
        except:
            pass
        
        # Hourly timeframe (5 days) - only during market hours
        try:
            hourly_df = stock.history(period="5d", interval="1h")
            if len(hourly_df) >= 10:
                timeframes['Hourly'] = hourly_df
        except:
            pass
        
        if not timeframes:
            return {}, 50, "Unable to fetch multi-timeframe data"
        
        signals = {}
        details = {}
        
        for tf_name, df in timeframes.items():
            if len(df) >= 14:
                close = df['Close']
                current = float(close.iloc[-1])
                
                # Calculate indicators
                rsi = calculate_rsi(close).iloc[-1]
                sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
                ema_9 = close.ewm(span=9).mean().iloc[-1]
                
                # MACD
                macd, signal_line, histogram = calculate_macd(close)
                macd_hist = histogram.iloc[-1] if len(histogram) > 0 else 0
                
                # Trend determination
                bullish_count = 0
                bearish_count = 0
                
                if rsi > 50:
                    bullish_count += 1
                else:
                    bearish_count += 1
                
                if current > sma_20:
                    bullish_count += 1
                else:
                    bearish_count += 1
                
                if current > ema_9:
                    bullish_count += 1
                else:
                    bearish_count += 1
                
                if macd_hist > 0:
                    bullish_count += 1
                else:
                    bearish_count += 1
                
                # Determine signal
                if bullish_count >= 3:
                    signal = "BULLISH"
                    strength = "Strong" if bullish_count == 4 else "Moderate"
                elif bearish_count >= 3:
                    signal = "BEARISH"
                    strength = "Strong" if bearish_count == 4 else "Moderate"
                else:
                    signal = "NEUTRAL"
                    strength = "Weak"
                
                signals[tf_name] = signal
                details[tf_name] = {
                    'signal': signal,
                    'strength': strength,
                    'rsi': rsi,
                    'above_sma20': current > sma_20,
                    'above_ema9': current > ema_9,
                    'macd_bullish': macd_hist > 0
                }
        
        # Calculate alignment score
        if position_type == "LONG":
            aligned = sum(1 for s in signals.values() if s == "BULLISH")
            against = sum(1 for s in signals.values() if s == "BEARISH")
        else:  # SHORT
            aligned = sum(1 for s in signals.values() if s == "BEARISH")
            against = sum(1 for s in signals.values() if s == "BULLISH")
        
        total = len(signals)
        if total > 0:
            alignment_score = int((aligned / total) * 100)
        else:
            alignment_score = 50
        
        # Generate recommendation
        if alignment_score >= 80:
            recommendation = f"✅ All timeframes aligned with {position_type}"
        elif alignment_score >= 60:
            recommendation = f"👍 Most timeframes support {position_type}"
        elif alignment_score >= 40:
            recommendation = f"⚠️ Mixed signals across timeframes"
        else:
            recommendation = f"🚨 Timeframes against {position_type} position"
        
        return {
            'signals': signals,
            'details': details,
            'alignment_score': alignment_score,
            'recommendation': recommendation,
            'aligned_count': aligned,
            'against_count': against,
            'total_timeframes': total
        }
        
    except Exception as e:
        return {
            'signals': {},
            'details': {},
            'alignment_score': 50,
            'recommendation': f"Error: {str(e)}",
            'aligned_count': 0,
            'against_count': 0,
            'total_timeframes': 0
        }

# ============================================================================
# MOMENTUM SCORING (0-100) ✅
# ============================================================================

def calculate_momentum_score(df):
    """
    Calculate comprehensive momentum score (0-100)
    Higher = More bullish, Lower = More bearish
    """
    close = df['Close']
    score = 50  # Start neutral
    components = {}
    
    # 1. RSI Component (0-20 points)
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if rsi > 70:
        rsi_score = -10  # Overbought, might reverse
    elif rsi > 60:
        rsi_score = 15  # Bullish
    elif rsi > 50:
        rsi_score = 10  # Slightly bullish
    elif rsi > 40:
        rsi_score = -5  # Slightly bearish
    elif rsi > 30:
        rsi_score = -15  # Bearish
    else:
        rsi_score = 10  # Oversold, might bounce
    
    score += rsi_score
    components['RSI'] = rsi_score
    
    # 2. MACD Component (0-20 points)
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    
    if hist_current > 0:
        if hist_current > hist_prev:
            macd_score = 20  # Bullish and expanding
        else:
            macd_score = 10  # Bullish but contracting
    else:
        if hist_current < hist_prev:
            macd_score = -20  # Bearish and expanding
        else:
            macd_score = -10  # Bearish but contracting
    
    score += macd_score
    components['MACD'] = macd_score
    
    # 3. Moving Average Component (0-20 points)
    current_price = close.iloc[-1]
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma_20
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    
    ma_score = 0
    if current_price > ema_9:
        ma_score += 5
    if current_price > sma_20:
        ma_score += 5
    if current_price > sma_50:
        ma_score += 5
    if sma_20 > sma_50:
        ma_score += 5
    
    if current_price < ema_9:
        ma_score -= 5
    if current_price < sma_20:
        ma_score -= 5
    if current_price < sma_50:
        ma_score -= 5
    if sma_20 < sma_50:
        ma_score -= 5
    
    score += ma_score
    components['MA'] = ma_score
    
    # 4. Price Momentum (0-15 points)
    returns_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
    returns_10d = ((close.iloc[-1] / close.iloc[-11]) - 1) * 100 if len(close) > 11 else 0
    
    momentum_score = min(15, max(-15, returns_5d * 3))
    score += momentum_score
    components['Momentum'] = momentum_score
    
    # 5. Trend Strength (0-10 points)
    if sma_50 != 0:
        adx_approx = abs(sma_20 - sma_50) / sma_50 * 100  # Simplified trend strength
    else:
        adx_approx = 0
    
    if current_price > sma_20:
        trend_score = min(10, adx_approx * 2)
    else:
        trend_score = -min(10, adx_approx * 2)
    
    score += trend_score
    components['Trend'] = trend_score
    
    # Cap between 0-100
    final_score = max(0, min(100, score))
    
    # Determine trend direction
    if final_score >= 70:
        trend = "STRONG BULLISH"
    elif final_score >= 55:
        trend = "BULLISH"
    elif final_score >= 45:
        trend = "NEUTRAL"
    elif final_score >= 30:
        trend = "BEARISH"
    else:
        trend = "STRONG BEARISH"
    
    return final_score, trend, components

# ============================================================================
# STOP LOSS RISK PREDICTION (0-100) ✅
# ============================================================================

def predict_sl_risk(df, current_price, stop_loss, position_type, entry_price, sl_alert_threshold=50):
    """
    Predict likelihood of hitting stop loss
    Returns: risk_score (0-100), reasons, recommendation, priority
    """
    risk_score = 0
    reasons = []
    close = df['Close']
    
    # 1. Distance to Stop Loss (0-40 points)
    if position_type == "LONG":
        distance_pct = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_pct = ((stop_loss - current_price) / current_price) * 100
    
    if distance_pct < 0:  # Already hit SL
        risk_score = 100
        reasons.append("⚠️ SL already breached!")
    elif distance_pct < 1:
        risk_score += 40
        reasons.append(f"🔴 Very close to SL ({distance_pct:.1f}% away)")
    elif distance_pct < 2:
        risk_score += 30
        reasons.append(f"🟠 Close to SL ({distance_pct:.1f}% away)")
    elif distance_pct < 3:
        risk_score += 15
        reasons.append(f"🟡 Approaching SL ({distance_pct:.1f}% away)")
    elif distance_pct < 5:
        risk_score += 5
    
    # 2. Trend Against Position (0-25 points)
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma_20
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    
    if position_type == "LONG":
        if current_price < ema_9:
            risk_score += 8
            reasons.append("📉 Below EMA 9")
        if current_price < sma_20:
            risk_score += 10
            reasons.append("📉 Below SMA 20")
        if current_price < sma_50:
            risk_score += 7
            reasons.append("📉 Below SMA 50")
        if sma_20 < sma_50:
            risk_score += 5
            reasons.append("📉 Death cross forming")
    else:  # SHORT
        if current_price > ema_9:
            risk_score += 8
            reasons.append("📈 Above EMA 9")
        if current_price > sma_20:
            risk_score += 10
            reasons.append("📈 Above SMA 20")
        if current_price > sma_50:
            risk_score += 7
            reasons.append("📈 Above SMA 50")
        if sma_20 > sma_50:
            risk_score += 5
            reasons.append("📈 Golden cross forming")
    
    # 3. MACD Against Position (0-15 points)
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    
    if position_type == "LONG":
        if hist_current < 0:
            risk_score += 8
            reasons.append("📊 MACD bearish")
        if hist_current < hist_prev:
            risk_score += 7
            reasons.append("📊 MACD declining")
    else:
        if hist_current > 0:
            risk_score += 8
            reasons.append("📊 MACD bullish")
        if hist_current > hist_prev:
            risk_score += 7
            reasons.append("📊 MACD rising")
    
    # 4. RSI Extreme (0-10 points)
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if position_type == "LONG" and rsi < 35:
        risk_score += 10
        reasons.append(f"📉 RSI weak ({rsi:.0f})")
    elif position_type == "SHORT" and rsi > 65:
        risk_score += 10
        reasons.append(f"📈 RSI strong ({rsi:.0f})")
    
    # 5. Consecutive Candles Against Position (0-10 points)
    if len(close) >= 4:
        last_3 = close.tail(4).diff().dropna()
        if position_type == "LONG" and all(last_3 < 0):
            risk_score += 10
            reasons.append("🕯️ 3 consecutive red candles")
        elif position_type == "SHORT" and all(last_3 > 0):
            risk_score += 10
            reasons.append("🕯️ 3 consecutive green candles")
    
    # 6. Volume Confirmation (0-10 points)
    volume_signal, volume_ratio, _, _ = analyze_volume(df)
    
    if position_type == "LONG" and volume_signal in ["STRONG_SELLING", "SELLING"]:
        risk_score += 10
        reasons.append(f"📊 Selling volume ({volume_ratio:.1f}x)")
    elif position_type == "SHORT" and volume_signal in ["STRONG_BUYING", "BUYING"]:
        risk_score += 10
        reasons.append(f"📊 Buying volume ({volume_ratio:.1f}x)")
    
    # Cap at 100
    risk_score = min(100, risk_score)
    
    # Generate recommendation based on threshold
    if risk_score >= 80:
        recommendation = "🚨 EXIT NOW - Very high risk"
        priority = "CRITICAL"
    elif risk_score >= sl_alert_threshold + 20:  # Dynamic based on user threshold
        recommendation = "⚠️ CONSIDER EXIT - High risk"
        priority = "HIGH"
    elif risk_score >= sl_alert_threshold:
        recommendation = "👀 WATCH CLOSELY - Moderate risk"
        priority = "MEDIUM"
    elif risk_score >= 20:
        recommendation = "✅ MONITOR - Low risk"
        priority = "LOW"
    else:
        recommendation = "✅ SAFE - Very low risk"
        priority = "SAFE"
    
    return risk_score, reasons, recommendation, priority

# ============================================================================
# UPSIDE POTENTIAL PREDICTION ✅
# ============================================================================

def predict_upside_potential(df, current_price, target1, target2, position_type):
    """
    Predict if stock can continue after hitting target
    Returns: upside_score (0-100), new_target, reasons, recommendation, action
    """
    score = 50  # Start neutral
    reasons = []
    close = df['Close']
    
    # 1. Momentum still strong?
    momentum_score, trend, _ = calculate_momentum_score(df)
    
    if position_type == "LONG":
        if momentum_score >= 70:
            score += 25
            reasons.append(f"🚀 Strong momentum ({momentum_score:.0f})")
        elif momentum_score >= 55:
            score += 15
            reasons.append(f"📈 Good momentum ({momentum_score:.0f})")
        elif momentum_score <= 40:
            score -= 20
            reasons.append(f"📉 Weak momentum ({momentum_score:.0f})")
    else:  # SHORT
        if momentum_score <= 30:
            score += 25
            reasons.append(f"🚀 Strong bearish momentum ({momentum_score:.0f})")
        elif momentum_score <= 45:
            score += 15
            reasons.append(f"📉 Good bearish momentum ({momentum_score:.0f})")
        elif momentum_score >= 60:
            score -= 20
            reasons.append(f"📈 Bullish reversal ({momentum_score:.0f})")
    
    # 2. RSI not extreme?
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if position_type == "LONG":
        if rsi < 60:
            score += 15
            reasons.append(f"✅ RSI has room ({rsi:.0f})")
        elif rsi > 75:
            score -= 25
            reasons.append(f"⚠️ RSI overbought ({rsi:.0f})")
        elif rsi > 65:
            score -= 10
            reasons.append(f"🟡 RSI getting high ({rsi:.0f})")
    else:
        if rsi > 40:
            score += 15
            reasons.append(f"✅ RSI has room ({rsi:.0f})")
        elif rsi < 25:
            score -= 25
            reasons.append(f"⚠️ RSI oversold ({rsi:.0f})")
    
    # 3. Volume confirming?
    volume_signal, volume_ratio, _, volume_trend = analyze_volume(df)
    
    if position_type == "LONG" and volume_signal in ["STRONG_BUYING", "BUYING"]:
        score += 15
        reasons.append(f"📊 Buying volume ({volume_ratio:.1f}x)")
    elif position_type == "SHORT" and volume_signal in ["STRONG_SELLING", "SELLING"]:
        score += 15
        reasons.append(f"📊 Selling volume ({volume_ratio:.1f}x)")
    elif volume_ratio < 0.7:
        score -= 10
        reasons.append("📊 Low volume")
    
    # 4. Bollinger Band position
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(close)
    
    if len(upper_bb) > 0 and len(lower_bb) > 0:
        bb_range = upper_bb.iloc[-1] - lower_bb.iloc[-1]
        if bb_range > 0:
            if position_type == "LONG":
                bb_position = (current_price - lower_bb.iloc[-1]) / bb_range
                if bb_position < 0.7:
                    score += 10
                    reasons.append("📈 Room to upper BB")
                elif bb_position > 0.95:
                    score -= 15
                    reasons.append("⚠️ At upper BB")
            else:
                bb_position = (current_price - lower_bb.iloc[-1]) / bb_range
                if bb_position > 0.3:
                    score += 10
                    reasons.append("📉 Room to lower BB")
                elif bb_position < 0.05:
                    score -= 15
                    reasons.append("⚠️ At lower BB")
    
    # 5. Calculate new target based on ATR and S/R
    atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
    if pd.isna(atr):
        atr = current_price * 0.02  # Default 2% of price
    
    sr_levels = find_support_resistance(df)
    
    if position_type == "LONG":
        # New target = next resistance or 3x ATR
        atr_target = current_price + (atr * 3)
        sr_target = sr_levels['nearest_resistance']
        new_target = min(atr_target, sr_target) if sr_target > current_price else atr_target
        potential_gain = ((new_target - current_price) / current_price) * 100
    else:
        atr_target = current_price - (atr * 3)
        sr_target = sr_levels['nearest_support']
        new_target = max(atr_target, sr_target) if sr_target < current_price else atr_target
        potential_gain = ((current_price - new_target) / current_price) * 100
    
    if potential_gain > 5:
        score += 10
        reasons.append(f"🎯 {potential_gain:.1f}% more potential")
    
    # Cap score
    score = max(0, min(100, score))
    
    # Generate recommendation
    if score >= 70:
        recommendation = "HOLD"
        action = f"Strong upside - New target: ₹{new_target:.2f}"
    elif score >= 50:
        recommendation = "PARTIAL_EXIT"
        action = f"Book 50%, hold rest for ₹{new_target:.2f}"
    else:
        recommendation = "EXIT"
        action = "Book full profits now"
    
    return score, new_target, reasons, recommendation, action

# ============================================================================
# DYNAMIC TARGET & TRAIL STOP CALCULATION ✅
# ============================================================================

def calculate_dynamic_levels(df, entry_price, current_price, stop_loss, position_type, pnl_percent, trail_trigger=3.0):
    """
    Calculate dynamic targets and trailing stop loss
    Uses trail_trigger from sidebar settings
    """
    close = df['Close']
    atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
    
    if pd.isna(atr):
        atr = current_price * 0.02  # Default 2%
    
    sr_levels = find_support_resistance(df)
    
    result = {
        'atr': atr,
        'support': sr_levels['nearest_support'],
        'resistance': sr_levels['nearest_resistance']
    }
    
    if position_type == "LONG":
        # Dynamic targets
        result['target1'] = current_price + (atr * 1.5)
        result['target2'] = current_price + (atr * 3)
        result['target3'] = min(current_price + (atr * 5), sr_levels['nearest_resistance'])
        
        # Trail stop based on profit level - Using dynamic threshold
        if pnl_percent >= trail_trigger * 3:  # e.g., 6% if trigger is 2%
            result['trail_stop'] = max(entry_price * 1.05, current_price - atr)  # Lock 5% profit
            result['trail_reason'] = f"Locking 5% profit (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger * 2:  # e.g., 4% if trigger is 2%
            result['trail_stop'] = max(entry_price * 1.02, current_price - (atr * 1.5))  # Lock 2%
            result['trail_reason'] = f"Locking 2% profit (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger:  # e.g., 2%
            result['trail_stop'] = max(entry_price, current_price - (atr * 2))  # Breakeven
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger * 0.5:  # e.g., 1%
            result['trail_stop'] = max(stop_loss, current_price - (atr * 2.5))
            result['trail_reason'] = f"Tightening SL (P&L: {pnl_percent:.1f}%)"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL"
        
        result['should_trail'] = result['trail_stop'] > stop_loss
        
    else:  # SHORT
        result['target1'] = current_price - (atr * 1.5)
        result['target2'] = current_price - (atr * 3)
        result['target3'] = max(current_price - (atr * 5), sr_levels['nearest_support'])
        
        if pnl_percent >= trail_trigger * 3:
            result['trail_stop'] = min(entry_price * 0.95, current_price + atr)
            result['trail_reason'] = f"Locking 5% profit (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger * 2:
            result['trail_stop'] = min(entry_price * 0.98, current_price + (atr * 1.5))
            result['trail_reason'] = f"Locking 2% profit (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger:
            result['trail_stop'] = min(entry_price, current_price + (atr * 2))
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger * 0.5:
            result['trail_stop'] = min(stop_loss, current_price + (atr * 2.5))
            result['trail_reason'] = f"Tightening SL (P&L: {pnl_percent:.1f}%)"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL"
        
        result['should_trail'] = result['trail_stop'] < stop_loss
    
    return result

# ============================================================================
# COMPLETE SMART ANALYSIS ✅ (UPDATED WITH ALL PARAMETERS)
# ============================================================================

@st.cache_data(ttl=15)  # FIXED: 15 second cache (less than refresh interval)
def smart_analyze_position(ticker, position_type, entry_price, quantity, stop_loss, 
                          target1, target2, trail_threshold=2.0, sl_alert_threshold=50,
                          enable_mtf=True):
    """
    Complete smart analysis with all features
    Now accepts sidebar parameters for dynamic thresholds
    """
    symbol = ticker if '.NS' in str(ticker) else f"{ticker}.NS"
    
    # Fetch data
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="6mo")
        
        if df.empty:
            symbol = symbol.replace('.NS', '.BO')
            stock = yf.Ticker(symbol)
            df = stock.history(period="6mo")
        
        if df.empty:
            return None
        
        df.reset_index(inplace=True)
        current_price = float(df['Close'].iloc[-1])
        
    except Exception as e:
        return None
    
    # Basic P&L
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
    else:
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
    
    # Technical Indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    if pd.isna(rsi):
        rsi = 50.0
    
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1]) if len(histogram) > 0 else 0
    if pd.isna(macd_hist):
        macd_hist = 0
    macd_signal = "BULLISH" if macd_hist > 0 else "BEARISH"
    
    # Momentum Score
    momentum_score, momentum_trend, momentum_components = calculate_momentum_score(df)
    
    # Volume Analysis
    volume_signal, volume_ratio, volume_desc, volume_trend = analyze_volume(df)
    
    # Support/Resistance
    sr_levels = find_support_resistance(df)
    
    # SL Risk Prediction - NOW USES THRESHOLD FROM SIDEBAR
    sl_risk, sl_reasons, sl_recommendation, sl_priority = predict_sl_risk(
        df, current_price, stop_loss, position_type, entry_price, sl_alert_threshold
    )
    
    # Multi-Timeframe Analysis (if enabled)
    if enable_mtf:
        mtf_result = multi_timeframe_analysis(ticker, position_type)
    else:
        mtf_result = {
            'signals': {},
            'details': {},
            'alignment_score': 50,
            'recommendation': "MTF disabled",
            'aligned_count': 0,
            'against_count': 0,
            'total_timeframes': 0
        }
    
    # Check if target hit
    if position_type == "LONG":
        target1_hit = current_price >= target1
        target2_hit = current_price >= target2
        sl_hit = current_price <= stop_loss
    else:
        target1_hit = current_price <= target1
        target2_hit = current_price <= target2
        sl_hit = current_price >= stop_loss
    
    # Upside prediction (if target hit)
    if target1_hit and not sl_hit:
        upside_score, new_target, upside_reasons, upside_rec, upside_action = predict_upside_potential(
            df, current_price, target1, target2, position_type
        )
    else:
        upside_score = 0
        new_target = target2
        upside_reasons = []
        upside_rec = ""
        upside_action = ""
    
    # Dynamic Levels - NOW USES TRAIL THRESHOLD FROM SIDEBAR
    dynamic_levels = calculate_dynamic_levels(
        df, entry_price, current_price, stop_loss, position_type, pnl_percent, trail_threshold
    )
    
    # Generate Alerts and Determine Overall Status
    alerts = []
    
    # Priority 1: SL Hit
    if sl_hit:
        alerts.append({
            'priority': 'CRITICAL',
            'type': '🚨 STOP LOSS HIT',
            'message': f'Price ₹{current_price:.2f} breached SL ₹{stop_loss:.2f}',
            'action': 'EXIT IMMEDIATELY'
        })
        overall_status = 'CRITICAL'
        overall_action = 'EXIT'
    
    # Priority 2: Early Exit Warning (High SL Risk)
    elif sl_risk >= sl_alert_threshold + 20:  # Dynamic: threshold + 20
        alerts.append({
            'priority': 'CRITICAL',
            'type': '⚠️ HIGH SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation
        })
        overall_status = 'CRITICAL'
        overall_action = 'EXIT_EARLY'
    
    elif sl_risk >= sl_alert_threshold:  # Dynamic threshold from sidebar
        alerts.append({
            'priority': 'HIGH',
            'type': '⚠️ MODERATE SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation
        })
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    
    # Priority 3: Target Hit with Upside Analysis
    elif target2_hit:
        alerts.append({
            'priority': 'HIGH',
            'type': '🎯 TARGET 2 HIT',
            'message': f'Both targets achieved! P&L: {pnl_percent:+.2f}%',
            'action': 'BOOK FULL PROFITS'
        })
        overall_status = 'SUCCESS'
        overall_action = 'BOOK_PROFITS'
    
    elif target1_hit:
        if upside_score >= 60:
            alerts.append({
                'priority': 'INFO',
                'type': '🎯 TARGET HIT - HOLD',
                'message': f'Upside Score: {upside_score}% - {", ".join(upside_reasons[:2])}',
                'action': f'{upside_action}'
            })
            overall_status = 'OPPORTUNITY'
            overall_action = 'HOLD_EXTEND'
        else:
            alerts.append({
                'priority': 'HIGH',
                'type': '🎯 TARGET HIT - EXIT',
                'message': f'Limited upside ({upside_score}%). Book profits.',
                'action': 'BOOK PROFITS'
            })
            overall_status = 'SUCCESS'
            overall_action = 'BOOK_PROFITS'
    
    # Priority 4: Trail Stop - FIXED: Uses dynamic threshold
    elif dynamic_levels['should_trail'] and pnl_percent >= trail_threshold:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '📈 TRAIL STOP LOSS',
            'message': f'{dynamic_levels.get("trail_reason", "Lock profits!")} Move SL from ₹{stop_loss:.2f} to ₹{dynamic_levels["trail_stop"]:.2f}',
            'action': f'New SL: ₹{dynamic_levels["trail_stop"]:.2f}'
        })
        overall_status = 'GOOD'
        overall_action = 'TRAIL_SL'
    
    # Priority 5: MTF Warning (if timeframes against position)
    elif enable_mtf and mtf_result['alignment_score'] < 40 and pnl_percent < 0:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '📊 MTF WARNING',
            'message': f'Timeframes against position ({mtf_result["alignment_score"]}% aligned)',
            'action': mtf_result['recommendation']
        })
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    
    else:
        overall_status = 'OK'
        overall_action = 'HOLD'
    
    # Add volume warning if against position
    if position_type == "LONG" and volume_signal == "STRONG_SELLING" and sl_risk < sl_alert_threshold:
        alerts.append({
            'priority': 'LOW',
            'type': '📊 VOLUME WARNING',
            'message': volume_desc,
            'action': 'Monitor closely'
        })
    elif position_type == "SHORT" and volume_signal == "STRONG_BUYING" and sl_risk < sl_alert_threshold:
        alerts.append({
            'priority': 'LOW',
            'type': '📊 VOLUME WARNING',
            'message': volume_desc,
            'action': 'Monitor closely'
        })
    
    return {
        # Basic Info
        'ticker': ticker,
        'position_type': position_type,
        'entry_price': entry_price,
        'current_price': current_price,
        'quantity': quantity,
        'pnl_percent': pnl_percent,
        'pnl_amount': pnl_amount,
        
        # Original Levels
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        
        # Technical Indicators
        'rsi': rsi,
        'macd_hist': macd_hist,
        'macd_signal': macd_signal,
        
        # Momentum
        'momentum_score': momentum_score,
        'momentum_trend': momentum_trend,
        'momentum_components': momentum_components,
        
        # Volume
        'volume_signal': volume_signal,
        'volume_ratio': volume_ratio,
        'volume_desc': volume_desc,
        'volume_trend': volume_trend,
        
        # Support/Resistance
        'support': sr_levels['nearest_support'],
        'resistance': sr_levels['nearest_resistance'],
        'distance_to_support': sr_levels['distance_to_support'],
        'distance_to_resistance': sr_levels['distance_to_resistance'],
        
        # SL Risk
        'sl_risk': sl_risk,
        'sl_reasons': sl_reasons,
        'sl_recommendation': sl_recommendation,
        'sl_priority': sl_priority,
        
        # Upside
        'upside_score': upside_score,
        'upside_reasons': upside_reasons,
        'new_target': new_target,
        
        # Dynamic Levels
        'trail_stop': dynamic_levels['trail_stop'],
        'should_trail': dynamic_levels['should_trail'],
        'trail_reason': dynamic_levels.get('trail_reason', ''),
        'dynamic_target1': dynamic_levels['target1'],
        'dynamic_target2': dynamic_levels['target2'],
        'atr': dynamic_levels['atr'],
        
        # Targets Status
        'target1_hit': target1_hit,
        'target2_hit': target2_hit,
        'sl_hit': sl_hit,
        
        # Multi-Timeframe
        'mtf_signals': mtf_result['signals'],
        'mtf_details': mtf_result.get('details', {}),
        'mtf_alignment': mtf_result['alignment_score'],
        'mtf_recommendation': mtf_result['recommendation'],
        
        # Alerts & Status
        'alerts': alerts,
        'overall_status': overall_status,
        'overall_action': overall_action,
        
        # Chart Data
        'df': df
    }

# ============================================================================
# LOAD PORTFOLIO
# ============================================================================

def load_portfolio():
    """Load portfolio from Excel"""
    try:
        if os.path.exists('my_portfolio.xlsx'):
            df = pd.read_excel('my_portfolio.xlsx', sheet_name='Portfolio')
            if 'Status' in df.columns:
                df = df[df['Status'].str.upper() == 'ACTIVE']
            return df
    except Exception as e:
        st.error(f"Error loading portfolio: {e}")
    
    # Return sample data
    return pd.DataFrame({
        'Ticker': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK'],
        'Position': ['LONG', 'LONG', 'SHORT', 'LONG'],
        'Entry_Price': [1550.00, 3280.00, 1650.00, 970.00],
        'Quantity': [10, 5, 8, 15],
        'Stop_Loss': [1500.00, 3200.00, 1720.00, 940.00],
        'Target_1': [1650.00, 3400.00, 1550.00, 1050.00],
        'Target_2': [1750.00, 3500.00, 1450.00, 1100.00],
        'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE']
    })

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">🧠 Smart Portfolio Monitor v5.1</h1>', unsafe_allow_html=True)
    
    # Market Status
    is_open, market_status, market_msg, market_icon = is_market_hours()
    ist_now = get_ist_now()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.markdown(f"### {market_icon} {market_status}")
        st.caption(market_msg)
    with col2:
        st.markdown(f"### 🕐 {ist_now.strftime('%H:%M:%S')} IST")
        st.caption(ist_now.strftime('%A, %B %d, %Y'))
    with col3:
        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    # Show settings summary
    with st.expander("⚙️ Current Settings", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Trail SL Trigger", f"{trail_sl_trigger}%")
        with col2:
            st.metric("SL Risk Alert", f"{sl_risk_threshold}%")
        with col3:
            st.metric("Refresh Interval", f"{refresh_interval}s")
        with col4:
            st.metric("MTF Analysis", "✅ On" if enable_multi_timeframe else "❌ Off")
    
    st.divider()
    
    # Load Portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.warning("⚠️ No positions found! Add positions to my_portfolio.xlsx")
        
        # Show sample format
        st.markdown("### 📋 Expected Excel Format:")
        sample_df = pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS'],
            'Position': ['LONG', 'SHORT'],
            'Entry_Price': [1550.00, 3280.00],
            'Quantity': [10, 5],
            'Stop_Loss': [1500.00, 3350.00],
            'Target_1': [1650.00, 3200.00],
            'Target_2': [1750.00, 3100.00],
            'Status': ['ACTIVE', 'ACTIVE']
        })
        st.dataframe(sample_df, use_container_width=True)
        return
    
    # Analyze All Positions
    results = []
    progress_bar = st.progress(0, text="Analyzing positions...")
    
    for i, (_, row) in enumerate(portfolio.iterrows()):
        progress_bar.progress((i + 0.5) / len(portfolio), text=f"Analyzing {row['Ticker']}...")
        
        result = smart_analyze_position(
            str(row['Ticker']),
            str(row['Position']).upper(),
            float(row['Entry_Price']),
            int(row.get('Quantity', 1)),
            float(row['Stop_Loss']),
            float(row['Target_1']),
            float(row.get('Target_2', row['Target_1'] * 1.1)),
            trail_sl_trigger,           # FIXED: Pass sidebar threshold
            sl_risk_threshold,          # FIXED: Pass sidebar threshold
            enable_multi_timeframe      # FIXED: Pass MTF setting
        )
        if result:
            results.append(result)
        
        progress_bar.progress((i + 1) / len(portfolio), text=f"Completed {row['Ticker']}")
    
    progress_bar.empty()
    
    if not results:
        st.error("❌ Could not fetch stock data. Check internet connection and try again.")
        return
    
    # Summary Metrics
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['entry_price'] * r['quantity'] for r in results)
    pnl_percent_total = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    critical_count = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['overall_status'] == 'WARNING')
    opportunity_count = sum(1 for r in results if r['overall_status'] == 'OPPORTUNITY')
    success_count = sum(1 for r in results if r['overall_status'] == 'SUCCESS')
    good_count = sum(1 for r in results if r['overall_status'] == 'GOOD')
    
    # Email Critical Alerts
    if email_enabled and critical_count > 0:
        critical_results = [r for r in results if r['overall_status'] == 'CRITICAL']
        
        email_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #dc3545;">🚨 CRITICAL ALERTS - {critical_count} positions need attention!</h2>
        <p>Time: {ist_now.strftime('%Y-%m-%d %H:%M:%S')} IST</p>
        <hr>
        """
        
        for r in critical_results:
            email_html += f"""
            <div style="background:#f8d7da; padding:20px; margin:15px 0; border-radius:10px; border-left:5px solid #dc3545;">
                <h3 style="margin:0;">{r['ticker']} - {r['overall_action'].replace('_', ' ')}</h3>
                <p><strong>Position:</strong> {r['position_type']} | Qty: {r['quantity']}</p>
                <p><strong>Current:</strong> ₹{r['current_price']:.2f} | Entry: ₹{r['entry_price']:.2f}</p>
                <p><strong>P&L:</strong> {r['pnl_percent']:+.2f}% (₹{r['pnl_amount']:+,.2f})</p>
                <p><strong>SL Risk Score:</strong> {r['sl_risk']}%</p>
                <p style="font-size:1.2em;"><strong>⚡ Action: {r['alerts'][0]['action'] if r['alerts'] else 'Review position'}</strong></p>
            </div>
            """
        
        email_html += """
        <hr>
        <p style="color:#666;">This is an automated alert from Smart Portfolio Monitor v5.1</p>
        </body>
        </html>
        """
        
        if send_email_alert(
            f"🚨 CRITICAL: {critical_count} positions need immediate action!",
            email_html, sender_email, sender_password, recipient_email
        ):
            st.toast("📧 Critical alert email sent!", icon="✅")
    
    # Display Summary Cards
    st.markdown("### 📊 Portfolio Summary")
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    with col1:
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric("💰 Total P&L", f"₹{total_pnl:+,.0f}", f"{pnl_percent_total:+.2f}%")
    with col2:
        st.metric("📊 Positions", len(results))
    with col3:
        st.metric("🔴 Critical", critical_count)
    with col4:
        st.metric("🟡 Warning", warning_count)
    with col5:
        st.metric("🟢 Good", good_count)
    with col6:
        st.metric("🔵 Opportunity", opportunity_count)
    with col7:
        st.metric("✅ Success", success_count)
    
    st.divider()
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "📈 Charts", "🔔 Alerts", "📉 MTF Analysis", "📋 Details"])
    
    # =============== DASHBOARD TAB ===============
    with tab1:
        # Sort by status priority
        status_order = {'CRITICAL': 0, 'WARNING': 1, 'OPPORTUNITY': 2, 'SUCCESS': 3, 'GOOD': 4, 'OK': 5}
        sorted_results = sorted(results, key=lambda x: status_order.get(x['overall_status'], 5))
        
        for r in sorted_results:
            status_icons = {
                'CRITICAL': '🔴', 'WARNING': '🟡', 'OPPORTUNITY': '🔵',
                'SUCCESS': '🟢', 'GOOD': '🟢', 'OK': '⚪'
            }
            status_icon = status_icons.get(r['overall_status'], '⚪')
            
            pnl_emoji = "📈" if r['pnl_percent'] >= 0 else "📉"
            
            with st.expander(
                f"{status_icon} **{r['ticker']}** | "
                f"{'📈 LONG' if r['position_type'] == 'LONG' else '📉 SHORT'} | "
                f"{pnl_emoji} P&L: **{r['pnl_percent']:+.2f}%** (₹{r['pnl_amount']:+,.0f}) | "
                f"SL Risk: **{r['sl_risk']}%** | "
                f"Action: **{r['overall_action'].replace('_', ' ')}**",
                expanded=(r['overall_status'] in ['CRITICAL', 'WARNING', 'OPPORTUNITY', 'SUCCESS'])
            ):
                # Row 1: Basic Info
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("##### 💰 Position")
                    st.write(f"**Entry:** ₹{r['entry_price']:,.2f}")
                    st.write(f"**Current:** ₹{r['current_price']:,.2f}")
                    st.write(f"**Qty:** {r['quantity']}")
                    pnl_color = "green" if r['pnl_percent'] >= 0 else "red"
                    st.markdown(f"**P&L:** <span style='color:{pnl_color};font-weight:bold;'>"
                               f"₹{r['pnl_amount']:+,.2f} ({r['pnl_percent']:+.2f}%)</span>",
                               unsafe_allow_html=True)
                
                with col2:
                    st.markdown("##### 🎯 Levels")
                    st.write(f"**Stop Loss:** ₹{r['stop_loss']:,.2f} {'🔴 HIT!' if r['sl_hit'] else ''}")
                    st.write(f"**Target 1:** ₹{r['target1']:,.2f} {'✅' if r['target1_hit'] else ''}")
                    st.write(f"**Target 2:** ₹{r['target2']:,.2f} {'✅' if r['target2_hit'] else ''}")
                    if r['should_trail']:
                        st.success(f"**Trail SL:** ₹{r['trail_stop']:,.2f}")
                        st.caption(r.get('trail_reason', ''))
                
                with col3:
                    st.markdown("##### 📊 Indicators")
                    rsi_color = "green" if 40 <= r['rsi'] <= 60 else "orange" if 30 <= r['rsi'] <= 70 else "red"
                    st.markdown(f"**RSI:** <span style='color:{rsi_color};'>{r['rsi']:.1f}</span>", unsafe_allow_html=True)
                    macd_color = "green" if r['macd_signal'] == "BULLISH" else "red"
                    st.markdown(f"**MACD:** <span style='color:{macd_color};'>{r['macd_signal']}</span>", unsafe_allow_html=True)
                    st.write(f"**Volume:** {r['volume_signal'].replace('_', ' ')}")
                    st.write(f"**Trend:** {r['momentum_trend']}")
                
                with col4:
                    st.markdown("##### 🛡️ Support/Resistance")
                    st.write(f"**Support:** ₹{r['support']:,.2f}")
                    st.write(f"**Resistance:** ₹{r['resistance']:,.2f}")
                    st.write(f"**ATR:** ₹{r['atr']:,.2f}")
                    st.write(f"**Distance to S:** {r['distance_to_support']:.1f}%")
                
                st.divider()
                
                # Row 2: Smart Scores
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("##### ⚠️ SL Risk Score")
                    risk_color = "#dc3545" if r['sl_risk'] >= 70 else "#ffc107" if r['sl_risk'] >= 50 else "#28a745"
                    st.markdown(f"<h2 style='color:{risk_color};text-align:center;'>{r['sl_risk']}%</h2>",
                               unsafe_allow_html=True)
                    st.progress(r['sl_risk'] / 100)
                    if r['sl_reasons']:
                        for reason in r['sl_reasons'][:3]:
                            st.caption(reason)
                
                with col2:
                    st.markdown("##### 📈 Momentum Score")
                    mom_color = "#28a745" if r['momentum_score'] >= 60 else "#ffc107" if r['momentum_score'] >= 40 else "#dc3545"
                    st.markdown(f"<h2 style='color:{mom_color};text-align:center;'>{r['momentum_score']:.0f}/100</h2>",
                               unsafe_allow_html=True)
                    st.progress(r['momentum_score'] / 100)
                    st.caption(r['momentum_trend'])
                
                with col3:
                    st.markdown("##### 🚀 Upside Score")
                    if r['target1_hit']:
                        up_color = "#28a745" if r['upside_score'] >= 60 else "#ffc107" if r['upside_score'] >= 40 else "#dc3545"
                        st.markdown(f"<h2 style='color:{up_color};text-align:center;'>{r['upside_score']}%</h2>",
                                   unsafe_allow_html=True)
                        st.progress(r['upside_score'] / 100)
                        if r['upside_score'] >= 60:
                            st.success(f"New Target: ₹{r['new_target']:,.2f}")
                    else:
                        st.markdown("<h2 style='color:#6c757d;text-align:center;'>N/A</h2>",
                                   unsafe_allow_html=True)
                        st.caption("Target not yet hit")
                
                with col4:
                    st.markdown("##### 📊 MTF Alignment")
                    if r['mtf_signals']:
                        mtf_color = "#28a745" if r['mtf_alignment'] >= 60 else "#ffc107" if r['mtf_alignment'] >= 40 else "#dc3545"
                        st.markdown(f"<h2 style='color:{mtf_color};text-align:center;'>{r['mtf_alignment']}%</h2>",
                                   unsafe_allow_html=True)
                        st.progress(r['mtf_alignment'] / 100)
                        for tf, signal in r['mtf_signals'].items():
                            sig_emoji = "🟢" if signal == "BULLISH" else "🔴" if signal == "BEARISH" else "⚪"
                            st.caption(f"{tf}: {sig_emoji} {signal}")
                    else:
                        st.markdown("<h2 style='color:#6c757d;text-align:center;'>N/A</h2>",
                                   unsafe_allow_html=True)
                        st.caption("MTF data unavailable")
                
                # Row 3: Alerts
                if r['alerts']:
                    st.markdown("##### ⚠️ Alerts & Recommendations")
                    for alert in r['alerts']:
                        if alert['priority'] == 'CRITICAL':
                            st.error(f"**{alert['type']}**: {alert['message']}\n\n**⚡ Action: {alert['action']}**")
                        elif alert['priority'] == 'HIGH':
                            st.warning(f"**{alert['type']}**: {alert['message']}\n\n**⚡ Action: {alert['action']}**")
                        elif alert['priority'] == 'MEDIUM':
                            st.info(f"**{alert['type']}**: {alert['message']}\n\n**Action: {alert['action']}**")
                        else:
                            st.caption(f"ℹ️ {alert['type']}: {alert['message']}")
                
                # Recommendation Box
                rec_colors = {
                    'EXIT': 'critical-box', 'EXIT_EARLY': 'critical-box',
                    'WATCH': 'warning-box', 'BOOK_PROFITS': 'success-box',
                    'HOLD_EXTEND': 'info-box', 'TRAIL_SL': 'success-box',
                    'HOLD': 'info-box'
                }
                rec_class = rec_colors.get(r['overall_action'], 'info-box')
                
                st.markdown(f"""
                <div class="{rec_class}">
                    📌 RECOMMENDATION: {r['overall_action'].replace('_', ' ')}
                </div>
                """, unsafe_allow_html=True)
    
    # =============== CHARTS TAB ===============
    with tab2:
        selected_stock = st.selectbox("Select Stock for Chart", [r['ticker'] for r in results])
        selected_result = next((r for r in results if r['ticker'] == selected_stock), None)
        
        if selected_result and 'df' in selected_result:
            df = selected_result['df']
            
            # Candlestick Chart
            fig = go.Figure()
            
            fig.add_trace(go.Candlestick(
                x=df['Date'], open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='Price'
            ))
            
            # Add moving averages
            df['SMA20'] = df['Close'].rolling(20).mean()
            df['EMA9'] = df['Close'].ewm(span=9).mean()
            
            fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA20'], mode='lines',
                                    name='SMA 20', line=dict(color='orange', width=1)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA9'], mode='lines',
                                    name='EMA 9', line=dict(color='purple', width=1)))
            
            # Add levels
            fig.add_hline(y=selected_result['entry_price'], line_dash="dash",
                         line_color="blue", annotation_text="Entry")
            fig.add_hline(y=selected_result['stop_loss'], line_dash="dash",
                         line_color="red", annotation_text="Stop Loss")
            fig.add_hline(y=selected_result['target1'], line_dash="dash",
                         line_color="green", annotation_text="Target 1")
            fig.add_hline(y=selected_result['target2'], line_dash="dot",
                         line_color="darkgreen", annotation_text="Target 2")
            fig.add_hline(y=selected_result['support'], line_dash="dot",
                         line_color="orange", annotation_text="Support")
            fig.add_hline(y=selected_result['resistance'], line_dash="dot",
                         line_color="purple", annotation_text="Resistance")
            
            if selected_result['should_trail']:
                fig.add_hline(y=selected_result['trail_stop'], line_dash="dash",
                             line_color="cyan", annotation_text="Trail SL", line_width=2)
            
            fig.update_layout(
                title=f"{selected_stock} - Price Chart with Levels",
                height=500,
                xaxis_rangeslider_visible=False,
                xaxis_title="Date",
                yaxis_title="Price (₹)"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # RSI and MACD Charts
            col1, col2 = st.columns(2)
            
            with col1:
                rsi_series = calculate_rsi(df['Close'])
                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(x=df['Date'], y=rsi_series, mode='lines', 
                                            name='RSI', line=dict(color='purple')))
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig_rsi.add_hline(y=50, line_dash="dot", line_color="gray")
                fig_rsi.update_layout(title="RSI (14)", height=250, yaxis_range=[0, 100])
                st.plotly_chart(fig_rsi, use_container_width=True)
            
            with col2:
                macd, signal, histogram = calculate_macd(df['Close'])
                colors = ['green' if h >= 0 else 'red' for h in histogram]
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Bar(x=df['Date'], y=histogram, name='Histogram',
                                         marker_color=colors))
                fig_macd.add_trace(go.Scatter(x=df['Date'], y=macd, mode='lines',
                                             name='MACD', line=dict(color='blue', width=1)))
                fig_macd.add_trace(go.Scatter(x=df['Date'], y=signal, mode='lines',
                                             name='Signal', line=dict(color='orange', width=1)))
                fig_macd.update_layout(title="MACD", height=250)
                st.plotly_chart(fig_macd, use_container_width=True)
            
            # Volume Chart
            fig_vol = go.Figure()
            vol_colors = ['green' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'red' 
                         for i in range(len(df))]
            fig_vol.add_trace(go.Bar(x=df['Date'], y=df['Volume'], name='Volume',
                                    marker_color=vol_colors))
            fig_vol.update_layout(title="Volume", height=200)
            st.plotly_chart(fig_vol, use_container_width=True)
    
    # =============== ALERTS TAB ===============
    with tab3:
        st.subheader("🔔 All Alerts")
        
        all_alerts = []
        for r in results:
            for alert in r['alerts']:
                all_alerts.append({
                    'Ticker': r['ticker'],
                    'Priority': alert['priority'],
                    'Type': alert['type'],
                    'Message': alert['message'],
                    'Action': alert['action'],
                    'P&L': f"{r['pnl_percent']:+.2f}%",
                    'SL Risk': f"{r['sl_risk']}%"
                })
        
        if all_alerts:
            # Sort by priority
            priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            all_alerts_sorted = sorted(all_alerts, key=lambda x: priority_order.get(x['Priority'], 4))
            
            df_alerts = pd.DataFrame(all_alerts_sorted)
            
            # Color code by priority
            def highlight_priority(row):
                if row['Priority'] == 'CRITICAL':
                    return ['background-color: #f8d7da'] * len(row)
                elif row['Priority'] == 'HIGH':
                    return ['background-color: #fff3cd'] * len(row)
                elif row['Priority'] == 'MEDIUM':
                    return ['background-color: #d1ecf1'] * len(row)
                return [''] * len(row)
            
            st.dataframe(df_alerts.style.apply(highlight_priority, axis=1), 
                        use_container_width=True, hide_index=True)
            
            # Summary by priority
            st.markdown("### Alert Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                critical = sum(1 for a in all_alerts if a['Priority'] == 'CRITICAL')
                st.metric("🔴 Critical", critical)
            with col2:
                high = sum(1 for a in all_alerts if a['Priority'] == 'HIGH')
                st.metric("🟠 High", high)
            with col3:
                medium = sum(1 for a in all_alerts if a['Priority'] == 'MEDIUM')
                st.metric("🟡 Medium", medium)
            with col4:
                low = sum(1 for a in all_alerts if a['Priority'] == 'LOW')
                st.metric("🟢 Low", low)
        else:
            st.success("✅ No alerts! All positions are healthy.")
            st.balloons()
    
    # =============== MTF ANALYSIS TAB ===============
    with tab4:
        st.subheader("📉 Multi-Timeframe Analysis")
        
        if not enable_multi_timeframe:
            st.warning("⚠️ Multi-Timeframe Analysis is disabled. Enable it in the sidebar settings.")
        else:
            for r in results:
                with st.expander(f"**{r['ticker']}** - MTF Alignment: {r['mtf_alignment']}%", 
                               expanded=(r['mtf_alignment'] < 50)):
                    
                    if r['mtf_signals']:
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            # Alignment gauge
                            alignment_color = "#28a745" if r['mtf_alignment'] >= 60 else "#ffc107" if r['mtf_alignment'] >= 40 else "#dc3545"
                            st.markdown(f"""
                            <div style='text-align:center;padding:20px;background:#f8f9fa;border-radius:10px;'>
                                <h1 style='color:{alignment_color};margin:0;'>{r['mtf_alignment']}%</h1>
                                <p style='margin:5px 0;'>Timeframe Alignment</p>
                                <p style='font-size:0.8em;color:#666;'>{r['mtf_recommendation']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            # Timeframe details
                            for tf, signal in r['mtf_signals'].items():
                                details = r['mtf_details'].get(tf, {})
                                sig_color = "🟢" if signal == "BULLISH" else "🔴" if signal == "BEARISH" else "⚪"
                                
                                strength = details.get('strength', 'Unknown')
                                rsi_tf = details.get('rsi', 0)
                                
                                st.markdown(f"""
                                **{tf}:** {sig_color} {signal} ({strength})
                                - RSI: {rsi_tf:.1f} | Above SMA20: {'✅' if details.get('above_sma20') else '❌'} | 
                                MACD: {'📈' if details.get('macd_bullish') else '📉'}
                                """)
                    else:
                        st.warning("MTF data not available for this stock")
    
    # =============== DETAILS TAB ===============
    with tab5:
        st.subheader("📋 Complete Analysis Data")
        
        details_data = []
        for r in results:
            details_data.append({
                'Ticker': r['ticker'],
                'Type': r['position_type'],
                'Entry': f"₹{r['entry_price']:,.2f}",
                'Current': f"₹{r['current_price']:,.2f}",
                'P&L %': f"{r['pnl_percent']:+.2f}%",
                'P&L ₹': f"₹{r['pnl_amount']:+,.0f}",
                'SL': f"₹{r['stop_loss']:,.2f}",
                'SL Risk': f"{r['sl_risk']}%",
                'Momentum': f"{r['momentum_score']:.0f}",
                'RSI': f"{r['rsi']:.1f}",
                'MACD': r['macd_signal'],
                'Volume': r['volume_signal'].replace('_', ' '),
                'Support': f"₹{r['support']:,.2f}",
                'Resistance': f"₹{r['resistance']:,.2f}",
                'Trail SL': f"₹{r['trail_stop']:,.2f}" if r['should_trail'] else '-',
                'MTF Align': f"{r['mtf_alignment']}%" if r['mtf_signals'] else 'N/A',
                'Status': r['overall_status'],
                'Action': r['overall_action'].replace('_', ' ')
            })
        
        df_details = pd.DataFrame(details_data)
        
        # Color code by status
        def highlight_status(row):
            status = row['Status']
            if status == 'CRITICAL':
                return ['background-color: #f8d7da'] * len(row)
            elif status == 'WARNING':
                return ['background-color: #fff3cd'] * len(row)
            elif status in ['SUCCESS', 'GOOD']:
                return ['background-color: #d4edda'] * len(row)
            elif status == 'OPPORTUNITY':
                return ['background-color: #d1ecf1'] * len(row)
            return [''] * len(row)
        
        st.dataframe(df_details.style.apply(highlight_status, axis=1), 
                    use_container_width=True, hide_index=True)
        
        # Export option
        st.download_button(
            "📥 Download Analysis as CSV",
            df_details.to_csv(index=False),
            file_name=f"portfolio_analysis_{ist_now.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    
    # =============== AUTO REFRESH ===============
    st.divider()
    
    if auto_refresh:
        if is_open:
            if HAS_AUTOREFRESH:
                # Use streamlit-autorefresh (non-blocking, best option)
                count = st_autorefresh(
                    interval=refresh_interval * 1000,  # Convert to milliseconds
                    limit=None,  # No limit
                    key="portfolio_autorefresh"
                )
                st.caption(f"🔄 Auto-refresh active | Next refresh in {refresh_interval}s | Count: {count}")
            else:
                # Fallback: Use st.rerun() with a placeholder
                st.caption(f"⏱️ Auto-refresh in {refresh_interval} seconds...")
                st.caption("💡 Install `streamlit-autorefresh` for better experience: `pip install streamlit-autorefresh`")
                
                # Create a countdown placeholder
                countdown_placeholder = st.empty()
                for remaining in range(refresh_interval, 0, -1):
                    countdown_placeholder.caption(f"🔄 Refreshing in {remaining} seconds...")
                    import time
                    time.sleep(1)
                countdown_placeholder.empty()
                st.cache_data.clear()
                st.rerun()
        else:
            st.caption(f"⏸️ Auto-refresh paused - {market_status}: {market_msg}")
    else:
        st.caption("🔄 Auto-refresh disabled. Click 'Refresh' button to update.")

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    main()
