import requests
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# KONFIGURASI STATIS - PRIVATE REPO ONLY
# ==========================================
TELEGRAM_BOT_TOKEN = "8663293715:AAEO-Hd4Sg6h5oyV1n2oOUy52ILit1cahg4"
TELEGRAM_CHAT_ID = "7465370442"
GEMINI_API_KEY = ""  # Isi nanti saat Fase 2

# Endpoint API Binance (Public & Gratis)
BINANCE_API = "https://api.binance.com/api/v3/klines"

def get_crypto_data(symbol, interval='5m', limit=50):
    """Mengambil data OHLCV dari Binance"""
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    try:
        response = requests.get(BINANCE_API, params=params, timeout=10)
        data = response.json()
        
        df = pd.DataFrame(data, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].astype(float)
        
        return df
    except Exception as e:
        print(f"Error mengambil data {symbol}: {e}")
        return None

def calculate_ema(series, period):
    """Menghitung Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()

def send_telegram_message(message):
    """Mengirim pesan ke Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)        result = response.json()
        if result.get('ok'):
            print("✅ Pesan berhasil dikirim ke Telegram.")
        else:
            print(f"❌ Telegram API Error: {result}")
    except Exception as e:
        print(f"❌ Gagal kirim Telegram: {e}")

def analyze_market(symbol):
    print(f"🔄 Menganalisis {symbol}...")
    df = get_crypto_data(symbol)
    
    if df is None or df.empty:
        print(f"⚠️ Data {symbol} kosong atau error")
        return

    # Hitung EMA
    df['ema_8'] = calculate_ema(df['close'], 8)
    df['ema_14'] = calculate_ema(df['close'], 14)
    
    # Ambil 2 candle terakhir untuk cek cross
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    current_price = last_row['close']
    ema_8_now = last_row['ema_8']
    ema_14_now = last_row['ema_14']
    
    ema_8_prev = prev_row['ema_8']
    ema_14_prev = prev_row['ema_14']
    
    # Logika Cross
    signal = "MONITORING"
    signal_emoji = "👀"
    
    # Golden Cross (EMA 8 naik melewati EMA 14)
    if ema_8_prev <= ema_14_prev and ema_8_now > ema_14_now:
        signal = "POTENSI BUY (Golden Cross)"
        signal_emoji = "🟢"
    # Death Cross (EMA 8 turun melewati EMA 14)
    elif ema_8_prev >= ema_14_prev and ema_8_now < ema_14_now:
        signal = "POTENSI SELL (Death Cross)"
        signal_emoji = "🔴"
        
    # Format Pesan untuk Telegram
    message = f"""
{signal_emoji} *BOT TRADING UPDATE: {symbol}*
⏰ Waktu: {datetime.now().strftime('%H:%M:%S')} UTC

📊 *Data Teknikal (Timeframe 5m)*Harga Terakhir: `${current_price:,.2f}`
EMA 8: `{ema_8_now:,.2f}`
EMA 14: `{ema_14_now:,.2f}`

🚨 *Status Signal:* {signal}

_(Fase 1: Test Data & Telegram)_
_(Fase 2: Integrasi AI Gemini untuk SL/TP)_
    """
    
    send_telegram_message(message)

def main():
    print("🚀 Bot Trading Dimulai...")
    coins = ["BTCUSDT", "ETHUSDT"]
    
    for coin in coins:
        analyze_market(coin)
    
    print("✅ Selesai.")

if __name__ == "__main__":
    main()
