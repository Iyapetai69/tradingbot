import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# KONFIGURASI
# ==========================================
# Disarankan menggunakan Environment Variables untuk keamanan
TELEGRAM_BOT_TOKEN = "8663293715:AAEO-Hd4Sg6h5oyV1n2oOUy52ILit1cahg4"
TELEGRAM_CHAT_ID = "7465370442"
GEMINI_API_KEY = ""  # Reserved for Phase 2

CRYPTOCOMPARE_API = "https://min-api.cryptocompare.com/data/v2/histominute"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# ==========================================
# FUNGSI UTILITAS DATA
# ==========================================

def parse_symbol(symbol):
    """Memisahkan pair symbol secara dinamis."""
    if symbol.endswith('USDT'):
        return symbol.replace('USDT', ''), 'USDT'
    if symbol.endswith('USD'):
        return symbol.replace('USD', ''), 'USD'
    return symbol[:3], symbol[3:]

def get_crypto_data(symbol, limit=50):
    """Mengambil dan membersihkan data OHLCV dari CryptoCompare."""
    fsym, tsym = parse_symbol(symbol)
    params = {
        'fsym': fsym,
        'tsym': tsym,
        'limit': limit,
        'aggregate': 1
    }
    
    for attempt in range(3):
        try:
            print(f"  📡 Request {symbol} (percobaan {attempt + 1})...")
            resp = requests.get(CRYPTOCOMPARE_API, params=params, headers=HEADERS, timeout=15)
            
            if resp.status_code != 200:
                time.sleep(2 ** attempt)
                continue
            
            data = resp.json()
            if data.get('Response') == 'Error' or 'Data' not in data:
                print(f"  ❌ API Error: {data.get('Message')}")
                return None
            
            # Extract & Convert to DataFrame
            candles = data['Data']['Data']
            df = pd.DataFrame(candles)
            
            # Formatting Columns
            df = df.rename(columns={'volumefrom': 'volume'})
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            
            df = df.dropna(subset=['close'])
            print(f"  ✅ Berhasil memuat {len(df)} baris data.")
            return df
            
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            time.sleep(2 ** attempt)
            
    return None

# ==========================================
# FUNGSI TEKNIKAL & SINYAL
# ==========================================

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def check_ema_cross(df):
    """Logika Golden Cross & Death Cross."""
    df['ema_8'] = calculate_ema(df['close'], 8)
    df['ema_14'] = calculate_ema(df['close'], 14)
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Deteksi Cross
    if prev['ema_8'] <= prev['ema_14'] and curr['ema_8'] > curr['ema_14']:
        return "POTENSI BUY (Golden Cross)", "🟢", curr
    elif prev['ema_8'] >= prev['ema_14'] and curr['ema_8'] < curr['ema_14']:
        return "POTENSI SELL (Death Cross)", "🔴", curr
    
    return "MONITORING", "👀", curr

# ==========================================
# NOTIFIKASI
# ==========================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Gagal kirim Telegram: {e}")

# ==========================================
# ALUR UTAMA
# ==========================================

def analyze_market(symbol):
    print(f"🔄 Menganalisis {symbol}...")
    df = get_crypto_data(symbol)
    
    if df is None or df.empty:
        send_telegram(f"❌ *ERROR:* Gagal mengambil data `{symbol}`")
        return

    signal_text, emoji, data = check_ema_cross(df)
    
    message = (
        f"{emoji} *TRADING UPDATE: {symbol}*\n"
        f"⏰ `{datetime.now().strftime('%H:%M:%S')} UTC`\n\n"
        f"💰 Harga: `${data['close']:,.2f}`\n"
        f"📈 EMA 8: `{data['ema_8']:,.2f}`\n"
        f"📉 EMA 14: `{data['ema_14']:,.2f}`\n\n"
        f"🚨 *Status:* {signal_text}\n\n"
        f"--- _Phase 1 Active_"
    )
    
    send_telegram(message)
    print(f"  📣 Sinyal {symbol}: {signal_text}")

def main():
    print("🚀 Bot Trading Dimulai...")
    assets = ["BTCUSDT", "ETHUSDT"]
    
    for asset in assets:
        analyze_market(asset)
    
    print("✅ Selesai.")

if __name__ == "__main__":
    main()
