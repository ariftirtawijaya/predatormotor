import { normalizeWa, waStatus, hasActiveSend } from "./wa";

test("normalisasi nomor Indonesia ke 62…", () => {
  expect(normalizeWa("081234567890")).toBe("6281234567890");
  expect(normalizeWa("6281234567890")).toBe("6281234567890");
  expect(normalizeWa("+62 812-3456-7890")).toBe("6281234567890");
});

test("nomor tidak valid ditolak", () => {
  expect(normalizeWa("")).toBeNull();
  expect(normalizeWa("12345")).toBeNull();
  expect(normalizeWa("0812abc")).toBeNull();
  expect(normalizeWa("+1 555 123 4567")).toBeNull();
  expect(normalizeWa("62021234567")).toBeNull();
});

test("label status memakai istilah antrean, bukan terkirim", () => {
  expect(waStatus("antre").label).toMatch(/antrean/);
  expect(waStatus("antre").label).not.toMatch(/terkirim|sampai/i);
  expect(waStatus("tidak_pasti").label).toMatch(/Tidak pasti/);
});

test("kirim ulang hanya diperlukan bila ada pengiriman aktif", () => {
  expect(hasActiveSend([{ status: "gagal" }, { status: "ditolak" }])).toBe(false);
  expect(hasActiveSend([{ status: "antre" }])).toBe(true);
  expect(hasActiveSend([{ status: "tidak_pasti" }])).toBe(true);
});
