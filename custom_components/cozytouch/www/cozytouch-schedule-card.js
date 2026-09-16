/*
 * Cozytouch schedule card : a week of a device's own weekly program, painted
 * by the hour and written back through cozytouch.set_schedule.
 *
 * The program lives in the device, not in Home Assistant, so what this draws
 * is what runs when Home Assistant is off.
 */

const DAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

// The device stores ten slots a day, unused ones being [0,0]. Mirrors
// MAX_SLOTS in services.py; the service refuses anything longer anyway.
const MAX_SLOTS = 10;

const LABELS = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

const STYLE = `
  ha-card { padding: 12px 16px 16px; }
  h2 { font-size: 16px; font-weight: 500; margin: 4px 0 12px;
       text-transform: capitalize; }
  .bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
         margin-bottom: 12px; }
  .swatch { width: 30px; height: 28px; border-radius: 4px; cursor: pointer;
            border: 2px solid transparent; font-size: 11px; color: #222;
            display: flex; align-items: center; justify-content: center; }
  .swatch.on { border-color: var(--primary-text-color); }
  input[type=number] { width: 62px; padding: 4px; }
  button { cursor: pointer; border-radius: 4px; padding: 5px 10px;
           border: 1px solid var(--divider-color);
           background: var(--card-background-color);
           color: var(--primary-text-color); font-size: 13px; }
  button.on { background: var(--primary-color); color: var(--text-primary-color); }
  button[disabled] { opacity: .45; cursor: default; }
  .grid { display: grid; grid-template-columns: 34px repeat(24, 1fr) 26px;
          gap: 1px; }
  .hour { font-size: 9px; text-align: center; white-space: nowrap;
          color: var(--secondary-text-color); }
  .day { font-size: 11px; line-height: 22px; color: var(--secondary-text-color); }
  .cell { height: 22px; cursor: pointer; }
  .cell:hover { outline: 2px solid var(--primary-text-color); outline-offset: -2px; }
  .copy { font-size: 13px; line-height: 22px; text-align: center; cursor: pointer;
          color: var(--secondary-text-color); }
  .foot { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
  .msg { font-size: 12px; flex: 1; }
  .msg.error { color: var(--error-color); }
  .msg.ok { color: var(--success-color, green); }
  .msg.warn { color: var(--warning-color, orange); }
`;

const toMinutes = (hhmm) => {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
};

const toClock = (minutes) =>
  `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(
    minutes % 60
  ).padStart(2, "0")}`;

/* The setpoint a day holds at a minute, which is the last slot before it. */
export const inChargeAt = (slots, minute) => {
  let held = null;
  for (const slot of slots) {
    if (toMinutes(slot.time) <= minute) held = slot.temperature;
  }
  return held;
};

/* Painting an hour owns that hour : anything already starting inside it is
 * replaced, so a cell and a slot stay the same thing. Erasing 00:00 is
 * refused for the reason build_matrix refuses it -- the beginning of a day
 * must have a setpoint.
 *
 * Pure, and exported, so tests/test_schedule_card.mjs can hold it to that
 * without a browser.
 */
export const applyPaint = (slots, hour, temperature) => {
  const start = hour * 60;
  const kept = slots.filter(
    (slot) => toMinutes(slot.time) < start || toMinutes(slot.time) >= start + 60
  );

  if (temperature === null) {
    if (hour === 0) {
      throw new Error("00:00 must keep a setpoint : repaint it instead");
    }
    return kept;
  }

  if (kept.length + 1 > MAX_SLOTS) {
    throw new Error(`A day holds ${MAX_SLOTS} slots at most`);
  }

  return [...kept, { time: toClock(start), temperature }].sort(
    (a, b) => toMinutes(a.time) - toMinutes(b.time)
  );
};

// The card's base in a browser, and something importable outside one : the
// pure helpers above are held to their rules by tests/test_schedule_card.mjs,
// which runs in node and has no DOM.
const CardBase = typeof HTMLElement === "undefined" ? class {} : HTMLElement;

class CozytouchScheduleCard extends CardBase {
  setConfig(config) {
    if (!config.entity) {
      throw new Error("cozytouch-schedule-card needs an `entity`");
    }
    this._config = {
      program: "heating",
      min: 5,
      max: 30,
      step: 1,
      ...config,
    };
    this._days = null;
    this._dirty = new Set();
    this._brush = null;
    this._erasing = false;
    this._status = "";
  }

  /* Rendering is driven by edits, not by state changes : a rebuild on every
   * poll would take the focus out of the brush while somebody is typing. */
  set hass(hass) {
    this._hass = hass;
    if (this._days === null) this._load();
  }

  getCardSize() {
    return 8;
  }

  async _load() {
    this._days = {};
    try {
      const result = await this._hass.callWS({
        type: "call_service",
        domain: "cozytouch",
        service: "get_schedule",
        service_data: { program: this._config.program },
        target: { entity_id: this._config.entity },
        return_response: true,
      });
      this._days = result.response[this._config.entity].days;
      this._brush = this._temperaturesInUse()[0] ?? 19;
    } catch (err) {
      this._status = `error|${err.message || err}`;
    }
    this._render();
  }

  _temperaturesInUse() {
    const seen = new Set();
    for (const slots of Object.values(this._days || {})) {
      for (const slot of slots) seen.add(slot.temperature);
    }
    return [...seen].sort((a, b) => a - b);
  }

  /* Blue where it is coldest, red where it is warmest, across whatever this
   * program actually spans rather than across the config's min and max --
   * a week between 19 and 21 would otherwise be seven shades of the same. */
  _colour(temperature) {
    if (temperature === null) return "var(--divider-color)";
    const used = this._temperaturesInUse();
    const low = Math.min(...used, temperature);
    const high = Math.max(...used, temperature);
    const ratio = high === low ? 0.5 : (temperature - low) / (high - low);
    return `hsl(${210 - 200 * ratio}, 70%, ${72 - 16 * ratio}%)`;
  }

  _paint(day, hour) {
    try {
      this._days[day] = applyPaint(
        this._days[day] || [],
        hour,
        this._erasing ? null : this._brush
      );
    } catch (err) {
      this._status = `warn|${err.message}`;
      return this._render();
    }

    this._dirty.add(day);
    this._status = "";
    this._render();
  }

  _copyTo(day, targets) {
    for (const target of targets) {
      if (target === day) continue;
      this._days[target] = this._days[day].map((slot) => ({ ...slot }));
      this._dirty.add(target);
    }
    this._status = "";
    this._render();
  }

  async _save() {
    this._status = "busy|Writing…";
    this._render();
    try {
      for (const day of this._dirty) {
        await this._hass.callService("cozytouch", "set_schedule", {
          entity_id: this._config.entity,
          program: this._config.program,
          days: [day],
          slots: this._days[day],
        });
      }
      this._dirty.clear();
      this._status = "ok|Written to the device";
    } catch (err) {
      this._status = `error|${err.message || err}`;
    }
    this._render();
  }

  _render() {
    if (!this._shadow) this._shadow = this.attachShadow({ mode: "open" });

    const [kind, message] = this._status.split("|");
    const days = DAYS.filter((day) => this._days[day]);
    const title = this._config.title || `${this._config.program} program`;

    this._shadow.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <h2>${title}</h2>
        ${days.length === 0 ? this._empty(kind, message) : this._week(days, kind, message)}
      </ha-card>`;

    this._bind(days);
  }

  _empty(kind, message) {
    return `<div class="msg ${kind || ""}">${message || "Loading…"}</div>`;
  }

  _week(days, kind, message) {
    const swatches = this._temperaturesInUse()
      .map((t) => {
        const on = t === this._brush && !this._erasing ? "on" : "";
        return `<div class="swatch ${on}" data-brush="${t}" style="background:${this._colour(t)}">${t}</div>`;
      })
      .join("");

    const hours = [...Array(24).keys()]
      .map((h) => `<div class="hour">${h % 3 === 0 ? h : ""}</div>`)
      .join("");

    const rows = days.map((day) => this._row(day)).join("");
    const pending = this._dirty.size;

    return `
      <div class="bar">
        ${swatches}
        <input type="number" id="brush" value="${this._brush}"
               min="${this._config.min}" max="${this._config.max}"
               step="${this._config.step}">
        <button id="erase" class="${this._erasing ? "on" : ""}">Erase</button>
      </div>
      <div class="grid">
        <div></div>${hours}<div></div>
        ${rows}
      </div>
      <div class="foot">
        <button id="save" ${pending ? "" : "disabled"}>Save${pending ? ` (${pending})` : ""}</button>
        <button id="reload">Reload</button>
        <div class="msg ${kind || ""}">${message || ""}</div>
      </div>`;
  }

  _row(day) {
    const cells = [...Array(24).keys()]
      .map((h) => {
        const t = inChargeAt(this._days[day], h * 60);
        const clock = `${String(h).padStart(2, "0")}:00`;
        const reads = t === null ? "—" : `${t} °C`;
        return `<div class="cell" data-day="${day}" data-hour="${h}"
                  title="${LABELS[day]} ${clock} — ${reads}"
                  style="background:${this._colour(t)}"></div>`;
      })
      .join("");

    return `<div class="day">${LABELS[day]}</div>${cells}
      <div class="copy" data-copy="${day}" title="Copy this day to the rest of the week">⧉</div>`;
  }

  _bind(days) {
    const root = this._shadow;

    root.querySelectorAll("[data-brush]").forEach((el) =>
      el.addEventListener("click", () => {
        this._brush = Number(el.dataset.brush);
        this._erasing = false;
        this._render();
      })
    );
    root.querySelectorAll(".cell").forEach((el) =>
      el.addEventListener("click", () =>
        this._paint(el.dataset.day, Number(el.dataset.hour))
      )
    );
    root.querySelectorAll("[data-copy]").forEach((el) =>
      el.addEventListener("click", () => this._copyTo(el.dataset.copy, days))
    );

    root.getElementById("brush")?.addEventListener("change", (event) => {
      this._brush = Number(event.target.value);
      this._erasing = false;
      this._render();
    });
    root.getElementById("erase")?.addEventListener("click", () => {
      this._erasing = !this._erasing;
      this._render();
    });
    root.getElementById("save")?.addEventListener("click", () => this._save());
    root.getElementById("reload")?.addEventListener("click", () => {
      this._days = null;
      this._dirty.clear();
      this._status = "";
      this.hass = this._hass;
    });
  }
}

// Guarded so the pure helpers above can be imported by node, which has
// neither a custom element registry nor a window.
if (typeof customElements !== "undefined") {
  customElements.define("cozytouch-schedule-card", CozytouchScheduleCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "cozytouch-schedule-card",
    name: "Cozytouch Schedule",
    description: "Paint a device's own weekly heating or cooling program",
  });
}
