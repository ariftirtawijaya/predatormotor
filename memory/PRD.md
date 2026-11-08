# PRD — Predator Autolight Bojonegoro

## Original problem statement
Saya ingin Anda membangun website publik, CMS, dan sistem operasional bengkel untuk Predator Autolight Bojonegoro. Usaha ini memasang lampu serta aksesoris kelistrikan kendaraan, menjual barang langsung di bengkel, dan menerima pesanan langsung melalui WhatsApp. (Brief lengkap 16 bagian: arsitektur portabel ke VPS; website publik Tailwind modern + dashboard admin terang; CMS terstruktur penuh dengan draft/pratinjau/terbit/riwayat; stok bengkel terpisah dari marketplace; peran owner/admin/kasir di backend; pelanggan/kendaraan & riwayat wajib; status pekerjaan hanya Masuk/Selesai; paket & snapshot nota; penjualan langsung; pesanan WA dengan aturan COD Jawa; garansi; mutasi stok & audit; DP/pembatalan/retur; nota + tombol WhatsApp; laporan rinci + CSV/PDF; keamanan; dokumentasi deploy, backup, restore; skenario uji.)

User choices: diskon disetujui owner dari dashboard; nota thermal 80 mm (utama) + A4; warna aksen website diatur dari admin; garansi default: tanpa garansi sampai diatur per barang/paket.

## Architecture
React 19 + Tailwind (public dark site w/ CMS accent var; admin light) · FastAPI (core, auth_routes, cms_routes, master_routes, tx_routes, report_routes) · MongoDB · local disk uploads · JWT httpOnly cookie auth (bcrypt) · Docker Compose (mongo, backend, Caddy w/ auto HTTPS) · scripts/backup.sh & restore.sh.

## User personas
Owner (Mas Latif) — semua modul, laporan laba, persetujuan diskon, pembatalan. Admin — barang, stok, paket, CMS. Kasir — pelanggan, pekerjaan, penjualan, pesanan WA, pembayaran.

## What's been implemented (2026-11-08)
- Public site: beranda (section CMS terurut), profil, layanan & paket, katalog, galeri sebelum/sesudah, kontak + peta, halaman custom /p/slug, tombol WA melayang, SEO meta per halaman, pratinjau draft.
- CMS: 11 bagian (identitas, navigasi, beranda, profil, layanan, katalog, galeri, kontak, footer, SEO, halaman), draft/pratinjau/terbit/buang draft, riwayat + pulihkan, media library (validasi & re-encode gambar).
- Operasional: master barang, paket (komponen + opsi), stok masuk/opname/koreksi/rusak/internal, mutasi append-only, nota pekerjaan & garansi, kasir POS, pesanan WA (COD Jawa), DP/pelunasan, diskon dengan persetujuan owner, retur & pembatalan, nota 80mm/A4, link nota publik bertoken, kirim WA, riwayat kendaraan, biaya operasional, laporan (omzet, kas, COD, DP, piutang, HPP, laba kotor/bersih) + CSV, pengguna, audit log.
- Docs: README (local, VPS, HTTPS, backup/restore, update, owner pertama), TESTING.md (17 skenario, 37/37 test lulus), .env.example.

## Prioritized backlog
- P1: Isi data asli via CMS (WA, alamat, jam, logo, foto, layanan) — tugas konten owner.
- P1: Server-side meta tags untuk pratinjau tautan (SSR/prerender) agar OG tampil di WhatsApp/Facebook.
- P2: Pemilih tanggal berformat Indonesia (saat ini input tanggal bawaan browser).
- P2: Migrasi data dari source lama jika diberikan.
- P2: Pecah tx_routes.py menjadi beberapa modul.

## Next tasks
Tunggu masukan owner setelah mencoba alur kasir & CMS.

## Update 2026-11-08 (pre-VPS fixes)
- frontend/yarn.lock committed; .env.example (root/backend/frontend) tracked; .gitignore updated (uploads, backups, test_reports ignored); test creds moved out of source (rotated).
- Prepaid WA order: stock deducted before settling payment is recorded (409 & no payment if stock short); ship requires stock_applied; per-nota pay_lock prevents double/over payment; cancel shares lock.
- Order cancel requires every pcs accounted (layak/rusak/belum_kembali); outstanding items shown and receivable later.
- Tests: 60/60 backend; clean-clone yarn build + pip install + README steps verified; Docker compose not runnable in pod.
