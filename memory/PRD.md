# PRD — Predator Autolight Bojonegoro

## Original problem statement
Saya ingin Anda membangun website publik, CMS, dan sistem operasional bengkel untuk Predator Autolight Bojonegoro. Usaha ini memasang lampu serta aksesoris kelistrikan kendaraan, menjual barang langsung di bengkel, dan menerima pesanan langsung melalui WhatsApp. (Brief lengkap 16 bagian: arsitektur portabel ke VPS; website publik Tailwind modern + dashboard admin terang; CMS terstruktur penuh dengan draft/pratinjau/terbit/riwayat; stok bengkel terpisah dari marketplace; peran owner/admin/kasir di backend; pelanggan/kendaraan & riwayat wajib; status pekerjaan hanya Masuk/Selesai; paket & snapshot nota; penjualan langsung; pesanan WA dengan aturan COD Jawa; garansi; mutasi stok & audit; DP/pembatalan/retur; nota + tombol WhatsApp; laporan rinci + CSV/PDF; keamanan; dokumentasi deploy, backup, restore; skenario uji.)

User choices: diskon disetujui owner dari dashboard; nota thermal 80 mm (utama) + A4; warna aksen website diatur dari admin; garansi default: tanpa garansi sampai diatur per barang/paket.

Permintaan fitur (2026-11-08): "Tolong tambahkan integrasi WhatsApp menggunakan Fonnte … menu Pengaturan → WhatsApp (token API Fonnte + nomor WhatsApp admin, owner saja, token tersamar & aman, tanpa edit .env/deploy ulang; nomor admin satu sumber untuk website & pesan percobaan mengikuti alur draft → pratinjau → terbit) … tombol Kirim Nota via WhatsApp lewat backend + API Fonnte ke nomor pelanggan (pekerjaan, penjualan langsung — kasir boleh isi nomor, pesanan WA), isi dari data tersimpan tanpa harga modal, hanya saat tombol ditekan, gagal kirim tidak mengubah transaksi … POST https://api.fonnte.com/send, Authorization tanpa Bearer, form data, normalisasi 62…, status true = antrean, tanpa kirim ulang otomatis saat timeout … Kirim Pesan Percobaan, riwayat setiap percobaan, cegah klik ganda, kirim ulang disengaja … tes backend & frontend dengan Fonnte di-mock."

## Architecture
React 19 + Tailwind (public dark site w/ CMS accent var; admin light) · FastAPI (core, auth_routes, cms_routes, master_routes, tx_routes, report_routes, wa_routes) · MongoDB · local disk uploads · JWT httpOnly cookie auth (bcrypt) · Docker Compose (mongo, backend, Caddy w/ auto HTTPS) · scripts/backup.sh & restore.sh · Fonnte API (httpx, backend only; token Fernet-encrypted in `settings`).

## User personas
Owner (Mas Latif) — semua modul, laporan laba, persetujuan diskon, pembatalan, pengaturan WhatsApp. Admin — barang, stok, paket, CMS. Kasir — pelanggan, pekerjaan, penjualan, pesanan WA, pembayaran, kirim nota WA.

## What's been implemented
### 2026-11-08 (MVP)
- Public site, CMS 11 bagian (draft/pratinjau/terbit/riwayat), media library, operasional lengkap (barang, paket, stok, pekerjaan, kasir, pesanan WA, DP, diskon, retur, pembatalan, nota 80mm/A4, nota publik, riwayat kendaraan, biaya, laporan + CSV, pengguna, audit log), docs.
### 2026-11-08 (pre-VPS fixes)
- yarn.lock, .env.example, .gitignore; prepaid WA order atomik; cancel wajib catat setiap pcs; 60/60 tes.
### 2026-11-08 (WhatsApp Fonnte)
- `wa_routes.py`: pengaturan owner (token terenkripsi/tersamar, ganti/hapus; nomor admin = draft CMS Kontak + tombol terbitkan), pesan percobaan, kirim nota job/sale/order, riwayat `wa_logs`, kunci per transaksi `wa_locks`, idempoten `send_key`, kirim ulang wajib alasan; status antre/ditolak/gagal/tidak_pasti.
- CMS Kontak: field WhatsApp read-only (dilindungi di backend saat simpan/pulihkan revisi).
- Frontend: `WhatsAppSettings.js`, `WaNota.js` (dialog pratinjau + kirim), `lib/wa.js` (+ jest test).
- Tes: 94/94 backend (Fonnte di-mock), 4/4 jest. conftest punya cadangan JWT bila password akun uji diubah lewat aplikasi.
### 2026-11-08 (perbaikan review Fonnte)
- Suite default terisolasi: conftest menyalakan uvicorn tes + DB `predator_pytest_*` sementara, akun berpassword acak, FONNTE_API_URL buntu; fallback JWT dihapus (login salah → gagal jelas). Tes live hanya-baca dipindah ke `tests_live/`. `requirements-dev.txt`, `pythonpath` di pytest.ini.
- Tautan nota memakai env `PUBLIC_SITE_URL` (compose: `https://${SITE_DOMAIN}`), bukan header Origin; kirim nota wajib `message_hash` dari pratinjau (409 jika isi berubah).
- `save_totals` kini bersyarat pada baris yang dibaca (memperbaiki total basi saat edit serentak, ditemukan tes paralel).
- Tes: clone bersih 90/90 (5x berturut-turut), jest 4/4.

### 2026-11-09 (Iterasi 7)
- Situs publik mode terang (Home, Pages, PublicLayout); menu mobile z-index diperbaiki.
- Reset Data khusus owner (`reset_routes.py`, `ResetData.js`) tanpa drop DB.
- Order WA terhubung Master Pelanggan + snapshot nama/HP/alamat saat order.
- COD hanya untuk ongkir; barang wajib lunas sebelum kirim.
- Produk induk + varian (items) dan impor Excel via openpyxl (`catalog_routes.py`, `ItemImport.js`); kolom cari bisa dikosongkan.
- Tes: backend 94/94, frontend testing agent 100% (iteration_7).

### 2026-11-09 (Iterasi 8)
- Impor Excel atomik: validasi seluruh file (nama sama/kode beda, spasi & huruf besar/kecil, SKU/varian ganda, campuran baris sederhana/varian, bentrok DB); Simpan = transaksi MongoDB (replica set) dengan pemeriksaan ulang + plan_hash; 409 bila data berubah; tanpa replica set Simpan ditolak 503. Docker mongo `--replSet rs0` + healthcheck rs.initiate; `MONGO_URL ...?replicaSet=rs0`; restore.sh cek PRIMARY; `scripts/test-replset.sh` (uji integrasi container sementara). Indeks unik baru: products.name_key, items(product_id, variant_key); koleksi baru `locks`, `deleted_records`.
- Hapus khusus owner (`delete_routes.py`): cek referensi semua status (nota/penjualan/pesanan/retur/klaim/rusak/mutasi transaksi/paket), stok >0 ditolak, arsip + audit, konfirmasi ketik nama; Nonaktifkan barang/produk/paket/akun; barang & paket nonaktif ditolak di transaksi baru.
- Sidebar grup buka/tutup + satu menu Pengaturan (tab WhatsApp & Reset Data); /admin/reset-data dialihkan.
- Produk sederhana (tanpa varian) default; Tambah Varian opsional; SKU otomatis; produk sederhana → varian: barang lama jadi varian pertama (ID/SKU/stok tetap).
- Paket: field merek/model dihapus dari form; Opsi Paket: Tambah barang / Ganti komponen (replaces) dengan selisih harga; opsi bertentangan ditolak; komponen terpasang disnapshot di nota.
- Tes: backend 114 passed pada replica set nyata (port 27018), standalone 109 passed + tes RS di-skip; frontend testing agent 100% (iteration_8) pada stack terisolasi localhost:3001/8002.

## Prioritized backlog
- P0: Owner menjalankan `./scripts/test-replset.sh` di VPS lalu migrasi Docker ke replica set sebelum impor data asli.
- P1: Ubah opsi paket lama (mode "Tambah barang") menjadi "Ganti komponen" bila memang upgrade.
- P0: Uji kirim nyata dengan token & perangkat Fonnte milik owner.
- P1: Isi data asli via CMS (alamat, jam, logo, foto, layanan) — tugas konten owner.
- P1: Server-side meta tags (SSR/prerender) untuk pratinjau tautan.
- P2: Cek status pengiriman Fonnte (webhook/status pesan) untuk menampilkan "terkirim/dibaca".
- P2: Pemilih tanggal berformat Indonesia; migrasi data lama; pecah tx_routes.py.

## Next tasks
Owner uji manual alur iterasi 8 lalu deploy VPS dengan replica set.
