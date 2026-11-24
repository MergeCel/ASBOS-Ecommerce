# Shopeepedia — E-Commerce Lokal (MVP)

Toko online sederhana dengan frontend HTML statis, API Flask, dan PostgreSQL.
Tidak ada framework frontend, tidak ada build step.

```
Browser ──> nginx (container web, port 8080) ──/api──> Flask (container api, port 5000) ──> PostgreSQL (host)
```

## Struktur

| Path | Isi |
|---|---|
| `index.html` | Halaman toko: katalog, filter kategori, pencarian, keranjang, checkout |
| `backend/app.py` | API Flask + query PostgreSQL |
| `backend/requirements.txt` | Flask, psycopg2-binary, gunicorn |
| `backend/Dockerfile` | Image Python 3.12-slim |
| `nginx/default.conf` | Konfigurasi nginx di container: serve HTML + proxy `/api/` |
| `db/schema.sql` | Skema + data contoh (DROP TABLE — hati-hati) |
| `docker-compose.yml` | Service `web` dan `api` |
| `.env.example` | Contoh konfigurasi database |

## Konfigurasi baru yang harus disiapkan

### 1. File `.env` di server

Salin `.env.example` menjadi `.env` di direktori project server
(`/var/www/ecommerce/.env`), lalu isi password PostgreSQL asli:

```dotenv
DB_HOST=host.docker.internal
DB_PORT=5432
DB_NAME=ecommerce_db
DB_USER=ecommerce_user
DB_PASSWORD=password_asli
```

`.env` sudah masuk `.gitignore`, jadi aman dari `git reset --hard` saat deploy.

### 2. PostgreSQL harus menerima koneksi dari container

Container tidak bisa memakai `localhost` host. Alamat `host.docker.internal`
diarahkan ke gateway Docker (biasanya `172.17.0.1`). Di `postgresql.conf`:

```conf
listen_addresses = '*'
```

Di `pg_hba.conf`, izinkan subnet Docker memakai password:

```conf
host    ecommerce_db    ecommerce_user    172.16.0.0/12    scram-sha-256
```

Lalu restart PostgreSQL (`sudo systemctl restart postgresql`) dan pastikan
port 5432 tetap tertutup dari internet (mis. `sudo ufw deny 5432`).

### 3. Inisialisasi database (sekali saja)

`schema.sql` menghapus lalu membuat ulang tabel, jadi **jangan** dijalankan
jika data sudah ada:

```bash
sudo -u postgres psql -d ecommerce_db -f db/schema.sql
```

### 4. Port

- `web` dipublikasikan ke `127.0.0.1:8080` (sama seperti sebelumnya).
- `api` **tidak** dipublikasikan ke host; hanya diakses nginx lewat jaringan Docker.

## Menjalankan

```bash
docker compose up -d --build
docker compose logs -f api        # cek error koneksi DB
curl http://127.0.0.1:8080/api/health
```

Buka `http://127.0.0.1:8080/` (atau lewat nginx host seperti biasa).

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
`api` ikut dibangun ulang. CI (`.github/workflows/deploy.yml`) juga memakai
`docker compose build` agar error build backend terdeteksi sebelum deploy.
