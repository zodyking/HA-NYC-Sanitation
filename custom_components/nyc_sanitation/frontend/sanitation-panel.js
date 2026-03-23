/**
 * NYC Sanitation — Home Assistant sidebar panel
 */
const WS_TYPE = "nyc_sanitation/get_collection_data";
const WEEK_ORDER = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

class NycSanitationPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._panel = null;
    this._data = null;
    this._loading = true;
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    if (hass && hass !== prev) {
      this._loadData();
    }
    this._render();
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    this._render();
    if (this._hass) {
      this._loadData();
    }
  }

  async _loadData() {
    if (!this._hass) return;
    this._loading = true;
    this._render();
    try {
      this._data = await this._hass.callWS({ type: WS_TYPE });
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
      this._render();
    }
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
    const refreshBtn = this.shadowRoot.querySelector("#refresh-btn");
    if (refreshBtn) {
      refreshBtn.onclick = () => this._loadData();
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

    const cols = WEEK_ORDER.map(
      (day) => `
      <div class="day-col ${day === today ? "today" : ""}">
        <div class="day-head">${day.slice(0, 3)}</div>
        <div class="day-body">
          ${this._chipsHtml(weekly[day] || [])}
        </div>
      </div>
    `
    ).join("");

    return `<div class="week-grid">${cols}</div>`;
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

  _render() {
    const title = "NYC Sanitation";
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
        .notice {
          background: var(--card-background-color, rgba(0,0,0,0.05));
          border-radius: 12px;
          padding: 20px;
          border: 1px solid var(--divider-color);
        }
        .notice h2 { margin: 0 0 8px; font-size: 1.1rem; }
        .week-grid {
          display: grid;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          gap: 8px;
          margin-bottom: 20px;
        }
        @media (max-width: 900px) {
          .week-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
        }
        @media (max-width: 520px) {
          .week-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        .day-col {
          background: var(--card-background-color, rgba(0,0,0,0.04));
          border-radius: 10px;
          border: 1px solid var(--divider-color);
          overflow: hidden;
          min-height: 120px;
          display: flex;
          flex-direction: column;
        }
        .day-col.today {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 1px var(--primary-color);
        }
        .day-head {
          padding: 8px;
          text-align: center;
          font-weight: 600;
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          background: rgba(128,128,128,0.08);
          border-bottom: 1px solid var(--divider-color);
        }
        .day-body {
          padding: 8px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          flex: 1;
        }
        .chip {
          display: block;
          font-size: 11px;
          padding: 6px 8px;
          border-radius: 6px;
          border-left: 3px solid var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 14%, transparent);
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
      </style>
      <div class="shell">
        <div class="toolbar">
          <button class="menu-btn" id="menu-btn" type="button" title="Menu" aria-label="Menu">
            <svg viewBox="0 0 24 24"><path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"/></svg>
          </button>
          <h1>${title}</h1>
          <button class="icon-btn" id="refresh-btn" type="button" title="Refresh" aria-label="Refresh">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          </button>
        </div>
        <div class="content">
          ${this._renderMeta()}
          ${this._renderWeekly()}
          ${this._renderRouting()}
        </div>
      </div>
    `;
    this._attachListeners();
  }
}

customElements.define("nyc-sanitation-panel", NycSanitationPanel);
