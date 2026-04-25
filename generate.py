import requests
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://pafimalinauselatan.org/"

res = requests.get(URL, timeout=10)
soup = BeautifulSoup(res.text, "html.parser")

# 🔥 ambil langsung div tabel
table_div = soup.find("div", {"class": "table", "title": "Paito SDY"})

if not table_div:
    raise Exception("Table tidak ditemukan")

# ambil isi HTML-nya
table_html = str(table_div)

# ===== BUILD FULL HTML =====
html = f"""
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Paito SGP</title>

<style>
body {{ font-family: Arial; }}

.colormenu {{
    background: #d9d9d9;
    border: 2px solid #d9d9d9;
    width: 796px;
    height: 30px;
    max-width: 100%;
    margin-bottom: 10px;
}}

#drawing-table td {{
    border:1px solid #d9d9d9;
    text-align:center;
    font-size:13px;
    font-weight:bold;
    padding:3px 0;
}}

.headd td {{
    background:#0000f4;
    color:#fff;
}}

td.asu {{ background:#fff; }}
td.asux {{ background:#f4f4f4; }}
</style>
</head>

<body>

<div align="center">

<h2>Paito SGP</h2>

{table_html}

<br>

<form>
<input placeholder="as">
<input placeholder="kop">
<input placeholder="kep">
<input placeholder="ekr">
</form>

</div>

<p>Update: {datetime.now()}</p>

</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("HTML generated (FULL DIV MODE)!")
