# Akses Login Internal Predator Autolight

Penjelasan cara masuk ke dashboard internal (Owner, Admin, Kasir) dan cara mengganti password owner.
Tidak ada fitur baru yang dibangun. Isinya hanya petunjuk akses dan satu langkah untuk mengamankan akun.

## Untuk siapa
- Owner (ainkarip@gmail.com), yang akan login pertama kali lalu mengganti password.
- Nantinya Admin dan Kasir, yang akunnya dibuat oleh Owner.

## Fitur inti & pengalaman
- Halaman login internal (preview): https://predator-led--6ee1x2sq.preview.emergentagent.com/admin
- Halaman login internal (setelah di VPS): https://[domain-anda]/admin
- Akun owner: ainkarip@gmail.com, dengan password sementara Predator-Own-EusLgfhHvwd6dC.
- Password lama "PredatorOwner#2026" sudah tidak berlaku karena diganti saat perbaikan keamanan.
- Menu ganti password tersedia di dashboard setelah login.

## Alur pengguna
1. Buka alamat /admin.
2. Masukkan email dan password sementara.
3. Setelah masuk, buka menu ganti password, isi password lama dan password baru, lalu simpan.
4. Untuk VPS: akun owner dibuat terpisah saat instalasi dengan password pilihan Anda sendiri. Password preview tidak ikut terbawa.

## Nuansa UI/UX
- Dashboard internal memakai tampilan terang dan bersih, terpisah dari website publik yang bertema gelap.

## Tahapan
- Fase 1 (sekarang): login dengan password sementara, lalu ganti password sendiri. Tidak ada perubahan kode.
- Fase 2: membantu deploy ke VPS dan membuat akun owner produksi.
- Fase 3: migrasi data lama Predator Autolight, jika data sumbernya diberikan.

## Asumsi
- Password sementara hanya berlaku di versi preview.
- Halaman /admin sengaja tidak ditautkan dari website publik.
