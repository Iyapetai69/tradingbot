import os
import time
import json
import requests
import pandas as pd
import numpy as np
import google.generativeai as genai
from datetime import datetime

# ==========================================
# KONFIGURASI
# ==========================================
TELEGRAM_BOT_TOKEN = "8663293715:AAEO-Hd4Sg6h5oyV1n2oOUy52ILit1cahg4"
TELEGRAM_CHAT_ID = "7465370442"
GEMINI_API_KEY = "AIzaSyDoCZj4aJGifLHjaV8jC2Y3dljcUEIZ2yc"

KUCOIN_API = "https://api.kucoin.com/api/v1/market/candles"
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json'
}

SYMBOL_MAPPING = {
    "BTCUSD": "BTC-USDT",
    "ETHUSD": "ETH-USDT",
    "BTCUSDT": "BTC-USDT",
    "ETHUSDT": "ETH-USDT"
}

# ==========================================
# FUNGSI UTILITAS & DATA
# ==========================================

def parse_symbol_kucoin(symbol):
    """Konversi symbol MT5 ke format KuCoin USDT"""
    return SYMBOL_MAPPING.get(symbol, f"{symbol[:3]}-USDT")

def get_crypto_data(symbol, interval='5min', limit=50):
    """Mengambil dan membersihkan data OHLCV dari KuCoin"""
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
            print(f"  📡 Fetching {kucoin_symbol} (Attempt {attempt + 1})...")
            resp = requests.get(KUCOIN_API, params=params, headers=HEADERS, timeout=15)
            
            if resp.status_code != 200:
                time.sleep(2 ** attempt)
                continue
                
            data = resp.json()
            if data.get('code') != '200000' or not data.get('data'):
                return None
            
            # Load ke DataFrame
            df = pd.DataFrame(data['data'], columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            
            # Konversi tipe data
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            
            # Urutkan dari candle terlama ke terbaru
            df = df.sort_values('time').reset_index(drop=True)
            return df.dropna(subset=['close'])
            
        except Exception as e:
            print(f"  ❌ Fetch Error: {e}")
            time.sleep(2 ** attempt)
            
    return None

# ==========================================
# INDIKATOR TEKNIKAL
# ==========================================

def calculate_indicators(df):
    """Menghitung semua indikator yang diperlukan dalam satu fungsi"""
    # EMA
    df['ema_8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema_14'] = df['close'].ewm(span=14, adjust=False).mean()
    
    # ATR
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                     abs(df['low'] - df['close'].shift(1))))
    atr = df['tr'].rolling(window=14).mean().iloc[-1]
    
    return df, atr

# ==========================================
# ANALISIS AI (GEMINI)
# ==========================================

def analyze_with_gemini(symbol, current_price, indicators, df):
    """Analisis mendalam menggunakan Gemini AI"""
    if not GEMINI_API_KEY or "GANTI" in GEMINI_API_KEY:
        return None
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Persiapan Data
        recent_candles = df.tail(5).to_dict('records')
        prompt = f"""
        Analyze {symbol} (5m timeframe). 
        Price: {current_price}, EMA8: {indicators['ema_8']:.2f}, EMA14: {indicators['ema_14']:.2f}, ATR: {indicators['atr']:.2f}.
        Support: {indicators['support']:.2f}, Resistance: {indicators['res']:.2f}.
        Last Candles: {recent_candles}

        Provide JSON only:
        {{
            "signal_valid": bool, "confidence": 0-100, "action": "BUY/SELL/WAIT",
            "entry_price": float, "stop_loss": float, "take_profit_1": float, 
            "take_profit_2": float, "risk_reward_ratio": float, "reasoning": "str", "warnings": []
        }}
        """
        
        response = model.generate_content(prompt)
        # Clean JSON String
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
        
    except Exception as e:
        print(f"  ❌ AI Error: {e}")
        return None

# ==========================================
# KOMUNIKASI & MAIN LOGIC
# ==========================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def run_analysis(symbol):
    print(f"\n🔍 Menganalisis {symbol}...")
    df = get_crypto_data(symbol)
    
    if df is None or len(df) < 20:
        print(f"  ⚠️ Data tidak cukup untuk {symbol}")
        return

    df, atr = calculate_indicators(df)
    
    # Data Point Terakhir
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Deteksi Cross
    signal_type = "MONITORING"
    if prev['ema_8'] <= prev['ema_14'] and last['ema_8'] > last['ema_14']:
        signal_type = "GOLDEN CROSS (BUY)"
    elif prev['ema_8'] >= prev['ema_14'] and last['ema_8'] < last['ema_14']:
        signal_type = "DEATH CROSS (SELL)"

    # Meta Data untuk AI
    indicator_data = {
        'ema_8': last['ema_8'], 'ema_14': last['ema_14'], 'atr': atr,
        'support': df['low'].tail(20).min(), 'res': df['high'].tail(20).max()
    }

    ai_rec = analyze_with_gemini(symbol, last['close'], indicator_data, df)
    
    # Konstruksi Pesan
    if ai_rec:
        status_emoji = "🎯" if ai_rec['confidence'] >= 70 else "⚡"
        msg = (
            f"{status_emoji} *AI SIGNAL: {symbol}*\n"
            f"💰 Price: `{last['close']:,.2f}`\n"
            f"📊 Action: *{ai_rec['action']}* ({ai_rec['confidence']}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Entry: `{ai_rec['entry_price']}`\n"
            f"🛑 SL: `{ai_rec['stop_loss']}` | ✅ TP: `{ai_rec['take_profit_1']}`\n"
            f"🧠 Reason: _{ai_rec['reasoning']}_"
        )
    else:
        msg = f"👀 *Update {symbol}*\nPrice: `{last['close']}`\nSignal: {signal_type}"

    send_telegram(msg)
    print(f"  ✅ Selesai: {symbol}")

def main():
    print("🚀 Bot started...")
    for coin in ["BTCUSD", "ETHUSD"]:
        run_analysis(coin)

if __name__ == "__main__":
    main()
