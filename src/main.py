import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ==========================================
# KONFIGURASI
# ==========================================
TELEGRAM_BOT_TOKEN = "8663293715:AAEO-Hd4Sg6h5oyV1n2oOUy52ILit1cahg4"
TELEGRAM_CHAT_ID = "7465370442"
GEMINI_API_KEY = ""  # Untuk Fase 2

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

# ==========================================
# FUNGSI UTILITY & API
# ==========================================

def parse_symbol_kucoin(symbol):
    """Konversi symbol MT5 ke format KuCoin USDT."""
    return SYMBOL_MAPPING.get(symbol, f"{symbol[:3]}-USDT")

def get_crypto_data(symbol, interval='5min', limit=50):
    """Mengambil data OHLCV dari KuCoin API dengan sistem retry."""
    kucoin_symbol = parse_symbol_kucoin(symbol)
    
    # Perbaikan Logika Waktu
    end_time = int(time.time())
    start_time = end_time - (limit * 5 * 60) 
    
    params = {
        'symbol': kucoin_symbol,
        'type': interval,
        'startAt': start_time,
        'endAt': end_time
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"  📡 Request {kucoin_symbol} (Attempt {attempt + 1})...")
            response = requests.get(KUCOIN_API, params=params, headers=HEADERS, timeout=15)
            
            if response.status_code != 200:
                print(f"  ❌ HTTP {response.status_code}: {response.text[:100]}")
                time.sleep(2 ** attempt)
                continue
            
            data = response.json()
            if data.get('code') != '200000':
                print(f"  ❌ KuCoin Error: {data.get('msg')}")
                return None
            
            candles = data.get('data', [])
            if not candles:
                return None
            
            # [0:time, 1:open, 2:close, 3:high, 4:low, 5:volume, 6:turnover]
            df = pd.DataFrame(candles, columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            
            # Konversi tipe data
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
            
            # Sort ascending & clean
            df = df.sort_values('time').reset_index(drop=True)
            df = df.dropna(subset=['close'])
            
            print(f"  ✅ Received {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            print(f"  ❌ Error: {type(e).__name__} - {e}")
            time.sleep(2 ** attempt)
            
    return None

def send_telegram(message):
    """Kirim notifikasi ke Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get('ok')
    except Exception as e:
        print(f"  ❌ Telegram Fail: {e}")
        return False

# ==========================================
# LOGIKA ANALISIS
# ==========================================

def calculate_indicators(df):
    """Menghitung semua indikator teknikal yang diperlukan."""
    df['ema_8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema_14'] = df['close'].ewm(span=14, adjust=False).mean()
    
    # ATR (Volatility)
    df['tr'] = df['high'] - df['low']
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # Support & Resistance (20 periods)
    df['support'] = df['low'].rolling(window=20).min()
    df['resistance'] = df['high'].rolling(window=20).max()
    
    return df

def analyze_market(symbol):
    """Alur utama analisis per koin."""
    print(f"\n🔄 Analyzing {symbol}...")
    df = get_crypto_data(symbol)
    
    if df is None or len(df) < 20:
        send_telegram(f"⚠️ *Data Error:* Gagal memproses {symbol}")
        return

    df = calculate_indicators(df)
    
    # Ambil baris data terbaru
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Logika Crossover EMA
    signal = "MONITORING"
    if prev['ema_8'] <= prev['ema_14'] and curr['ema_8'] > curr['ema_14']:
        signal = "🟢 *POTENSI BUY* (Golden Cross)"
    elif prev['ema_8'] >= prev['ema_14'] and curr['ema_8'] < curr['ema_14']:
        signal = "🔴 *POTENSI SELL* (Death Cross)"

    # Susun Pesan
    msg = (
        f"🤖 *MT5 SIGNAL: {symbol}*\n"
        f"⏰ `{datetime.now().strftime('%H:%M:%S')} UTC` (M5)\n\n"
        f"💰 Price: `${curr['close']:,.2f}`\n"
        f"📈 EMA 8/14: `{curr['ema_8']:,.2f}` / `{curr['ema_14']:,.2f}`\n\n"
        f"🎯 *Key Levels:*\n"
        f"🔹 Support: `${curr['support']:,.2f}`\n"
        f"🔹 Resist: `${curr['resistance']:,.2f}`\n"
        f"🔹 ATR: `${curr['atr']:,.2f}`\n\n"
        f"🚨 *Status:* {signal}\n\n"
        f"--- Phase 1 Active ---"
    )
    
    send_telegram(msg)

def main():
    print("🚀 Bot Started...")
    assets = ["BTCUSD", "ETHUSD"]
    for asset in assets:
        analyze_market(asset)
    print("\n✅ All tasks finished.")

if __name__ == "__main__":
    main()
    
