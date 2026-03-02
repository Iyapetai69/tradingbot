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

# Nama model terbaru sesuai permintaan
GEMINI_MODEL_NAME = 'gemini-3-flash-preview'

KUCOIN_API = "https://api.kucoin.com/api/v1/market/candles"
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

SYMBOL_MAPPING = {
    "BTCUSD": "BTC-USDT", "ETHUSD": "ETH-USDT",
    "BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT"
}

AI_TEST_TIMEOUT = 30

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Warning: google-generativeai not installed.")

# ==========================================
# ANALISIS TEKNIKAL
# ==========================================

def get_crypto_data(symbol, interval='5min', limit=50):
    kucoin_symbol = SYMBOL_MAPPING.get(symbol, f"{symbol[:3]}-USDT")
    end_time = int(time.time())
    start_time = end_time - (limit * 5 * 60)
    
    params = {'symbol': kucoin_symbol, 'type': interval, 'startAt': start_time, 'endAt': end_time}
    
    try:
        response = requests.get(KUCOIN_API, params=params, headers=HEADERS, timeout=15)
        data = response.json()
        if data.get('code') == '200000' and data.get('data'):
            df = pd.DataFrame(data['data'], columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            return df.sort_values('time').reset_index(drop=True).dropna()
    except Exception as e:
        print(f"  ❌ Error Data {symbol}: {e}")
    return None

# ==========================================
# AI ENGINE (GEMINI 3 FLASH PREVIEW)
# ==========================================

def analyze_with_gemini(symbol, current_price, indicators, df):
    if not GEMINI_AVAILABLE or "GANTI" in GEMINI_API_KEY:
        return None
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        
        # Ringkasan data untuk efisiensi token
        recent_candles = df.iloc[-10:].to_dict('records')
        
        prompt = f"""
        Role: Professional Crypto Scalper.
        Pair: {symbol} (M5 Timeframe).
        Price: {current_price}
        Technical: EMA8={indicators['ema8']:.2f}, EMA14={indicators['ema14']:.2f}, ATR={indicators['atr']:.2f}
        Signal: {indicators['signal']}
        History: {recent_candles}
        
        Task: 
        Evaluate if the signal is valid. Calculate SL and TP. 
        Return ONLY valid JSON.
        
        JSON Structure:
        {{
            "valid": bool,
            "confidence": 0-100,
            "action": "BUY/SELL/WAIT",
            "entry": number,
            "sl": number,
            "tp": number,
            "rr": number,
            "logic": "brief reasoning"
        }}
        """
        
        start_t = time.time()
        response = model.generate_content(
            prompt, 
            request_options={'timeout': AI_TEST_TIMEOUT}
        )
        
        # Bersihkan response jika AI menyertakan ```json ... ```
        raw_res = response.text.strip()
        if "{" in raw_res:
            raw_res = raw_res[raw_res.find("{"):raw_res.rfind("}")+1]
            
        res_json = json.loads(raw_res)
        res_json['latency'] = round(time.time() - start_t, 2)
        return res_json
    except Exception as e:
        print(f"  ❌ AI Error: {e}")
        return None

# ==========================================
# MAIN LOGIC
# ==========================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def run_bot(symbol):
    print(f"🔄 Menganalisis {symbol}...")
    df = get_crypto_data(symbol)
    if df is None: return

    # Indikator
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema14'] = df['close'].ewm(span=14, adjust=False).mean()
    atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    signal = "Neutral"
    if prev['ema8'] <= prev['ema14'] and last['ema8'] > last['ema14']: signal = "Golden Cross (BUY)"
    elif prev['ema8'] >= prev['ema14'] and last['ema8'] < last['ema14']: signal = "Death Cross (SELL)"

    # AI Analysis
    ai = analyze_with_gemini(symbol, last['close'], {
        'ema8': last['ema8'], 'ema14': last['ema14'], 
        'atr': atr, 'signal': signal
    }, df)

    if ai:
        icon = "🎯" if ai['valid'] else "⏳"
        msg = f"""
{icon} *GEMINI 3 FLASH SIGNAL*
Pair: `{symbol}` | Confidence: `{ai['confidence']}%`
━━━━━━━━━━━━━━━━━━━━━━
🔥 Action: *{ai['action']}*
💰 Price: `{last['close']}`
📊 Signal: `{signal}`

📍 Entry: `{ai['entry']}`
🛑 SL: `{ai['sl']}`
✅ TP: `{ai['tp']}`
📈 R/R: `1:{ai['rr']}`

🧠 *Logic:* _{ai['logic']}_
━━━━━━━━━━━━━━━━━━━━━━
⏱️ Latency: `{ai['latency']}s`
"""
        send_telegram(msg)
        print(f"  ✅ Sent to Telegram.")

def main():
    print(f"🚀 Bot Active with {GEMINI_MODEL_NAME}")
    for coin in ["BTCUSD", "ETHUSD"]:
        run_bot(coin)

if __name__ == "__main__":
    main()
    
