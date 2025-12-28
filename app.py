"""
================================================================================
🧠 SMART PORTFOLIO MONITOR v5.2 - ENHANCED EMAIL ALERTS
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
✅ Email alerts for critical events (ENHANCED)
✅ Multi-Timeframe Analysis (fully implemented)
✅ Better caching (15s TTL)

NEW EMAIL FEATURES:
📧 Critical alerts (SL hit, high risk)
📧 Target achieved notifications
📧 Approaching SL warnings
📧 Trail SL suggestions
📧 Target change notifications
📧 Daily summary emails
📧 Duplicate email prevention
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
    .email-sent {
        background: linear-gradient(135deg, #6f42c1, #5a32a3);
        color: white;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        margin: 5px 0;
        font-size: 0.9em;
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

if 'sent_emails' not in st.session_state:
    st.session_state.sent_emails = {}

if 'email_log' not in st.session_state:
    st.session_state.email_log = []

if 'last_email_summary_date' not in st.session_state:
    st.session_state.last_email_summary_date = None

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
        
        st.markdown("#### 📬 Email Notification Types")
        email_critical = st.checkbox("🔴 Critical Alerts (SL Hit, High Risk)", value=True,
                                    help="Email when SL is hit or risk is very high")
        email_target = st.checkbox("🎯 Target Achieved", value=True,
                                  help="Email when target price is reached")
        email_approaching_sl = st.checkbox("⚠️ Approaching SL Warning", value=True,
                                          help="Email when price is getting close to SL")
        email_trail_sl = st.checkbox("📈 Trail SL Suggestions", value=True,
                                    help="Email when trailing SL is recommended")
        email_target_change = st.checkbox("🔄 Target/SL Changes", value=True,
                                         help="Email when new targets are calculated")
        email_daily_summary = st.checkbox("📊 Daily Summary", value=False,
                                         help="Send daily portfolio summary")
        
        st.markdown("#### ⏰ Email Cooldown")
        email_cooldown = st.slider("Minutes between same alerts", 5, 60, 15,
                                  help="Prevent duplicate emails within this time")
    else:
        sender_email = ""
        sender_password = ""
        recipient_email = ""
        email_critical = True
        email_target = True
        email_approaching_sl = True
        email_trail_sl = True
        email_target_change = True
        email_daily_summary = False
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
    approaching_sl_threshold = st.slider("Approaching SL Warning %", 1.0, 5.0, 2.0, step=0.5,
                                        help="Warn when price is within this % of SL")
    
    st.divider()
    
    # Analysis Settings
    st.markdown("### 📊 Analysis Settings")
    enable_volume_analysis = st.checkbox("Volume Confirmation", value=True)
    enable_sr_detection = st.checkbox("Support/Resistance", value=True)
    enable_multi_timeframe = st.checkbox("Multi-Timeframe Analysis", value=True,
                                        help="Analyze Daily, Weekly, Hourly trends")
    
    st.divider()
    
    # Email Log
    with st.expander("📧 Email Log"):
        if st.session_state.email_log:
            for log_entry in st.session_state.email_log[-10:]:  # Show last 10 emails
                st.caption(f"{log_entry['time']} - {log_entry['type']}: {log_entry['ticker']}")
        else:
            st.caption("No emails sent yet")
        
        if st.button("Clear Email Log"):
            st.session_state.email_log = []
            st.session_state.sent_emails = {}
            st.success("Email log cleared!")
    
    # Debug Info
    with st.expander("🔧 Debug Info"):
        st.write(f"Auto-refresh library: {'✅ Installed' if HAS_AUTOREFRESH else '❌ Not installed'}")
        st.write(f"Refresh interval: {refresh_interval}s")
        st.write(f"Trail SL trigger: {trail_sl_trigger}%")
        st.write(f"SL Risk threshold: {sl_risk_threshold}%")
        st.write(f"Email cooldown: {email_cooldown} min")
        st.write(f"Emails in cooldown: {len(st.session_state.sent_emails)}")

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

# ============================================================================
# ENHANCED EMAIL SYSTEM
# ============================================================================

def generate_email_key(ticker, alert_type, details=""):
    """Generate a unique key for email deduplication"""
    key_string = f"{ticker}_{alert_type}_{details}"
    return hashlib.md5(key_string.encode()).hexdigest()

def can_send_email(email_key, cooldown_minutes=15):
    """Check if email can be sent (not in cooldown)"""
    if email_key not in st.session_state.sent_emails:
        return True
    
    last_sent = st.session_state.sent_emails[email_key]
    time_diff = (datetime.now() - last_sent).total_seconds() / 60
    
    return time_diff >= cooldown_minutes

def mark_email_sent(email_key, ticker, alert_type):
    """Mark email as sent and log it"""
    st.session_state.sent_emails[email_key] = datetime.now()
    st.session_state.email_log.append({
        'time': get_ist_now().strftime('%H:%M:%S'),
        'type': alert_type,
        'ticker': ticker,
        'key': email_key
    })

def create_email_html(alert_type, data, ist_now):
    """Create formatted HTML email content"""
    
    # Common header
    header = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
        <h1 style="color: white; margin: 0;">🧠 Smart Portfolio Monitor</h1>
        <p style="color: #e0e0e0; margin: 5px 0;">{ist_now.strftime('%Y-%m-%d %H:%M:%S')} IST</p>
    </div>
    """
    
    # Common footer
    footer = """
    <div style="background: #f5f5f5; padding: 15px; text-align: center; margin-top: 20px;">
        <p style="color: #666; font-size: 12px; margin: 0;">
            This is an automated alert from Smart Portfolio Monitor v5.2<br>
            📧 Manage your alert preferences in the app settings
        </p>
    </div>
    </body>
    </html>
    """
    
    if alert_type == "CRITICAL":
        content = f"""
        <div style="background: #f8d7da; border-left: 5px solid #dc3545; padding: 20px; margin: 20px;">
            <h2 style="color: #dc3545; margin-top: 0;">🚨 CRITICAL ALERT</h2>
            <h3 style="margin: 10px 0;">{data['ticker']} - {data['position_type']}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Status:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #dc3545; font-weight: bold;">{data['status']}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Current Price:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['current_price']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Entry Price:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['entry_price']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Stop Loss:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['stop_loss']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>P&L:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: {'green' if data['pnl_percent'] >= 0 else 'red'};">
                        {data['pnl_percent']:+.2f}% (₹{data['pnl_amount']:+,.2f})</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>SL Risk Score:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #dc3545; font-weight: bold;">{data['sl_risk']}%</td></tr>
            </table>
            <div style="background: #dc3545; color: white; padding: 15px; text-align: center; margin-top: 15px; border-radius: 5px;">
                <strong>⚡ ACTION REQUIRED: {data['action']}</strong>
            </div>
            <p style="margin-top: 15px;"><strong>Reasons:</strong></p>
            <ul>
                {''.join([f'<li>{reason}</li>' for reason in data.get('reasons', [])[:5]])}
            </ul>
        </div>
        """
    
    elif alert_type == "TARGET_HIT":
        content = f"""
        <div style="background: #d4edda; border-left: 5px solid #28a745; padding: 20px; margin: 20px;">
            <h2 style="color: #28a745; margin-top: 0;">🎯 TARGET ACHIEVED!</h2>
            <h3 style="margin: 10px 0;">{data['ticker']} - {data['position_type']}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Target Hit:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #28a745; font-weight: bold;">{data['target_hit']}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Current Price:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['current_price']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Entry Price:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['entry_price']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>P&L:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: green; font-weight: bold;">
                        {data['pnl_percent']:+.2f}% (₹{data['pnl_amount']:+,.2f})</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Upside Score:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{data.get('upside_score', 'N/A')}%</td></tr>
            </table>
            <div style="background: #28a745; color: white; padding: 15px; text-align: center; margin-top: 15px; border-radius: 5px;">
                <strong>💰 RECOMMENDATION: {data['action']}</strong>
            </div>
            {f"<p style='margin-top: 15px;'><strong>New Target:</strong> ₹{data.get('new_target', 0):.2f}</p>" if data.get('new_target') else ""}
        </div>
        """
    
    elif alert_type == "APPROACHING_SL":
        content = f"""
        <div style="background: #fff3cd; border-left: 5px solid #ffc107; padding: 20px; margin: 20px;">
            <h2 style="color: #856404; margin-top: 0;">⚠️ APPROACHING STOP LOSS</h2>
            <h3 style="margin: 10px 0;">{data['ticker']} - {data['position_type']}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Current Price:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['current_price']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Stop Loss:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #dc3545;">₹{data['stop_loss']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Distance to SL:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #ffc107; font-weight: bold;">{data['distance_to_sl']:.2f}%</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>SL Risk Score:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #ffc107; font-weight: bold;">{data['sl_risk']}%</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>P&L:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: {'green' if data['pnl_percent'] >= 0 else 'red'};">
                        {data['pnl_percent']:+.2f}%</td></tr>
            </table>
            <div style="background: #ffc107; color: #856404; padding: 15px; text-align: center; margin-top: 15px; border-radius: 5px;">
                <strong>👀 ACTION: {data['action']}</strong>
            </div>
            <p style="margin-top: 15px;"><strong>Warning Signs:</strong></p>
            <ul>
                {''.join([f'<li>{reason}</li>' for reason in data.get('reasons', [])[:5]])}
            </ul>
        </div>
        """
    
    elif alert_type == "TRAIL_SL":
        content = f"""
        <div style="background: #d1ecf1; border-left: 5px solid #17a2b8; padding: 20px; margin: 20px;">
            <h2 style="color: #0c5460; margin-top: 0;">📈 TRAIL STOP LOSS SUGGESTION</h2>
            <h3 style="margin: 10px 0;">{data['ticker']} - {data['position_type']}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Current Price:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['current_price']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Current SL:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['current_sl']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Suggested New SL:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #17a2b8; font-weight: bold;">₹{data['new_sl']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>P&L:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: green; font-weight: bold;">
                        {data['pnl_percent']:+.2f}% (₹{data['pnl_amount']:+,.2f})</td></tr>
            </table>
            <div style="background: #17a2b8; color: white; padding: 15px; text-align: center; margin-top: 15px; border-radius: 5px;">
                <strong>🔒 {data['trail_reason']}</strong>
            </div>
        </div>
        """
    
    elif alert_type == "TARGET_CHANGE":
        content = f"""
        <div style="background: #e2e3e5; border-left: 5px solid #6c757d; padding: 20px; margin: 20px;">
            <h2 style="color: #383d41; margin-top: 0;">🔄 TARGET/LEVEL UPDATE</h2>
            <h3 style="margin: 10px 0;">{data['ticker']} - {data['position_type']}</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Current Price:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['current_price']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>New Dynamic Target 1:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #28a745;">₹{data['new_target1']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>New Dynamic Target 2:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #28a745;">₹{data['new_target2']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Support Level:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['support']:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Resistance Level:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">₹{data['resistance']:.2f}</td></tr>
            </table>
            <p style="margin-top: 15px;"><strong>Based on ATR:</strong> ₹{data['atr']:.2f}</p>
        </div>
        """
    
    elif alert_type == "DAILY_SUMMARY":
        positions_html = ""
        for pos in data['positions']:
            pnl_color = 'green' if pos['pnl_percent'] >= 0 else 'red'
            status_emoji = {'CRITICAL': '🔴', 'WARNING': '🟡', 'SUCCESS': '🟢', 'GOOD': '🟢', 'OPPORTUNITY': '🔵', 'OK': '⚪'}
            positions_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{status_emoji.get(pos['status'], '⚪')} {pos['ticker']}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{pos['position_type']}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">₹{pos['current_price']:.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; color: {pnl_color};">{pos['pnl_percent']:+.2f}%</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{pos['sl_risk']}%</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{pos['action']}</td>
            </tr>
            """
        
        content = f"""
        <div style="padding: 20px; margin: 20px;">
            <h2 style="color: #333; margin-top: 0;">📊 Daily Portfolio Summary</h2>
            
            <div style="display: flex; justify-content: space-around; margin: 20px 0;">
                <div style="text-align: center; padding: 15px; background: #f8f9fa; border-radius: 10px;">
                    <h3 style="color: {'green' if data['total_pnl'] >= 0 else 'red'}; margin: 0;">₹{data['total_pnl']:+,.2f}</h3>
                    <p style="margin: 5px 0; color: #666;">Total P&L</p>
                </div>
                <div style="text-align: center; padding: 15px; background: #f8f9fa; border-radius: 10px;">
                    <h3 style="margin: 0;">{data['total_positions']}</h3>
                    <p style="margin: 5px 0; color: #666;">Positions</p>
                </div>
                <div style="text-align: center; padding: 15px; background: #f8d7da; border-radius: 10px;">
                    <h3 style="color: #dc3545; margin: 0;">{data['critical_count']}</h3>
                    <p style="margin: 5px 0; color: #666;">Critical</p>
                </div>
                <div style="text-align: center; padding: 15px; background: #d4edda; border-radius: 10px;">
                    <h3 style="color: #28a745; margin: 0;">{data['success_count']}</h3>
                    <p style="margin: 5px 0; color: #666;">At Target</p>
                </div>
            </div>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background: #667eea; color: white;">
                        <th style="padding: 10px; border: 1px solid #ddd;">Stock</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Type</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Price</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">P&L</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Risk</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {positions_html}
                </tbody>
            </table>
        </div>
        """
    
    else:
        content = f"""
        <div style="padding: 20px; margin: 20px;">
            <h2>Portfolio Alert</h2>
            <p>{data.get('message', 'Alert triggered')}</p>
        </div>
        """
    
    return header + content + footer

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

def process_email_alerts(results, email_settings, ist_now):
    """Process and send all email alerts based on results"""
    
    emails_sent = []
    
    if not email_settings['enabled']:
        return emails_sent
    
    for r in results:
        # 1. CRITICAL ALERTS (SL Hit or Very High Risk)
        if email_settings['critical'] and r['overall_status'] == 'CRITICAL':
            email_key = generate_email_key(r['ticker'], 'CRITICAL', str(r['sl_hit']))
            
            if can_send_email(email_key, email_settings['cooldown']):
                data = {
                    'ticker': r['ticker'],
                    'position_type': r['position_type'],
                    'status': 'STOP LOSS HIT!' if r['sl_hit'] else 'HIGH RISK',
                    'current_price': r['current_price'],
                    'entry_price': r['entry_price'],
                    'stop_loss': r['stop_loss'],
                    'pnl_percent': r['pnl_percent'],
                    'pnl_amount': r['pnl_amount'],
                    'sl_risk': r['sl_risk'],
                    'action': r['alerts'][0]['action'] if r['alerts'] else 'EXIT IMMEDIATELY',
                    'reasons': r['sl_reasons']
                }
                
                html_content = create_email_html('CRITICAL', data, ist_now)
                subject = f"🚨 CRITICAL: {r['ticker']} - {'SL HIT' if r['sl_hit'] else 'HIGH RISK'}"
                
                if send_email_alert(subject, html_content, 
                                   email_settings['sender'], 
                                   email_settings['password'], 
                                   email_settings['recipient']):
                    mark_email_sent(email_key, r['ticker'], 'CRITICAL')
                    emails_sent.append({'type': 'CRITICAL', 'ticker': r['ticker']})
        
        # 2. TARGET HIT ALERTS
        if email_settings['target'] and (r['target1_hit'] or r['target2_hit']) and not r['sl_hit']:
            target_hit = "Target 2" if r['target2_hit'] else "Target 1"
            email_key = generate_email_key(r['ticker'], 'TARGET', target_hit)
            
            if can_send_email(email_key, email_settings['cooldown']):
                data = {
                    'ticker': r['ticker'],
                    'position_type': r['position_type'],
                    'target_hit': target_hit,
                    'current_price': r['current_price'],
                    'entry_price': r['entry_price'],
                    'pnl_percent': r['pnl_percent'],
                    'pnl_amount': r['pnl_amount'],
                    'upside_score': r['upside_score'],
                    'new_target': r['new_target'],
                    'action': 'BOOK PROFITS' if r['upside_score'] < 60 else 'HOLD FOR MORE'
                }
                
                html_content = create_email_html('TARGET_HIT', data, ist_now)
                subject = f"🎯 TARGET HIT: {r['ticker']} - {target_hit} Achieved! P&L: {r['pnl_percent']:+.2f}%"
                
                if send_email_alert(subject, html_content,
                                   email_settings['sender'],
                                   email_settings['password'],
                                   email_settings['recipient']):
                    mark_email_sent(email_key, r['ticker'], 'TARGET_HIT')
                    emails_sent.append({'type': 'TARGET_HIT', 'ticker': r['ticker']})
        
        # 3. APPROACHING SL WARNING
        if email_settings['approaching_sl'] and r['sl_risk'] >= email_settings['sl_threshold'] and r['sl_risk'] < 80:
            # Calculate distance to SL
            if r['position_type'] == "LONG":
                distance_to_sl = ((r['current_price'] - r['stop_loss']) / r['current_price']) * 100
            else:
                distance_to_sl = ((r['stop_loss'] - r['current_price']) / r['current_price']) * 100
            
            if distance_to_sl <= email_settings['approaching_threshold'] and distance_to_sl > 0:
                email_key = generate_email_key(r['ticker'], 'APPROACHING_SL', f"{int(distance_to_sl)}")
                
                if can_send_email(email_key, email_settings['cooldown']):
                    data = {
                        'ticker': r['ticker'],
                        'position_type': r['position_type'],
                        'current_price': r['current_price'],
                        'stop_loss': r['stop_loss'],
                        'distance_to_sl': distance_to_sl,
                        'sl_risk': r['sl_risk'],
                        'pnl_percent': r['pnl_percent'],
                        'action': 'WATCH CLOSELY - Consider early exit',
                        'reasons': r['sl_reasons']
                    }
                    
                    html_content = create_email_html('APPROACHING_SL', data, ist_now)
                    subject = f"⚠️ WARNING: {r['ticker']} approaching SL ({distance_to_sl:.1f}% away)"
                    
                    if send_email_alert(subject, html_content,
                                       email_settings['sender'],
                                       email_settings['password'],
                                       email_settings['recipient']):
                        mark_email_sent(email_key, r['ticker'], 'APPROACHING_SL')
                        emails_sent.append({'type': 'APPROACHING_SL', 'ticker': r['ticker']})
        
        # 4. TRAIL SL SUGGESTIONS
        if email_settings['trail_sl'] and r['should_trail']:
            email_key = generate_email_key(r['ticker'], 'TRAIL_SL', f"{int(r['trail_stop'])}")
            
            if can_send_email(email_key, email_settings['cooldown']):
                data = {
                    'ticker': r['ticker'],
                    'position_type': r['position_type'],
                    'current_price': r['current_price'],
                    'current_sl': r['stop_loss'],
                    'new_sl': r['trail_stop'],
                    'pnl_percent': r['pnl_percent'],
                    'pnl_amount': r['pnl_amount'],
                    'trail_reason': r.get('trail_reason', 'Lock in profits')
                }
                
                html_content = create_email_html('TRAIL_SL', data, ist_now)
                subject = f"📈 TRAIL SL: {r['ticker']} - Move SL to ₹{r['trail_stop']:.2f}"
                
                if send_email_alert(subject, html_content,
                                   email_settings['sender'],
                                   email_settings['password'],
                                   email_settings['recipient']):
                    mark_email_sent(email_key, r['ticker'], 'TRAIL_SL')
                    emails_sent.append({'type': 'TRAIL_SL', 'ticker': r['ticker']})
        
        # 5. TARGET/LEVEL CHANGES (Significant changes only)
        if email_settings['target_change']:
            # Check if dynamic targets are significantly different from original
            target_diff = abs(r['dynamic_target1'] - r['target1']) / r['target1'] * 100
            
            if target_diff > 3:  # More than 3% difference
                email_key = generate_email_key(r['ticker'], 'TARGET_CHANGE', f"{int(r['dynamic_target1'])}")
                
                if can_send_email(email_key, email_settings['cooldown'] * 2):  # Longer cooldown for this
                    data = {
                        'ticker': r['ticker'],
                        'position_type': r['position_type'],
                        'current_price': r['current_price'],
                        'new_target1': r['dynamic_target1'],
                        'new_target2': r['dynamic_target2'],
                        'support': r['support'],
                        'resistance': r['resistance'],
                        'atr': r['atr']
                    }
                    
                    html_content = create_email_html('TARGET_CHANGE', data, ist_now)
                    subject = f"🔄 LEVELS UPDATE: {r['ticker']} - New targets calculated"
                    
                    if send_email_alert(subject, html_content,
                                       email_settings['sender'],
                                       email_settings['password'],
                                       email_settings['recipient']):
                        mark_email_sent(email_key, r['ticker'], 'TARGET_CHANGE')
                        emails_sent.append({'type': 'TARGET_CHANGE', 'ticker': r['ticker']})
    
    return emails_sent

def send_daily_summary(results, email_settings, ist_now):
    """Send daily portfolio summary"""
    
    if not email_settings['enabled'] or not email_settings['daily_summary']:
        return False
    
    # Check if already sent today
    today = ist_now.date()
    if st.session_state.last_email_summary_date == today:
        return False
    
    # Only send after market close
    if ist_now.hour < 16:  # Before 4 PM
        return False
    
    # Prepare summary data
    positions_data = []
    for r in results:
        positions_data.append({
            'ticker': r['ticker'],
            'position_type': r['position_type'],
            'current_price': r['current_price'],
            'pnl_percent': r['pnl_percent'],
            'sl_risk': r['sl_risk'],
            'status': r['overall_status'],
            'action': r['overall_action'].replace('_', ' ')
        })
    
    data = {
        'positions': positions_data,
        'total_pnl': sum(r['pnl_amount'] for r in results),
        'total_positions': len(results),
        'critical_count': sum(1 for r in results if r['overall_status'] == 'CRITICAL'),
        'warning_count': sum(1 for r in results if r['overall_status'] == 'WARNING'),
        'success_count': sum(1 for r in results if r['overall_status'] in ['SUCCESS', 'OPPORTUNITY'])
    }
    
    html_content = create_email_html('DAILY_SUMMARY', data, ist_now)
    subject = f"📊 Daily Summary: P&L ₹{data['total_pnl']:+,.0f} | {data['total_positions']} Positions"
    
    if send_email_alert(subject, html_content,
                       email_settings['sender'],
                       email_settings['password'],
                       email_settings['recipient']):
        st.session_state.last_email_summary_date = today
        return True
    
    return False

# ============================================================================
# TECHNICAL ANALYSIS FUNCTIONS (Same as before)
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
# VOLUME ANALYSIS
# ============================================================================

def analyze_volume(df):
    """Analyze volume to confirm price movements"""
    if 'Volume' not in df.columns or df['Volume'].iloc[-1] == 0:
        return "NEUTRAL", 1.0, "Volume data not available", "NEUTRAL"
    
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    
    vol_5d = df['Volume'].tail(5).mean()
    vol_20d = df['Volume'].tail(20).mean()
    volume_trend = "INCREASING" if vol_5d > vol_20d else "DECREASING"
    
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
# SUPPORT/RESISTANCE DETECTION
# ============================================================================

def find_support_resistance(df, lookback=60):
    """Find key support and resistance levels"""
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
    
    pivot_highs = []
    pivot_lows = []
    
    for i in range(2, len(high) - 2):
        if (high.iloc[i] > high.iloc[i-1] and high.iloc[i] > high.iloc[i-2] and 
            high.iloc[i] > high.iloc[i+1] and high.iloc[i] > high.iloc[i+2]):
            pivot_highs.append(float(high.iloc[i]))
        
        if (low.iloc[i] < low.iloc[i-1] and low.iloc[i] < low.iloc[i-2] and 
            low.iloc[i] < low.iloc[i+1] and low.iloc[i] < low.iloc[i+2]):
            pivot_lows.append(float(low.iloc[i]))
    
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
    
    supports_below = [s for s in support_levels if s < current_price]
    nearest_support = max(supports_below) if supports_below else current_price * 0.95
    
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
# MULTI-TIMEFRAME ANALYSIS
# ============================================================================

def multi_timeframe_analysis(ticker, position_type):
    """Analyze multiple timeframes for trend confirmation"""
    symbol = ticker if '.NS' in str(ticker) else f"{ticker}.NS"
    
    try:
        stock = yf.Ticker(symbol)
        
        timeframes = {}
        
        try:
            daily_df = stock.history(period="3mo", interval="1d")
            if len(daily_df) >= 20:
                timeframes['Daily'] = daily_df
        except:
            pass
        
        try:
            weekly_df = stock.history(period="1y", interval="1wk")
            if len(weekly_df) >= 10:
                timeframes['Weekly'] = weekly_df
        except:
            pass
        
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
                
                rsi = calculate_rsi(close).iloc[-1]
                sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
                ema_9 = close.ewm(span=9).mean().iloc[-1]
                
                macd, signal_line, histogram = calculate_macd(close)
                macd_hist = histogram.iloc[-1] if len(histogram) > 0 else 0
                
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
        
        if position_type == "LONG":
            aligned = sum(1 for s in signals.values() if s == "BULLISH")
            against = sum(1 for s in signals.values() if s == "BEARISH")
        else:
            aligned = sum(1 for s in signals.values() if s == "BEARISH")
            against = sum(1 for s in signals.values() if s == "BULLISH")
        
        total = len(signals)
        if total > 0:
            alignment_score = int((aligned / total) * 100)
        else:
            alignment_score = 50
        
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
# MOMENTUM SCORING (0-100)
# ============================================================================

def calculate_momentum_score(df):
    """Calculate comprehensive momentum score (0-100)"""
    close = df['Close']
    score = 50
    components = {}
    
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if rsi > 70:
        rsi_score = -10
    elif rsi > 60:
        rsi_score = 15
    elif rsi > 50:
        rsi_score = 10
    elif rsi > 40:
        rsi_score = -5
    elif rsi > 30:
        rsi_score = -15
    else:
        rsi_score = 10
    
    score += rsi_score
    components['RSI'] = rsi_score
    
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    
    if hist_current > 0:
        if hist_current > hist_prev:
            macd_score = 20
        else:
            macd_score = 10
    else:
        if hist_current < hist_prev:
            macd_score = -20
        else:
            macd_score = -10
    
    score += macd_score
    components['MACD'] = macd_score
    
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
    
    returns_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
    
    momentum_score = min(15, max(-15, returns_5d * 3))
    score += momentum_score
    components['Momentum'] = momentum_score
    
    if sma_50 != 0:
        adx_approx = abs(sma_20 - sma_50) / sma_50 * 100
    else:
        adx_approx = 0
    
    if current_price > sma_20:
        trend_score = min(10, adx_approx * 2)
    else:
        trend_score = -min(10, adx_approx * 2)
    
    score += trend_score
    components['Trend'] = trend_score
    
    final_score = max(0, min(100, score))
    
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
# STOP LOSS RISK PREDICTION (0-100)
# ============================================================================

def predict_sl_risk(df, current_price, stop_loss, position_type, entry_price, sl_alert_threshold=50):
    """Predict likelihood of hitting stop loss"""
    risk_score = 0
    reasons = []
    close = df['Close']
    
    if position_type == "LONG":
        distance_pct = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_pct = ((stop_loss - current_price) / current_price) * 100
    
    if distance_pct < 0:
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
    else:
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
    
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if position_type == "LONG" and rsi < 35:
        risk_score += 10
        reasons.append(f"📉 RSI weak ({rsi:.0f})")
    elif position_type == "SHORT" and rsi > 65:
        risk_score += 10
        reasons.append(f"📈 RSI strong ({rsi:.0f})")
    
    if len(close) >= 4:
        last_3 = close.tail(4).diff().dropna()
        if position_type == "LONG" and all(last_3 < 0):
            risk_score += 10
            reasons.append("🕯️ 3 consecutive red candles")
        elif position_type == "SHORT" and all(last_3 > 0):
            risk_score += 10
            reasons.append("🕯️ 3 consecutive green candles")
    
    volume_signal, volume_ratio, _, _ = analyze_volume(df)
    
    if position_type == "LONG" and volume_signal in ["STRONG_SELLING", "SELLING"]:
        risk_score += 10
        reasons.append(f"📊 Selling volume ({volume_ratio:.1f}x)")
    elif position_type == "SHORT" and volume_signal in ["STRONG_BUYING", "BUYING"]:
        risk_score += 10
        reasons.append(f"📊 Buying volume ({volume_ratio:.1f}x)")
    
    risk_score = min(100, risk_score)
    
    if risk_score >= 80:
        recommendation = "🚨 EXIT NOW - Very high risk"
        priority = "CRITICAL"
    elif risk_score >= sl_alert_threshold + 20:
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
# UPSIDE POTENTIAL PREDICTION
# ============================================================================

def predict_upside_potential(df, current_price, target1, target2, position_type):
    """Predict if stock can continue after hitting target"""
    score = 50
    reasons = []
    close = df['Close']
    
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
    else:
        if momentum_score <= 30:
            score += 25
            reasons.append(f"🚀 Strong bearish momentum ({momentum_score:.0f})")
        elif momentum_score <= 45:
            score += 15
            reasons.append(f"📉 Good bearish momentum ({momentum_score:.0f})")
        elif momentum_score >= 60:
            score -= 20
            reasons.append(f"📈 Bullish reversal ({momentum_score:.0f})")
    
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
    
    atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
    if pd.isna(atr):
        atr = current_price * 0.02
    
    sr_levels = find_support_resistance(df)
    
    if position_type == "LONG":
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
    
    score = max(0, min(100, score))
    
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
# DYNAMIC TARGET & TRAIL STOP CALCULATION
# ============================================================================

def calculate_dynamic_levels(df, entry_price, current_price, stop_loss, position_type, pnl_percent, trail_trigger=3.0):
    """Calculate dynamic targets and trailing stop loss"""
    close = df['Close']
    atr = calculate_atr(df['High'], df['Low'], close).iloc[-1]
    
    if pd.isna(atr):
        atr = current_price * 0.02
    
    sr_levels = find_support_resistance(df)
    
    result = {
        'atr': atr,
        'support': sr_levels['nearest_support'],
        'resistance': sr_levels['nearest_resistance']
    }
    
    if position_type == "LONG":
        result['target1'] = current_price + (atr * 1.5)
        result['target2'] = current_price + (atr * 3)
        result['target3'] = min(current_price + (atr * 5), sr_levels['nearest_resistance'])
        
        if pnl_percent >= trail_trigger * 3:
            result['trail_stop'] = max(entry_price * 1.05, current_price - atr)
            result['trail_reason'] = f"Locking 5% profit (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger * 2:
            result['trail_stop'] = max(entry_price * 1.02, current_price - (atr * 1.5))
            result['trail_reason'] = f"Locking 2% profit (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger:
            result['trail_stop'] = max(entry_price, current_price - (atr * 2))
            result['trail_reason'] = f"Moving to breakeven (P&L: {pnl_percent:.1f}%)"
        elif pnl_percent >= trail_trigger * 0.5:
            result['trail_stop'] = max(stop_loss, current_price - (atr * 2.5))
            result['trail_reason'] = f"Tightening SL (P&L: {pnl_percent:.1f}%)"
        else:
            result['trail_stop'] = stop_loss
            result['trail_reason'] = "Keep original SL"
        
        result['should_trail'] = result['trail_stop'] > stop_loss
        
    else:
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
# COMPLETE SMART ANALYSIS
# ============================================================================

@st.cache_data(ttl=15)
def smart_analyze_position(ticker, position_type, entry_price, quantity, stop_loss, 
                          target1, target2, trail_threshold=2.0, sl_alert_threshold=50,
                          enable_mtf=True):
    """Complete smart analysis with all features"""
    symbol = ticker if '.NS' in str(ticker) else f"{ticker}.NS"
    
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
    
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
    else:
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
    
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    if pd.isna(rsi):
        rsi = 50.0
    
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1]) if len(histogram) > 0 else 0
    if pd.isna(macd_hist):
        macd_hist = 0
    macd_signal = "BULLISH" if macd_hist > 0 else "BEARISH"
    
    momentum_score, momentum_trend, momentum_components = calculate_momentum_score(df)
    
    volume_signal, volume_ratio, volume_desc, volume_trend = analyze_volume(df)
    
    sr_levels = find_support_resistance(df)
    
    sl_risk, sl_reasons, sl_recommendation, sl_priority = predict_sl_risk(
        df, current_price, stop_loss, position_type, entry_price, sl_alert_threshold
    )
    
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
    
    if position_type == "LONG":
        target1_hit = current_price >= target1
        target2_hit = current_price >= target2
        sl_hit = current_price <= stop_loss
    else:
        target1_hit = current_price <= target1
        target2_hit = current_price <= target2
        sl_hit = current_price >= stop_loss
    
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
    
    dynamic_levels = calculate_dynamic_levels(
        df, entry_price, current_price, stop_loss, position_type, pnl_percent, trail_threshold
    )
    
    alerts = []
    
    if sl_hit:
        alerts.append({
            'priority': 'CRITICAL',
            'type': '🚨 STOP LOSS HIT',
            'message': f'Price ₹{current_price:.2f} breached SL ₹{stop_loss:.2f}',
            'action': 'EXIT IMMEDIATELY'
        })
        overall_status = 'CRITICAL'
        overall_action = 'EXIT'
    
    elif sl_risk >= sl_alert_threshold + 20:
        alerts.append({
            'priority': 'CRITICAL',
            'type': '⚠️ HIGH SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation
        })
        overall_status = 'CRITICAL'
        overall_action = 'EXIT_EARLY'
    
    elif sl_risk >= sl_alert_threshold:
        alerts.append({
            'priority': 'HIGH',
            'type': '⚠️ MODERATE SL RISK',
            'message': f'Risk Score: {sl_risk}% - {", ".join(sl_reasons[:2])}',
            'action': sl_recommendation
        })
        overall_status = 'WARNING'
        overall_action = 'WATCH'
    
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
    
    elif dynamic_levels['should_trail'] and pnl_percent >= trail_threshold:
        alerts.append({
            'priority': 'MEDIUM',
            'type': '📈 TRAIL STOP LOSS',
            'message': f'{dynamic_levels.get("trail_reason", "Lock profits!")} Move SL from ₹{stop_loss:.2f} to ₹{dynamic_levels["trail_stop"]:.2f}',
            'action': f'New SL: ₹{dynamic_levels["trail_stop"]:.2f}'
        })
        overall_status = 'GOOD'
        overall_action = 'TRAIL_SL'
    
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
        'ticker': ticker,
        'position_type': position_type,
        'entry_price': entry_price,
        'current_price': current_price,
        'quantity': quantity,
        'pnl_percent': pnl_percent,
        'pnl_amount': pnl_amount,
        
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        
        'rsi': rsi,
        'macd_hist': macd_hist,
        'macd_signal': macd_signal,
        
        'momentum_score': momentum_score,
        'momentum_trend': momentum_trend,
        'momentum_components': momentum_components,
        
        'volume_signal': volume_signal,
        'volume_ratio': volume_ratio,
        'volume_desc': volume_desc,
        'volume_trend': volume_trend,
        
        'support': sr_levels['nearest_support'],
        'resistance': sr_levels['nearest_resistance'],
        'distance_to_support': sr_levels['distance_to_support'],
        'distance_to_resistance': sr_levels['distance_to_resistance'],
        
        'sl_risk': sl_risk,
        'sl_reasons': sl_reasons,
        'sl_recommendation': sl_recommendation,
        'sl_priority': sl_priority,
        
        'upside_score': upside_score,
        'upside_reasons': upside_reasons,
        'new_target': new_target,
        
        'trail_stop': dynamic_levels['trail_stop'],
        'should_trail': dynamic_levels['should_trail'],
        'trail_reason': dynamic_levels.get('trail_reason', ''),
        'dynamic_target1': dynamic_levels['target1'],
        'dynamic_target2': dynamic_levels['target2'],
        'atr': dynamic_levels['atr'],
        
        'target1_hit': target1_hit,
        'target2_hit': target2_hit,
        'sl_hit': sl_hit,
        
        'mtf_signals': mtf_result['signals'],
        'mtf_details': mtf_result.get('details', {}),
        'mtf_alignment': mtf_result['alignment_score'],
        'mtf_recommendation': mtf_result['recommendation'],
        
        'alerts': alerts,
        'overall_status': overall_status,
        'overall_action': overall_action,
        
        'df': df
    }

# ============================================================================
# LOAD PORTFOLIO
# ============================================================================

def load_portfolio():
    """Load portfolio from Google Sheets"""
    GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/155htPsyom2e-dR5BZJx_cFzGxjQQjePJt3H2sRLSr6w/edit?usp=sharing"
    
    try:
        sheet_id = GOOGLE_SHEETS_URL.split('/d/')[1].split('/')[0]
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
        
        df = pd.read_csv(export_url)
        
        if 'Status' in df.columns:
            df = df[df['Status'].str.upper() == 'ACTIVE']
        
        df.columns = df.columns.str.strip()
        
        st.success(f"✅ Loaded {len(df)} active positions from Google Sheets")
        return df
        
    except Exception as e:
        st.error(f"❌ Error loading from Google Sheets: {e}")
        st.info("💡 Make sure the Google Sheet is set to 'Anyone with the link can view'")
        
        st.warning("⚠️ Using sample data as fallback")
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
    st.markdown('<h1 class="main-header">🧠 Smart Portfolio Monitor v5.2</h1>', unsafe_allow_html=True)
    
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
            st.metric("Refresh Interval", f"{refresh_interval}s")
        with col4:
            st.metric("MTF Analysis", "✅ On" if enable_multi_timeframe else "❌ Off")
        with col5:
            st.metric("Email Alerts", "✅ On" if email_enabled else "❌ Off")
    
    st.divider()
    
    # Load Portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.warning("⚠️ No positions found! Add positions to my_portfolio.xlsx")
        
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
            trail_sl_trigger,
            sl_risk_threshold,
            enable_multi_timeframe
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
    
    # ============================================================================
    # PROCESS EMAIL ALERTS
    # ============================================================================
    
    email_settings = {
        'enabled': email_enabled,
        'sender': sender_email,
        'password': sender_password,
        'recipient': recipient_email,
        'critical': email_critical if email_enabled else False,
        'target': email_target if email_enabled else False,
        'approaching_sl': email_approaching_sl if email_enabled else False,
        'trail_sl': email_trail_sl if email_enabled else False,
        'target_change': email_target_change if email_enabled else False,
        'daily_summary': email_daily_summary if email_enabled else False,
        'cooldown': email_cooldown if email_enabled else 15,
        'sl_threshold': sl_risk_threshold,
        'approaching_threshold': approaching_sl_threshold if email_enabled else 2.0
    }
    
    # Process and send email alerts
    if email_enabled:
        emails_sent = process_email_alerts(results, email_settings, ist_now)
        
        if emails_sent:
            email_summary 
