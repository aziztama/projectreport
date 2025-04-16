import mysql.connector

# Konfigurasi database
db_config = {
    "host": "localhost",  # atau "localhost"
    "user": "root",       # ganti dengan user MySQL lokal kamu
    "password": "",  # sesuaikan
    "database": "poscabang"       # pastikan database ini ada
}

try:
    
    
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    print("Koneksi ke database berhasil!")

    # Contoh query
    cursor.execute("SHOW TABLES")
    for table in cursor.fetchall():
        print(table)

except mysql.connector.Error as err:
    print(f"❌ Error: {err}")

finally:
    if conn.is_connected():
        cursor.close()
        conn.close()
