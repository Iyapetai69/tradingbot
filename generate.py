import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

URL = "https://pafimalinauselatan.org/"
OUTPUT_FILE = "data.json"

HEADERS = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
CHUNK_SIZE = 5
TOTAL_COLS = len(HEADERS) * CHUNK_SIZE  # 35


# =========================
# FETCH FULL DATA
# =========================
def fetch_all_rows():
    html = requests.get(URL, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("div", {
        "class": "table",
        "title": "Paito SGP"
    }).find("table")

    rows = table.find_all("tr")[1:]  # skip header

    all_data = []

    for row in rows:
        cols = [td.text.strip() for td in row.find_all("td")]

        # filter baris valid
        if len(cols) != TOTAL_COLS:
            continue

        # convert ke int
        try:
            cols = [int(x) for x in cols]
        except:
            continue

        all_data.append(cols)

    return all_data


# =========================
# FETCH LATEST ROW
# =========================
def fetch_latest_row():
    html = requests.get(URL, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("div", {
        "class": "table",
        "title": "Paito SGP"
    }).find("table")

    rows = table.find_all("tr")[1:]
    latest = rows[0]

    cols = [int(td.text.strip()) for td in latest.find_all("td")]

    if len(cols) != TOTAL_COLS:
        return None

    return cols


# =========================
# LOAD OLD DATA
# =========================
def load_old_data():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            return json.load(f)
    else:
        return {
            "updated_at": None,
            "total_rows": 0,
            "columns": HEADERS,
            "chunk_size": CHUNK_SIZE,
            "data": []
        }


# =========================
# SAVE DATA
# =========================
def save_data(data):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)


# =========================
# MAIN LOGIC
# =========================
def main():
    db = load_old_data()

    # =====================
    # FULL SCRAPE (FIRST RUN)
    # =====================
    if len(db["data"]) == 0:
        print("🚀 FULL SCRAPE MODE")

        all_rows = fetch_all_rows()

        db["data"] = all_rows
        db["total_rows"] = len(all_rows)
        db["updated_at"] = datetime.utcnow().isoformat()

        save_data(db)

        print(f"✅ Berhasil ambil {len(all_rows)} baris")
        return

    # =====================
    # INCREMENTAL UPDATE
    # =====================
    print("⚡ INCREMENTAL MODE")

    new_row = fetch_latest_row()

    if not new_row:
        print("❌ Gagal ambil data terbaru")
        return

    # cek duplikat
    if db["data"] and db["data"][0] == new_row:
        print("⏳ Tidak ada data baru")
        return

    # insert ke atas
    db["data"].insert(0, new_row)
    db["total_rows"] += 1
    db["updated_at"] = datetime.utcnow().isoformat()

    # limit biar nggak bengkak (opsional)
    MAX_ROWS = 3000
    db["data"] = db["data"][:MAX_ROWS]

    save_data(db)

    print("✅ Data baru ditambahkan")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
