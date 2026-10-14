"""Client API data.grandlyon.com pour les données temps réel TCL.

Documentation : https://rdata-grandlyon.readthedocs.io/fr/latest/services.html
Authentification : Basic Auth HTTP (compte data.grandlyon.com).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import aiohttp

from homeassistant.util import dt as dt_util

from .const import FALLBACK_COLORS
from .gtfs import TZ_LYON, fuzzy_match
from .siri import SIRI_ET_URL, line_ref, parse_estimated_calls, summarize

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://data.grandlyon.com/fr/datapusher/ws/rdata"
DATASET_SCHEMA = "tcl_sytral"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
# Le flux SIRI est un complément : il ne doit jamais retarder la mise à jour
SIRI_TIMEOUT = aiohttp.ClientTimeout(total=15)
ALERTS_CACHE_SECONDS = 300
SIRI_CACHE_SECONDS = 10

# Gravité des alertes trafic, de la plus forte à la plus faible
ALERT_TYPE_RANK = {
    "perturbation majeure": 3,
    "perturbation": 2,
    "travaux": 1,
    "information": 0,
}


def alert_level(alert: dict) -> int:
    """Gravité d'une alerte (type inconnu = 1, comme des travaux)."""
    return ALERT_TYPE_RANK.get(str(alert.get("type") or "").strip().lower(), 1)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant-TCL/1.0)",
    "Accept": "application/json",
}

# Champs possibles selon la version des datasets (le réseau TCL unifié a
# fait évoluer certains schémas) : on prend le premier champ présent.
LINE_CODE_FIELDS = ("ligne", "code_ligne", "ligne_com", "code_trace")
LINE_NAME_FIELDS = ("libelle", "nom_trace", "nom", "infos")
LINE_COLOR_FIELDS = ("couleur", "couleur_ligne")
STOP_ID_FIELDS = ("id", "idarret", "id_arret")
STOP_NAME_FIELDS = ("nom", "nom_arret", "libelle")
STOP_DESSERTE_FIELDS = ("desserte",)
PASSAGE_STOP_FIELDS = ("id", "idarret", "id_arret")
PASSAGE_LINE_FIELDS = ("ligne",)
PASSAGE_DIRECTION_FIELDS = ("direction", "destination")
PASSAGE_DELAY_FIELDS = ("delaipassage", "delai")
PASSAGE_TIME_FIELDS = ("heurepassage", "heure")
PASSAGE_TYPE_FIELDS = ("type",)
PASSAGE_DEST_ID_FIELDS = ("idtarretdestination",)
PASSAGE_COURSE_FIELDS = ("coursetheorique",)

# Noms de tables connus, essayés dans l'ordre si le catalogue
# /rdata/all.json est inaccessible (certains comptes reçoivent un 403).
# Les datasets sont versionnés (_2_0_0, _3_0_0…) et les versions changent :
# on sonde le nom nu puis chaque version, de la plus récente à la plus vieille.
_TABLE_BASES: dict[str, tuple[str, ...]] = {
    "passages": ("tclpassagearret",),
    "stops": ("tclarret", "tclpointarret"),
    "metro": ("tcllignemf",),
    "tram": ("tcllignetram",),
    "bus": ("tcllignebus",),
    "alerts": ("tclalertetrafic",),
}
_TABLE_VERSIONS = ("", "_5_0_0", "_4_0_0", "_3_0_0", "_2_0_0", "_1_0_0")

# Lignes structurelles du réseau, toujours proposées même si le temps réel
# ne les montre pas (la nuit, seules les lignes en circulation apparaissent).
KNOWN_LINES: dict[str, tuple[str, ...]] = {
    "metro": ("A", "B", "C", "D"),
    "funiculaire": ("F1", "F2"),
    "tram": ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "RX"),
    "bus": (),
}

# Terminus connus, toujours proposés au choix de direction (le temps réel
# ne montre des directions que si la ligne circule au moment de la config).
# Libellés = trip_headsign du GTFS du réseau unifié (sept. 2025), tels
# qu'affichés par le temps réel — souvent abrégés (Hôp., St-, Cat.…).
KNOWN_DIRECTIONS: dict[str, tuple[str, ...]] = {
    "A": ("Perrache", "Vaulx-en-Velin La Soie"),
    "B": ("Charpennes Charles Hernu", "St-Genis-Laval Hôp. Sud"),
    "C": ("Hôtel de Ville L. Pradel", "Cuire"),
    "D": ("Gare de Vaise-G.Collomb", "Gare de Vénissieux"),
    "F1": ("Vieux Lyon Cat. St-Jean", "Saint-Just"),
    "F2": ("Vieux Lyon Cat. St-Jean", "Fourvière"),
    "T1": ("Debourg", "IUT Feyssine"),
    "T2": ("Hôtel Région Montrochet", "Saint-Priest Bel Air"),
    "T3": ("Gare Part-Dieu Villette", "Meyzieu Z.i."),
    "T4": ("La Doua - Gaston Berger", "Hôp. Feyzin Vénissieux"),
    "T5": ("Grange Blanche", "Eurexpo Entrée Princ."),
    "T6": ("La Doua - Gaston Berger", "Debourg"),
    "T7": ("Vaulx-en-Velin La Soie", "Décines OL Vallée"),
    "RX": ("Gare Part-Dieu Villette", "Aéroport St Exupéry -RX"),
}
DEFAULT_TABLES: dict[str, tuple[str, ...]] = {
    key: tuple(
        f"{DATASET_SCHEMA}.{base}{version}"
        for base in bases
        for version in _TABLE_VERSIONS
    )
    for key, bases in _TABLE_BASES.items()
}
# Alertes : la v2 (vérifiée en oct. 2026) avant une éventuelle v1 figée
DEFAULT_TABLES["alerts"] = (
    f"{DATASET_SCHEMA}.tclalertetrafic_2",
    *DEFAULT_TABLES["alerts"],
)


class TCLApiError(Exception):
    """Erreur générique de l'API."""


class TCLAuthError(TCLApiError):
    """Identifiants invalides ou accès refusé."""


def _first(row: dict, fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in row and row[field] not in (None, ""):
            return row[field]
    return None


def _normalize_color(value: Any) -> str | None:
    """Normalise la couleur de l'API ('255 0 0' ou '#FF0000') en hex."""
    if not value:
        return None
    value = str(value).strip()
    if value.startswith("#"):
        return value
    match = re.fullmatch(r"(\d{1,3})\D+(\d{1,3})\D+(\d{1,3})", value)
    if match:
        r, g, b = (min(int(x), 255) for x in match.groups())
        return f"#{r:02X}{g:02X}{b:02X}"
    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return f"#{value.upper()}"
    return None


def parse_delay_minutes(delay_text: str | None, time_text: str | None) -> int | None:
    """Convertit le délai de l'API en minutes.

    'Proche' -> 0, '5 min' -> 5, sinon calcul depuis l'heure de passage.
    """
    if delay_text:
        text = str(delay_text).strip().lower()
        if "proche" in text or "quai" in text or "imminent" in text:
            return 0
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
    if time_text:
        passage_dt = _parse_passage_time(time_text)
        if passage_dt is not None:
            delta = (passage_dt - dt_util.now()).total_seconds()
            if delta < -60:
                return None  # départ passé
            return max(0, int(delta // 60))
    return None


def _parse_passage_time(value: str) -> Any:
    """Parse 'YYYY-MM-DD HH:MM:SS' (heure locale Europe/Paris)."""
    parsed = dt_util.parse_datetime(str(value).replace(" ", "T"))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ_LYON)
    return parsed


class TCLApiClient:
    """Client asynchrone pour les datasets TCL de data.grandlyon.com."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._auth = aiohttp.BasicAuth(username, password, encoding="utf-8")
        self.tables: dict[str, str | None] = {}
        self._discovery_done = False
        self._stops_cache: list[dict] | None = None
        self._filter_style: str | None = None
        self._scan_cache: tuple[float, list[dict]] | None = None
        self._warned_directions: set[str] = set()
        # id d'arrêt terminus -> libellé de direction (appris du temps réel)
        self._dest_names: dict[str, str] = {}
        self._alerts_cache: tuple[float, list[dict]] | None = None
        self._siri_cache: dict[str, tuple[float, Any]] = {}
        self.siri_available: bool | None = None
        # ligne -> état du flux SIRI (exposé en attribut pour le dépannage)
        self.siri_status: dict[str, dict] = {}

    async def _get_json(
        self,
        url: str,
        params: dict | None = None,
        timeout: aiohttp.ClientTimeout = REQUEST_TIMEOUT,
        quiet: bool = False,
    ) -> dict:
        try:
            async with self._session.get(
                url,
                params=params,
                auth=self._auth,
                headers=HEADERS,
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    body = (await resp.text())[:300]
                    _LOGGER.log(
                        logging.DEBUG if quiet else logging.WARNING,
                        "Réponse %s de %s : %s",
                        resp.status,
                        url,
                        body,
                    )
                    if resp.status == 401:
                        raise TCLAuthError(
                            "Identifiants refusés (401) par data.grandlyon.com"
                        )
                    if resp.status == 403:
                        raise TCLAuthError(
                            f"Accès refusé (403) : {body or 'requête bloquée'}"
                        )
                    raise TCLApiError(f"Erreur HTTP {resp.status} sur {url}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TCLApiError(f"Erreur réseau : {err!r}") from err
        except ValueError as err:  # JSON invalide
            raise TCLApiError(f"Réponse illisible de {url} : {err}") from err

    @staticmethod
    def _values(data: dict) -> list[dict]:
        values = data.get("values") or data.get("results") or []
        return [v for v in values if isinstance(v, dict)]

    async def _async_fetch_table_rows(
        self, table: str, page_size: int = 500, max_pages: int = 300
    ) -> list[dict]:
        """Récupère une table complète.

        maxfeatures=-1 renvoie la table entière en une seule requête ;
        en cas d'échec, repli sur la pagination via le lien 'next'.
        """
        url = f"{BASE_URL}/{table}/all.json"
        try:
            data = await self._get_json(url, params={"maxfeatures": -1})
            rows = self._values(data)
            if rows:
                return rows
        except TCLAuthError:
            raise
        except TCLApiError as err:
            _LOGGER.debug(
                "maxfeatures=-1 refusé sur %s (%s) : repli sur pagination",
                table,
                err,
            )

        params: dict | None = {"maxfeatures": page_size}
        rows = []
        for _ in range(max_pages):
            data = await self._get_json(url, params=params)
            page = self._values(data)
            rows.extend(page)
            next_url = data.get("next")
            if not next_url or not page:
                break
            url, params = next_url, None
        return rows

    # ------------------------------------------------------------------
    # Découverte des datasets
    # ------------------------------------------------------------------
    async def async_discover_tables(self) -> dict[str, str | None]:
        """Trouve les noms réels des tables tcl_sytral via le catalogue.

        Le catalogue /rdata/all.json renvoie un 403 pour certains comptes :
        dans ce cas on retombe sur les noms connus (DEFAULT_TABLES), testés
        à la demande par async_table().
        """
        try:
            data = await self._get_json(f"{BASE_URL}/all.json")
        except TCLApiError as err:
            _LOGGER.info(
                "Catalogue inaccessible (%s) : utilisation des noms de tables "
                "par défaut",
                err,
            )
            self.tables = {}
            return self.tables

        tables = [
            f"{r['table_schema']}.{r['table_name']}"
            for r in data.get("results", [])
            if r.get("table_schema") == DATASET_SCHEMA and r.get("table_name")
        ]

        def pick(patterns: tuple[str, ...], exclude: tuple[str, ...] = ()) -> str | None:
            candidates = [
                t
                for t in tables
                if any(p in t for p in patterns) and not any(e in t for e in exclude)
            ]
            # Le tri place la version la plus récente (suffixe _X_Y_Z) en dernier
            return sorted(candidates)[-1] if candidates else None

        discovered = {
            "passages": pick(("passagearret",)),
            "stops": pick(("pointarret", "tclarret"), exclude=("passage",)),
            "metro": pick(("lignemf",)),
            "tram": pick(("lignetram",)),
            "bus": pick(("lignebus",)),
            "alerts": pick(("alertetrafic",)),
        }
        # On ne garde que ce qui a été trouvé ; le reste passera par les défauts
        self.tables = {k: v for k, v in discovered.items() if v}
        self._discovery_done = True
        _LOGGER.debug("Tables TCL découvertes : %s", self.tables)
        return self.tables

    async def async_table(self, key: str) -> str:
        """Nom de table utilisable pour `key`, avec repli sur les défauts.

        Chaque candidat est validé par une requête maxfeatures=1. Un refus
        d'authentification (401/403 sur le dataset) est propagé tel quel.
        """
        if not self._discovery_done:
            self._discovery_done = True
            await self.async_discover_tables()
        if self.tables.get(key):
            return self.tables[key]

        last_err: TCLApiError | None = None
        for candidate in DEFAULT_TABLES.get(key, ()):
            try:
                await self._get_json(
                    f"{BASE_URL}/{candidate}/all.json", params={"maxfeatures": 1}
                )
            except TCLAuthError:
                raise
            except TCLApiError as err:
                last_err = err
                continue
            self.tables[key] = candidate
            _LOGGER.info("Table retenue pour '%s' : %s", key, candidate)
            return candidate
        raise TCLApiError(
            f"Aucune table utilisable pour '{key}' (dernière erreur : {last_err})"
        )

    # ------------------------------------------------------------------
    # Validation des identifiants
    # ------------------------------------------------------------------
    async def async_validate_credentials(self) -> None:
        """Vérifie l'accès au dataset temps réel (protégé par auth)."""
        table = await self.async_table("passages")
        await self._get_json(
            f"{BASE_URL}/{table}/all.json",
            params={"maxfeatures": 1},
        )

    # ------------------------------------------------------------------
    # Lignes
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_line(code: str) -> str:
        """Devine le mode d'une ligne à partir de son code commercial."""
        c = code.strip().upper()
        if c in ("A", "B", "C", "D", "E"):
            return "metro"
        if c in ("F1", "F2", "FUN"):
            return "funiculaire"
        if (c.startswith("T") and c[1:].isdigit()) or c in ("RX", "RHONEXPRESS"):
            return "tram"
        return "bus"

    async def _async_lines_from_passages(self, mode: str) -> list[dict]:
        """Repli : lignes déduites du dataset passages (seul garanti accessible).

        Essaie l'endpoint des valeurs distinctes (/ligne.json), qui peut
        renvoyer des chaînes ou des dicts selon les versions, puis à défaut
        échantillonne directement les enregistrements de passages.
        """
        table = await self.async_table("passages")
        codes: set[str] = set()

        try:
            data = await self._get_json(
                f"{BASE_URL}/{table}/ligne.json", params={"maxfeatures": 500}
            )
            for v in data.get("values", []):
                if isinstance(v, dict):
                    v = _first(v, PASSAGE_LINE_FIELDS)
                if v:
                    codes.add(str(v).strip())
        except TCLApiError as err:
            _LOGGER.debug("Endpoint ligne.json indisponible : %s", err)

        if not codes:
            _LOGGER.debug("Échantillonnage des passages pour lister les lignes")
            rows = await self._async_scan_passages()
            for row in rows:
                v = _first(row, PASSAGE_LINE_FIELDS)
                if v:
                    codes.add(str(v).strip())

        codes.update(KNOWN_LINES.get(mode, ()))
        lines = [
            {
                "code": c,
                "name": c,
                "color": FALLBACK_COLORS.get(c.upper()),
            }
            for c in sorted(codes, key=lambda x: (len(x), x))
            if self._classify_line(c) == mode
        ]
        _LOGGER.info(
            "Lignes %s déduites du temps réel : %s", mode, [l["code"] for l in lines]
        )
        return lines

    async def async_get_lines(self, mode: str) -> list[dict]:
        """Liste des lignes pour un mode : [{code, name, color}]."""
        table_key = "metro" if mode in ("metro", "funiculaire") else mode
        try:
            table = await self.async_table(table_key)
            data = {"values": await self._async_fetch_table_rows(table, 500)}
        except TCLApiError as err:
            _LOGGER.warning(
                "Dataset lignes '%s' inaccessible (%s) : repli sur le temps réel",
                table_key,
                err,
            )
            return await self._async_lines_from_passages(mode)
        lines: dict[str, dict] = {}
        for row in self._values(data):
            code = _first(row, LINE_CODE_FIELDS)
            if code is None:
                continue
            code = str(code).strip()
            is_funi = code.upper().startswith("F") and code.upper() not in ("F",)
            if mode == "metro" and is_funi:
                continue
            if mode == "funiculaire" and not is_funi:
                continue
            if code not in lines:
                lines[code] = {
                    "code": code,
                    "name": str(_first(row, LINE_NAME_FIELDS) or code),
                    "color": _normalize_color(_first(row, LINE_COLOR_FIELDS)),
                }
        return sorted(lines.values(), key=lambda l: (len(l["code"]), l["code"]))

    # ------------------------------------------------------------------
    # Arrêts / stations
    # ------------------------------------------------------------------
    async def _async_get_all_stops(self) -> list[dict]:
        if self._stops_cache is not None:
            return self._stops_cache
        try:
            table = await self.async_table("stops")
            rows = await self._async_fetch_table_rows(table, page_size=1000)
            data = {"values": rows}
        except TCLApiError as err:
            _LOGGER.warning(
                "Dataset arrêts inaccessible (%s) : les stations seront "
                "identifiées par leur numéro d'arrêt",
                err,
            )
            self._stops_cache = []
            return self._stops_cache
        stops = []
        for row in self._values(data):
            stop_id = _first(row, STOP_ID_FIELDS)
            name = _first(row, STOP_NAME_FIELDS)
            if stop_id is None or not name:
                continue
            stops.append(
                {
                    "id": str(stop_id),
                    "name": str(name).strip(),
                    "desserte": str(_first(row, STOP_DESSERTE_FIELDS) or ""),
                }
            )
        self._stops_cache = stops
        return stops

    async def async_get_stations_for_line(self, line_code: str) -> dict[str, list[str]]:
        """Stations desservies par une ligne : {nom_station: [stop_ids]}.

        Le champ 'desserte' d'un arrêt vaut par ex. 'C3:A,37:R'.
        """
        stops = await self._async_get_all_stops()
        target = line_code.strip().upper()
        stations: dict[str, list[str]] = {}
        for stop in stops:
            for token in stop["desserte"].split(","):
                served = token.split(":")[0].strip().upper()
                if served == target:
                    stations.setdefault(stop["name"], []).append(stop["id"])
                    break

        if not stations:
            # Fallback : arrêts observés dans les passages temps réel
            _LOGGER.debug(
                "Aucune station via desserte pour %s, fallback temps réel", line_code
            )
            passages = await self._async_passages_filtered("ligne", [line_code])
            by_id = {s["id"]: s["name"] for s in stops}
            for p in passages:
                stop_id = _first(p, PASSAGE_STOP_FIELDS)
                if stop_id is None:
                    continue
                stop_id = str(stop_id)
                name = by_id.get(stop_id, f"Arrêt {stop_id}")
                if stop_id not in stations.get(name, []):
                    stations.setdefault(name, []).append(stop_id)
        return dict(sorted(stations.items()))

    # ------------------------------------------------------------------
    # Passages temps réel
    # ------------------------------------------------------------------
    async def _async_fetch_passages(self, filters: dict) -> list[dict]:
        table = await self.async_table("passages")
        params = {"maxfeatures": 500, **filters}
        data = await self._get_json(
            f"{BASE_URL}/{table}/all.json", params=params
        )
        return self._values(data)

    async def _async_scan_passages(self) -> list[dict]:
        """Scan paginé du dataset passages complet (filtrage côté client).

        Le résultat est mis en cache 30 s : plusieurs entrées de config
        partagent le même client HTTP et ne déclenchent qu'un scan.
        """
        if self._scan_cache and time.monotonic() - self._scan_cache[0] < 30:
            return self._scan_cache[1]

        table = await self.async_table("passages")
        rows = await self._async_fetch_table_rows(table, page_size=500)
        _LOGGER.info("Scan passages : %d enregistrements", len(rows))
        self._scan_cache = (time.monotonic(), rows)
        return rows

    async def _async_passages_filtered(
        self, field: str, values: list[str]
    ) -> list[dict]:
        """Passages filtrés sur un champ.

        Le proxy data.grandlyon.com a changé plusieurs fois de syntaxe de
        filtre : on essaie ?field=&value=, ?<champ>=<valeur> puis
        ?<champ>__in=. Si aucune ne renvoie de résultat, scan complet
        filtré côté client (seule méthode garantie).
        """
        wanted = {str(v) for v in values}

        async def try_style(style: str) -> list[dict]:
            try:
                if style == "field":
                    rows: list[dict] = []
                    for v in values:
                        rows.extend(
                            await self._async_fetch_passages(
                                {"maxfeatures": 500, "field": field, "value": v}
                            )
                        )
                    return rows
                if style == "direct":
                    rows = []
                    for v in values:
                        rows.extend(
                            await self._async_fetch_passages(
                                {"maxfeatures": 500, field: v}
                            )
                        )
                    return rows
                return await self._async_fetch_passages(
                    {f"{field}__in": ",".join(values)}
                )
            except TCLApiError as err:
                _LOGGER.debug("Filtre '%s' en échec : %s", style, err)
                return []

        styles = (
            [self._filter_style]
            if self._filter_style
            else ["field", "direct", "django"]
        )
        for style in styles:
            rows = await try_style(style)
            # On vérifie que le serveur a réellement filtré (et pas ignoré
            # le paramètre en renvoyant n'importe quoi).
            rows = [r for r in rows if str(r.get(field, "")) in wanted]
            if rows:
                if self._filter_style != style:
                    _LOGGER.info("Syntaxe de filtre retenue : %s", style)
                    self._filter_style = style
                return rows

        rows = await self._async_scan_passages()
        matched = [r for r in rows if str(r.get(field, "")) in wanted]
        _LOGGER.debug(
            "Scan : %d/%d passages correspondent à %s in %s "
            "(exemples de valeurs du scan : %s)",
            len(matched),
            len(rows),
            field,
            sorted(wanted)[:5],
            sorted({str(r.get(field, "")) for r in rows[:200]})[:10],
        )
        return matched

    async def async_get_directions(
        self, stop_ids: list[str], line_code: str | None = None
    ) -> list[str]:
        """Directions (destinations) observées actuellement.

        D'abord aux arrêts demandés, sinon sur toute la ligne (utile quand
        la station n'a plus de passage au moment de la configuration).
        """
        seen: dict[str, None] = {}
        departures = await self.async_get_departures(stop_ids, line_code)
        for dep in departures:
            if dep["destination"]:
                seen.setdefault(dep["destination"], None)
        if not seen and line_code:
            rows = await self._async_passages_filtered("ligne", [line_code])
            for row in rows:
                dest = str(_first(row, PASSAGE_DIRECTION_FIELDS) or "").strip()
                if dest:
                    seen.setdefault(dest, None)
        # Terminus connus en complément (dédupliqués de façon tolérante)
        if line_code:
            for known in KNOWN_DIRECTIONS.get(line_code.strip().upper(), ()):
                if not any(fuzzy_match(known, d) for d in seen):
                    seen.setdefault(known, None)
        return list(seen)

    async def async_get_departures(
        self,
        stop_ids: list[str],
        line_code: str | None = None,
        direction: str | None = None,
    ) -> list[dict]:
        """Prochains départs triés par délai croissant."""
        rows = await self._async_passages_filtered(
            "id", [str(s) for s in stop_ids]
        )
        _LOGGER.debug(
            "Départs : %d passages pour les arrêts %s", len(rows), stop_ids
        )
        if line_code:
            target = line_code.strip().upper()
            rows = [
                r
                for r in rows
                if str(r.get("ligne", "")).strip().upper() == target
            ]
            _LOGGER.debug(
                "Départs : %d passages après filtre ligne %s", len(rows), target
            )

        departures = []
        rejected_directions: set[str] = set()
        for row in rows:
            delay_text = _first(row, PASSAGE_DELAY_FIELDS)
            time_text = _first(row, PASSAGE_TIME_FIELDS)
            delay = parse_delay_minutes(delay_text, time_text)
            if delay is None:
                continue
            dest = str(_first(row, PASSAGE_DIRECTION_FIELDS) or "").strip()
            dest_id = _first(row, PASSAGE_DEST_ID_FIELDS)
            if dest and dest_id is not None:
                # Sert à nommer les terminus des passages SIRI (qui n'ont
                # qu'un identifiant d'arrêt) avec le libellé officiel.
                self._dest_names[str(dest_id)] = dest
            if direction and not fuzzy_match(direction, dest):
                rejected_directions.add(dest)
                continue
            passage_dt = _parse_passage_time(time_text) if time_text else None
            course = _first(row, PASSAGE_COURSE_FIELDS)
            departures.append(
                {
                    "ligne": str(_first(row, PASSAGE_LINE_FIELDS) or ""),
                    "destination": dest,
                    "delai": delay,
                    "delai_texte": str(delay_text) if delay_text else f"{delay} min",
                    "heure": passage_dt.isoformat() if passage_dt else None,
                    "heure_theorique": None,
                    "retard": None,
                    "annule": False,
                    "temps_reel": str(_first(row, PASSAGE_TYPE_FIELDS) or "").upper()
                    == "E",
                    "source": "tcl",
                    "course": str(course) if course else None,
                }
            )
        if (
            direction
            and not departures
            and rejected_directions
            and direction not in self._warned_directions
        ):
            # Direction configurée introuvable : le signaler clairement
            # plutôt que d'afficher silencieusement zéro départ.
            self._warned_directions.add(direction)
            _LOGGER.warning(
                "Aucun passage ne correspond à la direction configurée '%s' "
                "(directions observées aux arrêts %s : %s). Reconfigurez "
                "l'entrée ou choisissez 'Toutes les directions'.",
                direction,
                stop_ids,
                sorted(rejected_directions),
            )
        departures.sort(key=lambda d: d["delai"])
        return departures

    # ------------------------------------------------------------------
    # Temps réel étendu : SIRI Lite estimated-timetables
    # ------------------------------------------------------------------
    async def _async_destination_name(self, dest_id: str | None) -> str:
        if not dest_id:
            return ""
        if dest_id in self._dest_names:
            return self._dest_names[dest_id]
        for stop in await self._async_get_all_stops():
            if stop["id"] == dest_id:
                return stop["name"]
        return ""

    async def async_get_siri_departures(
        self,
        stop_ids: list[str],
        line_code: str,
        direction: str | None = None,
    ) -> list[dict]:
        """Passages d'une ligne aux arrêts demandés, d'après le flux SIRI.

        Contrairement à tclpassagearret (2 passages), on obtient tous les
        passages des courses suivies, avec heure théorique, heure estimée
        (=> retard) et suppressions. Lève TCLApiError si le flux est
        indisponible : l'appelant doit le traiter comme facultatif.
        """
        key = line_code.strip().upper()
        cached = self._siri_cache.get(key)
        try:
            if cached and time.monotonic() - cached[0] < SIRI_CACHE_SECONDS:
                payload = cached[1]  # plusieurs arrêts suivis sur la même ligne
            else:
                payload = await self._get_json(
                    SIRI_ET_URL,
                    params={"LineRef": line_ref(line_code)},
                    timeout=SIRI_TIMEOUT,
                    quiet=True,
                )
                self._siri_cache[key] = (time.monotonic(), payload)
        except TCLApiError as err:
            if self.siri_available is not False:
                _LOGGER.info(
                    "Flux SIRI estimated-timetables indisponible pour la ligne %s "
                    "(%s) : repli sur tclpassagearret",
                    key,
                    err,
                )
            self.siri_available = False
            self.siri_status[key] = {
                "etat": "erreur",
                "detail": str(err)[:200],
                "maj": dt_util.now().isoformat(timespec="seconds"),
            }
            raise
        if self.siri_available is not True:
            _LOGGER.debug("Flux SIRI estimated-timetables disponible")
        self.siri_available = True

        calls = parse_estimated_calls(payload, stop_ids, line_code)
        now = dt_util.now()
        departures: list[dict] = []
        for call in calls:
            when = call["estime"] or call["theorique"]
            seconds = (when - now).total_seconds()
            if seconds < -30:
                continue  # déjà parti
            dest = call["destination_nom"] or await self._async_destination_name(
                call["destination_id"]
            )
            if direction and not (dest and fuzzy_match(direction, dest)):
                continue
            delay = max(0, int(seconds // 60))
            retard = None
            if call["estime"] is not None and call["theorique"] is not None:
                retard = round(
                    (call["estime"] - call["theorique"]).total_seconds() / 60
                )
            local = when.astimezone(TZ_LYON)
            departures.append(
                {
                    "ligne": call["ligne"] or line_code,
                    "destination": dest,
                    "delai": delay,
                    "delai_texte": "Supprimé"
                    if call["annule"]
                    else ("Proche" if delay == 0 else f"{delay} min"),
                    "heure": local.isoformat(),
                    "heure_theorique": call["theorique"].astimezone(TZ_LYON).isoformat()
                    if call["theorique"]
                    else None,
                    "retard": retard,
                    "annule": call["annule"],
                    "temps_reel": call["estime"] is not None,
                    "source": "siri",
                    "course": call["course"],
                }
            )
        summary = summarize(payload)
        if not summary["courses"]:
            state = "aucune course suivie sur la ligne"
        elif not calls:
            state = "aucun passage à ces arrêts"
        elif not departures:
            state = "passages hors direction ou déjà partis"
        else:
            state = "ok"
        self.siri_status[key] = {
            "etat": state,
            "maj": now.isoformat(timespec="seconds"),
            "courses_suivies": summary["courses"],
            "passages_aux_arrets": len(calls),
            "retenus": len(departures),
            "arrets_configures": [str(s) for s in stop_ids],
            **(
                {"lignes_recues": summary["lignes"], "exemples_arrets": summary["exemples_arrets"]}
                if state != "ok"
                else {}
            ),
        }
        _LOGGER.debug(
            "SIRI : %d passages ligne %s aux arrêts %s (%d retenus) %s",
            len(calls),
            line_code,
            stop_ids,
            len(departures),
            summary,
        )
        return departures

    # ------------------------------------------------------------------
    # Alertes trafic
    # ------------------------------------------------------------------
    async def _async_all_alerts(self) -> list[dict]:
        """Table complète des alertes (quelques centaines de lignes), en cache."""
        if (
            self._alerts_cache
            and time.monotonic() - self._alerts_cache[0] < ALERTS_CACHE_SECONDS
        ):
            return self._alerts_cache[1]
        table = await self.async_table("alerts")
        rows = await self._async_fetch_table_rows(table, page_size=500)
        self._alerts_cache = (time.monotonic(), rows)
        return rows

    async def async_get_alerts(self, line_code: str) -> list[dict]:
        """Alertes trafic EN COURS pour une ligne, les plus graves d'abord."""
        target = line_code.strip().upper()
        now = dt_util.now()
        alerts: dict[str, dict] = {}
        for row in await self._async_all_alerts():
            lines = {
                str(row.get(field) or "").strip().upper()
                for field in ("ligne_cli", "ligne_com")
            }
            lines.update(
                token.strip().upper()
                for token in re.split(r"[,;| ]+", str(row.get("listeobjet") or ""))
            )
            if target not in lines:
                continue
            start = _parse_passage_time(row["debut"]) if row.get("debut") else None
            end = _parse_passage_time(row["fin"]) if row.get("fin") else None
            if (start and start > now) or (end and end < now):
                continue
            title = str(row.get("titre") or "").strip().rstrip(" -")
            message = re.sub(r"\s+", " ", str(row.get("message") or "")).strip()
            key = f"{title}|{message}"
            if key in alerts:
                continue  # même alerte déclinée par sens/ligne commerciale
            alerts[key] = {
                "type": str(row.get("type") or "Information"),
                "cause": row.get("cause"),
                "titre": title or message[:80],
                "message": message,
                "debut": start.isoformat() if start else None,
                "fin": end.isoformat() if end else None,
            }
        return sorted(
            alerts.values(),
            key=lambda a: (-alert_level(a), a["debut"] or ""),
        )
