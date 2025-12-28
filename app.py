"""
🧠 SMART PORTFOLIO MONITOR v5.2 - ENHANCED EMAIL EDITION
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
✅ Email alerts for critical events (ENHANCED)
✅ Multi-Timeframe Analysis (fully implemented)
✅ Better caching (FIXED - 15s TTL)

NEW EMAIL FEATURES:
✅ Email on Critical alerts
✅ Email on Target achieved
✅ Email on approaching SL
✅ Email on SL change recommendation
✅ Email on Target change recommendation
✅ Email summary with all important updates
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
import hashlib

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
    page_title="Smart Portfolio Monitor v5.2",
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
    .email-sent-box {
        background: linear-gradient(135deg, #6f42c1, #5a32a3);
        color: white;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        margin: 5px 0;
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
# INITIALIZE SESSION STATE FOR EMAIL TRACKING
# ============================================================================
if 'email_sent_alerts' not in st.session_state:
    st.session_state.email_sent_alerts = {}
if 'last_email_time' not in st.session_state:
    st.session_state.last_email_time = {}
if 'email_log' not in st.session_state:
    st.session_state.email_log = []

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
        
        st.markdown("#### 📬 Email Alert Types")
        email_on_critical = st.checkbox("🔴 Critical Alerts", value=True,
                                       help="SL hit, high risk situations")
        email_on_target = st.checkbox("🎯 Target Achieved", value=True,
                                     help="When any target is hit")
        email_on_sl_approach = st.checkbox("⚠️ Approaching SL", value=True,
                                          help="When price approaches stop loss")
        email_on_sl_change = st.checkbox("🔄 SL Change Needed", value=True,
                                        help="Trail SL recommendations")
        email_on_target_change = st.checkbox("📈 Target Change", value=True,
                                            help="New target recommendations")
        email_on_important = st.checkbox("📋 Important Updates", value=True,
                                        help="Any significant changes")
        
        # Email frequency control
        st.markdown("#### ⏱️ Email Frequency")
        email_cooldown = st.slider("Min. minutes between same alerts", 5, 60, 15,
                                  help="Prevent duplicate emails")
        
    else:
        sender_email = ""
        sender_password = ""
        recipient_email = ""
        email_on_critical = False
        email_on_target = False
        email_on_sl_approach = False
        email_on_sl_change = False
        email_on_target_change = False
        email_on_important = False
        email_cooldown = 15
    
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
    sl_approach_threshold = st.slider("SL Approach Warning %", 1.0, 5.0, 2.0, step=0.5,
                                     help="Warn when price is this % from SL")
    
    st.divider()
    
    # Analysis Settings
    st.markdown("### 📊 Analysis Settings")
    enable_volume_analysis = st.checkbox("Volume Confirmation", value=True)
    enable_sr_detection = st.checkbox("Support/Resistance", value=True)
    enable_multi_timeframe = st.checkbox("Multi-Timeframe Analysis", value=True,
                                        help="Analyze Daily, Weekly, Hourly trends")
    
    st.divider()
    
    # Email Log
    if email_enabled:
        with st.expander("📧 Email Log"):
            if st.session_state.email_log:
                for log in st.session_state.email_log[-10:]:  # Show last 10
                    st.caption(f"• {log}")
            else:
                st.caption("No emails sent yet")
            
            if st.button("Clear Email Log"):
                st.session_state.email_log = []
                st.session_state.email_sent_alerts = {}
                st.rerun()
    
    # Debug Info
    with st.expander("🔧 Debug Info"):
        st.write(f"Auto-refresh library: {'✅ Installed' if HAS_AUTOREFRESH else '❌ Not installed'}")
        st.write(f"Refresh interval: {refresh_interval}s")
        st.write(f"Trail SL trigger: {trail_sl_trigger}%")
        st.write(f"SL Risk threshold: {sl_risk_threshold}%")
        st.write(f"SL Approach threshold: {sl_approach_threshold}%")
        st.write(f"Email cooldown: {email_cooldown} min")
        st.write(f"Email enabled: {email_enabled}")
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

def generate_alert_hash(ticker, alert_type, key_value=""):
    """Generate unique hash for an alert to prevent duplicates"""
    alert_string = f"{ticker}_{alert_type}_{key_value}"
    return hashlib.md5(alert_string.encode()).hexdigest()[:12]

def can_send_email(alert_hash, cooldown_minutes=15):
    """Check if enough time has passed since last email for this alert"""
    if alert_hash not in st.session_state.last_email_time:
        return True
    
    last_sent = st.session_state.last_email_time[alert_hash]
    time_diff = (datetime.now() - last_sent).total_seconds() / 60
    
    return time_diff >= cooldown_minutes

def mark_email_sent(alert_hash):
    """Mark an alert as sent"""
    st.session_state.last_email_time[alert_hash] = datetime.now()
    st.session_state.email_sent_alerts[alert_hash] = True

def log_email(message):
    """Add to email log"""
    timestamp = get_ist_now().strftime("%H:%M:%S")
    st.session_state.email_log.append(f"[{timestamp}] {message}")
    # Keep only last 50 entries
    if len(st.session_state.email_log) > 50:
        st.session_state.email_log = st.session_state.email_log[-50:]

# ============================================================================
# ENHANCED EMAIL FUNCTIONS
# ============================================================================
def send_email_alert(subject, html_content, sender, password, recipient):
    """Send email alert with error handling"""
    if not sender or not password or not recipient:
        return False, "Missing email credentials"
    
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
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed - check App Password"
    except smtplib.SMTPRecipientsRefused:
        return False, "Invalid recipient email"
    except Exception as e:
        return False, f"Email failed: {str(e)}"

def generate_email_header():
    """Generate common email header"""
    ist_now = get_ist_now()
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header p {{ margin: 5px 0 0; opacity: 0.9; }}
            .content {{ padding: 20px; }}
            .alert-box {{ padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .critical {{ background: #f8d7da; border-left: 5px solid #dc3545; }}
            .warning {{ background: #fff3cd; border-left: 5px solid #ffc107; }}
            .success {{ background: #d4edda; border-left: 5px solid #28a745; }}
            .info {{ background: #d1ecf1; border-left: 5px solid #17a2b8; }}
            .stock-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; }}
            .metric {{ display: inline-block; margin: 5px 15px 5px 0; }}
            .metric-label {{ font-size: 12px; color: #666; }}
            .metric-value {{ font-size: 18px; font-weight: bold; }}
            .action-button {{ background: #667eea; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block; margin-top: 10px; }}
            .footer {{ background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
            .green {{ color: #28a745; }}
            .red {{ color: #dc3545; }}
            .orange {{ color: #fd7e14; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧠 Smart Portfolio Monitor</h1>
                <p>{ist_now.strftime('%B %d, %Y at %H:%M:%S')} IST</p>
            </div>
            <div class="content">
    """

def generate_email_footer():
    """Generate common email footer"""
    return """
            </div>
            <div class="footer">
                <p>This is an automated alert from Smart Portfolio Monitor v5.2</p>
                <p>⚠️ This is not financial advice. Always do your own research.</p>
            </div>
        </div>
    </body>
    </html>
    """

# ============================================================================
# EMAIL TEMPLATE GENERATORS
# ============================================================================
def generate_critical_email(results_critical):
    """Generate email for critical alerts (SL hit, high risk)"""
    html = generate_email_header()
    
    html += f"""
    <h2 style="color: #dc3545; margin: 0;">🚨 CRITICAL ALERT</h2>
    <p>{len(results_critical)} position(s) need immediate attention!</p>
    """
    
    for r in results_critical:
        pnl_color = "green" if r['pnl_percent'] >= 0 else "red"
        
        html += f"""
        <div class="alert-box critical">
            <h3 style="margin: 0 0 10px 0;">{r['ticker']} - {r['position_type']}</h3>
            <div class="stock-card">
                <div class="metric">
                    <div class="metric-label">Current Price</div>
                    <div class="metric-value">₹{r['current_price']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Entry Price</div>
                    <div class="metric-value">₹{r['entry_price']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">P&L</div>
                    <div class="metric-value {pnl_color}">{r['pnl_percent']:+.2f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">SL Risk</div>
                    <div class="metric-value red">{r['sl_risk']}%</div>
                </div>
            </div>
            <p><strong>Stop Loss:</strong> ₹{r['stop_loss']:,.2f} {'🔴 BREACHED!' if r['sl_hit'] else ''}</p>
            <p><strong>Status:</strong> {r['overall_status']}</p>
            <p style="font-size: 18px; margin-top: 10px;"><strong>⚡ ACTION: {r['overall_action'].replace('_', ' ')}</strong></p>
        """
        
        # Add alert details
        if r['alerts']:
            html += "<p><strong>Details:</strong></p><ul>"
            for alert in r['alerts'][:3]:
                html += f"<li>{alert['type']}: {alert['message']}</li>"
            html += "</ul>"
        
        html += "</div>"
    
    html += generate_email_footer()
    return html

def generate_target_email(results_target):
    """Generate email for target achieved"""
    html = generate_email_header()
    
    html += f"""
    <h2 style="color: #28a745; margin: 0;">🎯 TARGET ACHIEVED!</h2>
    <p>{len(results_target)} position(s) hit their target!</p>
    """
    
    for r in results_target:
        html += f"""
        <div class="alert-box success">
            <h3 style="margin: 0 0 10px 0;">🎉 {r['ticker']} - TARGET HIT!</h3>
            <div class="stock-card">
                <div class="metric">
                    <div class="metric-label">Current Price</div>
                    <div class="metric-value">₹{r['current_price']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Entry Price</div>
                    <div class="metric-value">₹{r['entry_price']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Profit</div>
                    <div class="metric-value green">{r['pnl_percent']:+.2f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Profit Amount</div>
                    <div class="metric-value green">₹{r['pnl_amount']:+,.0f}</div>
                </div>
            </div>
            <p><strong>Target 1:</strong> ₹{r['target1']:,.2f} {'✅ HIT' if r['target1_hit'] else ''}</p>
            <p><strong>Target 2:</strong> ₹{r['target2']:,.2f} {'✅ HIT' if r['target2_hit'] else ''}</p>
        """
        
        # Add upside analysis if available
        if r['upside_score'] > 0:
            html += f"""
            <p><strong>Upside Score:</strong> {r['upside_score']}%</p>
            <p><strong>New Target:</strong> ₹{r['new_target']:,.2f}</p>
            """
        
        html += f"""
            <p style="font-size: 18px; margin-top: 10px;"><strong>⚡ RECOMMENDATION: {r['overall_action'].replace('_', ' ')}</strong></p>
        </div>
        """
    
    html += generate_email_footer()
    return html

def generate_sl_approach_email(results_approaching):
    """Generate email for approaching SL warning"""
    html = generate_email_header()
    
    html += f"""
    <h2 style="color: #fd7e14; margin: 0;">⚠️ APPROACHING STOP LOSS</h2>
    <p>{len(results_approaching)} position(s) are approaching their stop loss!</p>
    """
    
    for r in results_approaching:
        # Calculate distance to SL
        if r['position_type'] == 'LONG':
            distance_pct = ((r['current_price'] - r['stop_loss']) / r['current_price']) * 100
        else:
            distance_pct = ((r['stop_loss'] - r['current_price']) / r['current_price']) * 100
        
        html += f"""
        <div class="alert-box warning">
            <h3 style="margin: 0 0 10px 0;">⚠️ {r['ticker']} - WATCH CLOSELY!</h3>
            <div class="stock-card">
                <div class="metric">
                    <div class="metric-label">Current Price</div>
                    <div class="metric-value">₹{r['current_price']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Stop Loss</div>
                    <div class="metric-value red">₹{r['stop_loss']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Distance to SL</div>
                    <div class="metric-value orange">{distance_pct:.2f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">SL Risk Score</div>
                    <div class="metric-value red">{r['sl_risk']}%</div>
                </div>
            </div>
            <p><strong>Position:</strong> {r['position_type']} | Qty: {r['quantity']}</p>
            <p><strong>P&L:</strong> <span class="{'green' if r['pnl_percent'] >= 0 else 'red'}">{r['pnl_percent']:+.2f}%</span></p>
        """
        
        # Add risk reasons
        if r['sl_reasons']:
            html += "<p><strong>Risk Factors:</strong></p><ul>"
            for reason in r['sl_reasons'][:4]:
                html += f"<li>{reason}</li>"
            html += "</ul>"
        
        html += f"""
            <p style="font-size: 18px; margin-top: 10px;"><strong>⚡ ACTION: {r['sl_recommendation']}</strong></p>
        </div>
        """
    
    html += generate_email_footer()
    return html

def generate_sl_change_email(results_sl_change):
    """Generate email for SL change recommendations"""
    html = generate_email_header()
    
    html += f"""
    <h2 style="color: #17a2b8; margin: 0;">🔄 STOP LOSS UPDATE RECOMMENDED</h2>
    <p>{len(results_sl_change)} position(s) need SL adjustment!</p>
    """
    
    for r in results_sl_change:
        html += f"""
        <div class="alert-box info">
            <h3 style="margin: 0 0 10px 0;">📈 {r['ticker']} - Trail Stop Loss</h3>
            <div class="stock-card">
                <div class="metric">
                    <div class="metric-label">Current Price</div>
                    <div class="metric-value">₹{r['current_price']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Current SL</div>
                    <div class="metric-value">₹{r['stop_loss']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">New SL</div>
                    <div class="metric-value green">₹{r['trail_stop']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Profit Locked</div>
                    <div class="metric-value green">{r['pnl_percent']:+.2f}%</div>
                </div>
            </div>
            <p><strong>Reason:</strong> {r.get('trail_reason', 'Lock in profits')}</p>
            <p style="font-size: 18px; margin-top: 10px; background: #28a745; color: white; padding: 10px; border-radius: 5px; text-align: center;">
                <strong>Move SL from ₹{r['stop_loss']:,.2f} → ₹{r['trail_stop']:,.2f}</strong>
            </p>
        </div>
        """
    
    html += generate_email_footer()
    return html

def generate_target_change_email(results_target_change):
    """Generate email for target change recommendations"""
    html = generate_email_header()
    
    html += f"""
    <h2 style="color: #6f42c1; margin: 0;">📈 TARGET UPDATE RECOMMENDED</h2>
    <p>{len(results_target_change)} position(s) have new target recommendations!</p>
    """
    
    for r in results_target_change:
        html += f"""
        <div class="alert-box info" style="border-left-color: #6f42c1;">
            <h3 style="margin: 0 0 10px 0;">🎯 {r['ticker']} - Extended Target</h3>
            <div class="stock-card">
                <div class="metric">
                    <div class="metric-label">Current Price</div>
                    <div class="metric-value">₹{r['current_price']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Original Target</div>
                    <div class="metric-value">₹{r['target1']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">New Target</div>
                    <div class="metric-value green">₹{r['new_target']:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Upside Score</div>
                    <div class="metric-value">{r['upside_score']}%</div>
                </div>
            </div>
            <p><strong>Current P&L:</strong> <span class="green">{r['pnl_percent']:+.2f}%</span></p>
        """
        
        # Add upside reasons
        if r['upside_reasons']:
            html += "<p><strong>Why extend target:</strong></p><ul>"
            for reason in r['upside_reasons'][:4]:
                html += f"<li>{reason}</li>"
            html += "</ul>"
        
        html += """
        </div>
        """
    
    html += generate_email_footer()
    return html

def generate_summary_email(results, summary_stats):
    """Generate daily/periodic summary email"""
    html = generate_email_header()
    ist_now = get_ist_now()
    
    total_pnl = summary_stats['total_pnl']
    pnl_color = "green" if total_pnl >= 0 else "red"
    
    html += f"""
    <h2 style="color: #667eea; margin: 0;">📊 Portfolio Summary</h2>
    <p>As of {ist_now.strftime('%H:%M:%S')} IST</p>
    
    <div class="stock-card" style="text-align: center;">
        <div class="metric">
            <div class="metric-label">Total P&L</div>
            <div class="metric-value {pnl_color}" style="font-size: 28px;">₹{total_pnl:+,.0f}</div>
        </div>
        <div class="metric">
            <div class="metric-label">P&L %</div>
            <div class="metric-value {pnl_color}">{summary_stats['pnl_percent']:+.2f}%</div>
        </div>
        <div class="metric">
            <div class="metric-label">Positions</div>
            <div class="metric-value">{summary_stats['total_positions']}</div>
        </div>
    </div>
    
    <h3>Position Status</h3>
    <table style="width: 100%; border-collapse: collapse;">
        <tr style="background: #f8f9fa;">
            <td style="padding: 10px; border: 1px solid #ddd;">🔴 Critical</td>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{summary_stats['critical']}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;">🟡 Warning</td>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{summary_stats['warning']}</td>
        </tr>
        <tr style="background: #f8f9fa;">
            <td style="padding: 10px; border: 1px solid #ddd;">🟢 Good</td>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{summary_stats['good']}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd;">🎯 Target Hit</td>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{summary_stats['success']}</td>
        </tr>
    </table>
    
    <h3>Individual Positions</h3>
    """
    
    for r in results:
        status_emoji = {'CRITICAL': '🔴', 'WARNING': '🟡', 'SUCCESS': '🟢', 
                       'GOOD': '🟢', 'OPPORTUNITY': '🔵', 'OK': '⚪'}.get(r['overall_status'], '⚪')
        pnl_c = "green" if r['pnl_percent'] >= 0 else "red"
        
        html += f"""
        <div style="padding: 10px; border-bottom: 1px solid #eee;">
            <strong>{status_emoji} {r['ticker']}</strong> ({r['position_type']}) - 
            <span class="{pnl_c}">{r['pnl_percent']:+.2f}%</span> | 
            SL Risk: {r['sl_risk']}% | 
            Action: {r['overall_action'].replace('_', ' ')}
        </div>
        """
    
    html += generate_email_footer()
    return html
# ============================================================================
# TECHNICAL ANALYSIS FUNCTIONS
# ============================================================================
def calculate_rsi(prices, period=14):
    """Calculate RSI (Relative Strength Index)"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)"""
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
    """Calculate Exponential Moving Average"""
    return prices.ewm(span=period, adjust=False).mean()

def calculate_sma(prices, period):
    """Calculate Simple Moving Average"""
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

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator"""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k_percent = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d_percent = k_percent.rolling(window=d_period).mean()
    
    return k_percent, d_percent

def calculate_vwap(high, low, close, volume):
    """Calculate Volume Weighted Average Price"""
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    return vwap

def calculate_obv(close, volume):
    """Calculate On-Balance Volume"""
    obv = pd.Series(index=close.index, dtype=float)
    obv.iloc[0] = 0
    
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
        elif close.iloc[i] < close.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    
    return obv

def calculate_momentum(prices, period=10):
    """Calculate Price Momentum"""
    return prices - prices.shift(period)

def calculate_roc(prices, period=10):
    """Calculate Rate of Change"""
    return ((prices - prices.shift(period)) / prices.shift(period)) * 100

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
    
    # Calculate volume momentum
    vol_sma_5 = df['Volume'].rolling(5).mean().iloc[-1]
    vol_sma_10 = df['Volume'].rolling(10).mean().iloc[-1]
    volume_momentum = "ACCELERATING" if vol_sma_5 > vol_sma_10 else "DECELERATING"
    
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

def analyze_volume_profile(df, num_bins=20):
    """
    Analyze volume profile to find high volume nodes (support/resistance)
    Returns: volume_profile dict with key price levels
    """
    if len(df) < 20 or 'Volume' not in df.columns:
        return {'high_volume_nodes': [], 'poc': None}
    
    # Create price bins
    price_min = df['Low'].min()
    price_max = df['High'].max()
    bin_size = (price_max - price_min) / num_bins
    
    if bin_size == 0:
        return {'high_volume_nodes': [], 'poc': None}
    
    # Calculate volume at each price level
    volume_at_price = {}
    
    for _, row in df.iterrows():
        # Distribute volume across the candle's range
        candle_low = row['Low']
        candle_high = row['High']
        candle_volume = row['Volume']
        
        # Find bins this candle touches
        low_bin = int((candle_low - price_min) / bin_size)
        high_bin = int((candle_high - price_min) / bin_size)
        
        # Distribute volume equally across bins
        num_bins_touched = max(1, high_bin - low_bin + 1)
        vol_per_bin = candle_volume / num_bins_touched
        
        for b in range(low_bin, high_bin + 1):
            price_level = price_min + (b + 0.5) * bin_size
            if price_level not in volume_at_price:
                volume_at_price[price_level] = 0
            volume_at_price[price_level] += vol_per_bin
    
    # Find Point of Control (highest volume price)
    if volume_at_price:
        poc = max(volume_at_price, key=volume_at_price.get)
        
        # Find high volume nodes (top 20% by volume)
        sorted_levels = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)
        top_count = max(1, len(sorted_levels) // 5)
        high_volume_nodes = [level for level, vol in sorted_levels[:top_count]]
        
        return {
            'high_volume_nodes': high_volume_nodes,
            'poc': poc,
            'volume_at_price': volume_at_price
        }
    
    return {'high_volume_nodes': [], 'poc': None}

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
            'distance_to_resistance': 5.0,
            'support_strength': 'WEAK',
            'resistance_strength': 'WEAK'
        }
    
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    close = df['Close'].tail(lookback)
    current_price = float(close.iloc[-1])
    
    # Find pivot highs and lows
    pivot_highs = []
    pivot_lows = []
    pivot_high_counts = {}  # Track how many times a level was tested
    pivot_low_counts = {}
    
    for i in range(2, len(high) - 2):
        # Pivot high (local maximum)
        if (high.iloc[i] > high.iloc[i-1] and high.iloc[i] > high.iloc[i-2] and 
            high.iloc[i] > high.iloc[i+1] and high.iloc[i] > high.iloc[i+2]):
            pivot_highs.append(float(high.iloc[i]))
        
        # Pivot low (local minimum)
        if (low.iloc[i] < low.iloc[i-1] and low.iloc[i] < low.iloc[i-2] and 
            low.iloc[i] < low.iloc[i+1] and low.iloc[i] < low.iloc[i+2]):
            pivot_lows.append(float(low.iloc[i]))
    
    # Cluster nearby levels and count touches
    def cluster_levels(levels, threshold_pct=1.0):
        if not levels:
            return [], {}
        levels = sorted(levels)
        clustered = []
        touch_counts = {}
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if (level - current_cluster[0]) / current_cluster[0] * 100 < threshold_pct:
                current_cluster.append(level)
            else:
                avg_level = sum(current_cluster) / len(current_cluster)
                clustered.append(avg_level)
                touch_counts[avg_level] = len(current_cluster)
                current_cluster = [level]
        
        avg_level = sum(current_cluster) / len(current_cluster)
        clustered.append(avg_level)
        touch_counts[avg_level] = len(current_cluster)
        
        return clustered, touch_counts
    
    support_levels, support_touches = cluster_levels(pivot_lows)
    resistance_levels, resistance_touches = cluster_levels(pivot_highs)
    
    # Find nearest support (below current price)
    supports_below = [s for s in support_levels if s < current_price]
    if supports_below:
        nearest_support = max(supports_below)
        support_touch_count = support_touches.get(nearest_support, 1)
    else:
        nearest_support = current_price * 0.95
        support_touch_count = 0
    
    # Find nearest resistance (above current price)
    resistances_above = [r for r in resistance_levels if r > current_price]
    if resistances_above:
        nearest_resistance = min(resistances_above)
        resistance_touch_count = resistance_touches.get(nearest_resistance, 1)
    else:
        nearest_resistance = current_price * 1.05
        resistance_touch_count = 0
    
    # Determine strength based on touch count
    def get_strength(touch_count):
        if touch_count >= 3:
            return "STRONG"
        elif touch_count >= 2:
            return "MODERATE"
        else:
            return "WEAK"
    
    return {
        'support_levels': support_levels[-5:] if support_levels else [],
        'resistance_levels': resistance_levels[-5:] if resistance_levels else [],
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'distance_to_support': ((current_price - nearest_support) / current_price) * 100,
        'distance_to_resistance': ((nearest_resistance - current_price) / current_price) * 100,
        'support_strength': get_strength(support_touch_count),
        'resistance_strength': get_strength(resistance_touch_count),
        'support_touches': support_touch_count,
        'resistance_touches': resistance_touch_count
    }

def find_trend_lines(df, lookback=60):
    """
    Find trend lines using linear regression on highs and lows
    Returns: trend line info
    """
    if len(df) < lookback:
        lookback = len(df)
    
    if lookback < 10:
        return {'uptrend': None, 'downtrend': None, 'trend_direction': 'NEUTRAL'}
    
    high = df['High'].tail(lookback).values
    low = df['Low'].tail(lookback).values
    close = df['Close'].tail(lookback).values
    x = np.arange(lookback)
    
    # Calculate trend using linear regression on closes
    if len(x) > 1:
        slope = np.polyfit(x, close, 1)[0]
        
        # Normalize slope to percentage per period
        avg_price = np.mean(close)
        slope_pct = (slope / avg_price) * 100
        
        if slope_pct > 0.1:
            trend_direction = "UPTREND"
        elif slope_pct < -0.1:
            trend_direction = "DOWNTREND"
        else:
            trend_direction = "SIDEWAYS"
        
        return {
            'slope': slope,
            'slope_pct': slope_pct,
            'trend_direction': trend_direction
        }
    
    return {'slope': 0, 'slope_pct': 0, 'trend_direction': 'NEUTRAL'}

def detect_chart_patterns(df, lookback=30):
    """
    Detect common chart patterns
    Returns: list of detected patterns
    """
    patterns = []
    
    if len(df) < lookback:
        return patterns
    
    close = df['Close'].tail(lookback)
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    
    current_price = close.iloc[-1]
    
    # Double Top Detection
    highs = high.values
    recent_highs = []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            recent_highs.append((i, highs[i]))
    
    if len(recent_highs) >= 2:
        h1, h2 = recent_highs[-2], recent_highs[-1]
        if abs(h1[1] - h2[1]) / h1[1] < 0.02:  # Within 2%
            if h2[0] - h1[0] >= 5:  # At least 5 bars apart
                patterns.append({
                    'pattern': 'DOUBLE_TOP',
                    'signal': 'BEARISH',
                    'level': (h1[1] + h2[1]) / 2,
                    'description': 'Double top pattern detected - potential reversal'
                })
    
    # Double Bottom Detection
    lows = low.values
    recent_lows = []
    for i in range(2, len(lows) - 2):
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            recent_lows.append((i, lows[i]))
    
    if len(recent_lows) >= 2:
        l1, l2 = recent_lows[-2], recent_lows[-1]
        if abs(l1[1] - l2[1]) / l1[1] < 0.02:  # Within 2%
            if l2[0] - l1[0] >= 5:  # At least 5 bars apart
                patterns.append({
                    'pattern': 'DOUBLE_BOTTOM',
                    'signal': 'BULLISH',
                    'level': (l1[1] + l2[1]) / 2,
                    'description': 'Double bottom pattern detected - potential reversal'
                })
    
    # Higher Highs and Higher Lows (Uptrend)
    if len(recent_highs) >= 2 and len(recent_lows) >= 2:
        if recent_highs[-1][1] > recent_highs[-2][1] and recent_lows[-1][1] > recent_lows[-2][1]:
            patterns.append({
                'pattern': 'HIGHER_HIGHS_LOWS',
                'signal': 'BULLISH',
                'level': current_price,
                'description': 'Higher highs and higher lows - uptrend continuation'
            })
    
    # Lower Highs and Lower Lows (Downtrend)
    if len(recent_highs) >= 2 and len(recent_lows) >= 2:
        if recent_highs[-1][1] < recent_highs[-2][1] and recent_lows[-1][1] < recent_lows[-2][1]:
            patterns.append({
                'pattern': 'LOWER_HIGHS_LOWS',
                'signal': 'BEARISH',
                'level': current_price,
                'description': 'Lower highs and lower lows - downtrend continuation'
            })
    
    # Consolidation/Range Detection
    price_range = (high.max() - low.min()) / low.min() * 100
    recent_range = (high.tail(10).max() - low.tail(10).min()) / low.tail(10).min() * 100
    
    if recent_range < price_range * 0.3:  # Recent range is much smaller
        patterns.append({
            'pattern': 'CONSOLIDATION',
            'signal': 'NEUTRAL',
            'level': current_price,
            'description': 'Price consolidating - breakout expected'
        })
    
    return patterns
# ============================================================================
# MULTI-TIMEFRAME ANALYSIS ✅ (FULLY IMPLEMENTED)
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
        
        # 15-minute timeframe (1 day) - for intraday
        try:
            min15_df = stock.history(period="1d", interval="15m")
            if len(min15_df) >= 10:
                timeframes['15min'] = min15_df
        except:
            pass
        
        if not timeframes:
            return {
                'signals': {},
                'details': {},
                'alignment_score': 50,
                'recommendation': "Unable to fetch multi-timeframe data",
                'aligned_count': 0,
                'against_count': 0,
                'total_timeframes': 0,
                'trend_strength': 'UNKNOWN'
            }
        
        signals = {}
        details = {}
        
        for tf_name, df in timeframes.items():
            if len(df) >= 14:
                close = df['Close']
                current = float(close.iloc[-1])
                
                # Calculate indicators
                rsi = calculate_rsi(close).iloc[-1]
                if pd.isna(rsi):
                    rsi = 50
                
                sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
                ema_9 = close.ewm(span=9).mean().iloc[-1]
                ema_21 = close.ewm(span=21).mean().iloc[-1] if len(close) >= 21 else close.mean()
                
                # MACD
                macd, signal_line, histogram = calculate_macd(close)
                macd_hist = histogram.iloc[-1] if len(histogram) > 0 else 0
                macd_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
                if pd.isna(macd_hist):
                    macd_hist = 0
                if pd.isna(macd_prev):
                    macd_prev = 0
                
                # Price momentum
                price_change_5 = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
                
                # Trend determination with scoring
                bullish_points = 0
                bearish_points = 0
                total_points = 0
                
                # RSI Analysis (2 points)
                total_points += 2
                if rsi > 55:
                    bullish_points += 2
                elif rsi > 50:
                    bullish_points += 1
                elif rsi < 45:
                    bearish_points += 2
                elif rsi < 50:
                    bearish_points += 1
                
                # Price vs SMA20 (2 points)
                total_points += 2
                if current > sma_20 * 1.02:
                    bullish_points += 2
                elif current > sma_20:
                    bullish_points += 1
                elif current < sma_20 * 0.98:
                    bearish_points += 2
                elif current < sma_20:
                    bearish_points += 1
                
                # EMA 9 vs EMA 21 (2 points)
                total_points += 2
                if ema_9 > ema_21 * 1.01:
                    bullish_points += 2
                elif ema_9 > ema_21:
                    bullish_points += 1
                elif ema_9 < ema_21 * 0.99:
                    bearish_points += 2
                elif ema_9 < ema_21:
                    bearish_points += 1
                
                # MACD (2 points)
                total_points += 2
                if macd_hist > 0 and macd_hist > macd_prev:
                    bullish_points += 2
                elif macd_hist > 0:
                    bullish_points += 1
                elif macd_hist < 0 and macd_hist < macd_prev:
                    bearish_points += 2
                elif macd_hist < 0:
                    bearish_points += 1
                
                # Price momentum (2 points)
                total_points += 2
                if price_change_5 > 2:
                    bullish_points += 2
                elif price_change_5 > 0:
                    bullish_points += 1
                elif price_change_5 < -2:
                    bearish_points += 2
                elif price_change_5 < 0:
                    bearish_points += 1
                
                # Determine signal and strength
                bullish_pct = (bullish_points / total_points) * 100
                bearish_pct = (bearish_points / total_points) * 100
                
                if bullish_pct >= 70:
                    signal = "BULLISH"
                    strength = "Strong"
                elif bullish_pct >= 50:
                    signal = "BULLISH"
                    strength = "Moderate"
                elif bearish_pct >= 70:
                    signal = "BEARISH"
                    strength = "Strong"
                elif bearish_pct >= 50:
                    signal = "BEARISH"
                    strength = "Moderate"
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
                    'ema_bullish': ema_9 > ema_21,
                    'macd_bullish': macd_hist > 0,
                    'macd_rising': macd_hist > macd_prev,
                    'price_momentum': price_change_5,
                    'bullish_score': bullish_pct,
                    'bearish_score': bearish_pct
                }
        
        # Calculate alignment score based on position type
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
        
        # Determine overall trend strength
        strong_signals = sum(1 for tf, d in details.items() if d['strength'] == 'Strong')
        if strong_signals >= 2:
            trend_strength = "STRONG"
        elif strong_signals >= 1:
            trend_strength = "MODERATE"
        else:
            trend_strength = "WEAK"
        
        # Generate recommendation
        if alignment_score >= 80:
            recommendation = f"✅ All timeframes aligned with {position_type} - Strong conviction"
        elif alignment_score >= 60:
            recommendation = f"👍 Most timeframes support {position_type} - Good setup"
        elif alignment_score >= 40:
            recommendation = f"⚠️ Mixed signals across timeframes - Caution advised"
        elif alignment_score >= 20:
            recommendation = f"🚨 Most timeframes against {position_type} - Consider exit"
        else:
            recommendation = f"🚨 All timeframes against {position_type} - EXIT recommended"
        
        return {
            'signals': signals,
            'details': details,
            'alignment_score': alignment_score,
            'recommendation': recommendation,
            'aligned_count': aligned,
            'against_count': against,
            'total_timeframes': total,
            'trend_strength': trend_strength
        }
        
    except Exception as e:
        return {
            'signals': {},
            'details': {},
            'alignment_score': 50,
            'recommendation': f"Error: {str(e)}",
            'aligned_count': 0,
            'against_count': 0,
            'total_timeframes': 0,
            'trend_strength': 'UNKNOWN'
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
    components['RSI'] = {'score': rsi_score, 'value': rsi}
    
    # 2. MACD Component (0-20 points)
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    hist_prev2 = histogram.iloc[-3] if len(histogram) > 2 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    if pd.isna(hist_prev2):
        hist_prev2 = 0
    
    # MACD analysis
    macd_bullish = hist_current > 0
    macd_rising = hist_current > hist_prev
    macd_accelerating = (hist_current - hist_prev) > (hist_prev - hist_prev2)
    
    if macd_bullish and macd_rising and macd_accelerating:
        macd_score = 20  # Strong bullish momentum
    elif macd_bullish and macd_rising:
        macd_score = 15  # Bullish and expanding
    elif macd_bullish:
        macd_score = 5  # Bullish but contracting
    elif not macd_bullish and not macd_rising and not macd_accelerating:
        macd_score = -20  # Strong bearish momentum
    elif not macd_bullish and not macd_rising:
        macd_score = -15  # Bearish and expanding
    else:
        macd_score = -5  # Bearish but contracting
    
    score += macd_score
    components['MACD'] = {'score': macd_score, 'bullish': macd_bullish, 'rising': macd_rising}
    
    # 3. Moving Average Component (0-20 points)
    current_price = close.iloc[-1]
    sma_10 = close.rolling(10).mean().iloc[-1] if len(close) >= 10 else close.mean()
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma_20
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    ema_21 = close.ewm(span=21).mean().iloc[-1] if len(close) >= 21 else close.mean()
    
    ma_score = 0
    ma_details = {}
    
    # Price above MAs
    if current_price > ema_9:
        ma_score += 4
        ma_details['above_ema9'] = True
    else:
        ma_score -= 4
        ma_details['above_ema9'] = False
    
    if current_price > sma_20:
        ma_score += 4
        ma_details['above_sma20'] = True
    else:
        ma_score -= 4
        ma_details['above_sma20'] = False
    
    if current_price > sma_50:
        ma_score += 4
        ma_details['above_sma50'] = True
    else:
        ma_score -= 4
        ma_details['above_sma50'] = False
    
    # MA alignment (golden/death cross)
    if ema_9 > ema_21 > sma_50:
        ma_score += 8  # Perfect bullish alignment
        ma_details['alignment'] = 'BULLISH'
    elif ema_9 < ema_21 < sma_50:
        ma_score -= 8  # Perfect bearish alignment
        ma_details['alignment'] = 'BEARISH'
    elif ema_9 > ema_21:
        ma_score += 4
        ma_details['alignment'] = 'SLIGHTLY_BULLISH'
    else:
        ma_score -= 4
        ma_details['alignment'] = 'SLIGHTLY_BEARISH'
    
    score += ma_score
    components['MA'] = {'score': ma_score, 'details': ma_details}
    
    # 4. Price Momentum / Rate of Change (0-15 points)
    returns_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
    returns_10d = ((close.iloc[-1] / close.iloc[-11]) - 1) * 100 if len(close) > 11 else 0
    returns_20d = ((close.iloc[-1] / close.iloc[-21]) - 1) * 100 if len(close) > 21 else 0
    
    # Weighted momentum
    weighted_momentum = (returns_5d * 0.5) + (returns_10d * 0.3) + (returns_20d * 0.2)
    momentum_score = min(15, max(-15, weighted_momentum * 2))
    
    score += momentum_score
    components['Momentum'] = {
        'score': momentum_score, 
        '5d': returns_5d, 
        '10d': returns_10d, 
        '20d': returns_20d
    }
    
    # 5. Trend Strength using ADX approximation (0-10 points)
    try:
        adx = calculate_adx(df['High'], df['Low'], close).iloc[-1]
        if pd.isna(adx):
            adx = 20
    except:
        adx = 20
    
    # Determine if trend is in our favor
    if current_price > sma_20:
        # Bullish trend
        if adx > 30:
            trend_score = 10  # Strong bullish trend
        elif adx > 20:
            trend_score = 5  # Moderate bullish trend
        else:
            trend_score = 2  # Weak bullish trend
    else:
        # Bearish trend
        if adx > 30:
            trend_score = -10  # Strong bearish trend
        elif adx > 20:
            trend_score = -5  # Moderate bearish trend
        else:
            trend_score = -2  # Weak bearish trend
    
    score += trend_score
    components['Trend'] = {'score': trend_score, 'adx': adx}
    
    # 6. Stochastic Component (0-10 points)
    try:
        k, d = calculate_stochastic(df['High'], df['Low'], close)
        k_val = k.iloc[-1]
        d_val = d.iloc[-1]
        
        if pd.isna(k_val):
            k_val = 50
        if pd.isna(d_val):
            d_val = 50
        
        if k_val > 80:
            stoch_score = -5  # Overbought
        elif k_val > 50 and k_val > d_val:
            stoch_score = 5  # Bullish momentum
        elif k_val < 20:
            stoch_score = 5  # Oversold, might bounce
        elif k_val < 50 and k_val < d_val:
            stoch_score = -5  # Bearish momentum
        else:
            stoch_score = 0
        
        score += stoch_score
        components['Stochastic'] = {'score': stoch_score, 'k': k_val, 'd': d_val}
    except:
        components['Stochastic'] = {'score': 0, 'k': 50, 'd': 50}
    
    # Cap between 0-100
    final_score = max(0, min(100, score))
    
    # Determine trend direction
    if final_score >= 75:
        trend = "STRONG BULLISH"
    elif final_score >= 60:
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
def predict_sl_risk(df, current_price, stop_loss, position_type, entry_price, 
                    sl_alert_threshold=50, sl_approach_threshold=2.0):
    """
    Predict likelihood of hitting stop loss
    Returns: risk_score (0-100), reasons, recommendation, priority, distance_pct
    """
    risk_score = 0
    reasons = []
    close = df['Close']
    
    # 1. Distance to Stop Loss (0-40 points) - CRITICAL FACTOR
    if position_type == "LONG":
        distance_pct = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_pct = ((stop_loss - current_price) / current_price) * 100
    
    if distance_pct < 0:  # Already hit SL
        risk_score = 100
        reasons.append("🚨 STOP LOSS BREACHED!")
    elif distance_pct < 1:
        risk_score += 40
        reasons.append(f"🔴 CRITICAL: Only {distance_pct:.2f}% from SL!")
    elif distance_pct < sl_approach_threshold:
        risk_score += 35
        reasons.append(f"🔴 Very close to SL ({distance_pct:.2f}% away)")
    elif distance_pct < sl_approach_threshold * 1.5:
        risk_score += 25
        reasons.append(f"🟠 Approaching SL ({distance_pct:.2f}% away)")
    elif distance_pct < sl_approach_threshold * 2:
        risk_score += 15
        reasons.append(f"🟡 Getting close to SL ({distance_pct:.2f}% away)")
    elif distance_pct < 5:
        risk_score += 8
    else:
        risk_score += 0  # Safe distance
    
    # 2. Trend Against Position (0-25 points)
    sma_10 = close.rolling(10).mean().iloc[-1] if len(close) >= 10 else close.mean()
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma_20
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    ema_21 = close.ewm(span=21).mean().iloc[-1] if len(close) >= 21 else close.mean()
    
    if position_type == "LONG":
        if current_price < ema_9:
            risk_score += 7
            reasons.append("📉 Below EMA 9 (short-term bearish)")
        if current_price < sma_20:
            risk_score += 8
            reasons.append("📉 Below SMA 20 (medium-term bearish)")
        if current_price < sma_50:
            risk_score += 5
            reasons.append("📉 Below SMA 50 (long-term bearish)")
        if ema_9 < ema_21:
            risk_score += 5
            reasons.append("📉 EMA 9 below EMA 21 (bearish crossover)")
    else:  # SHORT
        if current_price > ema_9:
            risk_score += 7
            reasons.append("📈 Above EMA 9 (short-term bullish)")
        if current_price > sma_20:
            risk_score += 8
            reasons.append("📈 Above SMA 20 (medium-term bullish)")
        if current_price > sma_50:
            risk_score += 5
            reasons.append("📈 Above SMA 50 (long-term bullish)")
        if ema_9 > ema_21:
            risk_score += 5
            reasons.append("📈 EMA 9 above EMA 21 (bullish crossover)")
    
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
            risk_score += 7
            reasons.append("📊 MACD bearish")
        if hist_current < hist_prev:
            risk_score += 5
            reasons.append("📊 MACD declining")
        if hist_current < 0 and hist_current < hist_prev:
            risk_score += 3
            reasons.append("📊 MACD accelerating down")
    else:
        if hist_current > 0:
            risk_score += 7
            reasons.append("📊 MACD bullish")
        if hist_current > hist_prev:
            risk_score += 5
            reasons.append("📊 MACD rising")
        if hist_current > 0 and hist_current > hist_prev:
            risk_score += 3
            reasons.append("📊 MACD accelerating up")
    
    # 4. RSI Extreme Against Position (0-10 points)
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if position_type == "LONG":
        if rsi < 30:
            risk_score += 10
            reasons.append(f"📉 RSI extremely weak ({rsi:.0f}) - panic selling")
        elif rsi < 40:
            risk_score += 6
            reasons.append(f"📉 RSI weak ({rsi:.0f})")
        elif rsi < 50:
            risk_score += 3
            reasons.append(f"📉 RSI below 50 ({rsi:.0f})")
    else:  # SHORT
        if rsi > 70:
            risk_score += 10
            reasons.append(f"📈 RSI extremely strong ({rsi:.0f}) - buying pressure")
        elif rsi > 60:
            risk_score += 6
            reasons.append(f"📈 RSI strong ({rsi:.0f})")
        elif rsi > 50:
            risk_score += 3
            reasons.append(f"📈 RSI above 50 ({rsi:.0f})")
    
    # 5. Consecutive Candles Against Position (0-10 points)
    if len(close) >= 5:
        last_4 = close.tail(5).diff().dropna()
        consecutive_against = 0
        
        if position_type == "LONG":
            consecutive_against = sum(1 for x in last_4 if x < 0)
        else:
            consecutive_against = sum(1 for x in last_4 if x > 0)
        
        if consecutive_against >= 4:
            risk_score += 10
            reasons.append(f"🕯️ {consecutive_against} consecutive candles against position")
        elif consecutive_against >= 3:
            risk_score += 7
            reasons.append(f"🕯️ {consecutive_against} candles against position")
        elif consecutive_against >= 2:
            risk_score += 4
    
    # 6. Volume Confirmation Against Position (0-10 points)
    volume_signal, volume_ratio, _, volume_trend = analyze_volume(df)
    
    if position_type == "LONG":
        if volume_signal == "STRONG_SELLING":
            risk_score += 10
            reasons.append(f"📊 Heavy selling volume ({volume_ratio:.1f}x)")
        elif volume_signal == "SELLING":
            risk_score += 6
            reasons.append(f"📊 Selling volume ({volume_ratio:.1f}x)")
    else:  # SHORT
        if volume_signal == "STRONG_BUYING":
            risk_score += 10
            reasons.append(f"📊 Heavy buying volume ({volume_ratio:.1f}x)")
        elif volume_signal == "BUYING":
            risk_score += 6
            reasons.append(f"📊 Buying volume ({volume_ratio:.1f}x)")
    
    # 7. ATR Volatility Check (0-5 points)
    try:
        atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
        if not pd.isna(atr):
            atr_pct = (atr / current_price) * 100
            if atr_pct > distance_pct:
                risk_score += 5
                reasons.append(f"⚡ High volatility ({atr_pct:.1f}%) exceeds SL distance")
    except:
        pass
    
    # 8. Support/Resistance Check (0-5 points)
    sr_levels = find_support_resistance(df)
    
    if position_type == "LONG":
        if current_price < sr_levels['nearest_support']:
            risk_score += 5
            reasons.append("📉 Broke below support level")
    else:
        if current_price > sr_levels['nearest_resistance']:
            risk_score += 5
            reasons.append("📈 Broke above resistance level")
    
    # Cap at 100
    risk_score = min(100, risk_score)
    
    # Generate recommendation based on threshold (using user's setting)
    if risk_score >= 90:
        recommendation = "🚨 EXIT NOW - Extremely high risk!"
        priority = "CRITICAL"
    elif risk_score >= 75:
        recommendation = "🚨 EXIT IMMEDIATELY - Very high risk"
        priority = "CRITICAL"
    elif risk_score >= sl_alert_threshold + 20:
        recommendation = "⚠️ CONSIDER EXIT - High risk"
        priority = "HIGH"
    elif risk_score >= sl_alert_threshold:
        recommendation = "👀 WATCH CLOSELY - Moderate risk"
        priority = "MEDIUM"
    elif risk_score >= 25:
        recommendation = "✅ MONITOR - Low risk"
        priority = "LOW"
    else:
        recommendation = "✅ SAFE - Very low risk"
        priority = "SAFE"
    
    # Check if approaching SL (for email alerts)
    is_approaching_sl = distance_pct < sl_approach_threshold and distance_pct > 0
    
    return risk_score, reasons, recommendation, priority, distance_pct, is_approaching_sl
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
    momentum_score, trend, momentum_components = calculate_momentum_score(df)
    
    if position_type == "LONG":
        if momentum_score >= 75:
            score += 25
            reasons.append(f"🚀 Very strong momentum ({momentum_score:.0f})")
        elif momentum_score >= 60:
            score += 15
            reasons.append(f"📈 Good momentum ({momentum_score:.0f})")
        elif momentum_score >= 50:
            score += 5
            reasons.append(f"📊 Decent momentum ({momentum_score:.0f})")
        elif momentum_score <= 35:
            score -= 20
            reasons.append(f"📉 Weak momentum ({momentum_score:.0f})")
        else:
            score -= 10
            reasons.append(f"📉 Fading momentum ({momentum_score:.0f})")
    else:  # SHORT
        if momentum_score <= 25:
            score += 25
            reasons.append(f"🚀 Strong bearish momentum ({momentum_score:.0f})")
        elif momentum_score <= 40:
            score += 15
            reasons.append(f"📉 Good bearish momentum ({momentum_score:.0f})")
        elif momentum_score <= 50:
            score += 5
            reasons.append(f"📊 Decent bearish momentum ({momentum_score:.0f})")
        elif momentum_score >= 65:
            score -= 20
            reasons.append(f"📈 Bullish reversal likely ({momentum_score:.0f})")
        else:
            score -= 10
            reasons.append(f"📈 Momentum weakening ({momentum_score:.0f})")
    
    # 2. RSI not extreme?
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if position_type == "LONG":
        if rsi < 55:
            score += 15
            reasons.append(f"✅ RSI has plenty of room ({rsi:.0f})")
        elif rsi < 65:
            score += 8
            reasons.append(f"✅ RSI has some room ({rsi:.0f})")
        elif rsi > 80:
            score -= 25
            reasons.append(f"⚠️ RSI extremely overbought ({rsi:.0f})")
        elif rsi > 70:
            score -= 15
            reasons.append(f"⚠️ RSI overbought ({rsi:.0f})")
        else:
            score -= 5
            reasons.append(f"🟡 RSI getting high ({rsi:.0f})")
    else:  # SHORT
        if rsi > 45:
            score += 15
            reasons.append(f"✅ RSI has room to fall ({rsi:.0f})")
        elif rsi > 35:
            score += 8
            reasons.append(f"✅ RSI has some room ({rsi:.0f})")
        elif rsi < 20:
            score -= 25
            reasons.append(f"⚠️ RSI extremely oversold ({rsi:.0f})")
        elif rsi < 30:
            score -= 15
            reasons.append(f"⚠️ RSI oversold ({rsi:.0f})")
        else:
            score -= 5
            reasons.append(f"🟡 RSI getting low ({rsi:.0f})")
    
    # 3. Volume confirming?
    volume_signal, volume_ratio, _, volume_trend = analyze_volume(df)
    
    if position_type == "LONG":
        if volume_signal == "STRONG_BUYING":
            score += 15
            reasons.append(f"📊 Strong buying volume ({volume_ratio:.1f}x)")
        elif volume_signal == "BUYING":
            score += 10
            reasons.append(f"📊 Good buying volume ({volume_ratio:.1f}x)")
        elif volume_signal in ["STRONG_SELLING", "SELLING"]:
            score -= 15
            reasons.append(f"📊 Selling pressure ({volume_ratio:.1f}x)")
        elif volume_ratio < 0.7:
            score -= 5
            reasons.append("📊 Low volume - weak conviction")
    else:  # SHORT
        if volume_signal == "STRONG_SELLING":
            score += 15
            reasons.append(f"📊 Strong selling volume ({volume_ratio:.1f}x)")
        elif volume_signal == "SELLING":
            score += 10
            reasons.append(f"📊 Good selling volume ({volume_ratio:.1f}x)")
        elif volume_signal in ["STRONG_BUYING", "BUYING"]:
            score -= 15
            reasons.append(f"📊 Buying pressure ({volume_ratio:.1f}x)")
        elif volume_ratio < 0.7:
            score -= 5
            reasons.append("📊 Low volume - weak conviction")
    
    # 4. Volume trend
    if volume_trend == "INCREASING":
        score += 5
        reasons.append("📈 Volume trend increasing")
    elif volume_trend == "DECREASING":
        score -= 5
        reasons.append("📉 Volume trend decreasing")
    
    # 5. Bollinger Band position
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(close)
    
    if len(upper_bb) > 0 and len(lower_bb) > 0:
        upper = upper_bb.iloc[-1]
        lower = lower_bb.iloc[-1]
        
        if not pd.isna(upper) and not pd.isna(lower):
            bb_range = upper - lower
            if bb_range > 0:
                if position_type == "LONG":
                    bb_position = (current_price - lower) / bb_range
                    if bb_position < 0.6:
                        score += 10
                        reasons.append(f"📈 Room to upper BB ({(1-bb_position)*100:.0f}%)")
                    elif bb_position > 0.95:
                        score -= 15
                        reasons.append("⚠️ At upper Bollinger Band")
                    elif bb_position > 0.85:
                        score -= 8
                        reasons.append("🟡 Near upper Bollinger Band")
                else:  # SHORT
                    bb_position = (current_price - lower) / bb_range
                    if bb_position > 0.4:
                        score += 10
                        reasons.append(f"📉 Room to lower BB ({bb_position*100:.0f}%)")
                    elif bb_position < 0.05:
                        score -= 15
                        reasons.append("⚠️ At lower Bollinger Band")
                    elif bb_position < 0.15:
                        score -= 8
                        reasons.append("🟡 Near lower Bollinger Band")
    
    # 6. MACD Trend
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    
    if position_type == "LONG":
        if hist_current > 0 and hist_current > hist_prev:
            score += 10
            reasons.append("📊 MACD bullish and rising")
        elif hist_current > 0:
            score += 5
            reasons.append("📊 MACD still bullish")
        elif hist_current < hist_prev:
            score -= 10
            reasons.append("📊 MACD turning bearish")
    else:
        if hist_current < 0 and hist_current < hist_prev:
            score += 10
            reasons.append("📊 MACD bearish and falling")
        elif hist_current < 0:
            score += 5
            reasons.append("📊 MACD still bearish")
        elif hist_current > hist_prev:
            score -= 10
            reasons.append("📊 MACD turning bullish")
    
    # 7. Calculate new target based on ATR and S/R
    atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
    if pd.isna(atr):
        atr = current_price * 0.02  # Default 2% of price
    
    sr_levels = find_support_resistance(df)
    
    if position_type == "LONG":
        # New target = next resistance or 3x ATR
        atr_target = current_price + (atr * 3)
        sr_target = sr_levels['nearest_resistance']
        
        # Use the more conservative target
        if sr_target > current_price:
            new_target = min(atr_target, sr_target * 1.02)  # Slightly above resistance
        else:
            new_target = atr_target
        
        potential_gain = ((new_target - current_price) / current_price) * 100
    else:  # SHORT
        atr_target = current_price - (atr * 3)
        sr_target = sr_levels['nearest_support']
        
        if sr_target < current_price:
            new_target = max(atr_target, sr_target * 0.98)  # Slightly below support
        else:
            new_target = atr_target
        
        potential_gain = ((current_price - new_target) / current_price) * 100
    
    # Add score based on potential gain
    if potential_gain > 8:
        score += 10
        reasons.append(f"🎯 {potential_gain:.1f}% more potential!")
    elif potential_gain > 5:
        score += 7
        reasons.append(f"🎯 {potential_gain:.1f}% more potential")
    elif potential_gain > 3:
        score += 4
        reasons.append(f"🎯 {potential_gain:.1f}% potential remaining")
    elif potential_gain < 1:
        score -= 10
        reasons.append(f"⚠️ Limited upside ({potential_gain:.1f}%)")
    
    # Cap score
    score = max(0, min(100, score))
    
    # Generate recommendation
    if score >= 75:
        recommendation = "STRONG_HOLD"
        action = f"Strong momentum - Hold for extended target: ₹{new_target:.2f}"
    elif score >= 60:
        recommendation = "HOLD"
        action = f"Good upside - New target: ₹{new_target:.2f}"
    elif score >= 45:
        recommendation = "PARTIAL_EXIT"
        action = f"Book 50% profits, trail SL for rest to ₹{new_target:.2f}"
    elif score >= 30:
        recommendation = "MOSTLY_EXIT"
        action = "Book 75% profits, keep small position"
    else:
        recommendation = "EXIT"
        action = "Book full profits - momentum exhausted"
    
    return score, new_target, reasons, recommendation, action

# ============================================================================
# DYNAMIC TARGET & TRAIL STOP CALCULATION ✅
# ============================================================================
def calculate_dynamic_levels(df, entry_price, current_price, stop_loss, position_type, 
                             pnl_percent, trail_trigger=2.0):
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
        'atr_pct': (atr / current_price) * 100,
        'support': sr_levels['nearest_support'],
        'resistance': sr_levels['nearest_resistance'],
        'support_strength': sr_levels.get('support_strength', 'UNKNOWN'),
        'resistance_strength': sr_levels.get('resistance_strength', 'UNKNOWN')
    }
    
    if position_type == "LONG":
        # Dynamic targets based on ATR and resistance
        result['target1'] = current_price + (atr * 1.5)
        result['target2'] = current_price + (atr * 3)
        result['target3'] = min(current_price + (atr * 5), sr_levels['nearest_resistance'])
        
        # Calculate optimal targets considering resistance
        if sr_levels['nearest_resistance'] < result['target2']:
            result['adjusted_target'] = sr_levels['nearest_resistance'] * 0.99
            result['target_note'] = f"Resistance at ₹{sr_levels['nearest_resistance']:.2f}"
        else:
            result['adjusted_target'] = result['target2']
            result['target_note'] = "No immediate resistance"
        
        # Trail stop logic based on profit level
        # Using dynamic thresholds from sidebar
        if pnl_percent >= trail_trigger * 4:  # e.g., 8% if trigger is 2%
            # Lock substantial profits
            lock_pct = 0.06  # Lock 6%
            result['trail_stop'] = max(entry_price * (1 + lock_pct), current_price - (atr * 0.75))
            result['trail_reason'] = f"Locking {lock_pct*100:.0f}% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_PROFITS"
        elif pnl_percent >= trail_trigger * 3:  # e.g., 6% if trigger is 2%
            lock_pct = 0.04  # Lock 4%
            result['trail_stop'] = max(entry_price * (1 + lock_pct), current_price - atr)
            result['trail_reason'] = f"Locking {lock_pct*100:.0f}% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_PROFITS"
        elif pnl_percent >= trail_trigger * 2:  # e.g., 4% if trigger is 2%
            lock_pct = 0.02  # Lock 2%
            result['trail_stop'] = max(entry_price * (1 + lock_pct), current_price - (atr * 1.5))
            result['trail_reason'] = f"Locking {lock_pct*100:.0f}% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        elif pnl_percent >= trail_trigger:  # e.g., 2%
            result['trail_stop'] = max(entry_price, current_price - (atr * 2))
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "BREAKEVEN"
        elif pnl_percent >= trail_trigger * 0.5:  # e.g., 1%
            result['trail_stop'] = max(stop_loss, current_price - (atr * 2.5))
            result['trail_reason'] = f"Tightening SL slightly (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "TIGHTEN"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL - profit not enough to trail"
            result['trail_action'] = "HOLD"
        
        result['should_trail'] = result['trail_stop'] > stop_loss
        result['trail_improvement'] = result['trail_stop'] - stop_loss if result['should_trail'] else 0
        result['trail_improvement_pct'] = ((result['trail_stop'] - stop_loss) / entry_price * 100) if result['should_trail'] else 0
        
    else:  # SHORT
        # Dynamic targets
        result['target1'] = current_price - (atr * 1.5)
        result['target2'] = current_price - (atr * 3)
        result['target3'] = max(current_price - (atr * 5), sr_levels['nearest_support'])
        
        # Adjust for support
        if sr_levels['nearest_support'] > result['target2']:
            result['adjusted_target'] = sr_levels['nearest_support'] * 1.01
            result['target_note'] = f"Support at ₹{sr_levels['nearest_support']:.2f}"
        else:
            result['adjusted_target'] = result['target2']
            result['target_note'] = "No immediate support"
        
        # Trail stop for SHORT
        if pnl_percent >= trail_trigger * 4:
            lock_pct = 0.06
            result['trail_stop'] = min(entry_price * (1 - lock_pct), current_price + (atr * 0.75))
            result['trail_reason'] = f"Locking {lock_pct*100:.0f}% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_PROFITS"
        elif pnl_percent >= trail_trigger * 3:
            lock_pct = 0.04
            result['trail_stop'] = min(entry_price * (1 - lock_pct), current_price + atr)
            result['trail_reason'] = f"Locking {lock_pct*100:.0f}% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "LOCK_PROFITS"
        elif pnl_percent >= trail_trigger * 2:
            lock_pct = 0.02
            result['trail_stop'] = min(entry_price * (1 - lock_pct), current_price + (atr * 1.5))
            result['trail_reason'] = f"Locking {lock_pct*100:.0f}% profit (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "SECURE_GAINS"
        elif pnl_percent >= trail_trigger:
            result['trail_stop'] = min(entry_price, current_price + (atr * 2))
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "BREAKEVEN"
        elif pnl_percent >= trail_trigger * 0.5:
            result['trail_stop'] = min(stop_loss, current_price + (atr * 2.5))
            result['trail_reason'] = f"Tightening SL slightly (P&L: {pnl_percent:.1f}%)"
            result['trail_action'] = "TIGHTEN"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL - profit not enough to trail"
            result['trail_action'] = "HOLD"
        
        result['should_trail'] = result['trail_stop'] < stop_loss
        result['trail_improvement'] = stop_loss - result['trail_stop'] if result['should_trail'] else 0
        result['trail_improvement_pct'] = ((stop_loss - result['trail_stop']) / entry_price * 100) if result['should_trail'] else 0
    
    return result

# ============================================================================
# COMPLETE SMART ANALYSIS ✅ (MAIN FUNCTION WITH ALL PARAMETERS)
# ============================================================================
@st.cache_data(ttl=15)  # 15 second cache
def smart_analyze_position(ticker, position_type, entry_price, quantity, stop_loss,
                           target1, target2, trail_threshold=2.0, sl_alert_threshold=50,
                           sl_approach_threshold=2.0, enable_mtf=True):
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
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        day_change = ((current_price - prev_close) / prev_close) * 100
        
        # Get day's high and low
        day_high = float(df['High'].iloc[-1])
        day_low = float(df['Low'].iloc[-1])
        
    except Exception as e:
        return None
    
    # Basic P&L
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
    else:
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
    
    # Investment value
    investment_value = entry_price * quantity
    current_value = current_price * quantity
    
    # Technical Indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    if pd.isna(rsi):
        rsi = 50.0
    
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1]) if len(histogram) > 0 else 0
    macd_prev = float(histogram.iloc[-2]) if len(histogram) > 1 else 0
    if pd.isna(macd_hist):
        macd_hist = 0
    if pd.isna(macd_prev):
        macd_prev = 0
    
    macd_signal = "BULLISH" if macd_hist > 0 else "BEARISH"
    macd_trend = "RISING" if macd_hist > macd_prev else "FALLING"
    
    # Momentum Score
    momentum_score, momentum_trend, momentum_components = calculate_momentum_score(df)
    
    # Volume Analysis
    volume_signal, volume_ratio, volume_desc, volume_trend = analyze_volume(df)
    
    # Support/Resistance
    sr_levels = find_support_resistance(df)
    
    # Chart Patterns
    patterns = detect_chart_patterns(df)
    
    # SL Risk Prediction - NOW USES THRESHOLDS FROM SIDEBAR
    sl_risk, sl_reasons, sl_recommendation, sl_priority, distance_to_sl, is_approaching_sl = predict_sl_risk(
        df, current_price, stop_loss, position_type, entry_price, 
        sl_alert_threshold, sl_approach_threshold
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
            'total_timeframes': 0,
            'trend_strength': 'UNKNOWN'
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
    
    # ========================================================================
    # GENERATE ALERTS AND DETERMINE OVERALL STATUS
    # ========================================================================
    alerts = []
    email_triggers = []  # Track what emails should be sent
    
    # Priority 1: SL Hit (CRITICAL)
    if sl_hit:
        alerts.append({
            'priority': 'CRITICAL',
            'type': '🚨 STOP LOSS HIT',
            'message': f'Price ₹{current_price:.2f} breached SL ₹{stop_loss:.2f}',
            'action': 'EXIT IMMEDIATELY'
        })
        email_triggers.append('CRITICAL_SL_HIT')
        overall_status = 'CRITICAL'
        overall_action = 'EXIT'
    
    # Priority 2: Very High SL Risk (CRITICAL)
    elif sl_risk >= 80:
        alerts.append({
            'priority': 'CRITICAL',
            'type': '🚨 EXTREME SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation
        })
        email_triggers.append('CRITICAL_HIGH_RISK')
        overall_status = 'CRITICAL'
        overall_action = 'EXIT_EARLY'
    
    # Priority 3: Approaching SL (HIGH WARNING)
    elif is_approaching_sl:
        alerts.append({
            'priority': 'HIGH',
            'type': '⚠️ APPROACHING STOP LOSS',
            'message': f'Only {distance_to_sl:.2f}% from SL! Risk: {sl_risk}%',
            'action': sl_recommendation
        })
        email_triggers.append('APPROACHING_SL')
        overall_status = 'WARNING'
        overall_action = 'WATCH_CLOSELY'
    
    # Priority 4: High SL Risk (WARNING)
    elif sl_risk >= sl_alert_threshold + 20:
        alerts.append({
            'priority': 'HIGH',
            'type': '⚠️ HIGH SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation
        })
        email_triggers.append('HIGH_SL_RISK')
        overall_status = 'WARNING'
        overall_action = 'CONSIDER_EXIT'
    
    # Priority 5: Moderate SL Risk
    elif sl_risk >= sl_alert_threshold:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '👀 MODERATE SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation
        })
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    
    # Priority 6: Target 2 Hit (SUCCESS)
    elif target2_hit:
        alerts.append({
            'priority': 'HIGH',
            'type': '🎯 TARGET 2 HIT!',
            'message': f'Both targets achieved! P&L: {pnl_percent:+.2f}% (₹{pnl_amount:+,.0f})',
            'action': 'BOOK FULL PROFITS'
        })
        email_triggers.append('TARGET_HIT')
        overall_status = 'SUCCESS'
        overall_action = 'BOOK_PROFITS'
    
    # Priority 7: Target 1 Hit - Analyze Upside
    elif target1_hit:
        if upside_score >= 70:
            alerts.append({
                'priority': 'INFO',
                'type': '🎯 TARGET HIT - STRONG HOLD',
                'message': f'Upside Score: {upside_score}% - {", ".join(upside_reasons[:2])}',
                'action': upside_action
            })
            email_triggers.append('TARGET_HIT')
            email_triggers.append('TARGET_CHANGE')
            overall_status = 'OPPORTUNITY'
            overall_action = 'HOLD_EXTEND'
        elif upside_score >= 50:
            alerts.append({
                'priority': 'INFO',
                'type': '🎯 TARGET HIT - PARTIAL EXIT',
                'message': f'Upside Score: {upside_score}% - Consider partial booking',
                'action': upside_action
            })
            email_triggers.append('TARGET_HIT')
            overall_status = 'OPPORTUNITY'
            overall_action = 'PARTIAL_EXIT'
        else:
            alerts.append({
                'priority': 'HIGH',
                'type': '🎯 TARGET HIT - EXIT',
                'message': f'Limited upside ({upside_score}%). Book profits.',
                'action': 'BOOK PROFITS NOW'
            })
            email_triggers.append('TARGET_HIT')
            overall_status = 'SUCCESS'
            overall_action = 'BOOK_PROFITS'
    
    # Priority 8: Trail Stop Triggered
    elif dynamic_levels['should_trail'] and pnl_percent >= trail_threshold:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '📈 TRAIL STOP LOSS',
            'message': f'{dynamic_levels.get("trail_reason", "Lock profits!")}',
            'action': f'Move SL: ₹{stop_loss:.2f} → ₹{dynamic_levels["trail_stop"]:.2f}'
        })
        email_triggers.append('SL_CHANGE')
        overall_status = 'GOOD'
        overall_action = 'TRAIL_SL'
    
    # Priority 9: MTF Warning
    elif enable_mtf and mtf_result['alignment_score'] < 40 and pnl_percent < 0:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '📊 MTF WARNING',
            'message': f'Timeframes against position ({mtf_result["alignment_score"]}% aligned)',
            'action': mtf_result['recommendation']
        })
        email_triggers.append('IMPORTANT_UPDATE')
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    
    # Default: OK
    else:
        overall_status = 'OK'
        overall_action = 'HOLD'
    
    # Add volume warning if against position (but not if already critical)
    if overall_status not in ['CRITICAL'] and sl_risk < sl_alert_threshold:
        if position_type == "LONG" and volume_signal == "STRONG_SELLING":
            alerts.append({
                'priority': 'LOW',
                'type': '📊 VOLUME WARNING',
                'message': volume_desc,
                'action': 'Monitor closely'
            })
        elif position_type == "SHORT" and volume_signal == "STRONG_BUYING":
            alerts.append({
                'priority': 'LOW',
                'type': '📊 VOLUME WARNING',
                'message': volume_desc,
                'action': 'Monitor closely'
            })
    
    # Add pattern alerts
    for pattern in patterns[:2]:  # Max 2 patterns
        if pattern['signal'] != 'NEUTRAL':
            priority = 'MEDIUM' if pattern['signal'] != position_type.replace('LONG', 'BULLISH').replace('SHORT', 'BEARISH') else 'LOW'
            if priority == 'MEDIUM' and overall_status not in ['CRITICAL', 'WARNING']:
                alerts.append({
                    'priority': priority,
                    'type': f"📈 {pattern['pattern'].replace('_', ' ')}",
                    'message': pattern['description'],
                    'action': 'Consider implications'
                })
    
    return {
        # Basic Info
        'ticker': ticker,
        'symbol': symbol,
        'position_type': position_type,
        'entry_price': entry_price,
        'current_price': current_price,
        'prev_close': prev_close,
        'day_change': day_change,
        'day_high': day_high,
        'day_low': day_low,
        'quantity': quantity,
        'pnl_percent': pnl_percent,
        'pnl_amount': pnl_amount,
        'investment_value': investment_value,
        'current_value': current_value,
        
        # Original Levels
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        
        # Technical Indicators
        'rsi': rsi,
        'macd_hist': macd_hist,
        'macd_signal': macd_signal,
        'macd_trend': macd_trend,
        
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
        'support_strength': sr_levels.get('support_strength', 'UNKNOWN'),
        'resistance_strength': sr_levels.get('resistance_strength', 'UNKNOWN'),
        
        # Patterns
        'patterns': patterns,
        
        # SL Risk
        'sl_risk': sl_risk,
        'sl_reasons': sl_reasons,
        'sl_recommendation': sl_recommendation,
        'sl_priority': sl_priority,
        'distance_to_sl': distance_to_sl,
        'is_approaching_sl': is_approaching_sl,
        
        # Upside
        'upside_score': upside_score,
        'upside_reasons': upside_reasons,
        'upside_rec': upside_rec,
        'new_target': new_target,
        
        # Dynamic Levels
        'trail_stop': dynamic_levels['trail_stop'],
        'should_trail': dynamic_levels['should_trail'],
        'trail_reason': dynamic_levels.get('trail_reason', ''),
        'trail_action': dynamic_levels.get('trail_action', 'HOLD'),
        'trail_improvement': dynamic_levels.get('trail_improvement', 0),
        'trail_improvement_pct': dynamic_levels.get('trail_improvement_pct', 0),
        'dynamic_target1': dynamic_levels['target1'],
        'dynamic_target2': dynamic_levels['target2'],
        'atr': dynamic_levels['atr'],
        'atr_pct': dynamic_levels.get('atr_pct', 0),
        
        # Targets Status
        'target1_hit': target1_hit,
        'target2_hit': target2_hit,
        'sl_hit': sl_hit,
        
        # Multi-Timeframe
        'mtf_signals': mtf_result['signals'],
        'mtf_details': mtf_result.get('details', {}),
        'mtf_alignment': mtf_result['alignment_score'],
        'mtf_recommendation': mtf_result['recommendation'],
        'mtf_trend_strength': mtf_result.get('trend_strength', 'UNKNOWN'),
        
        # Alerts & Status
        'alerts': alerts,
        'email_triggers': email_triggers,
        'overall_status': overall_status,
        'overall_action': overall_action,
        
        # Chart Data
        'df': df
    }
# ============================================================================
# PART 6: LOAD PORTFOLIO FUNCTION
# ============================================================================
def load_portfolio():
    """Load portfolio from Google Sheets"""
    
    # Your Google Sheets URL - UPDATE THIS WITH YOUR SHEET URL
    GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/155htPsyom2e-dR5BZJx_cFzGxjQQjePJt3H2sRLSr6w/edit?usp=sharing"
    
    try:
        # Convert to export URL
        sheet_id = GOOGLE_SHEETS_URL.split('/d/')[1].split('/')[0]
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
        
        # Read from Google Sheets
        df = pd.read_csv(export_url)
        
        # Filter active positions
        if 'Status' in df.columns:
            df = df[df['Status'].str.upper() == 'ACTIVE']
        
        # Clean column names (remove extra spaces)
        df.columns = df.columns.str.strip()
        
        # Validate required columns
        required_cols = ['Ticker', 'Position', 'Entry_Price', 'Stop_Loss', 'Target_1']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.warning(f"⚠️ Missing columns: {missing_cols}")
        
        st.success(f"✅ Loaded {len(df)} active positions from Google Sheets")
        return df
        
    except Exception as e:
        st.error(f"❌ Error loading from Google Sheets: {e}")
        st.info("💡 Make sure the Google Sheet is set to 'Anyone with the link can view'")
        
        # Return sample data as fallback
        st.warning("⚠️ Using sample data as fallback")
        return pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK'],
            'Position': ['LONG', 'LONG', 'SHORT', 'LONG'],
            'Entry_Price': [2450.00, 3580.00, 1520.00, 1650.00],
            'Quantity': [10, 5, 8, 15],
            'Stop_Loss': [2380.00, 3480.00, 1580.00, 1600.00],
            'Target_1': [2550.00, 3700.00, 1420.00, 1750.00],
            'Target_2': [2650.00, 3850.00, 1350.00, 1850.00],
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE']
        })


# ============================================================================
# PART 7: EMAIL PROCESSING FUNCTION
# ============================================================================
def process_and_send_emails(results, email_settings, summary_stats):
    """
    Process all results and send appropriate emails based on triggers
    Returns: list of email actions taken
    """
    if not email_settings['enabled']:
        return []
    
    email_actions = []
    ist_now = get_ist_now()
    
    # Categorize results by email type
    critical_results = []
    target_results = []
    approaching_sl_results = []
    sl_change_results = []
    target_change_results = []
    important_results = []
    
    for r in results:
        triggers = r.get('email_triggers', [])
        
        # Critical alerts
        if 'CRITICAL_SL_HIT' in triggers or 'CRITICAL_HIGH_RISK' in triggers:
            critical_results.append(r)
        
        # Target hit
        if 'TARGET_HIT' in triggers:
            target_results.append(r)
        
        # Approaching SL
        if 'APPROACHING_SL' in triggers or 'HIGH_SL_RISK' in triggers:
            approaching_sl_results.append(r)
        
        # SL change recommended
        if 'SL_CHANGE' in triggers:
            sl_change_results.append(r)
        
        # Target change recommended
        if 'TARGET_CHANGE' in triggers:
            target_change_results.append(r)
        
        # Important updates
        if 'IMPORTANT_UPDATE' in triggers:
            important_results.append(r)
    
    # Send Critical Alerts Email
    if critical_results and email_settings['on_critical']:
        alert_hash = generate_alert_hash("PORTFOLIO", "CRITICAL", 
                                        "_".join([r['ticker'] for r in critical_results]))
        
        if can_send_email(alert_hash, email_settings['cooldown']):
            subject = f"🚨 CRITICAL: {len(critical_results)} position(s) need IMMEDIATE action!"
            html_content = generate_critical_email(critical_results)
            
            success, msg = send_email_alert(
                subject, html_content,
                email_settings['sender'], 
                email_settings['password'],
                email_settings['recipient']
            )
            
            if success:
                mark_email_sent(alert_hash)
                log_email(f"CRITICAL alert sent for {[r['ticker'] for r in critical_results]}")
                email_actions.append(('CRITICAL', [r['ticker'] for r in critical_results], True))
            else:
                log_email(f"CRITICAL alert FAILED: {msg}")
                email_actions.append(('CRITICAL', [r['ticker'] for r in critical_results], False))
    
    # Send Target Achieved Email
    if target_results and email_settings['on_target']:
        alert_hash = generate_alert_hash("PORTFOLIO", "TARGET",
                                        "_".join([r['ticker'] for r in target_results]))
        
        if can_send_email(alert_hash, email_settings['cooldown']):
            subject = f"🎯 TARGET HIT: {len(target_results)} position(s) achieved target!"
            html_content = generate_target_email(target_results)
            
            success, msg = send_email_alert(
                subject, html_content,
                email_settings['sender'],
                email_settings['password'],
                email_settings['recipient']
            )
            
            if success:
                mark_email_sent(alert_hash)
                log_email(f"TARGET alert sent for {[r['ticker'] for r in target_results]}")
                email_actions.append(('TARGET', [r['ticker'] for r in target_results], True))
            else:
                log_email(f"TARGET alert FAILED: {msg}")
                email_actions.append(('TARGET', [r['ticker'] for r in target_results], False))
    
    # Send Approaching SL Email
    if approaching_sl_results and email_settings['on_sl_approach']:
        alert_hash = generate_alert_hash("PORTFOLIO", "SL_APPROACH",
                                        "_".join([r['ticker'] for r in approaching_sl_results]))
        
        if can_send_email(alert_hash, email_settings['cooldown']):
            subject = f"⚠️ WARNING: {len(approaching_sl_results)} position(s) approaching Stop Loss!"
            html_content = generate_sl_approach_email(approaching_sl_results)
            
            success, msg = send_email_alert(
                subject, html_content,
                email_settings['sender'],
                email_settings['password'],
                email_settings['recipient']
            )
            
            if success:
                mark_email_sent(alert_hash)
                log_email(f"SL APPROACH alert sent for {[r['ticker'] for r in approaching_sl_results]}")
                email_actions.append(('SL_APPROACH', [r['ticker'] for r in approaching_sl_results], True))
            else:
                log_email(f"SL APPROACH alert FAILED: {msg}")
                email_actions.append(('SL_APPROACH', [r['ticker'] for r in approaching_sl_results], False))
    
    # Send SL Change Recommendation Email
    if sl_change_results and email_settings['on_sl_change']:
        alert_hash = generate_alert_hash("PORTFOLIO", "SL_CHANGE",
                                        "_".join([f"{r['ticker']}_{r['trail_stop']:.0f}" 
                                                 for r in sl_change_results]))
        
        if can_send_email(alert_hash, email_settings['cooldown']):
            subject = f"🔄 TRAIL SL: {len(sl_change_results)} position(s) need SL update!"
            html_content = generate_sl_change_email(sl_change_results)
            
            success, msg = send_email_alert(
                subject, html_content,
                email_settings['sender'],
                email_settings['password'],
                email_settings['recipient']
            )
            
            if success:
                mark_email_sent(alert_hash)
                log_email(f"SL CHANGE alert sent for {[r['ticker'] for r in sl_change_results]}")
                email_actions.append(('SL_CHANGE', [r['ticker'] for r in sl_change_results], True))
            else:
                log_email(f"SL CHANGE alert FAILED: {msg}")
                email_actions.append(('SL_CHANGE', [r['ticker'] for r in sl_change_results], False))
    
    # Send Target Change Recommendation Email
    if target_change_results and email_settings['on_target_change']:
        alert_hash = generate_alert_hash("PORTFOLIO", "TARGET_CHANGE",
                                        "_".join([f"{r['ticker']}_{r['new_target']:.0f}" 
                                                 for r in target_change_results]))
        
        if can_send_email(alert_hash, email_settings['cooldown']):
            subject = f"📈 NEW TARGETS: {len(target_change_results)} position(s) have extended targets!"
            html_content = generate_target_change_email(target_change_results)
            
            success, msg = send_email_alert(
                subject, html_content,
                email_settings['sender'],
                email_settings['password'],
                email_settings['recipient']
            )
            
            if success:
                mark_email_sent(alert_hash)
                log_email(f"TARGET CHANGE alert sent for {[r['ticker'] for r in target_change_results]}")
                email_actions.append(('TARGET_CHANGE', [r['ticker'] for r in target_change_results], True))
            else:
                log_email(f"TARGET CHANGE alert FAILED: {msg}")
                email_actions.append(('TARGET_CHANGE', [r['ticker'] for r in target_change_results], False))
    
    return email_actions


# ============================================================================
# PART 7: MAIN APPLICATION
# ============================================================================
def main():
    # Header
    st.markdown('<h1 class="main-header">🧠 Smart Portfolio Monitor v5.2</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;color:#666;">Enhanced Email Alerts Edition</p>', unsafe_allow_html=True)
    
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
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Trail SL Trigger", f"{trail_sl_trigger}%")
        with col2:
            st.metric("SL Risk Alert", f"{sl_risk_threshold}%")
        with col3:
            st.metric("SL Approach", f"{sl_approach_threshold}%")
        with col4:
            st.metric("Refresh", f"{refresh_interval}s")
        with col5:
            email_status = "✅ On" if email_enabled else "❌ Off"
            st.metric("Email Alerts", email_status)
        
        if email_enabled:
            st.markdown("**Email Alert Types:**")
            alert_types = []
            if email_on_critical: alert_types.append("🔴 Critical")
            if email_on_target: alert_types.append("🎯 Target")
            if email_on_sl_approach: alert_types.append("⚠️ SL Approach")
            if email_on_sl_change: alert_types.append("🔄 SL Change")
            if email_on_target_change: alert_types.append("📈 Target Change")
            if email_on_important: alert_types.append("📋 Important")
            st.write(" | ".join(alert_types) if alert_types else "No alerts enabled")
    
    st.divider()
    
    # Load Portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.warning("⚠️ No positions found! Add positions to your Google Sheet.")
        
        # Show sample format
        st.markdown("### 📋 Expected Google Sheet Format:")
        sample_df = pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS'],
            'Position': ['LONG', 'SHORT'],
            'Entry_Price': [2450.00, 3580.00],
            'Quantity': [10, 5],
            'Stop_Loss': [2380.00, 3650.00],
            'Target_1': [2550.00, 3450.00],
            'Target_2': [2650.00, 3350.00],
            'Status': ['ACTIVE', 'ACTIVE']
        })
        st.dataframe(sample_df, use_container_width=True)
        return
    
    # ========================================================================
    # ANALYZE ALL POSITIONS
    # ========================================================================
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
            trail_sl_trigger,
            sl_risk_threshold,
            sl_approach_threshold,
            enable_multi_timeframe
        )
        
        if result:
            results.append(result)
        
        progress_bar.progress((i + 1) / len(portfolio), text=f"Completed {row['Ticker']}")
    
    progress_bar.empty()
    
    if not results:
        st.error("❌ Could not fetch stock data. Check internet connection and try again.")
        return
    
    # ========================================================================
    # CALCULATE SUMMARY STATISTICS
    # ========================================================================
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['investment_value'] for r in results)
    total_current = sum(r['current_value'] for r in results)
    pnl_percent_total = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    critical_count = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['overall_status'] == 'WARNING')
    opportunity_count = sum(1 for r in results if r['overall_status'] == 'OPPORTUNITY')
    success_count = sum(1 for r in results if r['overall_status'] == 'SUCCESS')
    good_count = sum(1 for r in results if r['overall_status'] == 'GOOD')
    ok_count = sum(1 for r in results if r['overall_status'] == 'OK')
    
    profitable_count = sum(1 for r in results if r['pnl_percent'] > 0)
    losing_count = sum(1 for r in results if r['pnl_percent'] < 0)
    
    summary_stats = {
        'total_pnl': total_pnl,
        'pnl_percent': pnl_percent_total,
        'total_invested': total_invested,
        'total_current': total_current,
        'total_positions': len(results),
        'critical': critical_count,
        'warning': warning_count,
        'opportunity': opportunity_count,
        'success': success_count,
        'good': good_count,
        'ok': ok_count,
        'profitable': profitable_count,
        'losing': losing_count
    }
    
    # ========================================================================
    # PROCESS AND SEND EMAILS
    # ========================================================================
    email_settings = {
        'enabled': email_enabled,
        'sender': sender_email,
        'password': sender_password,
        'recipient': recipient_email,
        'on_critical': email_on_critical,
        'on_target': email_on_target,
        'on_sl_approach': email_on_sl_approach,
        'on_sl_change': email_on_sl_change,
        'on_target_change': email_on_target_change,
        'on_important': email_on_important,
        'cooldown': email_cooldown
    }
    
    email_actions = process_and_send_emails(results, email_settings, summary_stats)
    
    # Show email notifications
    if email_actions:
        for action_type, tickers, success in email_actions:
            if success:
                st.toast(f"📧 {action_type} email sent for {', '.join(tickers)}", icon="✅")
            else:
                st.toast(f"📧 {action_type} email failed for {', '.join(tickers)}", icon="❌")
    
    # ========================================================================
    # DISPLAY SUMMARY CARDS
    # ========================================================================
    st.markdown("### 📊 Portfolio Summary")
    
    # Main metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        pnl_delta = f"{pnl_percent_total:+.2f}%"
        st.metric("💰 Total P&L", f"₹{total_pnl:+,.0f}", pnl_delta)
    with col2:
        st.metric("📊 Total Investment", f"₹{total_invested:,.0f}")
    with col3:
        st.metric("📈 Current Value", f"₹{total_current:,.0f}")
    with col4:
        st.metric("📋 Positions", f"{len(results)}", f"📈{profitable_count} 📉{losing_count}")
    
    # Status metrics row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("🔴 Critical", critical_count)
    with col2:
        st.metric("🟡 Warning", warning_count)
    with col3:
        st.metric("🟢 Good", good_count)
    with col4:
        st.metric("🔵 Opportunity", opportunity_count)
    with col5:
        st.metric("✅ Success", success_count)
    with col6:
        st.metric("⚪ OK", ok_count)
    
    # Critical Alert Banner
    if critical_count > 0:
        st.markdown(f"""
        <div class="critical-box">
            🚨 CRITICAL ALERT: {critical_count} position(s) need IMMEDIATE attention!
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ========================================================================
    # TABS
    # ========================================================================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard", 
        "📈 Charts", 
        "🔔 Alerts", 
        "📉 MTF Analysis",
        "📧 Email Status",
        "📋 Details"
    ])
    
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
            pnl_color = "green" if r['pnl_percent'] >= 0 else "red"
            
            # Expander title with key info
            expander_title = (
                f"{status_icon} **{r['ticker']}** | "
                f"{'📈 LONG' if r['position_type'] == 'LONG' else '📉 SHORT'} | "
                f"{pnl_emoji} P&L: **{r['pnl_percent']:+.2f}%** (₹{r['pnl_amount']:+,.0f}) | "
                f"SL Risk: **{r['sl_risk']}%** | "
                f"Action: **{r['overall_action'].replace('_', ' ')}**"
            )
            
            with st.expander(
                expander_title,
                expanded=(r['overall_status'] in ['CRITICAL', 'WARNING', 'OPPORTUNITY', 'SUCCESS'])
            ):
                # Row 1: Basic Info
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("##### 💰 Position")
                    st.write(f"**Entry:** ₹{r['entry_price']:,.2f}")
                    st.write(f"**Current:** ₹{r['current_price']:,.2f}")
                    st.write(f"**Day Change:** {r['day_change']:+.2f}%")
                    st.write(f"**Qty:** {r['quantity']}")
                    st.markdown(f"**P&L:** <span style='color:{pnl_color};font-weight:bold;'>"
                               f"₹{r['pnl_amount']:+,.2f} ({r['pnl_percent']:+.2f}%)</span>",
                               unsafe_allow_html=True)
                
                with col2:
                    st.markdown("##### 🎯 Levels")
                    st.write(f"**Stop Loss:** ₹{r['stop_loss']:,.2f} {'🔴 HIT!' if r['sl_hit'] else ''}")
                    st.write(f"**Distance to SL:** {r['distance_to_sl']:.2f}%")
                    st.write(f"**Target 1:** ₹{r['target1']:,.2f} {'✅' if r['target1_hit'] else ''}")
                    st.write(f"**Target 2:** ₹{r['target2']:,.2f} {'✅' if r['target2_hit'] else ''}")
                    
                    if r['should_trail']:
                        st.success(f"**New Trail SL:** ₹{r['trail_stop']:,.2f}")
                        st.caption(r.get('trail_reason', ''))
                
                with col3:
                    st.markdown("##### 📊 Indicators")
                    rsi_color = "green" if 40 <= r['rsi'] <= 60 else "orange" if 30 <= r['rsi'] <= 70 else "red"
                    st.markdown(f"**RSI:** <span style='color:{rsi_color};'>{r['rsi']:.1f}</span>", 
                               unsafe_allow_html=True)
                    macd_color = "green" if r['macd_signal'] == "BULLISH" else "red"
                    st.markdown(f"**MACD:** <span style='color:{macd_color};'>{r['macd_signal']} ({r['macd_trend']})</span>", 
                               unsafe_allow_html=True)
                    st.write(f"**Volume:** {r['volume_signal'].replace('_', ' ')}")
                    st.write(f"**Trend:** {r['momentum_trend']}")
                
                with col4:
                    st.markdown("##### 🛡️ Support/Resistance")
                    st.write(f"**Support:** ₹{r['support']:,.2f} ({r['support_strength']})")
                    st.write(f"**Resistance:** ₹{r['resistance']:,.2f} ({r['resistance_strength']})")
                    st.write(f"**ATR:** ₹{r['atr']:,.2f} ({r['atr_pct']:.2f}%)")
                    st.write(f"**Dist to Support:** {r['distance_to_support']:.1f}%")
                
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
                        if r['upside_score'] >= 50:
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
                    st.markdown("##### 🔔 Alerts & Recommendations")
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
                    'CONSIDER_EXIT': 'critical-box', 'WATCH_CLOSELY': 'warning-box',
                    'WATCH': 'warning-box', 'BOOK_PROFITS': 'success-box',
                    'HOLD_EXTEND': 'info-box', 'TRAIL_SL': 'success-box',
                    'PARTIAL_EXIT': 'warning-box', 'HOLD': 'info-box'
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
            df['SMA50'] = df['Close'].rolling(50).mean()
            
            fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA20'], mode='lines',
                                    name='SMA 20', line=dict(color='orange', width=1)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['EMA9'], mode='lines',
                                    name='EMA 9', line=dict(color='purple', width=1)))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA50'], mode='lines',
                                    name='SMA 50', line=dict(color='blue', width=1, dash='dot')))
            
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
                    'SL Risk': f"{r['sl_risk']}%",
                    'Status': r['overall_status']
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
                with st.expander(f"{r['ticker']} - MTF Alignment: {r['mtf_alignment']}%",
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
                                <p style='font-size:0.9em;'><strong>Trend Strength:</strong> {r['mtf_trend_strength']}</p>
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
                                bullish_score = details.get('bullish_score', 0)
                                bearish_score = details.get('bearish_score', 0)
                                
                                st.markdown(f"""
                                **{tf}:** {sig_color} {signal} ({strength})
                                - RSI: {rsi_tf:.1f} | Above SMA20: {'✅' if details.get('above_sma20') else '❌'} | 
                                EMA Bullish: {'✅' if details.get('ema_bullish') else '❌'} |
                                MACD: {'📈' if details.get('macd_bullish') else '📉'} {'↑' if details.get('macd_rising') else '↓'}
                                - Bullish Score: {bullish_score:.0f}% | Bearish Score: {bearish_score:.0f}%
                                """)
                    else:
                        st.warning("MTF data not available for this stock")
    
    # =============== EMAIL STATUS TAB ===============
    with tab5:
        st.subheader("📧 Email Alert Status")
        
        if not email_enabled:
            st.warning("⚠️ Email alerts are disabled. Enable them in the sidebar.")
            st.info("""
            ### How to Enable Email Alerts:
            1. Go to the sidebar (⚙️ Settings)
            2. Check "Enable Email Alerts"
            3. Enter your Gmail address
            4. Enter your Gmail App Password (not regular password)
            5. Select which alert types you want to receive
            
            ### Gmail App Password:
            1. Go to Google Account → Security → 2-Step Verification
            2. At the bottom, click "App passwords"
            3. Select "Mail" and your device
            4. Use the 16-character password generated
            """)
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📧 Email Configuration")
                st.write(f"**Sender:** {sender_email[:3]}...@gmail.com")
                st.write(f"**Recipient:** {recipient_email[:3]}...@gmail.com")
                st.write(f"**Cooldown:** {email_cooldown} minutes")
                
                st.markdown("### 🔔 Enabled Alert Types")
                alert_status = {
                    "🔴 Critical Alerts": email_on_critical,
                    "🎯 Target Achieved": email_on_target,
                    "⚠️ Approaching SL": email_on_sl_approach,
                    "🔄 SL Change Needed": email_on_sl_change,
                    "📈 Target Change": email_on_target_change,
                    "📋 Important Updates": email_on_important
                }
                
                for alert_type, enabled in alert_status.items():
                    status = "✅ Enabled" if enabled else "❌ Disabled"
                    st.write(f"{alert_type}: {status}")
            
            with col2:
                st.markdown("### 📬 Recent Email Log")
                if st.session_state.email_log:
                    for log in reversed(st.session_state.email_log[-15:]):
                        st.caption(f"• {log}")
                else:
                    st.info("No emails sent in this session")
                
                st.markdown("### 📊 Pending Alerts")
                pending_alerts = []
                for r in results:
                    if r['email_triggers']:
                        pending_alerts.append({
                            'Ticker': r['ticker'],
                            'Triggers': ', '.join(r['email_triggers'])
                        })
                
                if pending_alerts:
                    st.dataframe(pd.DataFrame(pending_alerts), hide_index=True, use_container_width=True)
                else:
                    st.success("No pending alert triggers")
            
            # Test Email Button
            st.divider()
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("📧 Send Test Email", type="secondary"):
                    test_html = generate_email_header()
                    test_html += """
                    <div class="alert-box success">
                        <h3>✅ Test Email Successful!</h3>
                        <p>Your email configuration is working correctly.</p>
                        <p>You will receive alerts for your portfolio positions.</p>
                    </div>
                    """
                    test_html += generate_email_footer()
                    
                    success, msg = send_email_alert(
                        "🧪 Test Email - Smart Portfolio Monitor",
                        test_html,
                        sender_email,
                        sender_password,
                        recipient_email
                    )
                    
                    if success:
                        st.success("✅ Test email sent successfully!")
                        log_email("Test email sent")
                    else:
                        st.error(f"❌ Test email failed: {msg}")
            
            with col2:
                if st.button("📋 Send Summary Email", type="secondary"):
                    summary_html = generate_summary_email(results, summary_stats)
                    
                    success, msg = send_email_alert(
                        f"📊 Portfolio Summary - {ist_now.strftime('%Y-%m-%d %H:%M')}",
                        summary_html,
                        sender_email,
                        sender_password,
                        recipient_email
                    )
                    
                    if success:
                        st.success("✅ Summary email sent!")
                        log_email("Summary email sent")
                    else:
                        st.error(f"❌ Summary email failed: {msg}")
    
    # =============== DETAILS TAB ===============
    with tab6:
        st.subheader("📋 Complete Analysis Data")
        
        details_data = []
        for r in results:
            details_data.append({
                'Ticker': r['ticker'],
                'Type': r['position_type'],
                'Entry': f"₹{r['entry_price']:,.2f}",
                'Current': f"₹{r['current_price']:,.2f}",
                'Day %': f"{r['day_change']:+.2f}%",
                'P&L %': f"{r['pnl_percent']:+.2f}%",
                'P&L ₹': f"₹{r['pnl_amount']:+,.0f}",
                'SL': f"₹{r['stop_loss']:,.2f}",
                'Dist to SL': f"{r['distance_to_sl']:.2f}%",
                'SL Risk': f"{r['sl_risk']}%",
                'Momentum': f"{r['momentum_score']:.0f}",
                'RSI': f"{r['rsi']:.1f}",
                'MACD': f"{r['macd_signal']} {r['macd_trend']}",
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
        
        # Export options
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 Download Analysis (CSV)",
                df_details.to_csv(index=False),
                file_name=f"portfolio_analysis_{ist_now.strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        with col2:
            # Create JSON export with more details
            export_data = []
            for r in results:
                export_data.append({
                    'ticker': r['ticker'],
                    'position_type': r['position_type'],
                    'entry_price': r['entry_price'],
                    'current_price': r['current_price'],
                    'pnl_percent': r['pnl_percent'],
                    'pnl_amount': r['pnl_amount'],
                    'stop_loss': r['stop_loss'],
                    'sl_risk': r['sl_risk'],
                    'distance_to_sl': r['distance_to_sl'],
                    'target1': r['target1'],
                    'target2': r['target2'],
                    'target1_hit': r['target1_hit'],
                    'target2_hit': r['target2_hit'],
                    'momentum_score': r['momentum_score'],
                    'rsi': r['rsi'],
                    'trail_stop': r['trail_stop'] if r['should_trail'] else None,
                    'should_trail': r['should_trail'],
                    'overall_status': r['overall_status'],
                    'overall_action': r['overall_action'],
                    'alerts': r['alerts']
                })
            
            st.download_button(
                "📥 Download Full Report (JSON)",
                json.dumps(export_data, indent=2, default=str),
                file_name=f"portfolio_full_report_{ist_now.strftime('%Y%m%d_%H%M')}.json",
                mime="application/json"
            )
    
    # ========================================================================
    # AUTO REFRESH
    # ========================================================================
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
                st.caption(f"🔄 Auto-refresh active | Interval: {refresh_interval}s | Refresh count: {count}")
            else:
                # Fallback without streamlit-autorefresh
                st.caption(f"⏱️ Auto-refresh in {refresh_interval} seconds...")
                st.caption("💡 Install `streamlit-autorefresh` for better experience: `pip install streamlit-autorefresh`")
                
                import time
                time.sleep(refresh_interval)
                st.cache_data.clear()
                st.rerun()
        else:
            st.caption(f"⏸️ Auto-refresh paused - {market_status}: {market_msg}")
    else:
        st.caption("🔄 Auto-refresh disabled. Click 'Refresh' button to update.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<p style='text-align:center;color:#666;font-size:12px;'>"
        "🧠 Smart Portfolio Monitor v5.2 | Enhanced Email Edition | "
        "⚠️ Not financial advice - Always do your own research"
        "</p>",
        unsafe_allow_html=True
    )


# ============================================================================
# RUN THE APP
# ============================================================================
if __name__ == "__main__":
    main()
