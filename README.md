# Shopeepedia — E-Commerce Lokal (MVP)

Toko online sederhana dengan frontend HTML statis, API Flask, dan PostgreSQL.
Seluruh komponen aplikasi berjalan di Docker Compose, dengan Nginx di host
sebagai reverse proxy.

```
Browser
  └──> Nginx host (port 80/443)
         └──> nginx container "web" (127.0.0.1:8080)
                ├── /       -> index.html
                └── /api/   -> Flask container "api" (:5000)
                                 └──> PostgreSQL container "db" (:5432)
```

## Struktur

| Path | Isi |
|---|---|
| `index.html` | Halaman toko: katalog, filter kategori, pencarian, keranjang, checkout |
| `backend/app.py` | API Flask + query PostgreSQL |
| `backend/requirements.txt` | Flask, psycopg2-binary, gunicorn |
| `backend/Dockerfile` | Image Python 3.12-slim |
| `nginx/default.conf` | Konfigurasi nginx container: serve HTML + proxy `/api/` |
| `db/schema.sql` | Skema + data contoh (DROP TABLE — hati-hati) |
| `docker-compose.yml` | Service `web`, `api`, dan `db` |
| `.env.example` | Contoh kredensial database |

## Service container

| Service | Image / build | Port | Keterangan |
|---|---|---|---|
| `web` | build `.` | `127.0.0.1:8080:80` | Nginx + halaman toko, proxy `/api/` |
| `api` | build `./backend` | tidak dipublikasikan | Flask + gunicorn, hanya di network Compose |
| `db` | `postgres:16-alpine` | tidak dipublikasikan | Data disimpan di volume `db_data` |

Hanya `web` yang terbuka ke host. `api` dan `db` tidak punya port publik,
jadi database tidak bisa diakses dari internet maupun dari host secara langsung.

## Konfigurasi

### 1. File `.env` di server

Salin `.env.example` menjadi `.env` di direktori project server
(`/var/www/ecommerce/.env`), lalu isi password yang kuat:

```dotenv
DB_NAME=ecommerce_db
DB_USER=ecommerce_user
DB_PASSWORD=password_asli
```

`DB_HOST` dan `DB_PORT` tidak perlu diisi: `docker-compose.yml` sudah memakai
`db:5432` (nama service di network Compose). Nilai `DB_*` dipakai bersama oleh
container `db` (sebagai `POSTGRES_*`) dan container `api`.

`.env` sudah masuk `.gitignore`, jadi aman dari `git reset --hard` saat deploy.
Nilai `POSTGRES_*` hanya dibaca saat volume database pertama kali dibuat;
mengubahnya setelah itu tidak mengubah database yang sudah ada.

### 2. Isolasi database

Tidak ada konfigurasi `postgresql.conf` atau `pg_hba.conf` di host yang perlu
diubah. Database berjalan di container dan hanya bisa dijangkau container lain
di network Compose. Untuk masuk sebagai admin:

```bash
docker compose exec db psql -U ecommerce_user -d ecommerce_db
```

Data tetap ada saat container dihentikan atau di-rebuild. Perintah
`docker compose down -v` akan **menghapus volume** dan seluruh data.

### 3. Inisialisasi skema (sekali saja)

`schema.sql` menghapus lalu membuat ulang tabel, jadi **jangan** dijalankan
jika data sudah ada:

```bash
docker compose up -d db
docker compose exec -T db psql -U ecommerce_user -d ecommerce_db < db/schema.sql
```

### 4. Migrasi data dari PostgreSQL host (jika sudah ada data)

Lakukan dump sebelum beralih, lalu restore ke container. Pastikan volume `db`
masih kosong (jangan jalankan `schema.sql` lebih dulu):

```bash
# 1. Dump dari PostgreSQL host
pg_dump -h localhost -U ecommerce_user -d ecommerce_db -f /tmp/ecommerce_db.sql

# 2. Nyalakan database container
docker compose up -d db

# 3. Restore ke database container
docker compose exec -T db psql -U ecommerce_user -d ecommerce_db < /tmp/ecommerce_db.sql

# 4. Jalankan seluruh aplikasi
docker compose up -d --build
```

Jika volume sudah terisi data lain dan ingin memulai bersih, hentikan dulu
dengan `docker compose down -v` (data lama terhapus).

### 5. Port

- `web` dipublikasikan ke `127.0.0.1:8080` (dipakai Nginx host).
- `api` dan `db` tidak dipublikasikan ke host; hanya diakses lewat network Compose.
- Port 5432 tidak perlu dibuka di UFW.

## Menjalankan

```bash
docker compose up -d --build
docker compose ps                 # pastikan db healthy
docker compose logs -f api        # cek error koneksi database
curl http://127.0.0.1:8080/api/health
```

Buka `http://127.0.0.1:8080/` (atau lewat Nginx host seperti biasa).

## Backup

`scripts/backup_db.sh` menjalankan `pg_dump` di dalam container `db`, lalu
mengemas hasilnya menjadi `.tar.gz` bertimestamp. Tidak perlu `~/.pgpass`.

```bash
sudo /opt/scripts/backup_db.sh
```

Contoh cron harian pukul 02:00:

```cron
0 2 * * * /opt/scripts/backup_db.sh >> /var/log/backup_db.log 2>&1
```

Script memakai `APP_DIR=/var/www/ecommerce` dan `BACKUP_DIR=/var/backups/ecommerce`;
keduanya bisa dioverride lewat environment variable.

## Endpoint

| Method | Path | Keterangan |
|---|---|---|
| GET | `/api/health` | Cek API + koneksi database |
| GET | `/api/categories` | Daftar kategori + jumlah produk |
| GET | `/api/products` | Katalog; query `category_id`, `q`, `limit`, `offset` |
| GET | `/api/products/<id>` | Detail satu produk |
| POST | `/api/orders` | Buat pesanan (validasi stok + hitung total di server) |
| GET | `/api/orders/<id>` | Detail pesanan + item |

Contoh checkout:

```bash
curl -X POST http://127.0.0.1:8080/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer": {"full_name": "Siti", "email": "siti@example.com", "phone": "0812", "city": "Pontianak"},
    "items": [{"product_id": 1, "quantity": 2}]
  }'
```

Pesanan selalu dibuat dengan status `pending`, total dihitung ulang dari harga
di database, dan stok produk dikurangi dalam satu transaksi.

## Catatan deploy

`scripts/deploy.sh` menjalankan `docker compose up -d --build`, sehingga image
`api` ikut dibangun ulang dan container `db` ikut dinyalakan. CI
(`.github/workflows/deploy.yml`) juga memakai `docker compose build` agar error
build backend terdeteksi sebelum deploy.

Inisialisasi skema atau restore data cukup dilakukan sekali; deploy berikutnya
tidak menghapus volume `db_data`.
