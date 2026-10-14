/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  tcl-biv-card  —  BIV TCL (Lyon) pour Home Assistant   v3.3.1    ║
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
 * Vérification : la console F12 affiche le bandeau TCL-BIV-CARD v3.3.1.
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
 *   show_approach: true                 # tram/bus : « À L'APPROCHE » puis « À QUAI »
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

const CARD_VERSION = "3.3.1";
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
function ALERT_ICON_PATH() {
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor"
    d="M12 2 1 21h22L12 2Zm1 15h-2v2h2v-2Zm0-7h-2v5h2v-5Z"/></svg>`;
}

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

/* Tramway Citadis 302 de Lyon, vue de face (couleur = LED du panneau) */
const TRAM_PICTO = `
  <svg viewBox="40 40 432 440" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M256 98V78M256 78l-36-28M256 78l36-28M166 58q10-8 26-8h128q16 0 26 8"
      fill="none" stroke="currentColor" stroke-width="12" stroke-linecap="round"
      stroke-linejoin="round"/>
    <rect fill="currentColor" x="90" y="163" width="36" height="16" rx="8"/>
    <rect fill="currentColor" x="386" y="163" width="36" height="16" rx="8"/>
    <path fill="currentColor" fill-rule="evenodd" d="M256 96C310 96 352 102 377 118C390 127 394 150 396 172C400 205 401 240 401 270C401 320 400 360 399 390C398 420 396 440 388 451C380 464 372 470 364 470H148C140 470 132 464 124 451C116 440 114 420 113 390C112 360 111 320 111 270C111 240 112 205 116 172C118 150 122 127 135 118C160 102 202 96 256 96ZM150 334C163 240 201 163 256 163C311 163 349 240 362 334Q256 402 150 334ZM122 184Q150 196 161 228C150 258 139 300 135 332L139 364L122 358ZM390 184Q362 196 351 228C362 258 373 300 377 332L373 364L390 358ZM153 381a15 10 0 1 0 30 0a15 10 0 1 0-30 0ZM329 381a15 10 0 1 0 30 0a15 10 0 1 0-30 0ZM176 446a7 7 0 1 0 14 0a7 7 0 1 0-14 0ZM322 446a7 7 0 1 0 14 0a7 7 0 1 0-14 0Z"/>
  </svg>`;

/* Bus vue de face : girouette, pare-brise, phares, rétroviseurs */
const BUS_PICTO = `
  <svg viewBox="0 0 32 36" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" fill-rule="evenodd" d="
      M7 1.5 H25 Q29 1.5 29 5.5 V30 Q29 32 27 32 H5 Q3 32 3 30 V5.5 Q3 1.5 7 1.5 Z
      M9.5 3.4 H22.5 V5.6 H9.5 Z
      M6.2 7.5 H25.8 Q26.4 7.5 26.4 8.1 V18.4 Q26.4 19 25.8 19 H6.2 Q5.6 19 5.6 18.4 V8.1 Q5.6 7.5 6.2 7.5 Z
      M8 25 a2.2 2.2 0 1 0 4.4 0 a2.2 2.2 0 1 0 -4.4 0 Z
      M19.6 25 a2.2 2.2 0 1 0 4.4 0 a2.2 2.2 0 1 0 -4.4 0 Z
      M13.5 27.4 H18.5 V28.8 H13.5 Z"/>
    <rect fill="currentColor" x="5.5" y="31.5" width="5" height="4" rx="1"/>
    <rect fill="currentColor" x="21.5" y="31.5" width="5" height="4" rx="1"/>
    <path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
      d="M3 8.5 H1.2 V14.5 M29 8.5 H30.8 V14.5"/>
  </svg>`;

const vehiclePicto = (mode) =>
  mode === "tram" ? TRAM_PICTO : mode === "bus" ? BUS_PICTO : PICTO;

/* Icônes des alertes selon la cause */
const CAUSE_ICONS = {
  travaux: `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor"
    d="M10.6 2h2.8l1.2 4H9.4l1.2-4Zm-1.8 6h6.4l1.1 4H7.7l1.1-4Zm-1.7 6h9.8l1.1 4H6l1.1-4ZM3 20h18v2H3v-2Z"/></svg>`,
  social: `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor"
    d="M8 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 19c0-3.3 2.7-6 6-6s6 2.7 6 6v1H2v-1Zm13.5 1v-1c0-1.9-.7-3.6-1.9-4.9A5.5 5.5 0 0 1 22 19v1h-6.5Z"/></svg>`,
  incident: ALERT_ICON_PATH(),
  info: `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor"
    d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15h-2v-6h2v6Zm0-8h-2V7h2v2Z"/></svg>`,
};

function causeIcon(alert) {
  const text = `${alert.cause || ""} ${alert.titre || ""}`.toLowerCase();
  if (/travaux|chantier|ascenseur|escalator|maintenance/.test(text)) return CAUSE_ICONS.travaux;
  if (/social|grève|greve|manifest/.test(text)) return CAUSE_ICONS.social;
  if (/information/i.test(alert.type || "")) return CAUSE_ICONS.info;
  return CAUSE_ICONS.incident;
}

/* Gravité : 3 majeure, 2 perturbation, 1 travaux/inconnu, 0 information */
function alertLevel(alert) {
  const t = String(alert.type || "").trim().toLowerCase();
  if (t.includes("majeure")) return 3;
  if (t.startsWith("perturbation")) return 2;
  if (t.startsWith("information")) return 0;
  return 1;
}

const ALERT_LABELS = ["Info trafic", "Travaux", "Perturbation", "Perturbation majeure"];

function shortDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const day = d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
  const time = hhmm(d);
  return time === "00:00" ? day : `${day} ${time}`;
}

function alertPeriod(alert) {
  const from = alert.debut ? shortDate(alert.debut) : "";
  const to = alert.fin ? shortDate(alert.fin) : "";
  if (from && to) return `Du ${from} au ${to}`;
  if (from) return `Depuis le ${from}`;
  if (to) return `Jusqu'au ${to}`;
  return "";
}

/* Pastille « temps réel » (ondes, comme sur l'appli TCL) */
const RT_ICON = `
  <svg class="rt" viewBox="0 0 16 16" role="img" aria-label="temps réel">
    <title>Temps réel</title>
    <path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
      d="M3 13 A10 10 0 0 1 13 3 M3 8.4 A5.4 5.4 0 0 1 8.4 3"/>
    <circle cx="3.6" cy="12.4" r="2" fill="currentColor"/>
  </svg>`;

const ALERT_ICON = ALERT_ICON_PATH();

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
  show_approach: true,
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
        const secs = d.heure ? (new Date(d.heure) - now) / 1000 : null;
        deps.push({ ...d, delai, secs });
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
  _timeHtml(d, picto, atStopText, approach = false) {
    const c = this._config;
    if (d.annule) return `<span class="cancel">SUPPRIMÉ</span>`;
    // Tram/bus suivi en temps réel : états des BIV, déduits de l'heure
    // estimée par le SAE (pas de détection physique du véhicule).
    if (approach && c.show_approach && d.temps_reel && d.secs != null) {
      if (d.secs < 60) {
        return `<span class="t-state quai">${
          c.show_picto ? picto : ""
        }<span class="blink">À&#160;QUAI</span></span>`;
      }
      if (d.secs < 150) {
        return `<span class="t-state appr">${
          c.show_picto ? picto.replace(" blink", "") : ""
        }<span>À&#160;L'APPROCHE</span></span>`;
      }
    }
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
    const level = Math.max(...alerts.map(alertLevel));
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
    const open = !!this._alertsOpen;
    const detail = open
      ? `<div class="a-detail">${alerts
          .map(
            (a) => `
            <div class="a-item sev-${alertLevel(a)}">
              <span class="a-cause">${causeIcon(a)}</span>
              <div class="a-body">
                <div class="a-head">
                  <span class="a-type">${esc(ALERT_LABELS[alertLevel(a)])}</span>
                  <span class="a-when">${esc(alertPeriod(a))}</span>
                </div>
                <div class="a-title">${esc(a.titre)}</div>
                ${a.message && a.message !== a.titre ? `<div class="a-msg">${esc(a.message)}</div>` : ""}
              </div>
            </div>`
          )
          .join("")}</div>`
      : "";
    return `
      <div class="alerts sev-${level} ${open ? "open" : ""}" role="button" tabindex="0"
           aria-expanded="${open}" title="${open ? "Masquer" : "Afficher"} le détail des alertes">
        <span class="a-chip">${ALERT_ICON}<span>${esc(ALERT_LABELS[level])}</span>${
          alerts.length > 1 ? `<span class="a-count">${alerts.length}</span>` : ""
        }</span>
        <div class="a-track"><span class="a-text" style="animation-duration:${dur}s">${text}</span></div>
        <span class="a-chev" aria-hidden="true">▾</span>
      </div>
      ${detail}`;
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

    // Bandeau d'alertes : clic = déplier/replier le détail (pas la fiche)
    const banner = this.shadowRoot.querySelector(".alerts");
    if (banner) {
      const toggle = (ev) => {
        ev.stopPropagation();
        this._alertsOpen = !this._alertsOpen;
        this._lastHtml = null;
        this._render();
        this.shadowRoot.querySelector(".alerts")?.focus();
      };
      banner.addEventListener("click", toggle);
      banner.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          toggle(ev);
        }
      });
    }
    this.shadowRoot
      .querySelector(".a-detail")
      ?.addEventListener("click", (ev) => ev.stopPropagation());

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
              `<span class="m-rowpicto blink">${vehiclePicto(entities[0].attributes.mode)}</span>`,
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
            const picto = vehiclePicto(entities[0].attributes.mode);
            const delay = this._timeHtml(
              d,
              `<span class="t-rowpicto blink">${picto}</span>`,
              "&gt;&gt;",
              true
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
      <div class="biv tram" style="${this._cssVars()};--tcl-line:${esc(color)}">
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
    margin: 12px 16px 16px; border-radius: 14px; overflow: hidden;
    border: 1px solid #000; padding: 5px;
    /* boîtier en aluminium anodisé */
    background: linear-gradient(160deg, #3a3e44, #1d2024 45%, #121417);
    box-shadow: 0 8px 22px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.18),
                inset 0 -1px 0 rgba(0,0,0,.6);
    line-height: 1.15; cursor: pointer;
    container-type: inline-size; container-name: biv;
    transition: box-shadow .2s ease, transform .2s ease;
  }
  .biv:hover { box-shadow: 0 12px 28px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.18); }
  .biv > :first-child { border-radius: 9px 9px 0 0; }
  .biv > :last-child { border-radius: 0 0 9px 9px; }
  .biv > :only-child { border-radius: 9px; }

  /* verre de l'écran : reflet + trame fine */
  .m-screen, .t-screen { position: relative; overflow: hidden; }
  .m-screen::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: repeating-linear-gradient(0deg, rgba(255,255,255,.022) 0 1px, transparent 1px 3px);
  }
  .m-screen::after, .t-screen::after {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: linear-gradient(165deg, rgba(255,255,255,.075), rgba(255,255,255,0) 38%);
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

  /* bandeau d'alertes trafic : étiquette + texte LED défilant */
  .alerts {
    --sev: #f2a900; --sev-ink: #111; --sev-led: #ffc23d;
    display: flex; align-items: center; gap: 10px; padding: 6px 10px 6px 6px;
    background: #0b0b0c; border-top: 1px solid #2a2a2a;
    font-family: Arial, Helvetica, sans-serif; font-size: 13px; overflow: hidden;
    cursor: pointer; outline: none;
  }
  .alerts:focus-visible { box-shadow: inset 0 0 0 2px var(--sev); }
  .alerts.sev-0 { --sev: #2f7fd1; --sev-ink: #fff; --sev-led: #9fcbff; }
  .alerts.sev-1 { --sev: #f2a900; --sev-ink: #111; --sev-led: #ffc23d; }
  .alerts.sev-2 { --sev: #ef6c00; --sev-ink: #fff; --sev-led: #ff9a3d; }
  .alerts.sev-3 { --sev: #d6261c; --sev-ink: #fff; --sev-led: #ff5a4d; }
  .a-chip {
    flex: none; display: inline-flex; align-items: center; gap: 5px;
    padding: 4px 8px 4px 6px; border-radius: 5px;
    background: var(--sev); color: var(--sev-ink);
    font-weight: 800; font-size: 11px; letter-spacing: .6px; text-transform: uppercase;
    box-shadow: 0 0 10px color-mix(in srgb, var(--sev) 45%, transparent);
  }
  .alerts.sev-3 .a-chip { animation: tcl-pulse 1.6s ease-in-out infinite; }
  @keyframes tcl-pulse { 50% { box-shadow: 0 0 2px transparent; filter: brightness(1.15); } }
  .a-chip svg { width: 15px; height: 15px; }
  .a-count { margin-left: 2px; min-width: 16px; height: 16px; padding: 0 3px;
             border-radius: 8px; background: rgba(0,0,0,.28); color: inherit;
             display: inline-flex; align-items: center; justify-content: center;
             font-size: 10px; letter-spacing: 0; }
  .a-track { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap;
             color: var(--sev-led); font-weight: 700; letter-spacing: .4px;
             text-shadow: 0 0 6px color-mix(in srgb, var(--sev-led) 60%, transparent);
             mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent); }
  .a-text { display: inline-block; padding-left: 100%;
            animation: tcl-marquee 20s linear infinite; }
  .a-text b { color: #fff; text-shadow: 0 0 6px color-mix(in srgb, var(--sev-led) 70%, transparent); }
  .a-sep { margin: 0 14px; opacity: .55; }
  .a-chev { flex: none; color: #888; font-size: 14px; transition: transform .2s ease; }
  .alerts.open .a-chev { transform: rotate(180deg); }
  @keyframes tcl-marquee { from { transform: translateX(0) } to { transform: translateX(-100%) } }

  /* détail des alertes (dépliable) */
  .a-detail { background: #141518; border-top: 1px solid #2a2a2a; padding: 8px;
              display: flex; flex-direction: column; gap: 6px; cursor: default;
              font-family: Arial, Helvetica, sans-serif; color: #e8e8e8; }
  .a-item { --sev: #f2a900; display: flex; gap: 10px; padding: 9px 10px;
            border-radius: 8px; background: #1d1f23;
            border-left: 4px solid var(--sev); }
  .a-item.sev-0 { --sev: #2f7fd1; }
  .a-item.sev-2 { --sev: #ef6c00; }
  .a-item.sev-3 { --sev: #d6261c; background: #2a1715; }
  .a-cause { flex: none; width: 22px; height: 22px; color: var(--sev); margin-top: 1px; }
  .a-cause svg { width: 100%; height: 100%; }
  .a-body { flex: 1; min-width: 0; }
  .a-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px;
            margin-bottom: 3px; }
  .a-type { font-size: 10px; font-weight: 800; letter-spacing: .7px;
            text-transform: uppercase; color: var(--sev); }
  .a-when { font-size: 11px; color: #9aa0a6; }
  .a-title { font-size: 14px; font-weight: 700; line-height: 1.25; }
  .a-msg { margin-top: 3px; font-size: 12.5px; line-height: 1.4; color: #c4c7cc; }

  /* tram/bus : états « à l'approche » / « à quai » */
  .t-state { display: inline-flex; align-items: center; gap: 6px;
             font-size: .8em; letter-spacing: 1px; }
  .t-state .t-rowpicto { width: 1.75em; height: 1.75em; }
  .t-state.quai { color: #fff2c4; }

  @media (prefers-reduced-motion: reduce) {
    .a-track { white-space: normal; mask-image: none; }
    .a-text { animation: none; padding-left: 0; }
    .blink, .rt, .a-chip { animation: none !important; }
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
    background: var(--tcl-header-bg, linear-gradient(#fbd632, #f2c200 55%, #e4b000));
    border-bottom: 3px solid #c99700;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.45);
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
           font-weight: 700; padding: 2px 0; min-height: 32px; position: relative; }
  .m-row + .m-row { border-top: 1px solid rgba(255,255,255,.05); }
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
    background: var(--tcl-header-bg, linear-gradient(#5d636a, #3f4449));
    border-bottom: 2px solid #2e3236;
    box-shadow: inset 5px 0 0 var(--tcl-line, transparent),
                inset 0 1px 0 rgba(255,255,255,.12);
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
  .t-row + .t-row { border-top: 1px dotted rgba(255,166,26,.14); }
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
    .t-state { gap: 4px; letter-spacing: .5px; }
  }
  @container biv (max-width: 340px) {
    .m-screen { gap: 10px; padding: 10px 10px; }
    .m-clock { font-size: 22px; }
    .m-row { font-size: 16px; }
    .m-lbl { min-width: 76px; }
    .t-row { font-size: 15px; letter-spacing: .5px; }
    .a-chip { font-size: 9.5px; letter-spacing: .2px; padding: 3px 6px 3px 4px; }
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
  ["show_approach", "À l'approche / à quai (tram, bus)"],
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
