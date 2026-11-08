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

## Prioritized backlog
- P0: Uji kirim nyata dengan token & perangkat Fonnte milik owner.
- P1: Isi data asli via CMS (alamat, jam, logo, foto, layanan) — tugas konten owner.
- P1: Server-side meta tags (SSR/prerender) untuk pratinjau tautan.
- P2: Cek status pengiriman Fonnte (webhook/status pesan) untuk menampilkan "terkirim/dibaca".
- P2: Pemilih tanggal berformat Indonesia; migrasi data lama; pecah tx_routes.py.

## Next tasks
Owner mengisi token & nomor admin, kirim pesan percobaan ke nomor sendiri, lalu coba kirim satu nota.
