from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text
import zipfile, os, csv, json, shutil
import pymysql

app = FastAPI()

UPLOAD_DIR = "uploads"
PROGRESS_FILE = "progress.json"
DB_URL = "mysql+pymysql://root:@localhost/poscabang"

os.makedirs(UPLOAD_DIR, exist_ok=True)
engine = create_engine(DB_URL)

app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html") as f:
        return f.read()

@app.get("/progress")
def get_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"current": 0, "total": 0}

@app.post("/upload")
async def upload_zip(nama_tabel: str = Form(...), file: UploadFile = File(...)):
    try:
        table_name = "".join(c for c in nama_tabel if c.isalnum() or c == "_")
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        zip_path = os.path.join(UPLOAD_DIR, "uploaded.zip")
        with open(zip_path, "wb") as buffer:
            buffer.write(await file.read())

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(UPLOAD_DIR)

        csv_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".csv")]
        if not csv_files:
            return JSONResponse(status_code=400, content={"error": "ZIP tidak berisi file CSV"})

        with open(os.path.join(UPLOAD_DIR, csv_files[0]), newline='', encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

        header.append("PPN_RATE")
        header.append("KODE_TOKO")

        types = [
            "VARCHAR(10)", "VARCHAR(2)", "VARCHAR(8)", "VARCHAR(6)", "INT", "INT", "VARCHAR(2)",
            "INT", "BIGINT", "INT", "BIGINT", "BIGINT", "INT", "BIGINT", "BIGINT", "INT", "BIGINT", "DECIMAL(12,2)",
            "INT", "BIGINT", "DECIMAL(12,2)", "BIGINT", "INT", "BIGINT", "INT", "BIGINT", "DECIMAL(12,2)", "DECIMAL(12,2)",
            "DECIMAL(15,6)", "DECIMAL(12,2)", "BIGINT", "VARCHAR(1)", "VARCHAR(1)", "VARCHAR(4)", "CHAR(1)", "CHAR(1)",
            "INT", "INT", "INT", "INT", "BIGINT", "BIGINT", "BIGINT", "VARCHAR(4)", "VARCHAR(4)", "BIGINT", "BIGINT",
            "INT", "BIGINT", "INT", "BIGINT", "BIGINT", "BIGINT", "BIGINT", "INT", "VARCHAR(2)", "VARCHAR(4)",
            "VARCHAR(20)", "VARCHAR(10)"
        ]

        columns = [f"`{h.strip()}` {types[i] if i < len(types) else 'TEXT'}" for i, h in enumerate(header)]
        with engine.connect() as conn:
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({','.join(columns)})"))

        conn_raw = pymysql.connect(host="localhost", user="root", password="", database="poscabang")
        cur = conn_raw.cursor()

        rupiah_indexes = [8, 10, 11, 13, 14, 16, 18, 20, 21, 23, 25, 26, 27, 29, 30, 40, 41, 44, 45, 47, 48, 49, 50, 51, 52, 53]
        insert_sql = f"INSERT INTO `{table_name}` VALUES ({','.join(['%s'] * len(header))})"

        total_rows = 0
        for file_name in csv_files:
            file_path = os.path.join(UPLOAD_DIR, file_name)
            kode_toko = file_name[:4]

            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}` WHERE `KODE_TOKO` = :kt"), {"kt": kode_toko})
                if result.scalar() > 0:
                    continue

            with open(file_path, newline='', encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)

                for i, row in enumerate(reader):
                    while len(row) < len(header) - 2:
                        row.append("")
                    row.append("")
                    row.append(kode_toko)

                    for idx in rupiah_indexes:
                        if idx < len(row):
                            row[idx] = row[idx].replace('.', '')

                    try:
                        cur.execute(insert_sql, row)
                    except Exception as e:
                        print(f"[ERROR] Baris gagal dimasukkan: {row} => {e}")
                        continue

                    total_rows += 1
                    if total_rows % 100 == 0:
                        with open(PROGRESS_FILE, "w") as f:
                            json.dump({"current": total_rows, "total": "estimasi"}, f)

        conn_raw.commit()
        cur.close()
        conn_raw.close()

        with open(PROGRESS_FILE, "w") as f:
            json.dump({"current": total_rows, "total": total_rows}, f)

        return {"message": f"{total_rows} baris berhasil diunggah ke tabel {table_name}"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
