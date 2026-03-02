import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# ==========================================
# KONFIGURASI STATIS - PRIVATE REPO ONLY
# ==========================================
TELEGRAM_BOT_TOKEN = "8663293715:AAEO-Hd4Sg6h5oyV1n2oOUy52ILit1cahg4"
TELEGRAM_CHAT_ID = "7465370442"
GEMINI_API_KEY = ""  # Isi nanti saat Fase 2

# KuCoin API Public Endpoint (No Auth Required)
KUCOIN_API = "https://api.kucoin.com/api/v1/market/candles"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json'
}

def parse_symbol_kucoin(symbol):
    """
    Convert MT5 symbol to KuCoin format
    BTCUSD -> BTC-USD | ETHUSD -> ETH-USD | BTCUSDT -> BTC-USDT
    """
    if symbol.endswith('USDT'):
        base = symbol.replace('USDT', '')
        quote = 'USDT'
    elif symbol.endswith('USD') and not symbol.endswith('USDT'):
        base = symbol.replace('USD', '')
        quote = 'USD'
    else:
        base = symbol[:3]
        quote = symbol[3:]
    
    # KuCoin format: BTC-USD (dengan dash)
    return f"{base}-{quote}"

def get_crypto_data(symbol, interval='5min', limit=50):
    """
    Mengambil data OHLCV dari KuCoin API
    Timeframe options: 1min, 3min, 5min, 15min, 30min, 1hour, dll.
    """
    kucoin_symbol = parse_symbol_kucoin(symbol)
    
    # KuCoin menghitung waktu dalam timestamp (seconds)
    end_time = int(time.time())
    start_time = end_time - (limit * 5 * 60)  # limit * 5 menit * 60 detik
    
    params = {
        'symbol': kucoin_symbol,
        'type': interval,
        'startAt': start_time,
        'endAt': end_time
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"  📡 Request {kucoin_symbol} ke KuCoin (percobaan {attempt + 1})...")
            response = requests.get(
                KUCOIN_API, 
                params=params, 
                headers=HEADERS, 
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"  ❌ HTTP Error {response.status_code}: {response.text[:200]}")
                time.sleep(2 ** attempt)
                continue
            
            data = response.json()
            
            # KuCoin response structure: {code, data, msg}
            if data.get('code') != '200000':
                print(f"  ❌ KuCoin API Error: {data.get('msg', 'Unknown error')}")
                return None
            
            candles = data.get('data', [])
            
            if not candles or len(candles) == 0:
                print(f"  ⚠️ Response data kosong")
                return None
            
            # KuCoin candle format: [time, open, close, high, low, volume, turnover]
            df = pd.DataFrame(candles, columns=['time', 'open', 'close', 'high', 'low', 'volume', 'turnover'])
            
            # Konversi ke numeric
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Sort by time ascending
            df = df.sort_values('time').reset_index(drop=True)
            df = df.dropna(subset=['close'])
            
            if df.empty:
                print(f"  ⚠️ Data setelah cleaning kosong")
                return None
                
            print(f"  ✅ Berhasil ambil {len(df)} candle data {symbol} ({kucoin_symbol})")
            return df
            
        except requests.exceptions.Timeout:
            print(f"  ⏱️ Timeout (percobaan {attempt + 1})")
            time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError as e:
            print(f"  🔌 Connection Error: {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  ❌ Error: {type(e).__name__}: {e}")
            return None
    
    print(f"  ❌ Gagal setelah {max_retries} percobaan")
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
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        result = response.json()
        if result.get('ok'):
            print("✅ Pesan berhasil dikirim ke Telegram.")
            return True
        else:
            print(f"❌ Telegram API Error: {result}")
            return False
    except Exception as e:
        print(f"❌ Gagal kirim Telegram: {e}")
        return False

def analyze_market(symbol):
    print(f"🔄 Menganalisis {symbol}...")
    df = get_crypto_data(symbol, interval='5min', limit=50)
    
    if df is None or df.empty:
        error_msg = f"❌ *ERROR: Gagal ambil data {symbol}*\n\nAPI: KuCoin\nCek log GitHub Actions."
        send_telegram_message(error_msg)
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
    
    # Golden Cross
    if ema_8_prev <= ema_14_prev and ema_8_now > ema_14_now:
        signal = "🟢 POTENSI BUY (Golden Cross)"
    # Death Cross  
    elif ema_8_prev >= ema_14_prev and ema_8_now < ema_14_now:
        signal = "🔴 POTENSI SELL (Death Cross)"
        
    # Hitung Support/Resistance (20 candle terakhir)
    recent_lows = df['low'].iloc[-20:].min()
    recent_highs = df['high'].iloc[-20:].max()
    
    # ATR untuk volatility
    df['tr'] = df['high'] - df['low']
    atr = df['tr'].iloc[-14:].mean()
    
    # Format Pesan untuk Telegram
    message = (
        f"🤖 *MT5 TRADING SIGNAL: {symbol}*\n"
        f"⏰ Waktu: {datetime.now().strftime('%H:%M:%S')} UTC\n\n"
        f"📊 *Data Teknikal (M5)*\n"
        f"💰 Harga: `${current_price:,.2f}`\n"
        f"📈 EMA 8: `{ema_8_now:,.2f}`\n"
        f"📉 EMA 14: `{ema_14_now:,.2f}`\n"
        f"🎯 *Level Kunci (20 candle)*\n"
        f"🔹 Support: `${recent_lows:,.2f}`\n"
        f"🔹 Resistance: `${recent_highs:,.2f}`\n"
        f"🔹 ATR (14): `${atr:,.2f}`\n\n"
        f"🚨 *Status:* {signal}\n\n"
        f"_(Fase 1: Data & Telegram OK)_\n"
        f"_(Fase 2: AI Gemini akan hitung SL/TP)_"
    )
    
    send_telegram_message(message)
    return signal

def main():
    print("🚀 MT5 Trading Bot (KuCoin API) Dimulai...")
    # Format symbol untuk MT5: BTCUSD, ETHUSD
    coins = ["BTCUSD", "ETHUSD"]
    
    for coin in coins:
        analyze_market(coin)
    
    print("✅ Selesai.")

if __name__ == "__main__":
    main()
