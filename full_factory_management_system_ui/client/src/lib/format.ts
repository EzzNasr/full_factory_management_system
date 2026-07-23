export const fmtEGP = (val: number) =>
  "EGP " + (val ?? 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });