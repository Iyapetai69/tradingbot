import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ==========================================
# KONFIGURASI & CONSTANTS
# ==========================================
TELEGRAM_BOT_TOKEN = "8663293715:AAEO-Hd4Sg6h5oyV1n2oOUy52ILit1cahg4"
TELEGRAM_CHAT_ID = "7465370442"
GEMINI_API_KEY = ""  # Untuk Fase 2

API_URL = "https://min-api.cryptocompare.com/data/v2/histominute"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# ==========================================
# FUNGSI UTILITAS
# ==========================================

def parse_symbol(symbol):
    """Parse symbol MT5 ke format CryptoCompare (fsym/tsym)"""
    symbol = symbol.upper()
    if symbol.endswith('USDT'):
        return symbol.replace('USDT', ''), 'USDT'
    elif symbol.endswith('USD'):
        return symbol.replace('USD', ''), 'USD'
    
    # Fallback default
    return symbol[:3], symbol[3:]

def calculate_ema(series, period):
    """Menghitung Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()

def send_telegram(message):
    """Mengirim pesan ke Telegram dengan penanganan error"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        res.raise_for_status()
        print("  ✅ Telegram: Pesan terkirim.")
        return True
    except Exception as e:
        print(f"  ❌ Telegram Error: {e}")
        return False

# ==========================================
# CORE LOGIC
# ==========================================

def fetch_ohlcv(symbol, limit=100):
    """Mengambil data market dari API"""
    fsym, tsym = parse_symbol(symbol)
    params = {
        'fsym': fsym,
        'tsym': tsym,
        'limit': limit,
        'aggregate': 5 # 5-minute intervals (sesuai kebutuhan strategi M5)
    }

    for attempt in range(3):
        try:
            print(f"  📡 Fetching {fsym}/{tsym} (Attempt {attempt+1})...")
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
            data = resp.json()

            if data.get('Response') == 'Error':
                print(f"  ⚠️ API Error: {data.get('Message')}")
                return None

            raw_data = data.get('Data', {}).get('Data', [])
            if not raw_data:
                continue

            df = pd.DataFrame(raw_data)
            df = df.rename(columns={'volumefrom': 'volume'})
            
            # Convert types
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            
            return df.dropna()

        except Exception as e:
            print(f"  ❌ Network Error: {e}")
            time.sleep(2)
    
    return None

def analyze_market(symbol):
    """Logika analisis teknikal dan pengiriman sinyal"""
    print(f"\n🔍 Analisis {symbol} dimulai...")
    df = fetch_ohlcv(symbol)

    if df is None or len(df) < 20:
        send_telegram(f"⚠️ *Data Error:* Gagal mendapatkan data valid untuk {symbol}")
        return

    # Technical Indicators
    df['ema8'] = calculate_ema(df['close'], 8)
    df['ema14'] = calculate_ema(df['close'], 14)
    
    # Get Last 2 Rows
    curr, prev = df.iloc[-1], df.iloc[-2]
    
    # Crossover Logic
    status = "MONITORING"
    if prev['ema8'] <= prev['ema14'] and curr['ema8'] > curr['ema14']:
        status = "🟢 POTENSI BUY (Golden Cross)"
    elif prev['ema8'] >= prev['ema14'] and curr['ema8'] < curr['ema14']:
        status = "🔴 POTENSI SELL (Death Cross)"

    # Support & Resistance (Recent 20 periods)
    s_level = df['low'].tail(20).min()
    r_level = df['high'].tail(20).max()

    # Construct Message
    msg = (
        f"🤖 *MT5 SIGNAL: {symbol}*\n"
        f"⏰ `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC`\n\n"
        f"💰 Price: `${curr['close']:,.2f}`\n"
        f"📈 EMA 8/14: `{curr['ema8']:,.2f}` / `{curr['ema14']:,.2f}`\n"
        f"🛡️ S/R: `${s_level:,.2f}` / `${r_level:,.2f}`\n\n"
        f"🚨 *Status:* {status}\n"
        f"---"
    )
    
    send_telegram(msg)

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    start_time = time.time()
    print("🚀 MT5 Trading Bot Started")
    
    assets = ["BTCUSD", "ETHUSD"]
    for asset in assets:
        analyze_market(asset)
    
    end_time = time.time()
    print(f"\n✅ Selesai dalam {end_time - start_time:.2f} detik.")

if __name__ == "__main__":
    main()
    
