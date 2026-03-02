import requests
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime

# ==========================================
# KONFIGURASI & CREDENTIALS
# ==========================================
TELEGRAM_BOT_TOKEN = "8663293715:AAEO-Hd4Sg6h5oyV1n2oOUy52ILit1cahg4"
TELEGRAM_CHAT_ID = "7465370442"
GEMINI_API_KEY = "GANTI_DENGAN_API_KEY_GEMINI_ANDA"

KUCOIN_API = "https://api.kucoin.com/api/v1/market/candles"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json'
}

SYMBOL_MAPPING = {
    "BTCUSD": "BTC-USDT",
    "ETHUSD": "ETH-USDT",
    "BTCUSDT": "BTC-USDT",
    "ETHUSDT": "ETH-USDT"
}

# AI Settings
AI_TEST_MODE = True
AI_TEST_TIMEOUT = 30

# Load AI Library
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Warning: google-generativeai not installed.")

# ==========================================
# FUNGSI UTILTAS (HELPER)
# ==========================================

def parse_symbol_kucoin(symbol):
    """Convert MT5 symbol to KuCoin format"""
    return SYMBOL_MAPPING.get(symbol, f"{symbol[:3]}-USDT")

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_atr(df, period=14):
    df['tr'] = df['high'] - df['low']
    return df['tr'].iloc[-period:].mean()

# ==========================================
# CORE FUNCTIONS
# ==========================================

def get_crypto_data(symbol, interval='5min', limit=50):
    kucoin_symbol = parse_symbol_kucoin(symbol)
    end_time = int(time.time())
    start_time = end_time - (limit * 5 * 60)
    
    params = {
        'symbol': kucoin_symbol,
        'type': interval,
        'startAt': start_time,
        'endAt': end_time
    }
    
    for attempt in range(3):
        try:
            print(f"  📡 Requesting {kucoin_symbol} (Attempt {attempt + 1})...")
            response = requests.get(KUCOIN_API, params=params, headers=HEADERS, timeout=15)
            
            if response.status_code != 200:
                time.sleep(2 ** attempt)
                continue
            
            data = response.json()
            if data.get('code') != '200000': return None
            
            candles = data.get('data', [])
            if not candles: return None
            
            df = pd.DataFrame(candles, columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            
            df = df.sort_values('time').reset_index(drop=True)
            return df.dropna(subset=['close'])
            
        except Exception as e:
            print(f"  ❌ Fetch Error: {e}")
    return None

def test_gemini_ai():
    if not GEMINI_AVAILABLE or GEMINI_API_KEY == "GANTI_DENGAN_API_KEY_GEMINI_ANDA":
        return False, 0, "❌ API Key or Library missing"
    
    start_time = time.time()
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = "Respond ONLY with this JSON: {\"status\": \"ok\"}"
        response = model.generate_content(prompt, timeout=AI_TEST_TIMEOUT)
        
        res_time = round(time.time() - start_time, 2)
        return True, res_time, "✅ AI Connected"
    except Exception as e:
        return False, round(time.time() - start_time, 2), f"❌ AI Error: {str(e)[:50]}"

def analyze_with_gemini(symbol, current_price, ema_data, signal, levels, atr, df):
    if not GEMINI_AVAILABLE or "GANTI" in GEMINI_API_KEY:
        return None
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        recent_candles = df.iloc[-5:].to_dict('records')
        
        prompt = f"""
        Analyze {symbol} (M5). Current: ${current_price}. 
        EMA8: {ema_data['ema8']}, EMA14: {ema_data['ema14']}, Signal: {signal}.
        Support: {levels['sup']}, Resistance: {levels['res']}, ATR: {atr}.
        Last Candles: {recent_candles}
        
        Return JSON ONLY:
        {{
            "signal_valid": bool, "confidence": 0-100, "action": "BUY/SELL/WAIT",
            "entry_price": num, "stop_loss": num, "take_profit_1": num,
            "take_profit_2": num, "risk_reward_ratio": num, "reasoning": "str", "warnings": []
        }}
        """
        
        start_t = time.time()
        response = model.generate_content(prompt, timeout=AI_TEST_TIMEOUT)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        
        ai_data = json.loads(clean_text)
        ai_data['response_time'] = round(time.time() - start_t, 2)
        return ai_data
    except Exception as e:
        print(f"  ❌ AI Analysis Error: {e}")
        return None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

# ==========================================
# MAIN LOGIC
# ==========================================

def analyze_market(symbol):
    print(f"🔄 Analyzing {symbol}...")
    df = get_crypto_data(symbol)
    
    if df is None or df.empty:
        send_telegram(f"❌ *Error data {symbol}*")
        return

    # Technicals
    df['ema_8'] = calculate_ema(df['close'], 8)
    df['ema_14'] = calculate_ema(df['close'], 14)
    atr = calculate_atr(df)
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Signal Logic
    signal = "MONITORING"
    if prev['ema_8'] <= prev['ema_14'] and last['ema_8'] > last['ema_14']:
        signal = "🟢 GOLDEN CROSS (BUY)"
    elif prev['ema_8'] >= prev['ema_14'] and last['ema_8'] < last['ema_14']:
        signal = "🔴 DEATH CROSS (SELL)"

    # AI Analysis
    ai_res = analyze_with_gemini(
        symbol, last['close'], 
        {'ema8': last['ema_8'], 'ema14': last['ema_14']},
        signal, 
        {'sup': df['low'].iloc[-20:].min(), 'res': df['high'].iloc[-20:].max()},
        atr, df
    )

    # Message Construction
    if ai_res:
        conf = ai_res.get('confidence', 0)
        badge = "✅ VALID" if conf >= 70 else "⚠️ WEAK"
        msg = f"""
🎯 *AI SIGNAL: {symbol}*
━━━━━━━━━━━━━━━━━━━━━━
💰 Price: `${last['close']:,.2f}`
📊 Signal: `{signal}`
🤖 Status: *{badge} ({conf}%)*
📌 Action: *{ai_res.get('action')}*

📍 Entry: `{ai_res.get('entry_price')}`
🛑 SL: `{ai_res.get('stop_loss')}`
✅ TP: `{ai_res.get('take_profit_1')}`
📈 RR: `1:{ai_res.get('risk_reward_ratio')}`

🧠 *Reason:* _{ai_res.get('reasoning')}_
━━━━━━━━━━━━━━━━━━━━━━
"""
    else:
        msg = f"👀 *UPDATE {symbol}*\nPrice: `${last['close']:,.2f}`\nSignal: {signal}\n(AI Offline)"

    send_telegram(msg)

def main():
    print("🚀 Bot Started...")
    
    if AI_TEST_MODE:
        success, duration, note = test_gemini_ai()
        send_telegram(f"🧪 *SYSTEM TEST*\nAI: {note}\nLatency: `{duration}s`")
    
    for coin in ["BTCUSD", "ETHUSD"]:
        analyze_market(coin)
    
    print("✅ Session Finished.")

if __name__ == "__main__":
    main()
