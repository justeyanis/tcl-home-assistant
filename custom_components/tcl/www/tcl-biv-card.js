/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  tcl-biv-card  —  BIV TCL (Lyon) pour Home Assistant   v3.3.0    ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * Deux panneaux :
 *   metro : panneau jaune « Direction … » + écran noir, horloge verte,
 *           « Prochain : 2 min », picto clignotant à quai
 *   tram  : afficheur LED ambre à matrice de points, date/heure en pied
 *
 * Pictogrammes de ligne : les SVG OFFICIELS du site tcl.fr sont affichés
 * (https://www.tcl.fr/themes/custom/sytral_theme/img/lignes/<CODE>.svg),
 * avec repli automatique sur une pastille colorée si l'image ne charge pas.
 *
 * Éditeur graphique 100 % natif (aucune dépendance aux composants HA).
 *
 * ── Installation ─────────────────────────────────────────────────────
 * AUCUNE : ce fichier est servi et enregistré AUTOMATIQUEMENT comme
 * ressource Lovelace par l'intégration TCL (URL /tcl-biv-card/…?v=<version>,
 * cache géré tout seul à chaque mise à jour). En mode tableaux de bord YAML
 * uniquement, ajoutez la ressource manuellement.
 * Vérification : la console F12 affiche le bandeau TCL-BIV-CARD v3.3.0.
 *
 * ── Options YAML (défauts indiqués) ──────────────────────────────────
 *   entities: [sensor.tcl_b_debourg_0]  # entités "#0" ; sinon auto-découverte
 *   entity: sensor.tcl_b_debourg_0      # forme courte
 *   station: "Gare de Vénissieux"       # présélection (auto-découverte)
 *   style: auto                         # auto | metro | tram
 *   count: 3                            # nb de départs affichés
 *   title: ""
 *   line_icon: official                 # official | badge | none
 *   show_selector: false                # menu déroulant multi-stations
 *   show_header: true                   # bandeau direction
 *   show_clock: true                    # horloge
 *   show_date: true                     # date (pied tram)
 *   show_destination: true              # destination (colonne tram)
 *   show_picto: true                    # picto véhicule
 *   show_realtime: true                 # pastille « temps réel » / heures théoriques atténuées
 *   show_delay: true                    # retard (+3) et passages supprimés
 *   show_alerts: true                   # bandeau défilant des alertes trafic
 *   show_line: auto                     # badge de ligne par rangée : auto | true | false
 *   header: ""                          # direction forcée (déf.: config)
 *   header_prefix: "Direction"
 *   via: ""                             # sous-texte droite, multi-ligne
 *   labels: ["Prochain", "Suivant"]     # libellés métro (le dernier se répète)
 *   line_color: ""                      # pastille de repli
 *   header_bg: ""                       # fond bandeau
 *   clock_color: ""                     # horloge (déf. #39e639)
 *   label_color: ""                     # libellés "Prochain/Suivant" (déf. #ff7a1a)
 *   value_color: ""                     # délais et picto (déf. #3dc473)
 *   led_color: ""                       # LED tram (déf. #ffa61a)
 *
 * Comportements : le picto véhicule ne s'affiche QUE lorsque la rame est
 * à quai (délai 0), en remplacement du délai, et clignote. Un départ
 * disparaît 30 s avant son heure réelle. Un clic sur la carte ouvre le détail
 * de l'entité. Les passages théoriques (sans estimation temps réel) sont
 * atténués ; les passages suivis en temps réel portent une petite pastille.
 *
 * ── Exemple façon BIV funiculaire ────────────────────────────────────
 *   type: custom:tcl-biv-card
 *   entity: sensor.tcl_f1_vieux_lyon_saint_just_0
 *   style: metro
 *   count: 2
 *   header: SAINT-JUST
 *   via: "par Minimes\nThéâtres romains"
 */

"use strict";

const CARD_VERSION = "3.3.0";
console.info(
  `%c TCL-BIV-CARD %c v${CARD_VERSION} `,
  "background:#F8C300;color:#111;font-weight:700;border-radius:3px 0 0 3px",
  "background:#0a0a0a;color:#39e639;font-weight:700;border-radius:0 3px 3px 0"
);

/* ────────────────────────── Constantes ────────────────────────── */

/* Couleurs officielles (rebranding 2025, extraites des SVG tcl.fr) */
const FALLBACK_COLORS = {
  A: "#E03389", B: "#0075BC", C: "#F59B00", D: "#009E49",
  F1: "#8AB927", F2: "#8AB927",
  T1: "#8C368C", T2: "#8C368C", T3: "#8C368C", T4: "#8C368C",
  T5: "#8C368C", T6: "#8C368C", T7: "#8C368C", RX: "#B61B29",
};

const ICON_URL = (code) =>
  `https://www.tcl.fr/themes/custom/sytral_theme/img/lignes/${encodeURIComponent(
    String(code || "").toUpperCase()
  )}.svg`;

/* Face avant de rame (découpes transparentes), rails croisés */
const PICTO = `
  <svg viewBox="0 0 32 35" xmlns="http://www.w3.org/2000/svg">
    <path fill="currentColor" fill-rule="evenodd" d="
      M16 .5 C9.8 .5 6.6 5 6.6 11.6 L6.6 21 C6.6 24.2 8.8 26.2 11.8 26.2
      L20.2 26.2 C23.2 26.2 25.4 24.2 25.4 21 L25.4 11.6 C25.4 5 22.2 .5 16 .5 Z
      M11.6 5.6 L20.4 5.6 C21.8 5.6 22.8 6.7 22.6 8 L22.2 11.4
      C22.1 12.5 21.1 13.4 20 13.4 L12 13.4 C10.9 13.4 9.9 12.5 9.8 11.4
      L9.4 8 C9.2 6.7 10.2 5.6 11.6 5.6 Z
      M11.8 18.4 A2.1 2.1 0 1 0 11.8 22.6 A2.1 2.1 0 1 0 11.8 18.4 Z
      M20.2 18.4 A2.1 2.1 0 1 0 20.2 22.6 A2.1 2.1 0 1 0 20.2 18.4 Z"/>
    <path stroke="currentColor" stroke-width="2.8" stroke-linecap="round" fill="none"
      d="M11.2 24.6 L3.6 33.4 M20.8 24.6 L28.4 33.4 M2.2 31.4 L29.8 31.4"/>
  </svg>`;

/* Pastille « temps réel » (ondes, comme sur l'appli TCL) */
const RT_ICON = `
  <svg class="rt" viewBox="0 0 16 16" role="img" aria-label="temps réel">
    <title>Temps réel</title>
    <path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
      d="M3 13 A10 10 0 0 1 13 3 M3 8.4 A5.4 5.4 0 0 1 8.4 3"/>
    <circle cx="3.6" cy="12.4" r="2" fill="currentColor"/>
  </svg>`;

const ALERT_ICON = `
  <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor"
    d="M12 2 1 21h22L12 2Zm1 15h-2v2h2v-2Zm0-7h-2v5h2v-5Z"/></svg>`;

const DEFAULTS = {
  count: 3,
  style: "auto",
  line_icon: "official",
  show_selector: false,
  show_header: true,
  show_clock: true,
  show_date: true,
  show_destination: true,
  show_picto: true,
  show_realtime: true,
  show_delay: true,
  show_alerts: true,
  show_line: "auto",
  title: "",
  header: "",
  header_prefix: "Direction",
  via: "",
  labels: ["Prochain", "Suivant"],
  line_color: "",
  header_bg: "",
  clock_color: "",
  label_color: "",
  value_color: "",
  led_color: "",
};

/* ────────────────────────── Helpers ────────────────────────── */

const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

const upper = (s) =>
  (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

const hhmm = (d) =>
  d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

/** Pictogramme de ligne : SVG officiel tcl.fr, repli pastille colorée. */
function lineIconHtml(mode, code, color) {
  if (mode === "none" || !code) return "";
  const badge = `<span class="lbadge" style="background:${esc(color)}
    ${mode === "official" ? ";display:none" : ""}">${esc(code)}</span>`;
  if (mode !== "official") return badge;
  return `<img class="licon" alt="${esc(code)}" referrerpolicy="no-referrer"
      src="${esc(ICON_URL(code))}"
      onerror="this.style.display='none';this.nextElementSibling.style.display='inline-flex'"
    >${badge}`;
}

/* ────────────────────────── La carte ────────────────────────── */

class TclBivCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("tcl-biv-card-editor");
  }

  static getStubConfig(hass) {
    const first = Object.values(hass?.states || {}).find(
      (s) => s.attributes?.tcl_biv === true
    );
    return first ? { entities: [first.entity_id] } : {};
  }

  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
    this._selected = this._config.station || null;
    this._lastHtml = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  connectedCallback() {
    this._timer = setInterval(() => this._render(), 1000);
    this._render();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  getCardSize() {
    return 2 + Math.min(Number(this._config?.count) || 3, 6);
  }

  /* Vue « sections » : pleine largeur par défaut, hauteur automatique */
  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _moreInfo() {
    const entityId = this._mainEntityId;
    if (!entityId) return;
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      })
    );
  }

  /* ---------- données ---------- */

  _entities() {
    if (!this._hass) return [];
    const ids = this._config.entities
      ? this._config.entities
      : this._config.entity
        ? [this._config.entity]
        : null;
    if (ids) return ids.map((id) => this._hass.states[id]).filter(Boolean);
    return Object.values(this._hass.states).filter(
      (s) => s.entity_id.startsWith("sensor.") && s.attributes.tcl_biv === true
    );
  }

  _stations(entities) {
    const map = new Map();
    for (const e of entities) {
      const name = e.attributes.station || e.entity_id;
      if (!map.has(name)) map.set(name, []);
      map.get(name).push(e);
    }
    return map;
  }

  _lineColor(code, entities) {
    if (this._config.line_color) return this._config.line_color;
    for (const e of entities) {
      if (e.attributes.ligne === code && e.attributes.couleur) {
        return e.attributes.couleur;
      }
    }
    return FALLBACK_COLORS[(code || "").toUpperCase()] || "#8E8E8E";
  }

  _departures(entities) {
    const now = Date.now();
    const seen = new Set();
    const deps = [];
    for (const e of entities) {
      for (const d of e.attributes.departures || []) {
        if (d.annule && !this._config.show_delay) continue;
        let delai = d.delai;
        if (d.heure) {
          const msLeft = new Date(d.heure) - now;
          // Un départ disparaît 30 s avant son heure réelle
          if (msLeft < 30000) continue;
          delai = Math.min(delai, Math.max(0, Math.floor(msLeft / 60000)));
        }
        const key = `${d.ligne}|${d.destination}|${d.heure || d.delai}`;
        if (seen.has(key)) continue;
        seen.add(key);
        deps.push({ ...d, delai });
      }
    }
    deps.sort((a, b) => a.delai - b.delai);
    return deps.slice(0, this._config.count);
  }

  _alerts(entities) {
    if (!this._config.show_alerts) return [];
    const seen = new Map();
    for (const e of entities) {
      for (const a of e.attributes.alertes || []) {
        if (a && a.titre && !seen.has(a.titre)) seen.set(a.titre, a);
      }
    }
    return [...seen.values()];
  }

  /* Délai affiché : picto à quai, HH:MM au-delà d'une heure, sinon minutes,
     + pastille temps réel et retard. */
  _timeHtml(d, picto, atStopText) {
    const c = this._config;
    if (d.annule) return `<span class="cancel">SUPPRIMÉ</span>`;
    let html;
    if (d.delai === 0) {
      html = c.show_picto ? picto : atStopText;
    } else if (d.delai >= 60 && d.heure) {
      html = hhmm(new Date(d.heure));
    } else {
      html = `${d.delai}&#160;min`;
    }
    if (c.show_realtime && d.temps_reel && d.delai !== 0) {
      html += RT_ICON;
    }
    if (c.show_delay && Number(d.retard) >= 2) {
      html += `<span class="late" title="Retard">+${Number(d.retard)}</span>`;
    }
    return html;
  }

  _showLine(entities, deps) {
    const mode = this._config.show_line;
    if (mode === true || mode === "true") return true;
    if (mode === false || mode === "false") return false;
    return new Set(deps.map((d) => d.ligne)).size > 1;
  }

  _alertsHtml(alerts) {
    if (!alerts.length) return "";
    const major = alerts.some((a) => /majeure/i.test(a.type || ""));
    const text = alerts
      .map((a) => {
        const msg = (a.message || "").slice(0, 220);
        return `<b>${esc(a.titre)}</b>${msg && msg !== a.titre ? ` — ${esc(msg)}` : ""}`;
      })
      .join(`<span class="a-sep">◆</span>`);
    const chars = alerts.reduce(
      (n, a) => n + (a.titre || "").length + Math.min((a.message || "").length, 220),
      0
    );
    const dur = Math.max(12, Math.round(chars * 0.16));
    return `
      <div class="alerts ${major ? "major" : ""}" title="${esc(
        alerts.map((a) => a.titre).join(" • ")
      )}">
        <span class="a-ico">${ALERT_ICON}</span>
        <div class="a-track"><span class="a-text" style="animation-duration:${dur}s">${text}</span></div>
      </div>`;
  }

  _label(i) {
    const labels = this._config.labels || [];
    return labels[Math.min(i, labels.length - 1)] || "Suivant";
  }

  _headerTexts(entities) {
    const direction = this._config.header || entities[0].attributes.direction;
    return {
      prefix: direction ? this._config.header_prefix : "",
      main: direction || this._selected || "",
      via: this._config.via,
    };
  }

  /* ---------- rendu ---------- */

  _render() {
    if (!this._hass || !this.shadowRoot || !this._config) return;
    const active = this.shadowRoot.activeElement;
    if (active && active.id === "station") return;

    const html = this._buildHtml();
    if (html === this._lastHtml) return; // rien à faire
    this._lastHtml = html;
    this.shadowRoot.innerHTML = html;

    // Le défilement des alertes reprend là où il en était (pas de saut
    // à chaque rafraîchissement du panneau)
    const ticker = this.shadowRoot.querySelector(".a-text");
    if (ticker) {
      const dur = parseFloat(ticker.style.animationDuration) || 20;
      ticker.style.animationDelay = `-${(Date.now() / 1000) % dur}s`;
    }

    const card = this.shadowRoot.querySelector(".biv");
    if (card) card.addEventListener("click", () => this._moreInfo());

    const sel = this.shadowRoot.getElementById("station");
    if (sel) {
      sel.addEventListener("change", (ev) => {
        this._selected = ev.target.value;
        this._lastHtml = null;
        this._render();
      });
    }
  }

  _buildHtml() {
    const c = this._config;
    const entities = this._entities();
    const stations = this._stations(entities);

    if (stations.size === 0) {
      return `<ha-card style="padding:16px">Aucune entité TCL trouvée.
        Ajoutez l'intégration TCL ou choisissez des entités dans l'éditeur
        de la carte.</ha-card>`;
    }

    if (!this._selected || !stations.has(this._selected)) {
      this._selected = stations.keys().next().value;
    }
    const stationEntities = stations.get(this._selected);
    this._mainEntityId = stationEntities[0].entity_id;
    const mode = stationEntities[0].attributes.mode || "metro";
    const deps = this._departures(stationEntities);
    const style =
      c.style === "auto"
        ? mode === "metro" || mode === "funiculaire"
          ? "metro"
          : "tram"
        : c.style;

    const selector = c.show_selector
      ? `<select id="station">${[...stations.keys()]
          .map(
            (n) =>
              `<option value="${esc(n)}" ${n === this._selected ? "selected" : ""}>${esc(n)}</option>`
          )
          .join("")}</select>`
      : "";

    const unavailable = stationEntities.every((e) => e.state === "unavailable");
    const alerts = this._alertsHtml(this._alerts(stationEntities));
    const body =
      style === "metro"
        ? this._metroHtml(deps, stationEntities, alerts, unavailable)
        : this._tramHtml(deps, stationEntities, alerts, unavailable);

    return `
      <style>${CSS}</style>
      <ha-card>
        ${c.title ? `<h1 class="card-title">${esc(c.title)}</h1>` : ""}
        ${selector}
        ${body}
      </ha-card>`;
  }

  _cssVars() {
    const c = this._config;
    return esc(
      [
        ["--tcl-header-bg", c.header_bg],
        ["--tcl-clock", c.clock_color],
        ["--tcl-label", c.label_color],
        ["--tcl-value", c.value_color],
        ["--tcl-led", c.led_color],
      ]
        .filter(([, v]) => v)
        .map(([k, v]) => `${k}:${v}`)
        .join(";")
    );
  }

  /* Panneau métro/funiculaire : bandeau jaune + écran noir */
  _metroHtml(deps, entities, alerts = "", unavailable = false) {
    const c = this._config;
    const line = entities[0].attributes.ligne || "";
    const color = this._lineColor(line, entities);
    const t = this._headerTexts(entities);

    const header = c.show_header
      ? `<div class="m-header">
          ${lineIconHtml(c.line_icon, line, color)}
          <span class="m-dir">
            ${t.prefix ? `<span class="m-prefix">${esc(t.prefix)}</span> ` : ""}
            <span class="m-name">${esc(upper(t.main))}</span>
          </span>
          ${t.via ? `<span class="m-via">${esc(t.via)}</span>` : ""}
        </div>`
      : "";

    const multi = this._showLine(entities, deps);
    const rows = deps.length
      ? deps
          .map((d, i) => {
            // Le picto n'apparaît QUE lorsque la rame est à quai (délai 0),
            // à la place du délai, et clignote.
            const value = this._timeHtml(
              d,
              `<span class="m-rowpicto blink">${PICTO}</span>`,
              "proche"
            );
            const theo = c.show_realtime && d.temps_reel === false && !d.annule;
            const badge = multi
              ? `<span class="rowline" style="background:${esc(
                  this._lineColor(d.ligne, entities)
                )}">${esc(d.ligne)}</span>`
              : "";
            return `
              <div class="m-row ${d.annule ? "is-cancel" : ""}">
                <span class="m-lbl">${badge}${esc(this._label(i))}</span>
                <span class="m-val ${theo ? "theo" : ""}">:&#160;${value}</span>
              </div>`;
          })
          .join("")
      : `<div class="m-row"><span class="m-lbl">${esc(this._label(0))}</span>
           <span class="m-val off">:&#160;${unavailable ? "indisponible" : "— —"}</span></div>`;

    return `
      <div class="biv metro" style="${this._cssVars()}">
        ${header}
        <div class="m-screen">
          ${c.show_clock ? `<span class="m-clock">${hhmm(new Date())}</span>` : ""}
          <div class="m-rows">${rows}</div>
        </div>
        ${alerts}
      </div>`;
  }

  /* Panneau tram/bus : afficheur LED ambre à matrice de points */
  _tramHtml(deps, entities, alerts = "", unavailable = false) {
    const c = this._config;
    const line = entities[0].attributes.ligne || "";
    const color = this._lineColor(line, entities);
    const t = this._headerTexts(entities);
    const now = new Date();

    const header = c.show_header
      ? `<div class="t-header">
          ${lineIconHtml(c.line_icon, line, color)}
          <span class="t-dir">${t.prefix ? esc(t.prefix) + " " : ""}<b>${esc(t.main)}</b>${
            t.via ? ` <small>${esc(t.via)}</small>` : ""
          }</span>
        </div>`
      : "";

    const multi = this._showLine(entities, deps);
    const rows = deps.length
      ? deps
          .map((d) => {
            const delay = this._timeHtml(
              d,
              `<span class="t-rowpicto blink">${PICTO}</span>`,
              "&gt;&gt;"
            );
            const theo = c.show_realtime && d.temps_reel === false && !d.annule;
            const badge = multi
              ? `<span class="rowline" style="background:${esc(
                  this._lineColor(d.ligne, entities)
                )}">${esc(d.ligne)}</span>`
              : "";
            return `
              <div class="t-row ${theo ? "theo" : ""} ${d.annule ? "is-cancel" : ""}">
                ${badge}
                <span class="t-dest">${c.show_destination ? esc(upper(d.destination)) : ""}</span>
                <span class="t-delay">${delay}</span>
              </div>`;
          })
          .join("")
      : `<div class="t-row"><span class="t-dest">${
          unavailable ? "SERVICE INDISPONIBLE" : "PAS DE PASSAGE ANNONCE"
        }</span></div>`;

    const footer =
      c.show_date || c.show_clock
        ? `<div class="t-footer">
            <span>${c.show_date ? now.toLocaleDateString("fr-FR") : ""}</span>
            <span>${c.show_clock ? hhmm(now) : ""}</span>
          </div>`
        : "";

    return `
      <div class="biv tram" style="${this._cssVars()}">
        ${header}
        <div class="t-screen">
          <div class="t-inner">${rows}${footer}</div>
          <div class="t-dots"></div>
        </div>
        ${alerts}
      </div>`;
  }
}

/* ────────────────────────── Styles ────────────────────────── */

const CSS = `
  :host { display: block; }
  ha-card { overflow: hidden; }
  .card-title { font-size: 1.1em; margin: 12px 16px 0; }
  select {
    margin: 12px 16px 4px; padding: 6px 10px; border-radius: 6px;
    background: var(--secondary-background-color); color: var(--primary-text-color);
    border: 1px solid var(--divider-color); font-size: .95em;
    max-width: calc(100% - 32px);
  }
  .biv {
    margin: 12px 16px 16px; border-radius: 12px; overflow: hidden;
    border: 2px solid #1a1a1a;
    box-shadow: 0 6px 18px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.15);
    line-height: 1.15; cursor: pointer;
    container-type: inline-size; container-name: biv;
  }

  /* temps réel, retards, suppressions */
  .rt { width: .62em; height: .62em; margin-left: .35em; flex: none;
        align-self: flex-start; margin-top: -.05em;
        animation: tcl-rt 2.4s ease-in-out infinite; }
  @keyframes tcl-rt { 0%,100% { opacity: 1 } 50% { opacity: .45 } }
  .late { margin-left: .4em; padding: 0 .32em; border-radius: 4px;
          font-size: .7em; line-height: 1.45; background: #e5332a; color: #fff;
          text-shadow: none; letter-spacing: 0; align-self: center; }
  .cancel { color: #ff4d4d; letter-spacing: 1px; font-size: .8em;
            text-shadow: 0 0 6px rgba(255,77,77,.6); }
  .is-cancel .m-lbl, .is-cancel .t-dest { text-decoration: line-through;
            text-decoration-thickness: 2px; opacity: .6; }
  .rowline { display: inline-flex; align-items: center; justify-content: center;
             min-width: 2.1em; height: 1.45em; padding: 0 .3em; margin-right: .45em;
             border-radius: 4px; color: #fff; font-size: .74em; font-weight: 800;
             letter-spacing: 0; text-shadow: none; vertical-align: middle;
             font-family: Arial, Helvetica, sans-serif; }
  .t-row .rowline { flex: none; margin-right: 0; }

  /* bandeau d'alertes trafic (défilant) */
  .alerts {
    display: flex; align-items: center; gap: 8px; padding: 6px 12px;
    background: #f2a900; color: #111; font-family: Arial, Helvetica, sans-serif;
    font-size: 13px; border-top: 2px solid #b97f00; overflow: hidden;
  }
  .alerts.major { background: #d6261c; color: #fff; border-top-color: #8f160f; }
  .a-ico { flex: none; width: 18px; height: 18px; display: inline-flex; }
  .a-ico svg { width: 100%; height: 100%; }
  .a-track { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap;
             mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent); }
  .a-text { display: inline-block; padding-left: 100%;
            animation: tcl-marquee 20s linear infinite; }
  .a-sep { margin: 0 14px; opacity: .6; }
  @keyframes tcl-marquee { from { transform: translateX(0) } to { transform: translateX(-100%) } }
  @media (prefers-reduced-motion: reduce) {
    .a-track { white-space: normal; mask-image: none; }
    .a-text { animation: none; padding-left: 0; }
    .blink, .rt { animation: none; }
  }

  /* pictogramme de ligne (officiel + repli) */
  .licon { height: 30px; width: auto; display: inline-block; flex: none; }
  .lbadge {
    flex: none; min-width: 30px; height: 30px; padding: 0 5px;
    border-radius: 6px; color: #fff; font-weight: 800; font-size: 16px;
    display: inline-flex; align-items: center; justify-content: center;
    font-family: Arial, sans-serif;
  }

  /* ─── panneau métro / funiculaire ─── */
  .m-header {
    display: flex; align-items: center; gap: 12px; padding: 10px 14px;
    background: var(--tcl-header-bg, linear-gradient(#f8ce1e, #eab800));
    border-bottom: 3px solid #c99700;
    color: #111; font-family: Arial, Helvetica, sans-serif;
  }
  .m-dir { flex: 1 1 auto; min-width: 0; }
  .m-prefix { font-size: 15px; font-weight: 600; }
  .m-name { font-size: 27px; font-weight: 800; letter-spacing: .5px; }
  .m-via { flex: none; font-size: 12px; font-weight: 700; text-align: right;
           white-space: pre-line; max-width: 40%; }

  .m-screen {
    display: flex; align-items: center; gap: 26px;
    padding: 16px 20px; background: #060606;
    box-shadow: inset 0 0 34px rgba(0,0,0,.9), inset 0 2px 6px rgba(0,0,0,.8);
    font-family: Arial, Helvetica, sans-serif;
  }
  .m-clock {
    flex: none; font-size: 38px; font-weight: 800;
    color: var(--tcl-clock, #39e639); text-shadow: 0 0 8px;
  }
  .m-rows { flex: 1 1 auto; min-width: 0; }
  .m-row { display: flex; align-items: center; font-size: 24px;
           font-weight: 700; padding: 2px 0; min-height: 32px; }
  .m-lbl { color: var(--tcl-label, #ff7a1a); min-width: 130px;
           text-shadow: 0 0 6px; }
  .m-val { color: var(--tcl-value, #3dc473); text-shadow: 0 0 6px;
           display: flex; align-items: center; gap: 8px; }
  .m-val.theo { opacity: .6; }
  .m-val.off { color: #444; text-shadow: none; }
  .m-rowpicto { display: inline-flex; width: 26px; height: 28px;
                filter: drop-shadow(0 0 4px); }
  .m-rowpicto svg { width: 100%; height: 100%; }

  /* ─── panneau tram / bus (LED ambre, matrice de points) ─── */
  .t-header {
    display: flex; align-items: center; gap: 12px; padding: 9px 14px;
    background: var(--tcl-header-bg, linear-gradient(#585e64, #43484d));
    border-bottom: 2px solid #2e3236;
    color: #f0f0f0;
  }
  .t-dir { font-size: 16px; font-family: Arial, Helvetica, sans-serif;
           min-width: 0; }
  .t-dir b { letter-spacing: .3px; }
  .t-dir small { font-size: 11px; opacity: .8; }

  .t-screen {
    position: relative; background: #101010;
    box-shadow: inset 0 0 30px rgba(0,0,0,.9);
  }
  .t-inner { padding: 14px 18px; }
  .t-dots {
    position: absolute; inset: 0; pointer-events: none;
    background-image: radial-gradient(circle, rgba(0,0,0,0) 0 36%, rgba(6,6,6,.25) 42%);
    background-size: 3px 3px;
  }
  .t-row {
    display: flex; align-items: center; gap: 12px; padding: 5px 0;
    font-family: Arial, Helvetica, sans-serif;
    color: var(--tcl-led, #ffa61a); font-weight: 700; font-size: 20px;
    letter-spacing: 2px; text-shadow: 0 0 7px, 0 0 2px;
  }
  .t-dest { flex: 1; min-width: 0; }
  .t-delay { flex: none; display: inline-flex; align-items: center; }
  .t-row.theo { opacity: .6; }
  .t-rowpicto { flex: none; width: 24px; height: 26px;
                display: inline-flex; filter: drop-shadow(0 0 4px); }
  .t-rowpicto svg { width: 100%; height: 100%; }
  .t-footer {
    display: flex; justify-content: space-between; margin-top: 10px;
    padding-top: 6px; border-top: 1px solid rgba(255,166,26,.25);
    font-family: Arial, Helvetica, sans-serif;
    color: var(--tcl-led, #ffa61a); font-size: 13px;
    letter-spacing: 2px; opacity: .9; text-shadow: 0 0 4px;
  }

  /* cartes étroites (colonnes, mobile) */
  @container biv (max-width: 400px) {
    .m-header { gap: 8px; padding: 8px 10px; }
    .m-name { font-size: 20px; }
    .m-prefix { font-size: 12px; }
    .m-screen { gap: 14px; padding: 12px 12px; }
    .m-clock { font-size: 26px; }
    .m-row { font-size: 18px; min-height: 26px; }
    .m-lbl { min-width: 92px; }
    .licon { height: 24px; }
    .lbadge { height: 24px; min-width: 24px; font-size: 13px; }
    .t-row { font-size: 16px; letter-spacing: 1px; gap: 8px; }
    .t-inner { padding: 10px 12px; }
  }
  @container biv (max-width: 340px) {
    .m-screen { gap: 10px; padding: 10px 10px; }
    .m-clock { font-size: 22px; }
    .m-row { font-size: 16px; }
    .m-lbl { min-width: 76px; }
    .t-row { font-size: 15px; letter-spacing: .5px; }
  }

  @keyframes tcl-blink { 0%,49% {opacity:1} 50%,100% {opacity:.15} }
  .blink { animation: tcl-blink 1s step-start infinite; }
`;

/* ────────────────────────── Éditeur (contrôles natifs) ────────────────────────── */

const ED_TOGGLES = [
  ["show_header", "Bandeau direction"],
  ["show_clock", "Horloge"],
  ["show_date", "Date (tram)"],
  ["show_destination", "Destinations (tram)"],
  ["show_picto", "Pictos véhicule"],
  ["show_realtime", "Pastille temps réel"],
  ["show_delay", "Retards et suppressions"],
  ["show_alerts", "Alertes trafic"],
  ["show_selector", "Menu des stations"],
];

const ED_COLORS = [
  ["line_color", "Pastille de ligne"],
  ["header_bg", "Fond du bandeau"],
  ["clock_color", "Horloge (déf. #39e639)"],
  ["label_color", "Libellés Prochain/Suivant (déf. #ff7a1a)"],
  ["value_color", "Délais et picto (déf. #3dc473)"],
  ["led_color", "LED tram (déf. #ffa61a)"],
];

class TclBivCardEditor extends HTMLElement {
  setConfig(config) {
    // Ignorer l'écho de notre propre config-changed pour ne pas
    // reconstruire le formulaire pendant la saisie.
    if (this._emitted && JSON.stringify(config) === this._emitted) return;
    this._config = { ...config };
    this._built = false;
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._build();
  }

  connectedCallback() {
    this._build();
  }

  get _cfg() {
    return { ...DEFAULTS, ...this._config };
  }

  _candidates() {
    const list = Object.values(this._hass?.states || {})
      .filter((s) => s.attributes?.tcl_biv === true)
      .map((s) => s.entity_id)
      .sort();
    const selected = this._config.entities || (this._config.entity ? [this._config.entity] : []);
    for (const id of selected) if (!list.includes(id)) list.push(id);
    return { list, selected };
  }

  _build() {
    if (this._built || !this._config || !this._hass) return;
    this._built = true;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const c = this._cfg;
    const { list, selected } = this._candidates();

    const entRows = list.length
      ? list
          .map((id) => {
            const st = this._hass.states[id];
            const name = st?.attributes?.friendly_name || id;
            return `<label class="ent">
              <input type="checkbox" data-ent="${esc(id)}" ${selected.includes(id) ? "checked" : ""}>
              <span><b>${esc(name)}</b><small>${esc(id)}</small></span>
            </label>`;
          })
          .join("")
      : `<div class="hint">Aucun capteur TCL trouvé (attribut tcl_biv).
           Sans sélection, la carte les découvre automatiquement.</div>`;

    this.shadowRoot.innerHTML = `
      <style>${ED_CSS}</style>
      <div class="ed">
        <div class="sec">Entités (aucune cochée = auto-découverte)</div>
        <div class="ents">${entRows}</div>

        <div class="sec">Affichage</div>
        <div class="grid">
          <label>Style
            <select data-k="style">
              <option value="auto" ${c.style === "auto" ? "selected" : ""}>Auto (selon le mode)</option>
              <option value="metro" ${c.style === "metro" ? "selected" : ""}>Métro / funiculaire</option>
              <option value="tram" ${c.style === "tram" ? "selected" : ""}>Tram / bus (LED)</option>
            </select>
          </label>
          <label>Pictogramme de ligne
            <select data-k="line_icon">
              <option value="official" ${c.line_icon === "official" ? "selected" : ""}>Officiel TCL (tcl.fr)</option>
              <option value="badge" ${c.line_icon === "badge" ? "selected" : ""}>Pastille colorée</option>
              <option value="none" ${c.line_icon === "none" ? "selected" : ""}>Aucun</option>
            </select>
          </label>
          <label>Ligne sur chaque rangée
            <select data-k="show_line">
              <option value="auto" ${String(c.show_line) === "auto" ? "selected" : ""}>Auto (si plusieurs lignes)</option>
              <option value="true" ${String(c.show_line) === "true" ? "selected" : ""}>Toujours</option>
              <option value="false" ${String(c.show_line) === "false" ? "selected" : ""}>Jamais</option>
            </select>
          </label>
          <label>Nombre de départs
            <input type="number" min="1" max="10" step="1" data-k="count" value="${c.count}">
          </label>
          <label>Titre de la carte
            <input type="text" data-k="title" value="${esc(c.title)}">
          </label>
          <label class="wide">Libellés des rangs (virgules)
            <input type="text" data-k="labels" value="${esc(
              Array.isArray(c.labels) ? c.labels.join(", ") : c.labels
            )}">
          </label>
        </div>

        <div class="sec">Bandeau</div>
        <div class="grid">
          <label>Direction affichée (vide = direction configurée)
            <input type="text" data-k="header" value="${esc(c.header)}">
          </label>
          <label>Préfixe
            <input type="text" data-k="header_prefix" value="${esc(c.header_prefix)}">
          </label>
          <label class="wide">Sous-texte à droite (plusieurs lignes possibles)
            <textarea rows="2" data-k="via">${esc(c.via)}</textarea>
          </label>
        </div>

        <div class="sec">Éléments visibles</div>
        <div class="grid toggles">
          ${ED_TOGGLES.map(
            ([k, lbl]) => `<label class="tog">
              <input type="checkbox" data-k="${k}" ${c[k] ? "checked" : ""}>
              <span>${lbl}</span>
            </label>`
          ).join("")}
        </div>

        <div class="sec">Couleurs (vide = défaut)</div>
        <div class="grid">
          ${ED_COLORS.map(
            ([k, lbl]) => `<label>${lbl}
              <input type="text" data-k="${k}" placeholder="#RRGGBB"
                     value="${esc(c[k])}">
            </label>`
          ).join("")}
        </div>
      </div>`;

    this.shadowRoot.querySelectorAll("[data-k], [data-ent]").forEach((el) => {
      const ev = el.matches("input[type=text], textarea") ? "input" : "change";
      el.addEventListener(ev, () => this._changed());
    });
  }

  _changed() {
    clearTimeout(this._deb);
    this._deb = setTimeout(() => this._emit(), 250);
  }

  _emit() {
    const root = this.shadowRoot;
    const config = { type: "custom:tcl-biv-card" };
    if (this._config.station) config.station = this._config.station;

    const entities = [...root.querySelectorAll("[data-ent]")]
      .filter((el) => el.checked)
      .map((el) => el.dataset.ent);
    if (entities.length) config.entities = entities;

    const read = (k) => {
      const el = root.querySelector(`[data-k="${k}"]`);
      if (!el) return undefined;
      if (el.type === "checkbox") return el.checked;
      if (el.type === "number") {
        const n = Number(el.value);
        return Number.isFinite(n) ? n : undefined;
      }
      return el.value;
    };

    for (const [key, def] of Object.entries(DEFAULTS)) {
      let value = read(key);
      if (value === undefined) continue;
      if (key === "labels") {
        const arr = String(value)
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
        if (arr.length && arr.join(",") !== DEFAULTS.labels.join(",")) {
          config.labels = arr;
        }
        continue;
      }
      if (value === def || value === "") continue;
      config[key] = value;
    }

    this._config = config;
    this._emitted = JSON.stringify(config);
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config },
        bubbles: true,
        composed: true,
      })
    );
  }
}

const ED_CSS = `
  .ed { display: block; padding: 4px 2px 12px;
        color: var(--primary-text-color, #ddd); font-size: 14px;
        font-family: Arial, Helvetica, sans-serif; }
  .sec { font-weight: 600; margin: 14px 0 6px; opacity: .8;
         text-transform: uppercase; font-size: 11px; letter-spacing: .8px; }
  .ents { display: flex; flex-direction: column; gap: 4px;
          max-height: 180px; overflow-y: auto; }
  .ent { display: flex; align-items: center; gap: 8px; padding: 6px 8px;
         border: 1px solid var(--divider-color, #444); border-radius: 8px;
         cursor: pointer; }
  .ent b { display: block; font-weight: 600; }
  .ent small { display: block; opacity: .6; font-size: 11px; }
  .hint { opacity: .7; font-size: 13px; padding: 4px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .grid label { display: flex; flex-direction: column; gap: 4px;
                font-size: 12px; opacity: .95; }
  .grid label.wide { grid-column: 1 / -1; }
  input[type=text], input[type=number], select, textarea {
    padding: 8px 10px; border-radius: 8px; font: inherit;
    background: var(--secondary-background-color, #333);
    color: var(--primary-text-color, #eee);
    border: 1px solid var(--divider-color, #555);
  }
  textarea { resize: vertical; }
  .toggles { grid-template-columns: 1fr 1fr; }
  .tog { flex-direction: row !important; align-items: center;
         gap: 8px !important; font-size: 13px !important; cursor: pointer; }
  .tog input { width: 18px; height: 18px; accent-color: #F8C300; }
`;

/* ────────────────────────── Enregistrement ────────────────────────── */

customElements.define("tcl-biv-card", TclBivCard);
customElements.define("tcl-biv-card-editor", TclBivCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "tcl-biv-card",
  name: "TCL BIV Card",
  preview: true,
  description:
    "Prochains départs TCL façon BIV (panneau métro jaune / afficheur LED tram) : temps réel, retards, alertes trafic, pictogrammes officiels.",
});
