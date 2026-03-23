/**
 * NYC Sanitation — Home Assistant sidebar panel
 */
const WS_GET_COLLECTION = "nyc_sanitation/get_collection_data";
const WS_GET_TTS_OPTIONS = "nyc_sanitation/get_tts_options";
const WS_SET_TTS_OPTIONS = "nyc_sanitation/set_tts_options";
const WS_TEST_TTS = "nyc_sanitation/test_tts";

const POLL_MS = 60_000;

const WEEK_ORDER = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/** @param {number} h24 */
function hour24to12Parts(h24) {
  const h = Math.max(0, Math.min(23, Math.floor(h24)));
  if (h === 0) return { h12: 12, ampm: "am" };
  if (h < 12) return { h12: h, ampm: "am" };
  if (h === 12) return { h12: 12, ampm: "pm" };
  return { h12: h - 12, ampm: "pm" };
}

/** Stored exclusive end E: reminders run while local hour H satisfies start <= H < E (E = 24 → through hour 23). */
function hourExclusiveEndToDisplayParts(endExclusive) {
  const e = Math.max(1, Math.min(24, Math.floor(endExclusive)));
  if (e === 24) return { h12: 12, ampm: "am" };
  return hour24to12Parts(e);
}

/** User picks clock time as first excluded hour (e.g. 8 PM → E = 20). */
function hour12ToExclusiveEnd(h12, ampm) {
  const h = parseInt(String(h12), 10);
  if (!Number.isFinite(h) || h < 1 || h > 12) return 20;
  const isPm = ampm === "pm";
  let h24;
  if (h === 12 && !isPm) h24 = 0;
  else if (h === 12 && isPm) h24 = 12;
  else if (isPm) h24 = h + 12;
  else h24 = h;
  if (h24 === 0) return 24;
  return Math.min(24, h24);
}

/** @param {number} h12 @param {"am"|"pm"} ampm */
function hour12To24(h12, ampm) {
  const h = parseInt(String(h12), 10);
  if (!Number.isFinite(h) || h < 1 || h > 12) return 12;
  const isPm = ampm === "pm";
  if (h === 12 && !isPm) return 0;
  if (h === 12 && isPm) return 12;
  if (isPm) return h + 12;
  return h;
}

/** Next weekday in Mon→Sun cycle (Sunday wraps to Monday). */
function nextWeekdayInOrder(day) {
  const i = WEEK_ORDER.indexOf(day);
  if (i < 0) return null;
  return WEEK_ORDER[(i + 1) % WEEK_ORDER.length];
}

class NycSanitationPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._panel = null;
    this._data = null;
    this._loading = true;
    this._pollTimer = null;
    this._didInitialLoad = false;
    /** @type {"main"|"settings"} */
    this._view = "main";
    this._ttsLoading = false;
    this._ttsOptions = null;
    this._ttsTomorrowTypes = [];
    this._ttsPreviewMessage = "";
    this._mediaPlayers = [];
    this._ttsEntities = [];
    this._ttsLoadError = null;
    this._ttsSaveError = null;
    this._ttsValidationError = null;
    this._ttsTestError = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.isConnected) return;
    if (!this._pollTimer) {
      this._pollTimer = setInterval(() => this._loadData(), POLL_MS);
    }
    if (hass && !this._didInitialLoad) {
      this._didInitialLoad = true;
      this._loadData();
    }
    if (this._view === "main") {
      this._render();
    }
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    this._render();
    if (!this._pollTimer) {
      this._pollTimer = setInterval(() => this._loadData(), POLL_MS);
    }
    if (this._hass && !this._didInitialLoad) {
      this._didInitialLoad = true;
      this._loadData();
    }
  }

  disconnectedCallback() {
    if (this._pollTimer != null) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    this._didInitialLoad = false;
    this._view = "main";
  }

  async _loadData() {
    if (!this._hass) return;
    this._loading = true;
    if (this._view === "main") {
      this._render();
    }
    try {
      this._data = await this._hass.callWS({ type: WS_GET_COLLECTION });
    } catch (e) {
      console.error("NYC Sanitation panel WS error", e);
      this._data = {
        nyc_valid: false,
        error: "Could not load data",
        weekly: {},
        routing: {},
      };
    } finally {
      this._loading = false;
      if (this._view === "main") {
        this._render();
      }
    }
  }

  _isAdmin() {
    return this._hass?.user?.is_admin === true;
  }

  async _openSettings() {
    if (!this._hass || !this._isAdmin()) return;
    this._view = "settings";
    this._ttsLoading = true;
    this._ttsLoadError = null;
    this._ttsSaveError = null;
    this._ttsValidationError = null;
    this._ttsTestError = null;
    this._ttsOptions = null;
    this._render();
    try {
      const res = await this._hass.callWS({ type: WS_GET_TTS_OPTIONS });
      this._ttsOptions = res.options || {};
      this._ttsTomorrowTypes = res.tomorrow_types || [];
      this._ttsPreviewMessage = res.preview_message || "";
      this._mediaPlayers = res.media_players || [];
      this._ttsEntities = res.tts_entities || [];
    } catch (e) {
      this._ttsLoadError =
        e?.message || String(e) || "Could not load TTS settings";
      console.error("NYC Sanitation get_tts_options", e);
    } finally {
      this._ttsLoading = false;
      this._render();
    }
  }

  async _reloadTtsAndCollection() {
    await this._loadData();
    if (this._view !== "settings" || !this._hass) return;
    try {
      const res = await this._hass.callWS({ type: WS_GET_TTS_OPTIONS });
      this._ttsOptions = res.options || {};
      this._ttsTomorrowTypes = res.tomorrow_types || [];
      this._ttsPreviewMessage = res.preview_message || "";
      this._mediaPlayers = res.media_players || [];
      this._ttsEntities = res.tts_entities || [];
    } catch (e) {
      console.error("NYC Sanitation refresh TTS options", e);
    }
    this._render();
  }

  _closeSettings() {
    this._view = "main";
    this._ttsLoadError = null;
    this._ttsSaveError = null;
    this._ttsValidationError = null;
    this._ttsTestError = null;
    this._render();
  }

  _readSelect(root, id) {
    return root.querySelector(id)?.value ?? "";
  }

  _readNum(root, id, fallback) {
    const n = parseInt(root.querySelector(id)?.value ?? "", 10);
    return Number.isFinite(n) ? n : fallback;
  }

  async _saveTtsSettings(ev) {
    ev?.preventDefault?.();
    if (!this._hass) return;
    const root = this.shadowRoot;
    const enabled = root.querySelector("#tts-enabled")?.checked === true;

    const startH = hour12To24(
      this._readNum(root, "#tts-start-hour", 12),
      this._readSelect(root, "#tts-start-ampm") === "pm" ? "pm" : "am"
    );
    const endExclusive = hour12ToExclusiveEnd(
      this._readNum(root, "#tts-end-hour", 8),
      this._readSelect(root, "#tts-end-ampm") === "pm" ? "pm" : "am"
    );

    this._ttsValidationError = null;
    if (startH >= endExclusive) {
      this._ttsValidationError =
        "Start time must be before end time (same calendar day).";
      this._render();
      return;
    }

    const interval = this._readNum(root, "#tts-interval", 1);
    const minute = Math.max(
      0,
      Math.min(59, this._readNum(root, "#tts-minute-offset", 0))
    );
    const mediaPlayer =
      root.querySelector("#tts-media-player")?.value?.trim() ?? "";
    const ttsEntity = root.querySelector("#tts-tts-entity")?.value?.trim() ?? "";
    const volSlider = root.querySelector("#tts-volume-slider");
    const volumeApply = root.querySelector("#tts-volume-apply")?.checked === true;
    let volume = null;
    if (volumeApply && volSlider) {
      const v = Number(volSlider.value);
      if (!Number.isNaN(v)) volume = Math.min(1, Math.max(0, v));
    }

    const ttsCache = root.querySelector("#tts-cache")?.checked !== false;
    const ttsLanguage = root.querySelector("#tts-language")?.value?.trim() ?? "";
    let ttsOptionsRaw = root.querySelector("#tts-options-json")?.value ?? "";
    ttsOptionsRaw = String(ttsOptionsRaw).trim();
    let ttsOptionsPayload = null;
    if (ttsOptionsRaw) {
      try {
        ttsOptionsPayload = JSON.parse(ttsOptionsRaw);
        if (typeof ttsOptionsPayload !== "object" || ttsOptionsPayload === null) {
          this._ttsValidationError = "TTS options must be a JSON object.";
          this._render();
          return;
        }
      } catch {
        this._ttsValidationError = "TTS options must be valid JSON.";
        this._render();
        return;
      }
    }

    const prefix = root.querySelector("#tts-prefix")?.value ?? "";
    const msgTrash = root.querySelector("#tts-msg-trash")?.value ?? "";
    const msgRec = root.querySelector("#tts-msg-recycling")?.value ?? "";
    const msgCompost = root.querySelector("#tts-msg-compost")?.value ?? "";
    const msgBulk = root.querySelector("#tts-msg-large")?.value ?? "";
    const msgMixed = root.querySelector("#tts-msg-mixed")?.value ?? "";

    this._ttsSaveError = null;
    this._render();
    try {
      const payload = {
        type: WS_SET_TTS_OPTIONS,
        tts_enabled: enabled,
        tts_window_start_hour: startH,
        tts_window_end_hour: endExclusive,
        tts_interval_hours: Math.min(4, Math.max(1, interval)),
        tts_minute_offset: minute,
        media_player_entity_id: mediaPlayer,
        tts_entity_id: ttsEntity,
        volume,
        tts_cache: ttsCache,
        tts_language: ttsLanguage,
        tts_options: ttsOptionsPayload,
        tts_message_prefix: prefix,
        tts_message_trash: msgTrash,
        tts_message_recycling: msgRec,
        tts_message_compost: msgCompost,
        tts_message_large_items: msgBulk,
        tts_message_mixed: msgMixed,
      };
      const res = await this._hass.callWS(payload);
      this._ttsOptions = res.options || this._ttsOptions;
      this._ttsSaveError = null;
      try {
        const again = await this._hass.callWS({ type: WS_GET_TTS_OPTIONS });
        this._ttsPreviewMessage = again.preview_message || "";
        this._ttsTomorrowTypes = again.tomorrow_types || [];
      } catch {
        /* ignore */
      }
    } catch (e) {
      this._ttsSaveError =
        e?.message || String(e) || "Could not save settings";
      console.error("NYC Sanitation set_tts_options", e);
    }
    this._render();
  }

  async _testTts() {
    if (!this._hass) return;
    this._ttsTestError = null;
    this._render();
    try {
      await this._hass.callWS({ type: WS_TEST_TTS });
    } catch (e) {
      this._ttsTestError = e?.message || String(e) || "TTS test failed";
      console.error("NYC Sanitation test_tts", e);
    }
    this._render();
  }

  _toggleSidebar() {
    const event = new Event("hass-toggle-menu", { bubbles: true, composed: true });
    this.dispatchEvent(event);
  }

  _attachListeners() {
    const menuBtn = this.shadowRoot.querySelector("#menu-btn");
    if (menuBtn) {
      menuBtn.onclick = () => this._toggleSidebar();
    }
    const settingsBtn = this.shadowRoot.querySelector("#settings-btn");
    if (settingsBtn) {
      settingsBtn.onclick = () => this._openSettings();
    }
    this.shadowRoot.querySelectorAll(".js-settings-back").forEach((btn) => {
      btn.onclick = () => this._closeSettings();
    });
    const saveBtn = this.shadowRoot.querySelector("#tts-save");
    if (saveBtn) saveBtn.onclick = (ev) => this._saveTtsSettings(ev);
    const testBtn = this.shadowRoot.querySelector("#tts-test");
    if (testBtn) testBtn.onclick = () => this._testTts();
    const refreshBtn = this.shadowRoot.querySelector("#refresh-now-btn");
    if (refreshBtn) refreshBtn.onclick = () => this._reloadTtsAndCollection();
    const volSlider = this.shadowRoot.querySelector("#tts-volume-slider");
    const volLabel = this.shadowRoot.querySelector("#tts-volume-label");
    if (volSlider && volLabel) {
      volSlider.oninput = () => {
        volLabel.textContent = String(Number(volSlider.value).toFixed(2));
      };
    }
  }

  _todayName() {
    if (!this._hass) return "";
    const tz = this._hass.config?.time_zone;
    if (tz) {
      try {
        return new Intl.DateTimeFormat("en-US", {
          timeZone: tz,
          weekday: "long",
        }).format(new Date());
      } catch {
        /* fall through */
      }
    }
    const days = [
      "Sunday",
      "Monday",
      "Tuesday",
      "Wednesday",
      "Thursday",
      "Friday",
      "Saturday",
    ];
    return days[new Date().getDay()];
  }

  _renderWeekly() {
    if (this._loading) {
      return `<div class="muted center">Loading schedule…</div>`;
    }
    const data = this._data || {};
    if (!data.nyc_valid) {
      return `
        <div class="notice">
          <h2>NYC only</h2>
          <p>Sorry — this panel only works for New York City residences. Set your Home Assistant home location to a NYC address (or adjust the map pin) and reload.</p>
          ${data.error ? `<p class="muted">${this._escape(data.error)}</p>` : ""}
        </div>
      `;
    }

    const today = this._todayName();
    const weekly = data.weekly || {};

    const cols = WEEK_ORDER.map((day) => {
      const nextDay = nextWeekdayInOrder(day);
      const nextTypes = nextDay ? weekly[nextDay] || [] : [];
      const curbsideHint =
        nextTypes.length > 0
          ? `<div class="curbside-hint small muted">Prepare waste curbside for collection.</div>`
          : "";
      return `
      <div class="day-col ${day === today ? "today" : ""}">
        <div class="day-head">${day.slice(0, 3)}</div>
        <div class="day-body">
          ${this._chipsHtml(weekly[day] || [])}
          ${curbsideHint}
        </div>
      </div>
    `;
    }).join("");

    return `<div class="week-strip" role="region" aria-label="Weekly collection schedule"><div class="week-grid">${cols}</div></div>`;
  }

  _chipsHtml(types) {
    if (!types.length) {
      return `<span class="muted small">—</span>`;
    }
    return types
      .map((t) => {
        const cls = {
          Trash: "chip trash",
          Recycling: "chip recycling",
          Compost: "chip compost",
          "Large items": "chip bulk",
        }[t] || "chip";
        return `<span class="${cls}">${this._escape(t)}</span>`;
      })
      .join("");
  }

  _renderRouting() {
    const data = this._data || {};
    if (!data.nyc_valid) return "";
    const r = data.routing || {};
    return `
      <div class="card routing">
        <h3>Enforcement routing times</h3>
        <div class="routing-row">
          <span class="label">Residential</span>
          <span>${this._escape(r.residential || "—")}</span>
        </div>
        <div class="routing-row">
          <span class="label">Commercial</span>
          <span>${this._escape(r.commercial || "—")}</span>
        </div>
        <div class="routing-row">
          <span class="label">Mixed-use</span>
          <span>${this._escape(r.mixed_use || "—")}</span>
        </div>
      </div>
    `;
  }

  _renderMeta() {
    const data = this._data || {};
    if (!data.nyc_valid) return "";
    const parts = [];
    if (data.formatted_address) {
      parts.push(`<div class="addr">${this._escape(data.formatted_address)}</div>`);
    }
    if (data.community_board) {
      parts.push(
        `<div class="muted small">Community board: ${this._escape(data.community_board)}</div>`
      );
    }
    return parts.length ? `<div class="meta">${parts.join("")}</div>` : "";
  }

  _escape(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  _hourOptions12(selected) {
    let html = "";
    for (let h = 1; h <= 12; h += 1) {
      html += `<option value="${h}" ${h === selected ? "selected" : ""}>${h}</option>`;
    }
    return html;
  }

  _entitySelectOptions(entities, currentId) {
    const rows = Array.isArray(entities) ? entities : [];
    const seen = new Set();
    let html = `<option value="">Select an entity…</option>`;
    for (const row of rows) {
      const id = row.entity_id || "";
      seen.add(id);
      const label = this._escape(row.name ? `${row.name} (${id})` : id);
      const sel = id === currentId ? " selected" : "";
      html += `<option value="${this._escape(id)}"${sel}>${label}</option>`;
    }
    if (currentId && !seen.has(currentId)) {
      html += `<option value="${this._escape(currentId)}" selected>${this._escape(currentId)}</option>`;
    }
    return html;
  }

  _renderSettingsView() {
    const o = this._ttsOptions || {};
    const startH = Number.isFinite(o.tts_window_start_hour)
      ? o.tts_window_start_hour
      : 12;
    const endEx = Number.isFinite(o.tts_window_end_hour)
      ? o.tts_window_end_hour
      : 20;
    const startParts = hour24to12Parts(startH);
    const endParts = hourExclusiveEndToDisplayParts(endEx);
    const interval = Number.isFinite(o.tts_interval_hours)
      ? o.tts_interval_hours
      : 1;
    const minute = Number.isFinite(o.tts_minute_offset)
      ? o.tts_minute_offset
      : 0;
    const mp = o.media_player_entity_id || "";
    const tts = o.tts_entity_id || "";
    const vol =
      o.volume != null && o.volume !== ""
        ? Math.min(1, Math.max(0, Number(o.volume)))
        : 0.5;
    const volumeApply = o.volume != null && o.volume !== "";
    const ttsCache = o.tts_cache !== false;
    const lang = this._escape(o.tts_language || "");
    const optsJson =
      o.tts_options && typeof o.tts_options === "object"
        ? this._escape(JSON.stringify(o.tts_options, null, 2))
        : "";

    const previewTypes =
      this._ttsTomorrowTypes && this._ttsTomorrowTypes.length
        ? this._escape(this._ttsTomorrowTypes.join(", "))
        : "None (tomorrow)";
    const previewMsg = this._escape(
      this._ttsPreviewMessage || "(No pickup tomorrow or no preview)"
    );

    if (this._ttsLoading) {
      return `<div class="settings-body muted center pad">Loading…</div>`;
    }
    if (this._ttsLoadError) {
      return `<div class="settings-body"><div class="form-error pad">${this._escape(this._ttsLoadError)}</div>
        <button type="button" class="btn secondary js-settings-back">Back</button></div>`;
    }

    const enabled = o.tts_enabled === true;
    const i1 = interval === 1 ? "selected" : "";
    const i2 = interval === 2 ? "selected" : "";
    const i3 = interval === 3 ? "selected" : "";
    const i4 = interval === 4 ? "selected" : "";
    const startAm = startParts.ampm === "pm" ? "" : "selected";
    const startPm = startParts.ampm === "pm" ? "selected" : "";
    const endAm = endParts.ampm === "pm" ? "" : "selected";
    const endPm = endParts.ampm === "pm" ? "selected" : "";

    return `
      <div class="settings-body">
        <p class="muted small settings-lead">
          When reminders are enabled, Home Assistant checks on a repeating schedule (within the time window). If <strong>tomorrow</strong> has a DSNY pickup, it waits until the media player is <strong>idle</strong>, sets volume (if set), waits for <strong>idle</strong> again, then calls <code>tts.speak</code> (admin only).
        </p>
        <div class="preview-block muted small">
          <div>Tomorrow’s collections (preview): <strong>${previewTypes}</strong></div>
          <div class="preview-msg">Spoken preview: <strong>${previewMsg}</strong></div>
        </div>
        <div class="form-error" id="tts-validation-error" style="display:${this._ttsValidationError ? "block" : "none"}">${this._ttsValidationError ? this._escape(this._ttsValidationError) : ""}</div>
        <form id="tts-form" class="tts-form">
          <label class="check-row">
            <input type="checkbox" id="tts-enabled" ${enabled ? "checked" : ""} />
            <span>Enable reminders</span>
          </label>

          <fieldset class="fieldset">
            <legend>Active window (local time)</legend>
            <p class="muted small fieldset-hint">End is when reminders stop (half-open). Example: 12 PM–8 PM → last eligible hour is 7 PM at your minute.</p>
            <div class="tts-row2">
              <div class="tts-cell">
                <span class="sub-label">Start</span>
                <div class="time-inline">
                  <select id="tts-start-hour" aria-label="Start hour">${this._hourOptions12(startParts.h12)}</select>
                  <select id="tts-start-ampm" aria-label="Start AM or PM">
                    <option value="am" ${startAm}>AM</option>
                    <option value="pm" ${startPm}>PM</option>
                  </select>
                </div>
              </div>
              <div class="tts-cell">
                <span class="sub-label">End</span>
                <div class="time-inline">
                  <select id="tts-end-hour" aria-label="End hour">${this._hourOptions12(endParts.h12)}</select>
                  <select id="tts-end-ampm" aria-label="End AM or PM">
                    <option value="am" ${endAm}>AM</option>
                    <option value="pm" ${endPm}>PM</option>
                  </select>
                </div>
              </div>
            </div>
          </fieldset>

          <div class="tts-row2">
            <div class="field-row compact">
              <label for="tts-interval">Repeat every</label>
              <select id="tts-interval">
                <option value="1" ${i1}>1 hour</option>
                <option value="2" ${i2}>2 hours</option>
                <option value="3" ${i3}>3 hours</option>
                <option value="4" ${i4}>4 hours</option>
              </select>
            </div>
            <div class="field-row compact">
              <label for="tts-minute-offset">Minute (0–59)</label>
              <input type="number" id="tts-minute-offset" min="0" max="59" value="${minute}" />
              <span class="muted small">e.g. 32 → …:32</span>
            </div>
          </div>

          <div class="field-row">
            <label for="tts-media-player">Media player</label>
            <select id="tts-media-player">${this._entitySelectOptions(this._mediaPlayers, mp)}</select>
          </div>
          <div class="field-row">
            <label for="tts-tts-entity">TTS engine</label>
            <select id="tts-tts-entity">${this._entitySelectOptions(this._ttsEntities, tts)}</select>
          </div>

          <div class="tts-row2 tts-vol-cache">
            <div class="field-row compact">
              <div class="vol-head">
                <label for="tts-volume-slider">Volume</label>
                <label class="inline-check"><input type="checkbox" id="tts-volume-apply" ${volumeApply ? "checked" : ""} /> Apply before speak</label>
              </div>
              <div class="slider-row">
                <input type="range" id="tts-volume-slider" min="0" max="1" step="0.01" value="${vol}" />
                <span id="tts-volume-label" class="vol-label">${vol.toFixed(2)}</span>
              </div>
            </div>
            <div class="field-row compact tts-cache-cell">
              <label class="check-row tight flush"><input type="checkbox" id="tts-cache" ${ttsCache ? "checked" : ""} /><span>Cache (tts.speak)</span></label>
            </div>
          </div>

          <div class="tts-row2">
            <div class="field-row compact">
              <label for="tts-language">Language</label>
              <input type="text" id="tts-language" placeholder="optional, e.g. en" value="${lang}" autocomplete="off" />
            </div>
            <div class="field-row compact">
              <label for="tts-options-json">Options JSON</label>
              <textarea id="tts-options-json" rows="3" placeholder="{}" spellcheck="false">${optsJson}</textarea>
            </div>
          </div>

          <fieldset class="fieldset">
            <legend>Message templates</legend>
            <p class="muted small tpl-hint">Placeholders include <code>{curb_reminder}</code>, <code>{type_status}</code>, <code>{routing_first_start}</code>, <code>{large_items_note}</code>, <code>{weekday}</code>, <code>{types_sentence}</code>, …</p>
            <div class="template-grid">
              <div class="field-row tpl-full">
                <label for="tts-prefix">Prefix</label>
                <input type="text" id="tts-prefix" value="${this._escape(o.tts_message_prefix || "")}" autocomplete="off" />
              </div>
              <div class="field-row">
                <label for="tts-msg-trash">Trash only</label>
                <textarea id="tts-msg-trash" rows="2" spellcheck="false">${this._escape(o.tts_message_trash || "")}</textarea>
              </div>
              <div class="field-row">
                <label for="tts-msg-recycling">Recycling only</label>
                <textarea id="tts-msg-recycling" rows="2" spellcheck="false">${this._escape(o.tts_message_recycling || "")}</textarea>
              </div>
              <div class="field-row">
                <label for="tts-msg-compost">Compost only</label>
                <textarea id="tts-msg-compost" rows="2" spellcheck="false">${this._escape(o.tts_message_compost || "")}</textarea>
              </div>
              <div class="field-row">
                <label for="tts-msg-large">Large items only</label>
                <textarea id="tts-msg-large" rows="2" spellcheck="false">${this._escape(o.tts_message_large_items || "")}</textarea>
              </div>
              <div class="field-row tpl-full">
                <label for="tts-msg-mixed">Multiple types</label>
                <textarea id="tts-msg-mixed" rows="2" spellcheck="false">${this._escape(o.tts_message_mixed || "")}</textarea>
              </div>
            </div>
          </fieldset>

          ${this._ttsSaveError ? `<div class="form-error">${this._escape(this._ttsSaveError)}</div>` : ""}
          ${this._ttsTestError ? `<div class="form-error">${this._escape(this._ttsTestError)}</div>` : ""}
        </form>
        <div class="settings-actions">
          <button type="button" class="btn secondary" id="refresh-now-btn">Refresh schedule</button>
          <button type="button" class="btn secondary" id="tts-test">Test announcement</button>
          <button type="button" class="btn secondary js-settings-back">Back</button>
          <button type="button" class="btn primary" id="tts-save">Save</button>
        </div>
      </div>
    `;
  }

  _render() {
    const title = "NYC Sanitation";
    const admin = this._isAdmin();
    const onSettings = this._view === "settings";

    const settingsBtn =
      admin && !onSettings
        ? `
          <button class="icon-btn" id="settings-btn" type="button" title="Settings" aria-label="Settings">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.68 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z"/></svg>
          </button>
        `
        : "";

    const backBtn =
      onSettings && admin
        ? `
        <button class="icon-btn js-settings-back" type="button" title="Back" aria-label="Back">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z"/></svg>
        </button>`
        : "";

    const toolbarTitle = onSettings ? "TTS settings" : title;

    const mainContent = !onSettings
      ? `
        <div class="content">
          ${this._renderMeta()}
          ${this._renderWeekly()}
          ${this._renderRouting()}
        </div>`
      : "";

    const settingsContent = onSettings && admin ? this._renderSettingsView() : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          box-sizing: border-box;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-family: var(--mdc-typography-body1-font-family, var(--paper-font-body1_-_font-family, Roboto, sans-serif));
          font-size: 14px;
          line-height: 1.45;
        }
        .shell {
          min-height: 100%;
          display: flex;
          flex-direction: column;
        }
        .toolbar {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 16px;
          background: var(--app-header-background-color, var(--primary-color));
          color: var(--app-header-text-color, var(--text-primary-color, #fff));
          flex-shrink: 0;
        }
        .toolbar h1 {
          margin: 0;
          font-size: 1.15rem;
          font-weight: 500;
          flex: 1;
        }
        .menu-btn {
          display: none;
          width: 40px;
          height: 40px;
          border-radius: 8px;
          border: none;
          background: transparent;
          color: inherit;
          cursor: pointer;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .menu-btn svg { width: 24px; height: 24px; fill: currentColor; }
        .menu-btn:hover { background: rgba(255,255,255,0.12); }
        @media (max-width: 870px) {
          .menu-btn { display: flex; }
        }
        .icon-btn {
          width: 40px;
          height: 40px;
          border-radius: 8px;
          border: none;
          background: rgba(255,255,255,0.15);
          color: inherit;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .icon-btn:hover { background: rgba(255,255,255,0.22); }
        .content {
          padding: 16px;
          flex: 1;
          overflow: auto;
        }
        .settings-scroll {
          flex: 1;
          overflow: auto;
          padding: 16px;
        }
        .settings-body { max-width: 640px; margin: 0 auto; }
        .settings-lead { margin: 0 0 12px; }
        .preview-block { margin-bottom: 16px; line-height: 1.5; }
        .preview-msg { margin-top: 8px; }
        .meta { margin-bottom: 16px; }
        .addr { font-weight: 500; margin-bottom: 4px; }
        .muted { color: var(--secondary-text-color); }
        .small { font-size: 12px; }
        .center { text-align: center; padding: 24px; }
        .pad { padding: 16px; }
        .notice {
          background: var(--card-background-color, rgba(0,0,0,0.05));
          border-radius: 12px;
          padding: 20px;
          border: 1px solid var(--divider-color);
        }
        .notice h2 { margin: 0 0 8px; font-size: 1.1rem; }
        .week-strip {
          margin-bottom: 20px;
          overflow-x: hidden;
          width: 100%;
        }
        .week-grid {
          display: grid;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          width: 100%;
          gap: clamp(3px, 1.1vw, 8px);
          box-sizing: border-box;
        }
        .day-col {
          background: var(--card-background-color, rgba(0,0,0,0.04));
          border-radius: clamp(6px, 1.5vw, 10px);
          border: 1px solid var(--divider-color);
          overflow: hidden;
          min-height: clamp(72px, 22vw, 120px);
          min-width: 0;
          display: flex;
          flex-direction: column;
        }
        .day-col.today {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 1px var(--primary-color);
        }
        .day-head {
          padding: clamp(4px, 1.2vw, 8px);
          text-align: center;
          font-weight: 600;
          font-size: clamp(9px, 2.4vw, 12px);
          text-transform: uppercase;
          letter-spacing: 0.03em;
          background: rgba(128,128,128,0.08);
          border-bottom: 1px solid var(--divider-color);
        }
        .day-body {
          padding: clamp(4px, 1.2vw, 8px);
          display: flex;
          flex-direction: column;
          gap: clamp(3px, 0.9vw, 6px);
          flex: 1;
          min-width: 0;
        }
        .curbside-hint {
          margin-top: 2px;
          font-size: clamp(7px, 1.9vw, 10px);
          line-height: 1.3;
          font-style: italic;
          overflow-wrap: anywhere;
          word-break: break-word;
        }
        .chip {
          display: block;
          font-size: clamp(8px, 2.1vw, 11px);
          padding: clamp(3px, 0.9vw, 6px) clamp(4px, 1.1vw, 8px);
          border-radius: clamp(4px, 1vw, 6px);
          border-left: clamp(2px, 0.6vw, 3px) solid var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 14%, transparent);
          overflow-wrap: anywhere;
          word-break: break-word;
        }
        .chip.trash { border-left-color: var(--primary-text-color); }
        .chip.recycling { border-left-color: var(--info-color, #039be5); }
        .chip.compost { border-left-color: var(--warning-color, #ffa600); }
        .chip.bulk { border-left-color: var(--secondary-text-color); }
        .card {
          background: var(--card-background-color, rgba(0,0,0,0.04));
          border-radius: 12px;
          padding: 16px;
          border: 1px solid var(--divider-color);
        }
        .routing h3 {
          margin: 0 0 12px;
          font-size: 1rem;
          font-weight: 600;
        }
        .routing-row {
          display: grid;
          grid-template-columns: 120px 1fr;
          gap: 8px;
          padding: 8px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        .routing-row:last-child { border-bottom: none; }
        .routing-row .label {
          color: var(--secondary-text-color);
          font-size: 13px;
        }
        .tts-form .field-row {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-bottom: 12px;
        }
        .tts-form .field-row.compact { margin-bottom: 0; }
        .tts-row2 {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px 16px;
          margin-bottom: 12px;
          align-items: start;
        }
        @media (max-width: 560px) {
          .tts-row2 { grid-template-columns: 1fr; }
        }
        .tts-cell .sub-label {
          display: block;
          font-size: 12px;
          font-weight: 600;
          margin-bottom: 4px;
          color: var(--secondary-text-color);
        }
        .time-inline {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          align-items: center;
        }
        .time-inline select { min-height: 44px; }
        .vol-head {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        .inline-check {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          font-weight: 500;
          cursor: pointer;
          white-space: nowrap;
        }
        .inline-check input { width: 16px; height: 16px; }
        .tts-cache-cell {
          display: flex;
          align-items: center;
          min-height: 44px;
        }
        .check-row.flush { margin-bottom: 0; min-height: 44px; }
        .template-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 10px;
        }
        @media (min-width: 720px) {
          .template-grid { grid-template-columns: 1fr 1fr; }
          .template-grid .tpl-full { grid-column: 1 / -1; }
        }
        .tpl-hint { margin-top: 0; margin-bottom: 10px; }
        .tts-form label { font-size: 13px; font-weight: 500; }
        .tts-form input[type="text"],
        .tts-form input[type="number"],
        .tts-form select,
        .tts-form textarea {
          padding: 10px 12px;
          border-radius: 8px;
          border: 1px solid var(--divider-color);
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
          min-height: 44px;
          box-sizing: border-box;
        }
        .tts-form textarea { min-height: 72px; font-family: inherit; }
        .fieldset {
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          padding: 12px;
          margin-bottom: 16px;
        }
        .fieldset legend { padding: 0 6px; font-weight: 600; }
        .fieldset-hint { margin: 0 0 10px; }
        .time-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 8px;
          margin-bottom: 10px;
        }
        .time-label { min-width: 48px; font-weight: 500; }
        .time-row select { min-height: 44px; }
        .slider-row {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .slider-row input[type="range"] { flex: 1; min-height: 44px; }
        .vol-label { min-width: 40px; font-variant-numeric: tabular-nums; }
        .check-row {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 16px;
          cursor: pointer;
          min-height: 44px;
        }
        .check-row input { width: 18px; height: 18px; }
        .check-row.tight { margin-bottom: 8px; min-height: 36px; }
        .form-error {
          color: var(--error-color, #db4437);
          font-size: 13px;
          margin: 8px 0;
        }
        .settings-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          justify-content: flex-end;
          margin-top: 20px;
          padding-bottom: 24px;
        }
        .btn {
          min-height: 44px;
          padding: 0 16px;
          border-radius: 8px;
          border: none;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
        }
        .btn.primary {
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
        }
        .btn.secondary {
          background: var(--card-background-color, rgba(128,128,128,0.15));
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
        }
        .btn:hover { filter: brightness(1.05); }
      </style>
      <div class="shell">
        <div class="toolbar">
          <button class="menu-btn" id="menu-btn" type="button" title="Menu" aria-label="Menu">
            <svg viewBox="0 0 24 24"><path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"/></svg>
          </button>
          ${backBtn}
          <h1>${toolbarTitle}</h1>
          ${settingsBtn}
        </div>
        ${mainContent}
        ${onSettings && admin ? `<div class="settings-scroll">${settingsContent}</div>` : ""}
      </div>
    `;
    this._attachListeners();
  }
}

customElements.define("nyc-sanitation-panel", NycSanitationPanel);
