# Skenario Pengujian & Hasil (2026-11-08)

Dijalankan otomatis: `cd backend && python -m pytest tests/ -q -n 0` → **37 lulus / 37** (setelah perbaikan iterasi 2), ditambah pengujian UI otomatis (Playwright) desktop 1920px & ponsel 390px.

| # | Skenario | Hasil |
|---|---|---|
| 1 | Beberapa nota pekerjaan Masuk disimpan bersamaan, muncul di daftar Masuk, bisa dibuka lagi | Lulus |
| 2 | Paket BiLED + opsi Shroud RGB: Selesai mengurangi komponen tepat sekali (BiLED −2, Shroud −2, Relay −1, RGB −2); 3 permintaan Selesai bersamaan / ulang tidak memotong lagi | Lulus |
| 3 | Kasir boleh tambah baris; ubah/hapus baris lama oleh kasir → 403; admin bisa dengan alasan + audit; edit admin & tambah kasir bersamaan tidak saling menimpa | Lulus |
| 4 | Diskon diajukan kasir → menunggu; Selesai diblokir saat menunggu; owner setujui; diskon yang membuat total < uang dibayar ditolak | Lulus |
| 5 | DP lalu pelunasan; pembayaran berlebih ditolak; idem_key sama dua kali tercatat sekali; omzet tidak ganda | Lulus |
| 6 | Pembatalan nota ber-DP oleh owner dengan pengembalian sebagian; DP ditahan tercatat; kasir/admin 403; laba kotor tidak terpengaruh | Lulus |
| 7 | Penjualan langsung per pembeli, idempoten, stok kurang → 409, rekap harian otomatis | Lulus |
| 8 | Satu stok bengkel terpakai oleh pekerjaan, penjualan, dan pesanan WA | Lulus |
| 9 | Pesanan WA prabayar ke Bali: COD ditolak; stok berkurang hanya saat lunas; kirim diblokir sebelum lunas | Lulus |
| 10 | COD ke Jawa Timur: stok berkurang saat dikirim; tampil di "COD belum cair"; uang hanya dihitung saat dana cair | Lulus |
| 11 | Retur: barang layak menambah stok, rusak masuk Barang Rusak; transaksi asli tetap; paket COD kembali → status Kembali, tagihan COD dihapus dari omzet bersih (sekali, tanpa ongkir) | Lulus |
| 12 | Klaim garansi: nota NG- terhubung ke nota & item awal; pengganti Rp0 mengurangi stok; perbaikan saja tidak mengubah stok; klaim ke-2 tercatat; tampil di riwayat kendaraan; klaim atas baris yang dihapus ditolak | Lulus |
| 13 | Koreksi stok wajib alasan + log mutasi + audit; opname; stok tidak bisa negatif | Lulus |
| 14 | Pembatasan akses: kasir tidak bisa laporan/CMS/barang/koreksi; admin tidak bisa laporan/diskon/pengguna; modal tidak dikirim ke kasir | Lulus |
| 15 | CMS: edit hero → simpan draft (publik belum berubah) → pratinjau (banner) → terbitkan (publik berubah); ubah nomor WA → tombol WA publik memakai nomor baru; tambah layanan tampil di /layanan; ubah urutan bagian; riwayat & pulihkan; pratinjau tanpa login ditolak; tautan `javascript:` & `//domain` ditolak | Lulus |
| 16 | Unggah media (gambar valid diterima, non-gambar ditolak); foto galeri hanya tampil bila tampil + izin + plat disamarkan | Lulus |
| 17 | UI: kasir → nota modal; nota baru → tambah paket → Selesai; formulir pesanan (opsi COD hanya provinsi Jawa); cetak 80 mm & A4; Kirim via WhatsApp membuka wa.me; laporan & unduh CSV; tampilan ponsel | Lulus |

Data uji yang dibuat selama pengujian sudah dihapus.

## Pembaruan sebelum deploy VPS (2026-11-08)

Suite backend: `python -m pytest tests/ -q -n 0` → **60 lulus / 60** (diuji ulang oleh agen penguji independen, iterasi 3–5).

| # | Skenario | Hasil |
|---|---|---|
| 18 | Prabayar, stok kurang saat pelunasan → 409, pembayaran TIDAK tercatat, stok tetap, tidak bisa dikirim; setelah stok ditambah, pelunasan berhasil & stok terpotong sekali | Lulus |
| 19 | Prabayar dengan DP, unit terakhir terjual di kasir, pelunasan → 409, dibayar tetap DP, tidak bisa dikirim | Lulus |
| 20 | Permintaan pelunasan diulang (idem_key sama) dan 4–6 permintaan serentak → 1 pembayaran, 1 potong stok | Lulus |
| 21 | Pembayaran serentak dengan kunci berbeda (dua kasir/tab) → tidak ada kelebihan bayar (pesanan & nota pekerjaan) | Lulus |
| 22 | Batal pesanan yang stoknya terpotong: tanpa barang / jumlah kurang / lebih / kondisi tidak valid → ditolak dengan rincian selisih; data tidak berubah | Lulus |
| 23 | Batal campuran 1 layak + 1 rusak + 1 belum kembali → stok +1, catatan rusak 1, "barang belum kembali" 1 pcs tampil; saat barang datang dicatat layak → stok +1, status tetap Batal | Lulus |
| 24 | Pembayaran vs pembatalan serentak (24× pesanan, 24× nota) → tidak pernah ada pembayaran masuk pada nota Batal, refund tidak melebihi uang diterima | Lulus |
| 25 | Input batal yang rusak (tanpa item_id, qty bukan angka/0) → 422, tidak ada error 500 | Lulus |
| 26 | Clone git bersih: `yarn install --frozen-lockfile` + `yarn build` berhasil; backend venv baru `pip install -r requirements-prod.txt`, `.env` dari `.env.example`, `create_owner.py`, login, data kosong, CMS terinisialisasi | Lulus |
| 27 | `docker compose up -d --build` | **Belum dijalankan** — Docker tidak tersedia di lingkungan Emergent; jalankan di VPS | Yang tersisa di lingkungan preview: akun owner, akun uji admin/kasir, dan barang/paket berawalan `[TEST]` dari `seed_demo.py`.
