import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

URL = "https://pafimalinauselatan.org/"
OUTPUT_FILE = "data.json"

HEADERS = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"]
CHUNK_SIZE = 5


def fetch_latest_row():
    html = requests.get(URL, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("div", {
        "class": "table",
        "title": "Paito SDY"
    }).find("table")

    rows = table.find_all("tr")[1:]  # skip header
    latest = rows[0]

    cols = [int(td.text.strip()) for td in latest.find_all("td")]

    # flatten row (35 angka)
    return cols


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


def save_data(data):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def main():
    new_row = fetch_latest_row()
    db = load_old_data()

    # cek duplikat (bandingin row pertama)
    if db["data"] and db["data"][0] == new_row:
        print("⏳ Tidak ada data baru")
        return

    # insert ke atas
    db["data"].insert(0, new_row)
    db["total_rows"] += 1
    db["updated_at"] = datetime.utcnow().isoformat()

    # limit biar nggak bengkak (opsional)
    MAX_ROWS = 10000
    db["data"] = db["data"][:MAX_ROWS]

    save_data(db)

    print("✅ Data baru ditambahkan")


if __name__ == "__main__":
    main()
