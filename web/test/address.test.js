import assert from "node:assert/strict";
import { test } from "node:test";

import { toChomeQuery } from "../js/address.js";

test("hyphenated block and house numbers become a chome", () => {
  assert.equal(toChomeQuery("高円寺南3-22-1"), "高円寺南3丁目");
  assert.equal(toChomeQuery("高円寺南３－２２－１"), "高円寺南3丁目");
  assert.equal(toChomeQuery("東京都杉並区高円寺南3-22"), "杉並区高円寺南3丁目");
});

test("anything after 丁目 is dropped", () => {
  assert.equal(toChomeQuery("高円寺南3丁目22番1号"), "高円寺南3丁目");
  assert.equal(toChomeQuery("高円寺南三丁目22-1"), "高円寺南三丁目");
});

test("lot numbers without a chome are dropped", () => {
  assert.equal(toChomeQuery("大泉町1234番地"), "大泉町");
  assert.equal(toChomeQuery("大泉町1234番5"), "大泉町");
});

test("place names that contain 番 or no numbers are kept", () => {
  assert.equal(toChomeQuery("千代田区三番町"), "千代田区三番町");
  assert.equal(toChomeQuery("こうえんじ"), "こうえんじ");
  assert.equal(toChomeQuery("高円寺"), "高円寺");
});
