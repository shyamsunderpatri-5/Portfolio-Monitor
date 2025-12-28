"""
================================================================================
SMART PORTFOLIO MONITOR v4.0 - PREDICTIVE EDITION
================================================================================
Features:
- Early exit signals BEFORE stop loss hits
- Hold recommendations after target
- Dynamic target adjustment
- Multi-timeframe analysis
- Volume confirmation
- Support/Resistance detection
- Momentum scoring
================================================================================
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Email settings from environment
    "sender_email": os.environ.get("SENDER_EMAIL", ""),
    "sender_password": os.environ.get("SENDER_PASSWORD", ""),
    "recipient_email": os.environ.get("RECIPIENT_EMAIL", ""),
    "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
    
    # Files
    "excel_file": "my_portfolio.xlsx",
    
    # Market hours
    "market_open": "09:15",
    "market_close": "15:30",
    
    # Smart analysis settings
    "early_exit_threshold": 0.7,      # Exit if 70% likely to hit SL
    "hold_after_target_threshold": 0.6,  # Hold if 60% chance of more upside
    "volume_confirmation_multiplier": 1.3,  # Need 1.3x avg volume
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_hours():
    ist_now = get_ist_now()
    if ist_now.weekday() >= 5:
        return False
    market_open = datetime.strptime(CONFIG['market_open'], "%H:%M").time()
    market_close = datetime.strptime(CONFIG['market_close'], "%H:%M").time()
    return market_open <= ist_now.time() <= market_close

# ============================================================================
# TECHNICAL ANALYSIS FUNCTIONS
# ============================================================================

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices):
    exp12 = prices.ewm(span=12, adjust=False).mean()
    exp26 = prices.ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal

def calculate_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def calculate_volume_profile(df):
    """Analyze volume to detect buying/selling pressure"""
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
    
    # Check if volume confirms price movement
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    
    if price_change > 0 and volume_ratio > 1.3:
        return "STRONG_BUYING", volume_ratio
    elif price_change < 0 and volume_ratio > 1.3:
        return "STRONG_SELLING", volume_ratio
    elif price_change > 0:
        return "WEAK_BUYING", volume_ratio
    elif price_change < 0:
        return "WEAK_SELLING", volume_ratio
    else:
        return "NEUTRAL", volume_ratio

def find_support_resistance(df, lookback=50):
    """Find key support and resistance levels"""
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    close = df['Close'].tail(lookback)
    
    # Find pivot points
    pivot_highs = []
    pivot_lows = []
    
    for i in range(2, len(high) - 2):
        # Pivot high
        if high.iloc[i] > high.iloc[i-1] and high.iloc[i] > high.iloc[i-2] and \
           high.iloc[i] > high.iloc[i+1] and high.iloc[i] > high.iloc[i+2]:
            pivot_highs.append(high.iloc[i])
        
        # Pivot low
        if low.iloc[i] < low.iloc[i-1] and low.iloc[i] < low.iloc[i-2] and \
           low.iloc[i] < low.iloc[i+1] and low.iloc[i] < low.iloc[i+2]:
            pivot_lows.append(low.iloc[i])
    
    current_price = close.iloc[-1]
    
    # Find nearest support (below current price)
    supports = [p for p in pivot_lows if p < current_price]
    nearest_support = max(supports) if supports else current_price * 0.95
    
    # Find nearest resistance (above current price)
    resistances = [p for p in pivot_highs if p > current_price]
    nearest_resistance = min(resistances) if resistances else current_price * 1.05
    
    return nearest_support, nearest_resistance

def calculate_momentum_score(df):
    """Calculate overall momentum score (0-100)"""
    close = df['Close']
    
    score = 50  # Start neutral
    
    # RSI contribution (0-20 points)
    rsi = calculate_rsi(close).iloc[-1]
    if rsi > 60:
        score += (rsi - 60) * 0.5  # Up to +20
    elif rsi < 40:
        score -= (40 - rsi) * 0.5  # Down to -20
    
    # MACD contribution (0-20 points)
    macd, signal, histogram = calculate_macd(close)
    if histogram.iloc[-1] > 0:
        if histogram.iloc[-1] > histogram.iloc[-2]:
            score += 20  # Strong bullish
        else:
            score += 10  # Weak bullish
    else:
        if histogram.iloc[-1] < histogram.iloc[-2]:
            score -= 20  # Strong bearish
        else:
            score -= 10  # Weak bearish
    
    # Moving average contribution (0-20 points)
    sma_20 = close.rolling(20).mean().iloc[-1]
    sma_50 = close.rolling(50).mean().iloc[-1]
    current_price = close.iloc[-1]
    
    if current_price > sma_20 > sma_50:
        score += 20  # Strong uptrend
    elif current_price > sma_20:
        score += 10  # Above short-term MA
    elif current_price < sma_20 < sma_50:
        score -= 20  # Strong downtrend
    elif current_price < sma_20:
        score -= 10  # Below short-term MA
    
    # Price momentum (0-10 points)
    returns_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100
    score += min(10, max(-10, returns_5d * 2))
    
    return max(0, min(100, score))

# ============================================================================
# SMART PREDICTION FUNCTIONS
# ============================================================================

def predict_stop_loss_risk(df, current_price, stop_loss, position_type):
    """
    Predict likelihood of hitting stop loss
    Returns: risk_score (0-100), reasons, recommendation
    """
    risk_score = 0
    reasons = []
    
    close = df['Close']
    
    # 1. Distance to stop loss
    if position_type == "LONG":
        distance_pct = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_pct = ((stop_loss - current_price) / current_price) * 100
    
    if distance_pct < 1:
        risk_score += 40
        reasons.append(f"Very close to SL ({distance_pct:.1f}% away)")
    elif distance_pct < 2:
        risk_score += 25
        reasons.append(f"Close to SL ({distance_pct:.1f}% away)")
    elif distance_pct < 3:
        risk_score += 10
    
    # 2. Trend direction
    sma_20 = close.rolling(20).mean().iloc[-1]
    sma_50 = close.rolling(50).mean().iloc[-1]
    
    if position_type == "LONG":
        if current_price < sma_20:
            risk_score += 15
            reasons.append("Price below 20 SMA (bearish)")
        if current_price < sma_50:
            risk_score += 10
            reasons.append("Price below 50 SMA (bearish)")
        if sma_20 < sma_50:
            risk_score += 10
            reasons.append("20 SMA below 50 SMA (downtrend)")
    else:  # SHORT
        if current_price > sma_20:
            risk_score += 15
            reasons.append("Price above 20 SMA (bullish)")
        if current_price > sma_50:
            risk_score += 10
            reasons.append("Price above 50 SMA (bullish)")
    
    # 3. MACD direction
    macd, signal, histogram = calculate_macd(close)
    
    if position_type == "LONG":
        if histogram.iloc[-1] < 0 and histogram.iloc[-1] < histogram.iloc[-2]:
            risk_score += 15
            reasons.append("MACD bearish and falling")
        elif histogram.iloc[-1] < 0:
            risk_score += 8
    else:
        if histogram.iloc[-1] > 0 and histogram.iloc[-1] > histogram.iloc[-2]:
            risk_score += 15
            reasons.append("MACD bullish and rising")
    
    # 4. RSI
    rsi = calculate_rsi(close).iloc[-1]
    
    if position_type == "LONG" and rsi < 35:
        risk_score += 10
        reasons.append(f"RSI weak ({rsi:.1f})")
    elif position_type == "SHORT" and rsi > 65:
        risk_score += 10
        reasons.append(f"RSI strong ({rsi:.1f})")
    
    # 5. Volume analysis
    volume_type, volume_ratio = calculate_volume_profile(df)
    
    if position_type == "LONG" and volume_type == "STRONG_SELLING":
        risk_score += 15
        reasons.append(f"Strong selling pressure ({volume_ratio:.1f}x volume)")
    elif position_type == "SHORT" and volume_type == "STRONG_BUYING":
        risk_score += 15
        reasons.append(f"Strong buying pressure ({volume_ratio:.1f}x volume)")
    
    # 6. Recent price action
    last_3_candles = close.tail(3)
    if position_type == "LONG":
        if all(last_3_candles.diff().dropna() < 0):
            risk_score += 10
            reasons.append("3 consecutive red candles")
    else:
        if all(last_3_candles.diff().dropna() > 0):
            risk_score += 10
            reasons.append("3 consecutive green candles")
    
    # Cap at 100
    risk_score = min(100, risk_score)
    
    # Generate recommendation
    if risk_score >= 70:
        recommendation = "EXIT NOW - High risk of SL hit"
        priority = "CRITICAL"
    elif risk_score >= 50:
        recommendation = "CONSIDER EXIT - Moderate risk"
        priority = "HIGH"
    elif risk_score >= 30:
        recommendation = "WATCH CLOSELY - Some warning signs"
        priority = "MEDIUM"
    else:
        recommendation = "HOLD - Position looks safe"
        priority = "LOW"
    
    return risk_score, reasons, recommendation, priority

def predict_upside_potential(df, current_price, target1, target2, position_type):
    """
    Predict if stock can go higher after hitting target
    Returns: upside_score (0-100), new_target, recommendation
    """
    upside_score = 50  # Start neutral
    reasons = []
    
    close = df['Close']
    high = df['High']
    
    # 1. Momentum score
    momentum = calculate_momentum_score(df)
    if momentum > 70:
        upside_score += 20
        reasons.append(f"Strong momentum ({momentum:.0f}/100)")
    elif momentum > 55:
        upside_score += 10
        reasons.append(f"Good momentum ({momentum:.0f}/100)")
    elif momentum < 40:
        upside_score -= 15
        reasons.append(f"Weak momentum ({momentum:.0f}/100)")
    
    # 2. RSI - not overbought
    rsi = calculate_rsi(close).iloc[-1]
    
    if position_type == "LONG":
        if rsi < 60:
            upside_score += 15
            reasons.append(f"RSI has room to run ({rsi:.1f})")
        elif rsi > 75:
            upside_score -= 20
            reasons.append(f"RSI overbought ({rsi:.1f})")
    else:  # SHORT
        if rsi > 40:
            upside_score += 15
            reasons.append(f"RSI has room to fall ({rsi:.1f})")
        elif rsi < 25:
            upside_score -= 20
            reasons.append(f"RSI oversold ({rsi:.1f})")
    
    # 3. Volume confirmation
    volume_type, volume_ratio = calculate_volume_profile(df)
    
    if position_type == "LONG" and volume_type == "STRONG_BUYING":
        upside_score += 15
        reasons.append(f"Strong buying volume ({volume_ratio:.1f}x)")
    elif position_type == "SHORT" and volume_type == "STRONG_SELLING":
        upside_score += 15
        reasons.append(f"Strong selling volume ({volume_ratio:.1f}x)")
    
    # 4. Bollinger Band position
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(close)
    
    if position_type == "LONG":
        bb_position = (current_price - lower_bb.iloc[-1]) / (upper_bb.iloc[-1] - lower_bb.iloc[-1])
        if bb_position < 0.7:
            upside_score += 10
            reasons.append("Room to upper Bollinger Band")
        elif bb_position > 0.95:
            upside_score -= 15
            reasons.append("At upper Bollinger Band")
    else:
        bb_position = (current_price - lower_bb.iloc[-1]) / (upper_bb.iloc[-1] - lower_bb.iloc[-1])
        if bb_position > 0.3:
            upside_score += 10
            reasons.append("Room to lower Bollinger Band")
    
    # 5. Find resistance for new target
    support, resistance = find_support_resistance(df)
    atr = calculate_atr(high, df['Low'], close).iloc[-1]
    
    if position_type == "LONG":
        # New target based on resistance and ATR
        new_target = min(resistance, current_price + (atr * 3))
        potential_gain = ((new_target - current_price) / current_price) * 100
    else:
        new_target = max(support, current_price - (atr * 3))
        potential_gain = ((current_price - new_target) / current_price) * 100
    
    if potential_gain > 5:
        upside_score += 10
        reasons.append(f"Potential {potential_gain:.1f}% more")
    
    # Cap score
    upside_score = max(0, min(100, upside_score))
    
    # Generate recommendation
    if upside_score >= 70:
        recommendation = f"HOLD - Strong upside to Rs.{new_target:.2f}"
        action = "HOLD_EXTEND_TARGET"
    elif upside_score >= 50:
        recommendation = f"PARTIAL EXIT - Book 50%, hold rest for Rs.{new_target:.2f}"
        action = "PARTIAL_EXIT"
    else:
        recommendation = "EXIT - Book profits now"
        action = "EXIT"
    
    return upside_score, new_target, reasons, recommendation, action

def calculate_dynamic_targets(df, entry_price, position_type):
    """Calculate smart dynamic targets based on ATR and S/R levels"""
    close = df['Close']
    current_price = close.iloc[-1]
    
    atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
    support, resistance = find_support_resistance(df)
    
    if position_type == "LONG":
        # Target 1: 1.5x ATR or next resistance
        target1_atr = current_price + (atr * 1.5)
        target1 = min(target1_atr, resistance) if resistance > current_price else target1_atr
        
        # Target 2: 3x ATR
        target2 = current_price + (atr * 3)
        
        # Stop loss: 2x ATR below entry or support
        stop_loss_atr = entry_price - (atr * 2)
        stop_loss = max(stop_loss_atr, support * 0.99) if support < entry_price else stop_loss_atr
        
        # Trailing stop (if in profit)
        if current_price > entry_price:
            trail_stop = current_price - (atr * 1.5)
        else:
            trail_stop = stop_loss
    else:  # SHORT
        target1_atr = current_price - (atr * 1.5)
        target1 = max(target1_atr, support) if support < current_price else target1_atr
        
        target2 = current_price - (atr * 3)
        
        stop_loss_atr = entry_price + (atr * 2)
        stop_loss = min(stop_loss_atr, resistance * 1.01) if resistance > entry_price else stop_loss_atr
        
        if current_price < entry_price:
            trail_stop = current_price + (atr * 1.5)
        else:
            trail_stop = stop_loss
    
    return {
        'target1': target1,
        'target2': target2,
        'stop_loss': stop_loss,
        'trail_stop': trail_stop,
        'atr': atr,
        'support': support,
        'resistance': resistance
    }

# ============================================================================
# SMART ANALYSIS
# ============================================================================

def smart_analyze_position(position_data):
    """Enhanced analysis with predictions"""
    ticker = str(position_data['Ticker'])
    symbol = ticker if '.NS' in ticker else f"{ticker}.NS"
    position_type = str(position_data['Position']).upper()
    entry_price = float(position_data['Entry_Price'])
    quantity = int(position_data.get('Quantity', 1))
    stop_loss = float(position_data['Stop_Loss'])
    target1 = float(position_data['Target_1'])
    target2 = float(position_data.get('Target_2', target1 * 1.1))
    
    log(f"Smart analyzing {ticker}...")
    
    # Fetch data
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="6mo")  # Get more data for better analysis
        
        if df.empty:
            symbol = symbol.replace('.NS', '.BO')
            stock = yf.Ticker(symbol)
            df = stock.history(period="6mo")
        
        if df.empty:
            log(f"No data for {ticker}", "WARNING")
            return None
        
        df.reset_index(inplace=True)
        current_price = float(df['Close'].iloc[-1])
        
    except Exception as e:
        log(f"Error fetching {ticker}: {e}", "ERROR")
        return None
    
    # Basic calculations
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
    else:
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
    
    # Technical indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1])
    momentum_score = calculate_momentum_score(df)
    volume_type, volume_ratio = calculate_volume_profile(df)
    
    # SMART PREDICTIONS
    
    # 1. Predict stop loss risk
    sl_risk, sl_reasons, sl_recommendation, sl_priority = predict_stop_loss_risk(
        df, current_price, stop_loss, position_type
    )
    
    # 2. Check if target hit and predict upside
    target_hit = False
    upside_score = 0
    new_target = target2
    upside_reasons = []
    upside_recommendation = ""
    
    if position_type == "LONG" and current_price >= target1:
        target_hit = True
        upside_score, new_target, upside_reasons, upside_recommendation, upside_action = predict_upside_potential(
            df, current_price, target1, target2, position_type
        )
    elif position_type == "SHORT" and current_price <= target1:
        target_hit = True
        upside_score, new_target, upside_reasons, upside_recommendation, upside_action = predict_upside_potential(
            df, current_price, target1, target2, position_type
        )
    
    # 3. Calculate dynamic levels
    dynamic_levels = calculate_dynamic_targets(df, entry_price, position_type)
    
    # Generate smart alerts
    alerts = []
    
    # Early exit warning (BEFORE SL hits)
    if sl_risk >= 50 and not (position_type == "LONG" and current_price <= stop_loss) and \
       not (position_type == "SHORT" and current_price >= stop_loss):
        alerts.append({
            'type': 'EARLY EXIT WARNING',
            'priority': sl_priority,
            'message': f"SL Risk: {sl_risk}% - {', '.join(sl_reasons[:2])}",
            'action': sl_recommendation
        })
    
    # Stop loss hit
    sl_hit = (position_type == "LONG" and current_price <= stop_loss) or \
             (position_type == "SHORT" and current_price >= stop_loss)
    if sl_hit:
        alerts.append({
            'type': 'STOP LOSS HIT',
            'priority': 'CRITICAL',
            'message': f'Price Rs.{current_price:.2f} hit stop loss Rs.{stop_loss:.2f}',
            'action': 'EXIT IMMEDIATELY'
        })
    
    # Target hit with upside analysis
    if target_hit:
        if upside_score >= 60:
            alerts.append({
                'type': 'TARGET HIT - HOLD FOR MORE',
                'priority': 'HIGH',
                'message': f"Upside potential: {upside_score}% - {', '.join(upside_reasons[:2])}",
                'action': f"{upside_recommendation} | New Target: Rs.{new_target:.2f}"
            })
        else:
            alerts.append({
                'type': 'TARGET HIT - BOOK PROFITS',
                'priority': 'HIGH',
                'message': f"Limited upside ({upside_score}%) - {', '.join(upside_reasons[:2])}",
                'action': 'BOOK PROFITS NOW'
            })
    
    # Trailing stop loss suggestion
    if pnl_percent >= 3:  # In good profit
        if position_type == "LONG" and dynamic_levels['trail_stop'] > stop_loss:
            alerts.append({
                'type': 'TRAIL STOP LOSS',
                'priority': 'MEDIUM',
                'message': f"Lock in profits. Move SL from Rs.{stop_loss:.2f} to Rs.{dynamic_levels['trail_stop']:.2f}",
                'action': f"New SL: Rs.{dynamic_levels['trail_stop']:.2f}"
            })
        elif position_type == "SHORT" and dynamic_levels['trail_stop'] < stop_loss:
            alerts.append({
                'type': 'TRAIL STOP LOSS',
                'priority': 'MEDIUM',
                'message': f"Lock in profits. Move SL from Rs.{stop_loss:.2f} to Rs.{dynamic_levels['trail_stop']:.2f}",
                'action': f"New SL: Rs.{dynamic_levels['trail_stop']:.2f}"
            })
    
    # Dynamic target update suggestion
    if not target_hit and pnl_percent > 0:
        if position_type == "LONG" and dynamic_levels['target1'] > target1:
            alerts.append({
                'type': 'UPDATE TARGET',
                'priority': 'LOW',
                'message': f"Based on momentum, consider new target Rs.{dynamic_levels['target1']:.2f}",
                'action': 'OPTIONAL: Extend target'
            })
    
    # Determine overall recommendation
    if sl_hit:
        overall_action = "EXIT"
        overall_status = "CRITICAL"
    elif sl_risk >= 70:
        overall_action = "EXIT_EARLY"
        overall_status = "CRITICAL"
    elif sl_risk >= 50:
        overall_action = "WATCH_CLOSELY"
        overall_status = "WARNING"
    elif target_hit and upside_score >= 60:
        overall_action = "HOLD_EXTEND"
        overall_status = "OPPORTUNITY"
    elif target_hit:
        overall_action = "BOOK_PROFITS"
        overall_status = "SUCCESS"
    elif pnl_percent >= 3:
        overall_action = "TRAIL_SL"
        overall_status = "GOOD"
    else:
        overall_action = "HOLD"
        overall_status = "OK"
    
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
        
        # Technical
        'rsi': rsi,
        'macd_histogram': macd_hist,
        'momentum_score': momentum_score,
        'volume_type': volume_type,
        'volume_ratio': volume_ratio,
        
        # Smart predictions
        'sl_risk_score': sl_risk,
        'sl_reasons': sl_reasons,
        'upside_score': upside_score,
        'upside_reasons': upside_reasons,
        'new_suggested_target': new_target,
        
        # Dynamic levels
        'dynamic_target1': dynamic_levels['target1'],
        'dynamic_target2': dynamic_levels['target2'],
        'dynamic_stop_loss': dynamic_levels['stop_loss'],
        'trail_stop': dynamic_levels['trail_stop'],
        'support': dynamic_levels['support'],
        'resistance': dynamic_levels['resistance'],
        
        # Alerts and status
        'alerts': alerts,
        'overall_action': overall_action,
        'overall_status': overall_status
    }

# ============================================================================
# EMAIL FUNCTION
# ============================================================================

def send_smart_email(results):
    """Send comprehensive smart analysis email"""
    ist_now = get_ist_now()
    
    total_pnl = sum(r['pnl_amount'] for r in results)
    pnl_color = '#28a745' if total_pnl >= 0 else '#dc3545'
    
    # Count by status
    critical_count = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['overall_status'] == 'WARNING')
    
    # Build positions HTML
    positions_html = ""
    for r in results:
        status_colors = {
            'CRITICAL': '#dc3545',
            'WARNING': '#fd7e14',
            'OPPORTUNITY': '#17a2b8',
            'SUCCESS': '#28a745',
            'GOOD': '#28a745',
            'OK': '#6c757d'
        }
        status_color = status_colors.get(r['overall_status'], '#6c757d')
        pnl_c = '#28a745' if r['pnl_percent'] >= 0 else '#dc3545'
        
        # Risk indicator
        if r['sl_risk_score'] >= 70:
            risk_display = f"<span style='color:#dc3545;font-weight:bold;'>HIGH RISK ({r['sl_risk_score']}%)</span>"
        elif r['sl_risk_score'] >= 50:
            risk_display = f"<span style='color:#fd7e14;'>MODERATE ({r['sl_risk_score']}%)</span>"
        else:
            risk_display = f"<span style='color:#28a745;'>LOW ({r['sl_risk_score']}%)</span>"
        
        # Alerts for this position
        alerts_html = ""
        for alert in r['alerts']:
            alert_color = '#dc3545' if alert['priority'] == 'CRITICAL' else '#fd7e14' if alert['priority'] == 'HIGH' else '#ffc107'
            alerts_html += f"""
            <div style="background:{alert_color}20; border-left:4px solid {alert_color}; padding:10px; margin:5px 0; border-radius:5px;">
                <strong>[{alert['priority']}] {alert['type']}</strong><br>
                {alert['message']}<br>
                <strong>Action: {alert['action']}</strong>
            </div>
            """
        
        positions_html += f"""
        <div style="background:#f8f9fa; padding:20px; border-radius:10px; margin:15px 0; border-left:5px solid {status_color};">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <div>
                    <h3 style="margin:0; color:#333;">{r['ticker']}</h3>
                    <span style="background:{'#28a745' if r['position_type']=='LONG' else '#dc3545'}; color:white; padding:3px 10px; border-radius:3px; font-size:12px;">
                        {r['position_type']}
                    </span>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:24px; font-weight:bold; color:{pnl_c};">
                        {r['pnl_percent']:+.2f}%
                    </div>
                    <div style="color:{pnl_c};">Rs. {r['pnl_amount']:+,.2f}</div>
                </div>
            </div>
            
            <table style="width:100%; font-size:14px;">
                <tr>
                    <td>Entry: Rs.{r['entry_price']:,.2f}</td>
                    <td>Current: Rs.{r['current_price']:,.2f}</td>
                    <td>SL: Rs.{r['stop_loss']:,.2f}</td>
                    <td>Target: Rs.{r['target1']:,.2f}</td>
                </tr>
            </table>
            
            <div style="margin-top:15px; padding:10px; background:white; border-radius:5px;">
                <strong>Smart Analysis:</strong><br>
                SL Risk: {risk_display} | 
                Momentum: {r['momentum_score']:.0f}/100 | 
                RSI: {r['rsi']:.1f} |
                Volume: {r['volume_type'].replace('_', ' ')} ({r['volume_ratio']:.1f}x)
            </div>
            
            <div style="margin-top:10px; padding:10px; background:#e3f2fd; border-radius:5px;">
                <strong>Smart Levels:</strong><br>
                Support: Rs.{r['support']:,.2f} | 
                Resistance: Rs.{r['resistance']:,.2f} |
                Trail SL: Rs.{r['trail_stop']:,.2f}
            </div>
            
            {alerts_html if alerts_html else '<p style="color:#28a745; margin-top:10px;">✓ No alerts - Position looks good</p>'}
            
            <div style="margin-top:15px; padding:15px; background:{status_color}; color:white; border-radius:5px; text-align:center;">
                <strong>RECOMMENDATION: {r['overall_action'].replace('_', ' ')}</strong>
            </div>
        </div>
        """
    
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family:Arial,sans-serif; max-width:800px; margin:0 auto; padding:20px; background:#f5f5f5;">
    <div style="background:white; border-radius:15px; padding:25px; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        
        <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; padding:30px; border-radius:10px; text-align:center; margin-bottom:25px;">
            <h1 style="margin:0;">🧠 Smart Portfolio Analysis</h1>
            <p style="margin:10px 0 0 0;">{ist_now.strftime('%A, %B %d, %Y')} | {ist_now.strftime('%H:%M')} IST</p>
        </div>
        
        <div style="display:flex; justify-content:space-around; margin-bottom:25px; flex-wrap:wrap;">
            <div style="flex:1; min-width:100px; background:#f8f9fa; padding:15px; border-radius:10px; text-align:center; margin:5px;">
                <div style="font-size:24px; font-weight:bold; color:{pnl_color};">Rs. {total_pnl:+,.2f}</div>
                <div style="color:#666; font-size:12px;">Total P&L</div>
            </div>
            <div style="flex:1; min-width:100px; background:#f8f9fa; padding:15px; border-radius:10px; text-align:center; margin:5px;">
                <div style="font-size:24px; font-weight:bold; color:#dc3545;">{critical_count}</div>
                <div style="color:#666; font-size:12px;">Critical</div>
            </div>
            <div style="flex:1; min-width:100px; background:#f8f9fa; padding:15px; border-radius:10px; text-align:center; margin:5px;">
                <div style="font-size:24px; font-weight:bold; color:#fd7e14;">{warning_count}</div>
                <div style="color:#666; font-size:12px;">Warnings</div>
            </div>
        </div>
        
        {positions_html}
        
        <div style="text-align:center; color:#999; font-size:12px; margin-top:20px; padding-top:20px; border-top:1px solid #eee;">
            Smart Portfolio Monitor v4.0 | Predictive Analysis Enabled
        </div>
    </div>
</body>
</html>
    """
    
    subject = f"🧠 Smart Analysis: {critical_count} Critical, {warning_count} Warnings | P&L: Rs.{total_pnl:+,.2f}"
    
    # Send email
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = CONFIG['sender_email']
        msg['To'] = CONFIG['recipient_email']
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP(CONFIG['smtp_server'], CONFIG['smtp_port'])
        server.starttls()
        server.login(CONFIG['sender_email'], CONFIG['sender_password'])
        server.sendmail(CONFIG['sender_email'], CONFIG['recipient_email'], msg.as_string())
        server.quit()
        
        log(f"Smart email sent!")
        return True
    except Exception as e:
        log(f"Email error: {e}", "ERROR")
        return False

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def run_smart_monitor(force_run=False):
    """Run smart portfolio monitor"""
    ist_now = get_ist_now()
    
    log("=" * 70)
    log("SMART PORTFOLIO MONITOR v4.0 - PREDICTIVE EDITION")
    log("=" * 70)
    log(f"Current IST: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check market hours
    if not force_run and not is_market_hours():
        log("Market is closed. Use --force to run anyway.")
        return
    
    # Load portfolio
    if not os.path.exists(CONFIG['excel_file']):
        log(f"Portfolio file not found: {CONFIG['excel_file']}", "ERROR")
        return
    
    try:
        portfolio = pd.read_excel(CONFIG['excel_file'], sheet_name='Portfolio')
        if 'Status' in portfolio.columns:
            portfolio = portfolio[portfolio['Status'].str.upper() == 'ACTIVE']
        log(f"Loaded {len(portfolio)} active positions")
    except Exception as e:
        log(f"Error loading portfolio: {e}", "ERROR")
        return
    
    # Analyze each position
    results = []
    
    log("-" * 70)
    for _, row in portfolio.iterrows():
        result = smart_analyze_position(row.to_dict())
        if result:
            results.append(result)
            
            # Print summary
            status_icon = {'CRITICAL': '🔴', 'WARNING': '🟡', 'OPPORTUNITY': '🔵', 
                          'SUCCESS': '🟢', 'GOOD': '🟢', 'OK': '⚪'}.get(result['overall_status'], '⚪')
            
            log(f"  {status_icon} {result['ticker']}: Rs.{result['current_price']:.2f} | "
                f"P&L: {result['pnl_percent']:+.2f}% | "
                f"SL Risk: {result['sl_risk_score']}% | "
                f"Action: {result['overall_action']}")
            
            for alert in result['alerts']:
                log(f"     ⚠️ [{alert['priority']}] {alert['type']}: {alert['action']}")
    
    # Send email
    if results:
        log("-" * 70)
        send_smart_email(results)
    
    # Summary
    log("-" * 70)
    total_pnl = sum(r['pnl_amount'] for r in results)
    critical = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warnings = sum(1 for r in results if r['overall_status'] == 'WARNING')
    
    log("SMART ANALYSIS SUMMARY:")
    log(f"  Positions: {len(results)}")
    log(f"  Total P&L: Rs. {total_pnl:+,.2f}")
    log(f"  Critical Actions: {critical}")
    log(f"  Warnings: {warnings}")
    log("=" * 70)

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Smart Portfolio Monitor')
    parser.add_argument('--force', action='store_true', help='Run even if market is closed')
    args = parser.parse_args()
    
    run_smart_monitor(force_run=args.force)
