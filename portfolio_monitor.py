"""
================================================================================
PORTFOLIO MONITOR v3.0 - GITHUB ACTIONS EDITION
================================================================================
Designed for GitHub Actions:
- Runs on schedule (cron)
- Sends email alerts and daily summary
- Reads portfolio from Excel in repo
- No web server needed
================================================================================
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get from environment variables (GitHub Secrets)
CONFIG = {
    # Email settings from GitHub Secrets
    "sender_email": os.environ.get("SENDER_EMAIL", ""),
    "sender_password": os.environ.get("SENDER_PASSWORD", ""),
    "recipient_email": os.environ.get("RECIPIENT_EMAIL", ""),
    "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
    
    # File paths
    "excel_file": "my_portfolio.xlsx",
    "alert_history_file": "alert_history.json",
    
    # Market hours (IST)
    "market_open": "09:15",
    "market_close": "15:30",
    
    # Alert thresholds
    "alert_on_loss_percent": -2.0,
    "alert_on_profit_percent": 5.0,
    "trailing_sl_trigger": 3.0,
    "trend_reversal_sensitivity": 0.7,
    
    # Email cooldown (minutes)
    "email_cooldown_minutes": 60,
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def get_ist_now():
    """Get current IST time"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_hours():
    """Check if market is open"""
    ist_now = get_ist_now()
    
    # Skip weekends
    if ist_now.weekday() >= 5:
        return False
    
    market_open = datetime.strptime(CONFIG['market_open'], "%H:%M").time()
    market_close = datetime.strptime(CONFIG['market_close'], "%H:%M").time()
    
    return market_open <= ist_now.time() <= market_close

def get_market_status():
    """Get market status details"""
    ist_now = get_ist_now()
    
    if ist_now.weekday() >= 5:
        return {'is_open': False, 'status': 'WEEKEND', 'message': 'Markets closed for weekend'}
    
    market_open = datetime.strptime(CONFIG['market_open'], "%H:%M").time()
    market_close = datetime.strptime(CONFIG['market_close'], "%H:%M").time()
    current_time = ist_now.time()
    
    if current_time < market_open:
        return {'is_open': False, 'status': 'PRE-MARKET', 'message': f'Opens at {CONFIG["market_open"]} IST'}
    elif current_time > market_close:
        return {'is_open': False, 'status': 'CLOSED', 'message': 'Market closed for today'}
    else:
        return {'is_open': True, 'status': 'OPEN', 'message': f'Closes at {CONFIG["market_close"]} IST'}

def load_alert_history():
    """Load alert history from JSON file"""
    try:
        if os.path.exists(CONFIG['alert_history_file']):
            with open(CONFIG['alert_history_file'], 'r') as f:
                return json.load(f)
    except Exception as e:
        log(f"Error loading alert history: {e}", "WARNING")
    return {'cooldowns': {}, 'history': []}

def save_alert_history(data):
    """Save alert history to JSON file"""
    try:
        with open(CONFIG['alert_history_file'], 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log(f"Error saving alert history: {e}", "ERROR")

def can_send_alert(ticker, alert_type, history):
    """Check if alert can be sent (cooldown check)"""
    key = f"{ticker}_{alert_type}"
    cooldown = timedelta(minutes=CONFIG['email_cooldown_minutes'])
    cooldowns = history.get('cooldowns', {})
    
    if key in cooldowns:
        try:
            last_time = datetime.fromisoformat(cooldowns[key])
            if datetime.now() - last_time < cooldown:
                return False
        except:
            pass
    
    cooldowns[key] = datetime.now().isoformat()
    history['cooldowns'] = cooldowns
    return True

# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_email(subject, html_content):
    """Send email"""
    if not CONFIG['sender_email'] or not CONFIG['sender_password']:
        log("Email credentials not configured. Skipping email.", "WARNING")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = CONFIG['sender_email']
        msg['To'] = CONFIG['recipient_email']
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP(CONFIG['smtp_server'], CONFIG['smtp_port'])
        server.starttls()
        server.login(CONFIG['sender_email'], CONFIG['sender_password'])
        server.sendmail(CONFIG['sender_email'], CONFIG['recipient_email'], msg.as_string())
        server.quit()
        
        log(f"Email sent: {subject}")
        return True
    except Exception as e:
        log(f"Email error: {e}", "ERROR")
        return False

def send_alert_email(result, alert):
    """Send individual alert email"""
    r = result
    pnl_color = '#28a745' if r['pnl_percent'] >= 0 else '#dc3545'
    priority_colors = {'CRITICAL': '#dc3545', 'HIGH': '#fd7e14', 'MEDIUM': '#ffc107'}
    priority_color = priority_colors.get(alert['priority'], '#6c757d')
    ist_now = get_ist_now()
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
    <div style="background: white; border-radius: 15px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        
        <!-- Header -->
        <div style="background: {priority_color}; color: white; padding: 25px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
            <h2 style="margin: 0; font-size: 18px;">[{alert['priority']}] {alert['type']}</h2>
            <h1 style="margin: 10px 0 0 0; font-size: 32px;">{r['ticker']}</h1>
        </div>
        
        <!-- Position Details -->
        <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 15px 0; color: #333;">Position Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">Position Type</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">
                        <span style="background: {'#28a745' if r['position_type'] == 'LONG' else '#dc3545'}; color: white; padding: 3px 10px; border-radius: 3px;">
                            {r['position_type']}
                        </span>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">Entry Price</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">Rs. {r['entry_price']:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">Current Price</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">Rs. {r['current_price']:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">P&L</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold; color: {pnl_color};">
                        {r['pnl_percent']:+.2f}% (Rs. {r['pnl_amount']:+,.2f})
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">Stop Loss</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">Rs. {r['stop_loss']:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">Target 1</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">Rs. {r['target1']:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0;">Quantity</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: bold;">{r['quantity']}</td>
                </tr>
            </table>
        </div>
        
        <!-- Technical Indicators -->
        <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 15px 0; color: #333;">Technical Indicators</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">RSI (14)</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{r['rsi']:.1f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee;">Trend</td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #eee; text-align: right; font-weight: bold; color: {'#28a745' if r['trend'] == 'BULLISH' else '#dc3545'};">
                        {r['trend']} ({r['trend_strength']:.0f}%)
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0;">MACD Histogram</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: bold;">{r['macd_histogram']:.2f}</td>
                </tr>
            </table>
        </div>
        
        <!-- Alert Message -->
        <div style="background: #fff3cd; padding: 15px; border-radius: 10px; border-left: 4px solid #ffc107; margin-bottom: 20px;">
            <strong>Alert:</strong> {alert['message']}
        </div>
        
        <!-- Action Box -->
        <div style="background: #007bff; color: white; padding: 25px; border-radius: 10px; text-align: center;">
            <h3 style="margin: 0; font-size: 14px;">RECOMMENDED ACTION</h3>
            <p style="margin: 10px 0 0 0; font-size: 20px; font-weight: bold;">{alert['action']}</p>
        </div>
        
        <!-- Footer -->
        <p style="text-align: center; color: #999; font-size: 12px; margin-top: 20px;">
            Portfolio Monitor | {ist_now.strftime('%Y-%m-%d %H:%M:%S')} IST<br>
            Powered by GitHub Actions
        </p>
    </div>
</body>
</html>
    """
    
    return send_email(f"[{alert['priority']}] {r['ticker']}: {alert['type']}", html)

def send_summary_email(results, market):
    """Send portfolio summary email"""
    ist_now = get_ist_now()
    total_pnl = sum(r['pnl_amount'] for r in results) if results else 0
    total_pnl_color = '#28a745' if total_pnl >= 0 else '#dc3545'
    total_alerts = sum(len(r.get('alerts', [])) for r in results)
    
    # Build positions table
    positions_html = ""
    for r in results:
        pnl_color = '#28a745' if r['pnl_percent'] >= 0 else '#dc3545'
        status_color = '#dc3545' if r['status'] == 'CRITICAL' else '#ffc107' if r['status'] in ['WARNING', 'INFO'] else '#28a745'
        pos_color = '#28a745' if r['position_type'] == 'LONG' else '#dc3545'
        
        positions_html += f"""
        <tr>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee;"><strong>{r['ticker']}</strong></td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee;">
                <span style="background: {pos_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">
                    {r['position_type']}
                </span>
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: right;">Rs. {r['entry_price']:,.2f}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: right;">Rs. {r['current_price']:,.2f}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: right; color: {pnl_color}; font-weight: bold;">
                {r['pnl_percent']:+.2f}%<br>
                <small>Rs. {r['pnl_amount']:+,.2f}</small>
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: center;">{r['rsi']:.1f}</td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: center; color: {'#28a745' if r['trend'] == 'BULLISH' else '#dc3545'};">
                {r['trend']}
            </td>
            <td style="padding: 12px 8px; border-bottom: 1px solid #eee; text-align: center;">
                <span style="background: {status_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px;">
                    {r['status']}
                </span>
            </td>
        </tr>
        """
    
    # Build alerts section
    alerts_html = ""
    for r in results:
        for alert in r.get('alerts', []):
            priority_color = '#dc3545' if alert['priority'] == 'CRITICAL' else '#fd7e14' if alert['priority'] == 'HIGH' else '#ffc107'
            alerts_html += f"""
            <div style="background: #f8f9fa; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid {priority_color};">
                <strong>[{alert['priority']}] {r['ticker']}</strong>: {alert['type']}<br>
                <small style="color: #666;">{alert['message']}</small><br>
                <strong style="color: #007bff;">Action: {alert['action']}</strong>
            </div>
            """
    
    if not alerts_html:
        alerts_html = '<p style="color: #28a745; text-align: center; padding: 20px;">All positions are healthy! No alerts.</p>'
    
    market_color = '#28a745' if market['is_open'] else '#dc3545'
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
    <div style="background: white; border-radius: 15px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 25px;">
            <h1 style="margin: 0; font-size: 24px;">Portfolio Summary</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">{ist_now.strftime('%A, %B %d, %Y')} | {ist_now.strftime('%H:%M')} IST</p>
        </div>
        
        <!-- Summary Cards -->
        <div style="display: flex; justify-content: space-between; margin-bottom: 25px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 120px; background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; margin: 5px;">
                <div style="font-size: 24px; font-weight: bold; color: {total_pnl_color};">Rs. {total_pnl:+,.2f}</div>
                <div style="color: #666; font-size: 12px; margin-top: 5px;">Total P&L</div>
            </div>
            <div style="flex: 1; min-width: 120px; background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; margin: 5px;">
                <div style="font-size: 24px; font-weight: bold; color: #333;">{len(results)}</div>
                <div style="color: #666; font-size: 12px; margin-top: 5px;">Positions</div>
            </div>
            <div style="flex: 1; min-width: 120px; background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; margin: 5px;">
                <div style="font-size: 24px; font-weight: bold; color: {'#dc3545' if total_alerts > 0 else '#28a745'};">{total_alerts}</div>
                <div style="color: #666; font-size: 12px; margin-top: 5px;">Alerts</div>
            </div>
            <div style="flex: 1; min-width: 120px; background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; margin: 5px;">
                <div style="font-size: 18px; font-weight: bold;">
                    <span style="background: {market_color}; color: white; padding: 3px 10px; border-radius: 3px;">{market['status']}</span>
                </div>
                <div style="color: #666; font-size: 12px; margin-top: 8px;">Market</div>
            </div>
        </div>
        
        <!-- Positions Table -->
        <div style="margin-bottom: 25px;">
            <h3 style="color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px;">Your Positions</h3>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 12px 8px; text-align: left;">Ticker</th>
                            <th style="padding: 12px 8px; text-align: left;">Type</th>
                            <th style="padding: 12px 8px; text-align: right;">Entry</th>
                            <th style="padding: 12px 8px; text-align: right;">Current</th>
                            <th style="padding: 12px 8px; text-align: right;">P&L</th>
                            <th style="padding: 12px 8px; text-align: center;">RSI</th>
                            <th style="padding: 12px 8px; text-align: center;">Trend</th>
                            <th style="padding: 12px 8px; text-align: center;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {positions_html}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Alerts Section -->
        <div style="margin-bottom: 25px;">
            <h3 style="color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px;">Alerts & Recommendations</h3>
            {alerts_html}
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; color: #999; font-size: 12px; padding-top: 20px; border-top: 1px solid #eee;">
            <p>Portfolio Monitor v3.0 | Powered by GitHub Actions</p>
            <p>Data from Yahoo Finance | Generated at {ist_now.strftime('%Y-%m-%d %H:%M:%S')} IST</p>
        </div>
    </div>
</body>
</html>
    """
    
    subject = f"Portfolio Summary: {ist_now.strftime('%Y-%m-%d %H:%M')} | P&L: Rs. {total_pnl:+,.2f}"
    return send_email(subject, html)

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

def calculate_trend(prices, period=20):
    sma = prices.rolling(window=period).mean()
    above_sma = (prices > sma).astype(int)
    trend_consistency = above_sma.rolling(window=period).mean().iloc[-1]
    direction = "BULLISH" if trend_consistency > 0.5 else "BEARISH"
    strength = trend_consistency * 100 if direction == "BULLISH" else (1 - trend_consistency) * 100
    return direction, strength

def detect_trend_reversal(df, position_type):
    if len(df) < 20:
        return False, ""
    
    close = df['Close']
    rsi = calculate_rsi(close).iloc[-1]
    macd, signal, histogram = calculate_macd(close)
    macd_hist = histogram.iloc[-1]
    macd_hist_prev = histogram.iloc[-3:-1].mean()
    sma_20 = close.rolling(20).mean().iloc[-1]
    current_price = close.iloc[-1]
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    
    reversal_signals = []
    reversal_score = 0
    
    if position_type == "LONG":
        if rsi > 70:
            reversal_signals.append("RSI overbought")
            reversal_score += 1
        if macd_hist < 0 and macd_hist < macd_hist_prev:
            reversal_signals.append("MACD bearish")
            reversal_score += 1
        if current_price < ema_9:
            reversal_signals.append("Below EMA 9")
            reversal_score += 1
        if current_price < sma_20:
            reversal_signals.append("Below SMA 20")
            reversal_score += 2
    else:
        if rsi < 30:
            reversal_signals.append("RSI oversold")
            reversal_score += 1
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            reversal_signals.append("MACD bullish")
            reversal_score += 1
        if current_price > ema_9:
            reversal_signals.append("Above EMA 9")
            reversal_score += 1
        if current_price > sma_20:
            reversal_signals.append("Above SMA 20")
            reversal_score += 2
    
    threshold = 3 * CONFIG['trend_reversal_sensitivity']
    return reversal_score >= threshold, ", ".join(reversal_signals)

# ============================================================================
# PORTFOLIO FUNCTIONS
# ============================================================================

def load_portfolio():
    """Load portfolio from Excel file"""
    if not os.path.exists(CONFIG['excel_file']):
        log(f"Excel file not found: {CONFIG['excel_file']}", "ERROR")
        return None
    
    try:
        df = pd.read_excel(CONFIG['excel_file'], sheet_name='Portfolio')
        
        # Filter active positions
        if 'Status' in df.columns:
            df = df[df['Status'].str.upper() == 'ACTIVE']
        
        log(f"Loaded {len(df)} active positions")
        return df
    except Exception as e:
        log(f"Error loading portfolio: {e}", "ERROR")
        return None

def analyze_stock(position_data, alert_history):
    """Analyze a single stock position"""
    ticker = str(position_data['Ticker'])
    symbol = ticker if '.NS' in ticker else f"{ticker}.NS"
    position_type = str(position_data['Position']).upper()
    entry_price = float(position_data['Entry_Price'])
    quantity = int(position_data.get('Quantity', 1))
    stop_loss = float(position_data['Stop_Loss'])
    target1 = float(position_data['Target_1'])
    target2 = float(position_data.get('Target_2', target1 * 1.1))
    
    log(f"Analyzing {ticker}...")
    
    # Fetch stock data
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="3mo")
        
        if df.empty:
            symbol = symbol.replace('.NS', '.BO')
            stock = yf.Ticker(symbol)
            df = stock.history(period="3mo")
        
        if df.empty:
            log(f"No data for {ticker}", "WARNING")
            return None
        
        df.reset_index(inplace=True)
        current_price = float(df['Close'].iloc[-1])
        
    except Exception as e:
        log(f"Error fetching {ticker}: {e}", "ERROR")
        return None
    
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
    
    # Calculate technical indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    trend_dir, trend_str = calculate_trend(df['Close'])
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1])
    atr = float(calculate_atr(df['High'], df['Low'], df['Close']).iloc[-1])
    
    # Generate alerts
    alerts = []
    
    # Stop loss check
    sl_hit = (position_type == "LONG" and current_price <= stop_loss) or \
             (position_type == "SHORT" and current_price >= stop_loss)
    if sl_hit:
        alerts.append({
            'type': 'STOP LOSS HIT',
            'priority': 'CRITICAL',
            'message': f'Price Rs.{current_price:.2f} breached stop loss Rs.{stop_loss:.2f}',
            'action': 'EXIT IMMEDIATELY'
        })
    
    # Target checks
    if position_type == "LONG":
        if current_price >= target2:
            alerts.append({'type': 'TARGET 2 HIT', 'priority': 'HIGH', 'message': 'Target 2 reached!', 'action': 'BOOK FULL PROFITS'})
        elif current_price >= target1:
            alerts.append({'type': 'TARGET 1 HIT', 'priority': 'MEDIUM', 'message': 'Target 1 reached!', 'action': 'BOOK 50% PROFITS'})
    else:
        if current_price <= target2:
            alerts.append({'type': 'TARGET 2 HIT', 'priority': 'HIGH', 'message': 'Target 2 reached!', 'action': 'BOOK FULL PROFITS'})
        elif current_price <= target1:
            alerts.append({'type': 'TARGET 1 HIT', 'priority': 'MEDIUM', 'message': 'Target 1 reached!', 'action': 'BOOK 50% PROFITS'})
    
    # Trailing stop loss suggestion
    if pnl_percent >= CONFIG['trailing_sl_trigger']:
        if position_type == "LONG":
            suggested_sl = df['High'].tail(10).max() - (atr * 2)
            if suggested_sl > stop_loss:
                alerts.append({'type': 'TRAIL SL', 'priority': 'MEDIUM', 
                             'message': f'Trail SL to Rs.{suggested_sl:.2f}', 'action': 'UPDATE STOP LOSS'})
        else:
            suggested_sl = df['Low'].tail(10).min() + (atr * 2)
            if suggested_sl < stop_loss:
                alerts.append({'type': 'TRAIL SL', 'priority': 'MEDIUM',
                             'message': f'Trail SL to Rs.{suggested_sl:.2f}', 'action': 'UPDATE STOP LOSS'})
    
    # Trend reversal detection
    is_reversal, reversal_reasons = detect_trend_reversal(df, position_type)
    if is_reversal:
        alerts.append({'type': 'TREND REVERSAL', 'priority': 'HIGH',
                      'message': reversal_reasons, 'action': 'REVIEW POSITION'})
    
    # High loss warning
    if pnl_percent <= CONFIG['alert_on_loss_percent']:
        alerts.append({'type': 'HIGH LOSS', 'priority': 'HIGH',
                      'message': f'Loss exceeds {abs(CONFIG["alert_on_loss_percent"])}%', 'action': 'REVIEW POSITION'})
    
    # High profit notification
    if pnl_percent >= CONFIG['alert_on_profit_percent']:
        alerts.append({'type': 'HIGH PROFIT', 'priority': 'MEDIUM',
                      'message': f'Profit exceeds {CONFIG["alert_on_profit_percent"]}%', 'action': 'CONSIDER BOOKING PROFITS'})
    
    # Determine overall status
    if any(a['priority'] == 'CRITICAL' for a in alerts):
        status = 'CRITICAL'
    elif any(a['priority'] == 'HIGH' for a in alerts):
        status = 'WARNING'
    elif alerts:
        status = 'INFO'
    else:
        status = 'OK'
    
    log(f"  {ticker}: Rs.{current_price:.2f} | P&L: {pnl_percent:+.2f}% | Status: {status}")
    
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
        'status': status
    }

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def run_monitor(force_run=False, send_summary=True):
    """Main monitoring function"""
    ist_now = get_ist_now()
    market = get_market_status()
    
    log("=" * 60)
    log("PORTFOLIO MONITOR - GITHUB ACTIONS")
    log("=" * 60)
    log(f"Current IST: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Market Status: {market['status']} - {market['message']}")
    
    # Check market hours
    if not force_run and not market['is_open']:
        log("Market is closed. Use --force to run anyway.")
        return
    
    # Load portfolio
    portfolio = load_portfolio()
    if portfolio is None or len(portfolio) == 0:
        log("No positions to monitor", "ERROR")
        return
    
    # Load alert history
    alert_history = load_alert_history()
    
    # Analyze each position
    results = []
    alerts_sent = 0
    
    log("-" * 60)
    log("Analyzing positions...")
    
    for _, row in portfolio.iterrows():
        result = analyze_stock(row.to_dict(), alert_history)
        if result:
            results.append(result)
            
            # Send individual alert emails
            for alert in result['alerts']:
                if can_send_alert(result['ticker'], alert['type'], alert_history):
                    if send_alert_email(result, alert):
                        alerts_sent += 1
                        
                        # Add to history
                        if 'history' not in alert_history:
                            alert_history['history'] = []
                        alert_history['history'].insert(0, {
                            'timestamp': datetime.now().isoformat(),
                            'ticker': result['ticker'],
                            'type': alert['type'],
                            'priority': alert['priority'],
                            'message': alert['message']
                        })
                        alert_history['history'] = alert_history['history'][:100]
    
    # Save alert history
    save_alert_history(alert_history)
    
    # Send summary email
    if send_summary and results:
        log("-" * 60)
        log("Sending summary email...")
        send_summary_email(results, market)
    
    # Print summary
    log("-" * 60)
    total_pnl = sum(r['pnl_amount'] for r in results)
    log(f"SUMMARY:")
    log(f"  Positions analyzed: {len(results)}")
    log(f"  Alert emails sent: {alerts_sent}")
    log(f"  Total P&L: Rs. {total_pnl:+,.2f}")
    log("=" * 60)
    log("MONITOR COMPLETE")
    log("=" * 60)

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Monitor')
    parser.add_argument('--force', action='store_true', help='Run even if market is closed')
    parser.add_argument('--no-summary', action='store_true', help='Skip summary email')
    args = parser.parse_args()
    
    run_monitor(force_run=args.force, send_summary=not args.no_summary)
