const ICON_OPTS = [["wrench", "Kunci"], ["shield", "Perisai"], ["message", "Chat"], ["zap", "Petir"], ["bulb", "Lampu"], ["clock", "Jam"], ["star", "Bintang"], ["award", "Penghargaan"]];
const LINK_HINT = "Contoh: /layanan, /kontak, #whatsapp (buka WhatsApp), atau https://…";

export const SECTION_TYPES = {
  hero: { label: "Hero (bagian atas)", fields: [
    { k: "title", label: "Judul", type: "text" }, { k: "subtitle", label: "Subjudul", type: "textarea" },
    { k: "image", label: "Gambar latar", type: "image" },
    { k: "cta_label", label: "Teks tombol utama", type: "text" }, { k: "cta_link", label: "Tautan tombol utama", type: "text", hint: LINK_HINT },
    { k: "cta2_label", label: "Teks tombol kedua", type: "text" }, { k: "cta2_link", label: "Tautan tombol kedua", type: "text", hint: LINK_HINT }] },
  features: { label: "Keunggulan", fields: [{ k: "title", label: "Judul", type: "text" },
    { k: "items", label: "Daftar keunggulan", type: "list", itemLabel: "title", fields: [{ k: "title", label: "Judul", type: "text" }, { k: "desc", label: "Deskripsi", type: "textarea" }, { k: "icon", label: "Ikon", type: "select", options: ICON_OPTS }] }] },
  stats: { label: "Statistik", fields: [{ k: "items", label: "Angka", type: "list", itemLabel: "label", hint: "Isi hanya dengan angka yang benar.", fields: [{ k: "value", label: "Angka", type: "text" }, { k: "label", label: "Keterangan", type: "text" }] }] },
  services: { label: "Layanan unggulan", fields: [{ k: "title", label: "Judul", type: "text" }, { k: "subtitle", label: "Subjudul", type: "text" }], hint: "Menampilkan layanan berjenis 'Layanan' yang ditandai unggulan dan tampil." },
  packages: { label: "Paket unggulan", fields: [{ k: "title", label: "Judul", type: "text" }, { k: "subtitle", label: "Subjudul", type: "text" }], hint: "Menampilkan item berjenis 'Paket' yang ditandai unggulan dan tampil." },
  testimonials: { label: "Testimoni", fields: [{ k: "title", label: "Judul", type: "text" },
    { k: "items", label: "Testimoni", type: "list", itemLabel: "name", fields: [{ k: "name", label: "Nama", type: "text" }, { k: "vehicle", label: "Kendaraan", type: "text" }, { k: "text", label: "Isi", type: "textarea" }] }] },
  gallery: { label: "Galeri pilihan", fields: [{ k: "title", label: "Judul", type: "text" }, { k: "subtitle", label: "Subjudul", type: "text" }], hint: "Menampilkan 6 foto galeri pertama yang tampil." },
  faq: { label: "FAQ", fields: [{ k: "title", label: "Judul", type: "text" },
    { k: "items", label: "Pertanyaan", type: "list", itemLabel: "q", fields: [{ k: "q", label: "Pertanyaan", type: "text" }, { k: "a", label: "Jawaban", type: "textarea" }] }] },
  cta: { label: "Ajakan menghubungi", fields: [{ k: "title", label: "Judul", type: "text" }, { k: "text", label: "Teks", type: "textarea" }, { k: "button_label", label: "Teks tombol", type: "text" }] },
};

export const CMS_SCHEMA = {
  identity: { label: "Identitas usaha", fields: [
    { k: "name", label: "Nama usaha", type: "text" }, { k: "slogan", label: "Slogan", type: "text" }, { k: "short_desc", label: "Deskripsi singkat", type: "textarea" },
    { k: "logo", label: "Logo", type: "image" }, { k: "favicon", label: "Favicon (PNG/ICO persegi)", type: "image" },
    { k: "accent_color", label: "Warna aksen website", type: "color", hint: "Dipakai untuk tombol & sorotan. Latar website tetap gelap agar kontras terjaga." },
    { k: "default_image", label: "Gambar default (berbagi tautan / hero)", type: "image" }] },
  navigation: { label: "Navigasi", fields: [
    { k: "items", label: "Menu", type: "list", itemLabel: "label", fields: [{ k: "label", label: "Teks menu", type: "text" }, { k: "href", label: "Tautan", type: "text", hint: LINK_HINT }, { k: "enabled", label: "Aktif", type: "toggle" }] },
    { k: "cta_label", label: "Teks tombol utama di menu", type: "text" }, { k: "cta_href", label: "Tautan tombol utama", type: "text", hint: LINK_HINT }] },
  home: { label: "Beranda", fields: [{ k: "sections", label: "Bagian halaman", type: "sections" }] },
  profile: { label: "Profil usaha", fields: [
    { k: "title", label: "Judul", type: "text" }, { k: "story", label: "Cerita usaha", type: "textarea", rows: 8 }, { k: "image", label: "Foto usaha", type: "image" },
    { k: "highlights", label: "Poin layanan", type: "list", itemLabel: "title", fields: [{ k: "title", label: "Judul", type: "text" }, { k: "text", label: "Teks", type: "textarea" }] },
    { k: "team", label: "Tim (opsional)", type: "list", itemLabel: "name", fields: [{ k: "name", label: "Nama", type: "text" }, { k: "role", label: "Peran", type: "text" }, { k: "photo", label: "Foto", type: "image" }] }] },
  services: { label: "Layanan & paket publik", fields: [
    { k: "items", label: "Layanan / paket", type: "list", itemLabel: "title", hint: "Hanya item dengan 'Tampil di website' yang terlihat pengunjung. Paket bengkel internal tidak otomatis tampil.", fields: [
      { k: "title", label: "Judul", type: "text" }, { k: "kind", label: "Jenis", type: "select", options: [["paket", "Paket"], ["layanan", "Layanan"]] },
      { k: "slug", label: "Slug (otomatis aman)", type: "text" }, { k: "description", label: "Deskripsi", type: "textarea" }, { k: "image", label: "Foto", type: "image" },
      { k: "price", label: "Harga (angka, opsional)", type: "number" }, { k: "price_text", label: "Teks harga (mis. 'Mulai Rp…')", type: "text" },
      { k: "features", label: "Termasuk", type: "list", itemLabel: "text", fields: [{ k: "text", label: "Fitur", type: "text" }] },
      { k: "addons", label: "Tambahan pilihan", type: "list", itemLabel: "name", fields: [{ k: "name", label: "Nama", type: "text" }, { k: "price_text", label: "Harga", type: "text" }] },
      { k: "featured", label: "Unggulan di beranda", type: "toggle" }, { k: "visible", label: "Tampil di website", type: "toggle" }] }] },
  catalog: { label: "Katalog publik", fields: [
    { k: "categories", label: "Kategori", type: "list", itemLabel: "name", fields: [{ k: "name", label: "Nama kategori", type: "text" }] },
    { k: "products", label: "Produk", type: "list", itemLabel: "name", hint: "Barang inventaris tidak otomatis tampil; tambahkan di sini dan aktifkan 'Tampil'.", fields: [
      { k: "name", label: "Nama", type: "text" }, { k: "category", label: "Kategori", type: "catref" }, { k: "item_ref", label: "Referensi master barang (internal)", type: "itemref" },
      { k: "description", label: "Deskripsi", type: "textarea" }, { k: "image", label: "Foto", type: "image" }, { k: "price_text", label: "Harga yang boleh tampil", type: "text" },
      { k: "label", label: "Label (mis. Baru, Best seller)", type: "text" },
      { k: "variants", label: "Variasi", type: "list", itemLabel: "name", fields: [{ k: "name", label: "Variasi", type: "text" }, { k: "price_text", label: "Harga", type: "text" }] },
      { k: "visible", label: "Tampil di website", type: "toggle" }] }] },
  gallery: { label: "Galeri", fields: [
    { k: "albums", label: "Album", type: "list", itemLabel: "name", fields: [{ k: "name", label: "Nama album", type: "text" }] },
    { k: "items", label: "Foto pekerjaan", type: "list", itemLabel: "title", hint: "Foto hanya tampil jika: Tampil + Izin pelanggan + Plat sudah disamarkan.", fields: [
      { k: "title", label: "Judul", type: "text" }, { k: "album", label: "Album", type: "albumref" }, { k: "description", label: "Deskripsi pekerjaan", type: "textarea" },
      { k: "image", label: "Foto utama", type: "image" }, { k: "before_image", label: "Foto sebelum (opsional)", type: "image" }, { k: "after_image", label: "Foto sesudah (opsional)", type: "image" },
      { k: "consent", label: "Pelanggan mengizinkan publikasi", type: "toggle" }, { k: "plate_masked", label: "Plat nomor sudah disamarkan / tidak terlihat", type: "toggle" },
      { k: "visible", label: "Tampil di website", type: "toggle" }] }] },
  contact: { label: "Kontak", fields: [
    { k: "whatsapp", label: "Nomor WhatsApp tujuan", type: "readonly", hint: "Diubah oleh owner di menu Pengaturan · WhatsApp (tetap lewat draft → pratinjau → terbitkan)." },
    { k: "wa_message", label: "Pesan awal WhatsApp", type: "textarea" }, { k: "address", label: "Alamat", type: "textarea" },
    { k: "phone", label: "Telepon", type: "text" }, { k: "email", label: "Email", type: "text" },
    { k: "hours", label: "Jam operasional", type: "list", itemLabel: "day", fields: [{ k: "day", label: "Hari", type: "text" }, { k: "time", label: "Jam", type: "text" }] },
    { k: "map_link", label: "Tautan Google Maps", type: "text" }, { k: "map_embed", label: "URL embed peta (https://www.google.com/maps/embed?…)", type: "text" },
    { k: "socials", label: "Media sosial", type: "list", itemLabel: "platform", fields: [{ k: "platform", label: "Platform", type: "text" }, { k: "url", label: "URL", type: "text" }] }] },
  footer: { label: "Footer", fields: [
    { k: "text", label: "Teks footer", type: "textarea" }, { k: "copyright", label: "Hak cipta", type: "text" },
    { k: "links", label: "Tautan", type: "list", itemLabel: "label", fields: [{ k: "label", label: "Teks", type: "text" }, { k: "href", label: "Tautan", type: "text", hint: LINK_HINT }] }] },
  seo: { label: "SEO & berbagi tautan", fields: [
    { k: "pages", label: "Per halaman", type: "list", itemLabel: "page", fixed: true, fields: [
      { k: "page", label: "Halaman", type: "readonly" }, { k: "title", label: "Judul SEO", type: "text" }, { k: "description", label: "Deskripsi SEO", type: "textarea" },
      { k: "og_image", label: "Gambar Open Graph", type: "image" }, { k: "noindex", label: "Jangan diindeks mesin pencari", type: "toggle" }] }] },
  pages: { label: "Halaman informasi lain", fields: [
    { k: "items", label: "Halaman", type: "list", itemLabel: "title", hint: "Alamat halaman: /p/slug. Tambahkan tautannya di Navigasi bila perlu.", fields: [
      { k: "title", label: "Judul", type: "text" }, { k: "slug", label: "Slug", type: "text" }, { k: "image", label: "Gambar", type: "image" },
      { k: "body", label: "Isi (teks biasa, baris baru dipertahankan)", type: "textarea", rows: 8 }, { k: "visible", label: "Tampil", type: "toggle" }] }] },
};
