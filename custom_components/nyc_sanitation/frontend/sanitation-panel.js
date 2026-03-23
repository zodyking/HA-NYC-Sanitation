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
    this._settingsOpen = false;
    this._ttsLoading = false;
    this._ttsOptions = null;
    this._ttsTomorrowTypes = [];
    this._ttsLoadError = null;
    this._ttsSaveError = null;
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
    if (!this._settingsOpen) {
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
    this._settingsOpen = false;
  }

  async _loadData() {
    if (!this._hass) return;
    this._loading = true;
    if (!this._settingsOpen) {
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
      if (!this._settingsOpen) {
        this._render();
      }
    }
  }

  _isAdmin() {
    return this._hass?.user?.is_admin === true;
  }

  async _openSettings() {
    if (!this._hass || !this._isAdmin()) return;
    this._settingsOpen = true;
    this._ttsLoading = true;
    this._ttsLoadError = null;
    this._ttsSaveError = null;
    this._ttsTestError = null;
    this._ttsOptions = null;
    this._render();
    try {
      const res = await this._hass.callWS({ type: WS_GET_TTS_OPTIONS });
      this._ttsOptions = res.options || {};
      this._ttsTomorrowTypes = res.tomorrow_types || [];
    } catch (e) {
      this._ttsLoadError =
        e?.message || String(e) || "Could not load TTS settings";
      console.error("NYC Sanitation get_tts_options", e);
    } finally {
      this._ttsLoading = false;
      this._render();
    }
  }

  _closeSettings() {
    this._settingsOpen = false;
    this._ttsLoadError = null;
    this._ttsSaveError = null;
    this._ttsTestError = null;
    this._render();
  }

  async _saveTtsSettings(ev) {
    ev?.preventDefault?.();
    if (!this._hass) return;
    const root = this.shadowRoot;
    const enabled = root.querySelector("#tts-enabled")?.checked === true;
    const hour = parseInt(root.querySelector("#tts-hour")?.value ?? "19", 10);
    const minute = parseInt(root.querySelector("#tts-minute")?.value ?? "0", 10);
    const mediaPlayer = root.querySelector("#tts-media-player")?.value?.trim() ?? "";
    const ttsEntity = root.querySelector("#tts-entity")?.value?.trim() ?? "";
    const volRaw = root.querySelector("#tts-volume")?.value?.trim() ?? "";
    let volume = null;
    if (volRaw !== "") {
      const v = Number(volRaw);
      if (!Number.isNaN(v)) volume = Math.min(1, Math.max(0, v));
    }

    this._ttsSaveError = null;
    this._render();
    try {
      const payload = {
        type: WS_SET_TTS_OPTIONS,
        tts_enabled: enabled,
        announce_hour: Number.isFinite(hour) ? hour : 19,
        announce_minute: Number.isFinite(minute) ? minute : 0,
        media_player_entity_id: mediaPlayer,
        tts_entity_id: ttsEntity,
        volume,
      };
      const res = await this._hass.callWS(payload);
      this._ttsOptions = res.options || this._ttsOptions;
      this._ttsSaveError = null;
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
    const modalBackdrop = this.shadowRoot.querySelector("#settings-modal");
    const modalDialog = this.shadowRoot.querySelector("#settings-dialog");
    if (modalDialog) {
      modalDialog.onclick = (ev) => ev.stopPropagation();
    }
    if (modalBackdrop) {
      modalBackdrop.onclick = (ev) => {
        if (ev.target === modalBackdrop) this._closeSettings();
      };
    }
    const cancelBtn = this.shadowRoot.querySelector("#tts-cancel");
    if (cancelBtn) cancelBtn.onclick = () => this._closeSettings();
    const saveBtn = this.shadowRoot.querySelector("#tts-save");
    if (saveBtn) saveBtn.onclick = (ev) => this._saveTtsSettings(ev);
    const testBtn = this.shadowRoot.querySelector("#tts-test");
    if (testBtn) testBtn.onclick = () => this._testTts();
    const refreshNow = this.shadowRoot.querySelector("#refresh-now-btn");
    if (refreshNow) refreshNow.onclick = () => this._loadData();
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

  _renderSettingsModal() {
    if (!this._settingsOpen) return "";

    const o = this._ttsOptions || {};
    const enabled = o.tts_enabled === true;
    const hour = Number.isFinite(o.announce_hour) ? o.announce_hour : 19;
    const minute = Number.isFinite(o.announce_minute) ? o.announce_minute : 0;
    const mp = this._escape(o.media_player_entity_id || "");
    const tts = this._escape(o.tts_entity_id || "");
    const vol =
      o.volume != null && o.volume !== ""
        ? String(o.volume)
        : "";

    const preview =
      this._ttsTomorrowTypes && this._ttsTomorrowTypes.length
        ? this._escape(this._ttsTomorrowTypes.join(", "))
        : "None (tomorrow)";

    let body = "";
    if (this._ttsLoading) {
      body = `<div class="muted center pad">Loading…</div>`;
    } else if (this._ttsLoadError) {
      body = `<div class="form-error pad">${this._escape(this._ttsLoadError)}</div>`;
    } else {
      body = `
        <p class="muted small modal-lead">
          Once per day at the time below, if tomorrow has a DSNY pickup, Home Assistant will announce it on the chosen media player (admin only).
        </p>
        <div class="preview-row muted small">Tomorrow’s collections (preview): <strong>${preview}</strong></div>
        <form id="tts-form" class="tts-form">
          <label class="check-row">
            <input type="checkbox" id="tts-enabled" ${enabled ? "checked" : ""} />
            <span>Enable day-before reminders</span>
          </label>
          <div class="field-row">
            <label for="tts-hour">Hour (0–23)</label>
            <input type="number" id="tts-hour" min="0" max="23" value="${hour}" />
          </div>
          <div class="field-row">
            <label for="tts-minute">Minute (0–59)</label>
            <input type="number" id="tts-minute" min="0" max="59" value="${minute}" />
          </div>
          <div class="field-row">
            <label for="tts-media-player">Media player entity</label>
            <input type="text" id="tts-media-player" placeholder="media_player.living_room" value="${mp}" autocomplete="off" />
          </div>
          <div class="field-row">
            <label for="tts-entity">TTS entity (optional)</label>
            <input type="text" id="tts-entity" placeholder="Leave empty to auto-pick tts.*" value="${tts}" autocomplete="off" />
          </div>
          <div class="field-row">
            <label for="tts-volume">Volume 0–1 (optional)</label>
            <input type="text" id="tts-volume" placeholder="e.g. 0.4" value="${vol}" autocomplete="off" />
          </div>
          ${this._ttsSaveError ? `<div class="form-error">${this._escape(this._ttsSaveError)}</div>` : ""}
          ${this._ttsTestError ? `<div class="form-error">${this._escape(this._ttsTestError)}</div>` : ""}
        </form>
        <div class="modal-actions">
          <button type="button" class="btn secondary" id="refresh-now-btn">Refresh schedule now</button>
          <button type="button" class="btn secondary" id="tts-test">Test announcement</button>
          <button type="button" class="btn secondary" id="tts-cancel">Cancel</button>
          <button type="button" class="btn primary" id="tts-save">Save</button>
        </div>
      `;
    }

    return `
      <div class="modal-backdrop" id="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <div class="modal-dialog" id="settings-dialog">
          <h2 id="settings-title">TTS reminder settings</h2>
          ${body}
        </div>
      </div>
    `;
  }

  _render() {
    const title = "NYC Sanitation";
    const admin = this._isAdmin();
    const settingsBtn = admin
      ? `
          <button class="icon-btn" id="settings-btn" type="button" title="Settings" aria-label="Settings">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.68 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z"/></svg>
          </button>
        `
      : "";

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
        .modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.45);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 100;
          padding: 16px;
          box-sizing: border-box;
        }
        .modal-dialog {
          background: var(--card-background-color, var(--primary-background-color));
          color: var(--primary-text-color);
          border-radius: 12px;
          border: 1px solid var(--divider-color);
          max-width: 440px;
          width: 100%;
          max-height: 90vh;
          overflow: auto;
          padding: 20px;
          box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        .modal-dialog h2 {
          margin: 0 0 12px;
          font-size: 1.15rem;
          font-weight: 600;
        }
        .modal-lead { margin: 0 0 12px; }
        .preview-row { margin-bottom: 16px; }
        .tts-form .field-row {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-bottom: 12px;
        }
        .tts-form label { font-size: 13px; font-weight: 500; }
        .tts-form input[type="text"],
        .tts-form input[type="number"] {
          padding: 10px 12px;
          border-radius: 8px;
          border: 1px solid var(--divider-color);
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
          min-height: 44px;
          box-sizing: border-box;
        }
        .check-row {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 16px;
          cursor: pointer;
          min-height: 44px;
        }
        .check-row input { width: 18px; height: 18px; }
        .form-error {
          color: var(--error-color, #db4437);
          font-size: 13px;
          margin: 8px 0;
        }
        .modal-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          justify-content: flex-end;
          margin-top: 16px;
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
          <h1>${title}</h1>
          ${settingsBtn}
        </div>
        <div class="content">
          ${this._renderMeta()}
          ${this._renderWeekly()}
          ${this._renderRouting()}
        </div>
      </div>
      ${this._renderSettingsModal()}
    `;
    this._attachListeners();
  }
}

customElements.define("nyc-sanitation-panel", NycSanitationPanel);
