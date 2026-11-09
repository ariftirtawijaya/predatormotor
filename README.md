# Predator Autolight Bojonegoro — Website Publik, CMS & Sistem Bengkel

Satu aplikasi: website publik (dikelola CMS) + dashboard internal (kasir, pekerjaan bengkel, pesanan WhatsApp, stok, garansi, laporan).

- Frontend: React 19 + Tailwind CSS (`/frontend`)
- Backend: Python FastAPI (`/backend`)
- Database: MongoDB
- File unggahan: disk lokal (`UPLOAD_DIR`), bukan layanan khusus Emergent
- Autentikasi: email + password (bcrypt) dengan JWT di cookie httpOnly — tidak bergantung pada layanan eksternal

## 1. Struktur modul

| Modul | File backend | Halaman admin |
|---|---|---|
| Login, pengguna, audit log | `auth_routes.py` | Pengguna, Audit Log |
| CMS (draft/terbit/revisi), media, situs publik | `cms_routes.py` | CMS Website, Media |
| Master barang, paket, pelanggan, kendaraan, stok, biaya | `master_routes.py` | Master Barang, Paket, Mutasi Stok, Barang Rusak, Biaya |
| Nota pekerjaan, garansi, penjualan langsung, pesanan WA, pembayaran, diskon, retur | `tx_routes.py` | Pekerjaan, Kasir, Nota Penjualan, Pesanan WA, Riwayat Kendaraan, Persetujuan Diskon |
| Laporan, dashboard, ekspor CSV | `report_routes.py` | Dashboard, Laporan |
| Fungsi inti (DB, auth, mutasi stok atomik, pembayaran idempoten) | `core.py` | — |

### Hubungan data (koleksi MongoDB)
- `customers` 1—n `vehicles` (plat unik, dinormalisasi tanpa spasi).
- `jobs` (nota pekerjaan & nota garansi) → `customer_id`, `vehicle_id`; baris (`lines`) menyimpan **snapshot** nama, harga, komponen, modal. Nota garansi menyimpan `claim.ref_id` + `claim.line_lid` ke nota & item awal.
- `sales` (penjualan langsung), `orders` (pesanan WA) — juga menyimpan snapshot baris.
- `payments` — setiap uang masuk/keluar (DP, pelunasan, COD cair, refund) dengan `idem_key` unik → permintaan ulang tidak mencatat dua kali.
- `items` (stok fisik bengkel) — stok hanya berubah lewat `stock_mutations` (append-only: sebelum, sesudah, selisih, alasan, referensi, pengguna).
- `damaged`, `expenses`, `audit_logs`, `cms`, `cms_revisions`, `media`, `counters` (nomor nota).

### Aturan bisnis yang diterapkan
- Status pekerjaan hanya **Masuk / Selesai** (plus **Batal** oleh owner untuk nota Masuk). Pembayaran & garansi terpisah.
- Stok komponen paket + barang tambahan berkurang **sekali** saat Selesai (kunci status atomik; tombol ulang/reload aman). Stok paket itu sendiri tidak ada — hanya komponen.
- Pengurangan stok memakai `$inc` bersyarat (`stock >= qty`) → tidak bisa negatif, dua kasir tidak bisa menjual barang terakhir dua kali.
- Penjualan langsung: stok berkurang saat transaksi disimpan & dibayar. Rekap harian dihitung otomatis.
- Pesanan WA prabayar: stok berkurang saat pembayaran lunas diterima. COD: hanya provinsi Pulau Jawa (daftar terstruktur), stok berkurang saat dikirim, uang dicatat saat dana COD cair.
- Diskon pekerjaan/pesanan WA diajukan kasir → disetujui/ditolak owner (tercatat). Diskon penjualan langsung hanya oleh owner.
- Retur/pembatalan tidak menghapus transaksi; barang kembali ke stok hanya jika dipilih "layak", "rusak" masuk catatan barang rusak.
- Pembatalan DP: owner menentukan jumlah pengembalian per kasus; sisa tercatat sebagai "DP ditahan".
- Kasir tidak menerima data modal/HPP dari API (disaring di backend).

## 2. Menjalankan secara lokal

```bash
# MongoDB lokal berjalan di 27017
cd backend
cp .env.example .env     # isi JWT_SECRET (openssl rand -hex 32), MONGO_URL=mongodb://localhost:27017, UPLOAD_DIR=./uploads, CORS_ORIGINS=http://localhost:3000, COOKIE_SECURE=false
pip install -r requirements-prod.txt
uvicorn server:app --reload --port 8001

cd ../frontend
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
yarn install && yarn start
```

Data uji (hanya untuk pengembangan, **jangan di produksi**): `ALLOW_DEMO_SEED=true DEMO_ADMIN_PASSWORD=<min8> DEMO_KASIR_PASSWORD=<min8> python seed_demo.py` (membuat admin/kasir uji dan barang berawalan `[TEST]`).

Tes backend (hanya butuh MongoDB berjalan dan `MONGO_URL` di `backend/.env` atau env `TEST_MONGO_URL`):
```bash
cd backend
pip install -r requirements-dev.txt
pytest tests -q
```
Suite default menyalakan server uvicorn khusus tes dengan database sementara `predator_pytest_*`, akun uji berpassword acak, folder unggahan sementara, dan JWT_SECRET acak; semuanya dihapus setelah tes. Database aplikasi (`DB_NAME`) tidak disentuh dan API Fonnte dialihkan ke alamat buntu, jadi tidak ada pesan WhatsApp nyata yang terkirim. Frontend: `cd frontend && CI=true yarn test --watchAll=false`.

Tes live opsional (hanya baca, tidak mengubah token/nomor dan tidak mengirim pesan) terhadap server yang sudah berjalan: set `LIVE_BASE_URL`, `LIVE_OWNER_EMAIL`, `LIVE_OWNER_PASSWORD`, `LIVE_KASIR_EMAIL`, `LIVE_KASIR_PASSWORD`, lalu `pytest tests_live -q -n 0`.

## 3. Deploy ke VPS baru (Docker Compose + HTTPS otomatis)

Prasyarat: Ubuntu 22.04/24.04, domain yang A-record-nya mengarah ke IP VPS, port 80/443 terbuka.

```bash
curl -fsSL https://get.docker.com | sh
git clone <repo-anda> predator && cd predator
cp .env.example .env                 # SITE_DOMAIN=domain-anda.com
cp backend/.env.example backend/.env # isi JWT_SECRET, CORS_ORIGINS=https://domain-anda.com, DB_NAME
docker compose up -d --build
```

- `web` = Caddy: menyajikan build React, reverse proxy `/api/*` ke backend, **HTTPS Let's Encrypt otomatis**.
- Volume persisten: `mongo_data` (database), `uploads` (foto), `caddy_data` (sertifikat).
- Catatan: `frontend/package.json` memuat devDependency `@emergentbase/*` (khusus editor Emergent). Jika `yarn install` gagal mengunduhnya di VPS, hapus dua baris itu dan baris pemanggilnya di `craco.config.js`, lalu jalankan `yarn install` untuk memperbarui `yarn.lock`.

Ingin memakai Nginx? Arahkan `location /api/ { proxy_pass http://127.0.0.1:8001; }` dan `location / { root /var/www/build; try_files $uri /index.html; }`, lalu `certbot --nginx -d domain-anda.com`.

### Membuat akun owner pertama dengan aman
Opsi A (disarankan): setelah container jalan,
```bash
docker compose exec backend python create_owner.py email@owner.com "Nama Owner"
```
Password diminta secara interaktif (tidak tersimpan di riwayat shell/berkas).
Opsi B: isi `OWNER_EMAIL` & `OWNER_PASSWORD` di `backend/.env` — hanya dipakai bila belum ada pengguna sama sekali. Setelah login pertama, **kosongkan kembali** kedua nilai itu.
Owner lalu membuat akun admin/kasir dari menu **Pengguna**.

### Impor Excel & replica set MongoDB
- `docker-compose.yml` menjalankan `mongo --replSet rs0`; healthcheck otomatis melakukan `rs.initiate` pada start pertama. `backend/.env` wajib `MONGO_URL="mongodb://mongo:27017/?replicaSet=rs0"`.
- **VPS yang sudah berjalan tanpa replica set:** `./scripts/backup.sh` → `git pull` → ubah `MONGO_URL` seperti di atas → `docker compose up -d --build` → `docker compose ps` (mongo *healthy*) → `docker compose exec mongo mongosh --quiet --eval 'rs.status().ok'` harus `1`. Data di volume `mongo_data` tetap dipakai.
- Tanpa replica set, pratinjau impor tetap jalan tetapi tombol Simpan ditolak (HTTP 503) — tidak ada data parsial.
- **Sebelum mengimpor data asli**, jalankan uji integrasi terhadap replica set sungguhan (container sementara, data aplikasi tidak disentuh): `./scripts/test-replset.sh`. Pastikan tidak ada tes impor yang berstatus SKIPPED.
- Validasi pratinjau (seluruh file sekaligus, spasi & huruf besar/kecil dinormalisasi): nama produk sama dengan kode berbeda, kode sama dengan nama/kategori/merek berbeda, SKU ganda, nama varian ganda, campuran baris tanpa/dengan nama varian, dan bentrok dengan produk/varian di database. Saat Simpan, server memeriksa ulang di dalam transaksi; bila data berubah sejak pratinjau → ditolak (409), pratinjau ulang.
- Impor ulang file yang sama aman: varian yang ada tidak digandakan dan `stok_awal` diabaikan untuk varian lama.

### Backup & restore
```bash
chmod +x scripts/*.sh
./scripts/backup.sh                       # db-*.archive.gz + uploads-*.tar.gz di ./backups (simpan 30 hari)
./scripts/restore.sh backups/db-X.archive.gz backups/uploads-X.tar.gz
```
Jadwalkan harian: `crontab -e` → `0 2 * * * cd /root/predator && ./scripts/backup.sh >> backups/log.txt 2>&1`. Salin folder `backups` ke tempat lain (Google Drive/rclone) secara berkala.

### Memperbarui aplikasi
```bash
./scripts/backup.sh
git pull
docker compose up -d --build
docker compose logs -f backend   # periksa
```
Data & foto tetap aman di volume.

### Memindahkan data dari Emergent ke VPS
`mongodump --uri "$MONGO_URL" --db <DB_NAME> --archive --gzip > db.archive.gz`, salin juga folder `UPLOAD_DIR`; di VPS pulihkan dengan `scripts/restore.sh`. Pastikan `DB_NAME` di VPS sama, atau pakai `--nsFrom/--nsTo` pada mongorestore.

## 4. Environment variables (backend)
| Nama | Keterangan |
|---|---|
| MONGO_URL, DB_NAME | Koneksi MongoDB |
| JWT_SECRET | Rahasia token (wajib, acak 64 karakter) |
| CORS_ORIGINS | Domain frontend (pisahkan koma) |
| UPLOAD_DIR | Folder unggahan persisten (`public/` & `private/`) |
| COOKIE_SECURE / COOKIE_SAMESITE | `true` / `lax` untuk HTTPS satu domain |
| MAX_UPLOAD_MB | Batas ukuran gambar (default 5) |
| OWNER_EMAIL / OWNER_PASSWORD | Opsional, hanya untuk membuat owner pertama |
| DISABLE_DOCS | `true` untuk menyembunyikan /api/docs di produksi |
| PUBLIC_SITE_URL | Alamat website publik untuk tautan nota di pesan WhatsApp (mis. `https://bengkel-anda.example`). Di Docker Compose otomatis diisi `https://${SITE_DOMAIN}` |

## 5. Keamanan
- Password bcrypt; JWT akses 30 menit + refresh 7 hari di cookie httpOnly; pembatasan 5 percobaan login gagal → kunci 15 menit.
- Izin peran ditegakkan di setiap endpoint backend (`require(...)`), bukan hanya disembunyikan di UI.
- Unggahan: diverifikasi sebagai gambar dengan Pillow, di-encode ulang (metadata/EXIF dibuang), hanya JPG/PNG/WEBP/ICO, nama file acak. Foto pelanggan disimpan di folder privat yang membutuhkan login.
- Konten CMS dibersihkan dari tag HTML; tautan `javascript:` ditolak.
- Tautan nota publik memakai token acak 32 karakter dan hanya menampilkan nama, item, total & pembayaran (tanpa nomor WA/alamat/modal).
- Audit log untuk perubahan penting (baris nota, diskon, pembayaran, koreksi stok, pembatalan, publikasi CMS, pengguna).

## 5a. WhatsApp via Fonnte
- Owner mengisi **token Fonnte** dan **nomor WhatsApp admin** di menu *Pengaturan · WhatsApp* — tidak perlu mengubah `.env` atau deploy ulang.
- Token disimpan terenkripsi di MongoDB (koleksi `settings`) dengan kunci turunan `JWT_SECRET`. Jika `JWT_SECRET` diganti, token harus diisi ulang dari panel.
- Nomor admin = nomor WhatsApp di CMS Kontak (draft). Website publik baru berubah setelah bagian Kontak diterbitkan.
- Pesan dikirim dari perangkat WhatsApp yang terhubung ke token Fonnte. Nota hanya dikirim saat petugas menekan tombol; riwayat ada di koleksi `wa_logs`.
- Server VPS harus bisa mengakses `https://api.fonnte.com` (HTTPS keluar).


## 6. Batasan yang diketahui
- MongoDB di Docker berjalan sebagai **replica set satu node** (`rs0`). Impor Excel memakai multi-document transaction (semua atau tidak sama sekali). Alur transaksi lain (nota, pembayaran, stok) tetap memakai operasi atomik per dokumen, kunci status, kunci idempoten, dan rollback kompensasi (tercatat sebagai mutasi "Batal otomatis").
- SEO dirender di sisi klien (SPA). Judul/deskripsi/OG diatur per halaman, tetapi crawler yang tidak menjalankan JavaScript (sebagian pratinjau tautan WhatsApp/Facebook) mungkin hanya melihat judul default `index.html`.
- Pratinjau CMS menampilkan seluruh draft semua bagian sekaligus.
- Produk induk + varian (SKU & stok per varian). Produk tanpa varian disimpan sebagai satu barang internal tanpa nama varian.
- Belum ada impor data dari sistem lama (source lama belum diberikan).
