// Turn an address typed down to the block or house number into a chome-level query.
// places.json only has 町丁目 (ABR town names), so "高円寺南3-22-1" is searched as "高円寺南3丁目".

const DASH = "[-‐‑‒–—―－ー−]";

export function toChomeQuery(input) {
  let s = input.normalize("NFKC").replace(/\s+/g, "");
  s = s.replace(/^東京都/, "");
  if (s.includes("丁目")) return s.replace(/(丁目).*$/, "$1");
  // "高円寺南3-22-1" / "高円寺南3-22": the first number is the chome
  const hyphen = s.match(new RegExp(`^(\\D+)(\\d+)${DASH}\\d.*$`));
  if (hyphen) return `${hyphen[1]}${hyphen[2]}丁目`;
  // "大泉町1234番地" / "大泉町1234番5": lot numbers without a chome
  return s.replace(/^(\D+)\d+番.*$/, "$1");
}
