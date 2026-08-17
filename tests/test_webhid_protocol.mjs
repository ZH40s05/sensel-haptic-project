#!/usr/bin/env node
// SPDX-License-Identifier: GPL-2.0-or-later
// Headless protocol test for tools/sensel-haptic-web.html.
//
// Runs the page's embedded JavaScript in a VM against a fake Sensel
// firmware that implements the register framing from
// docs/sensel-windows-reverse-engineering.md, then checks the protocol
// layer: framed reads/writes, checksums, save records, preview/commit
// register writes, and the release-ratio helpers.
//
// Requires node 18+. No browser or hardware needed.

"use strict";

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const html = readFileSync(join(root, "tools", "sensel-haptic-web.html"), "utf8");
const match = html.match(/<script>([\s\S]*)<\/script>/);
if (!match) throw new Error("no <script> block found in sensel-haptic-web.html");
let js = match[1];

// Export the protocol layer for testing; skip the boot block that pokes
// the DOM. The page itself is unchanged — the bridge only exists here.
js = js.replace("if (!navigator.hid) {", "if (false) {");
js += "\n;globalThis.__exports = { SenselPipe, releaseForce, ratioFromRegisters," +
      " levelToRaw, rawToLevel, REG, readState, previewClickForce," +
      " commitClickForce, previewTpForce, commitTpForce, ui, currentDraft," +
      " applyState, refreshDirty };\n";

class FakeSensel {
  constructor() {
    this.regs = new Map([
      [0x0038, 82], [0x0090, 53],
      [0x0091, 38], [0x0092, 25], [0x0093, 38], [0x0094, 25],
      [0x0095, 38], [0x0096, 25],
      [0x008a, 1], [0x00ab, 100],
    ]);
    this.listeners = [];
    this.sent = [];
  }

  addEventListener(_type, fn) { this.listeners.push(fn); }
  removeEventListener(_type, _fn) {}

  async sendReport(id, data) {
    if (id !== 9) throw new Error(`unexpected report id ${id}`);
    this.sent.push(data);
    const payload = Array.from(data.slice(1, 1 + data[0]));
    const [first, addrLow, size] = payload;
    const address = (((first & ~0x80) << 7) & 0x3f00) | addrLow;
    const rest = payload.slice(3);
    const respond = (bytes) => {
      const out = new Uint8Array(20);
      out[0] = bytes.length;
      out.set(bytes, 1);
      const view = new DataView(out.buffer);
      for (const fn of this.listeners) fn({ reportId: 9, data: view });
    };
    if (first & 0x80) {
      const body = Array.from({ length: size }, (_, i) => this.regs.get(address + i) ?? 0);
      const sum = body.reduce((a, b) => a + b, 0) & 0xff;
      respond([0x01, 0x00, size & 0xff, size >> 8, ...body, sum]);
    } else {
      const body = rest.slice(0, size);
      const checksum = rest[size];
      if ((body.reduce((a, b) => a + b, 0) & 0xff) !== checksum) {
        respond([0x05, 0x01]);  // bad checksum -> NACK
        return;
      }
      for (let i = 0; i < size; i++) this.regs.set(address + i, body[i]);
      respond([0x05, 0x00]);
    }
  }
}

function makeElement() {
  return {
    value: "5", checked: false, textContent: "", className: "",
    disabled: false, dataset: {},
    classList: { add() {}, remove() {} },
    addEventListener() {},
  };
}

const elements = {};
const documentStub = {
  getElementById: (id) => (elements[id] ??= makeElement()),
  querySelector: () => null,
  querySelectorAll: () => [],
};

const context = {
  navigator: { hid: {}, language: "zh-CN" },
  document: documentStub,
  console, setTimeout, clearTimeout,
};
context.globalThis = context;
vm.createContext(context);
vm.runInContext(js, context);

const E = context.__exports;
const failures = [];
function check(condition, label) {
  if (condition) {
    console.log(`ok - ${label}`);
  } else {
    failures.push(label);
    console.error(`FAIL - ${label}`);
  }
}

const fake = new FakeSensel();
const pipe = new E.SenselPipe(fake);

try {
  // Framed register read.
  const intensity = await pipe.readRegister(E.REG.INTENSITY, 1);
  check(intensity[0] === 100, "framed register read returns value");

  // RAM-only write (preview).
  await pipe.writeRegister(E.REG.INTENSITY, [55], false);
  check(fake.regs.get(E.REG.INTENSITY) === 55, "persist=false write changes RAM");

  // Persisted write emits a UserSetting save record to 0x0230.
  const before = fake.sent.length;
  await pipe.writeRegister(E.REG.CLICK_DOWN, [60], true);
  check(fake.regs.get(E.REG.CLICK_DOWN) === 60, "persist=true write applied");
  const saveReport = fake.sent.slice(before).find((report) => {
    const p = Array.from(report.slice(1, 1 + report[0]));
    const addr = (((p[0] & ~0x80) << 7) & 0x3f00) | p[1];
    return addr === 0x0230;
  });
  check(Boolean(saveReport), "save record sent to 0x0230");
  if (saveReport) {
    const record = Array.from(saveReport.slice(1, 1 + saveReport[0])).slice(3);
    check(
      record[0] === 0x38 && record[1] === 0x00 &&
      record[2] === 0x00 && record[3] === 0x40 && record[4] === 0x51,
      "save record payload is <address><0x4000><0x51>",
    );
  }

  // Full state read recovers the release ratio from the register pair.
  const state = await E.readState(pipe);
  check(state.intensity === 55 && state.clickForce === 60,
    "readState returns all values");
  check(state.clickRatio === 88,
    `release ratio recovered from registers (${state.clickRatio}%)`);

  // Preview click force: down=90 at 80% -> up=72.
  await E.previewClickForce(pipe, 90, 80);
  check(fake.regs.get(0x0038) === 90 && fake.regs.get(0x0090) === 72,
    "previewClickForce writes down and up registers");

  // Commit TrackPoint force: six registers, six interleaved saves.
  fake.sent.length = 0;
  await E.commitTpForce(pipe, 50, 40);
  check(fake.regs.get(0x0091) === 50 && fake.regs.get(0x0096) === 20,
    "commitTpForce writes all six registers");
  const saves = fake.sent.filter((report) => {
    const p = Array.from(report.slice(1, 1 + report[0]));
    const addr = (((p[0] & ~0x80) << 7) & 0x3f00) | p[1];
    return addr === 0x0230;
  });
  check(saves.length === 6, `six interleaved save records (${saves.length})`);

  // Pure helpers.
  check(E.releaseForce(1, 5) === 1 && E.releaseForce(95, 65) === 62,
    "releaseForce clamps and computes");
  check(E.ratioFromRegisters(95, 62) === 65 && E.ratioFromRegisters(60, 60) === 100,
    "ratioFromRegisters round-trips and clamps");
  check(E.levelToRaw(5) === 71 && E.rawToLevel(71) === 5,
    "intensity level mapping");

  // Reset must work from a clean, non-default state and leave the saved
  // baseline untouched until Save is pressed.
  E.ui.pipe = pipe;
  E.ui.device = fake;
  E.ui.loaded = true;
  E.ui.saving = false;
  E.ui.previewing = false;
  const nonDefault = {
    intensity: 55, clickForce: 90, clickRatio: 80,
    tpForce: 50, tpRatio: 40, tpButtons: true,
  };
  E.ui.saved = nonDefault;
  E.applyState(nonDefault);
  E.refreshDirty();
  check(!E.ui.dirty, "clean non-default state starts clean");
  await context.document.getElementById("reset-btn").onclick();
  check(E.currentDraft().intensity === 100 && E.currentDraft().clickForce === 60 &&
        E.currentDraft().clickRatio === 65 && E.currentDraft().tpForce === 120 &&
        E.currentDraft().tpRatio === 65 && E.currentDraft().tpButtons === true,
        "reset applies the complete default draft from a clean state");
  check(E.ui.dirty && E.ui.saved === nonDefault,
    "reset marks the draft dirty without changing the saved baseline");

  // Resetting back to an already-saved default must clear dirty state.
  const defaults = {
    intensity: 100, clickForce: 60, clickRatio: 65,
    tpForce: 120, tpRatio: 65, tpButtons: true,
  };
  E.ui.saved = defaults;
  E.applyState({
    intensity: 55, clickForce: 90, clickRatio: 80,
    tpForce: 50, tpRatio: 40, tpButtons: false,
  });
  E.refreshDirty();
  await context.document.getElementById("reset-btn").onclick();
  check(!E.ui.dirty &&
        context.document.getElementById("save-btn").disabled &&
        context.document.getElementById("cancel-btn").disabled,
        "reset clears dirty state when defaults are already saved");
} finally {
  pipe.close();
}

if (failures.length) {
  console.error(`${failures.length} check(s) failed`);
  process.exit(1);
}
console.log("All WebHID protocol checks passed.");
