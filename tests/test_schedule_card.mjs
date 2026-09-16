/*
 * What the schedule card does to a day when somebody paints an hour.
 *
 * Run by hand -- `node --test tests/test_schedule_card.mjs` -- since CI has
 * no javascript job. The rest of the suite is python.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  applyPaint,
  inChargeAt,
} from "../custom_components/cozytouch/www/cozytouch-schedule-card.js";

const DAY = [
  { time: "00:00", temperature: 17 },
  { time: "07:30", temperature: 21 },
  { time: "22:00", temperature: 17 },
];

test("a setpoint holds until the next slot takes over", () => {
  assert.equal(inChargeAt(DAY, 0), 17);
  assert.equal(inChargeAt(DAY, 7 * 60), 17);
  assert.equal(inChargeAt(DAY, 7 * 60 + 30), 21);
  assert.equal(inChargeAt(DAY, 21 * 60), 21);
  assert.equal(inChargeAt(DAY, 23 * 60), 17);
});

test("nothing is in charge before the first slot", () => {
  assert.equal(inChargeAt([{ time: "06:00", temperature: 19 }], 0), null);
});

test("painting an hour replaces whatever started inside it", () => {
  assert.deepEqual(applyPaint(DAY, 7, 19), [
    { time: "00:00", temperature: 17 },
    { time: "07:00", temperature: 19 },
    { time: "22:00", temperature: 17 },
  ]);
});

test("painting an untouched hour adds a slot, in order", () => {
  assert.deepEqual(applyPaint(DAY, 12, 23), [
    { time: "00:00", temperature: 17 },
    { time: "07:30", temperature: 21 },
    { time: "12:00", temperature: 23 },
    { time: "22:00", temperature: 17 },
  ]);
});

test("erasing an hour drops the slot that started in it", () => {
  assert.deepEqual(applyPaint(DAY, 7, null), [
    { time: "00:00", temperature: 17 },
    { time: "22:00", temperature: 17 },
  ]);
});

test("erasing an hour that holds no slot changes nothing", () => {
  assert.deepEqual(applyPaint(DAY, 12, null), DAY);
});

test("00:00 cannot be erased", () => {
  assert.throws(() => applyPaint(DAY, 0, null), /00:00/);
});

test("00:00 can be repainted", () => {
  assert.equal(applyPaint(DAY, 0, 18)[0].temperature, 18);
});

test("a day refuses an eleventh slot", () => {
  const full = Array.from({ length: 10 }, (_, index) => ({
    time: `${String(index).padStart(2, "0")}:00`,
    temperature: 20,
  }));
  assert.throws(() => applyPaint(full, 20, 21), /10 slots/);
  // Replacing one of the ten is still allowed.
  assert.equal(applyPaint(full, 5, 21).length, 10);
});

test("painting leaves the original untouched", () => {
  const before = JSON.stringify(DAY);
  applyPaint(DAY, 9, 25);
  assert.equal(JSON.stringify(DAY), before);
});
