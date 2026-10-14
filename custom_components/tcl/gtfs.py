"""Horaires théoriques GTFS TCL.

Complète le temps réel (tclpassagearret) quand celui-ci est vide, typiquement
la nuit : permet d'afficher les premiers départs du lendemain.

Le fichier GTFS officiel est téléchargé avec les mêmes identifiants
data.grandlyon.com (licence Mobilités) et ré-indexé uniquement pour les
stations/lignes configurées, en tâche de fond.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import time
import unicodedata
import zipfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Les horaires TCL (GTFS et temps réel) sont exprimés en heure de Lyon,
# indépendamment du fuseau configuré dans Home Assistant.
TZ_LYON = ZoneInfo("Europe/Paris")

GTFS_URL = (
    "https://download.data.grandlyon.com/files/rdata/"
    "tcl_sytral.tcltheorique/GTFS_TCL.ZIP"
)
MAX_AGE_SECONDS = 7 * 24 * 3600  # re-téléchargement hebdomadaire
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=900)


def norm(value: str | None) -> str:
    """Normalisation tolérante : accents, casse, ponctuation."""
    if not value:
        return ""
    text = unicodedata.normalize("NFD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = "".join(c if c.isalnum() else " " for c in text.casefold())
    return " ".join(text.split())


# Abréviations des girouettes/BIV TCL ("St-Genis-Laval Hôp. Sud",
# "Vieux Lyon Cat. St-Jean", "Eurexpo Entrée Princ."…).
_ABBREVIATIONS = {
    "st": "saint",
    "ste": "sainte",
    "hop": "hopital",
    "cat": "cathedrale",
    "princ": "principale",
    "gde": "grande",
}


def _tokens(value: str | None) -> tuple[str, ...]:
    return tuple(_ABBREVIATIONS.get(t, t) for t in norm(value).split())


def fuzzy_match(a: str, b: str) -> bool:
    """Comparaison tolérante : accents, casse, abréviations, mots manquants.

    Les destinations affichées sont souvent abrégées : « St-Genis-Laval
    Hôp. Sud » doit correspondre à « Saint-Genis-Laval Hôpital Lyon Sud ».
    Après normalisation et expansion des abréviations, on accepte si une
    chaîne contient l'autre, ou si tous les mots de la plus courte
    apparaissent dans la plus longue.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    sa, sb = " ".join(ta), " ".join(tb)
    if sa in sb or sb in sa:
        return True
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return set(small) <= set(big)


def _parse_gtfs_time(value: str) -> int | None:
    """'25:04:00' -> secondes depuis minuit (peut dépasser 24 h)."""
    try:
        h, m, s = value.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except (ValueError, AttributeError):
        return None


class TCLGtfsSchedule:
    """Index GTFS partagé entre toutes les entrées de configuration."""

    def __init__(
        self, hass: HomeAssistant, session: aiohttp.ClientSession, auth: aiohttp.BasicAuth
    ) -> None:
        self._hass = hass
        self._session = session
        self._auth = auth
        self._path = hass.config.path("tcl_gtfs.zip")
        self._lock = asyncio.Lock()
        self._loading = False
        self._interests: set[tuple[str, str]] = set()
        self._built_for: set[tuple[str, str]] = set()
        # (station_norm, line_norm) -> [(secondes, service_id, destination)]
        self._index: dict[tuple[str, str], list[tuple[int, str, str]]] = {}
        # service_id -> (jours actifs 0-6, début, fin, ajouts, retraits)
        self._services: dict[str, tuple[set[int], date, date, set[date], set[date]]] = {}

    def register(self, station: str, line: str) -> None:
        self._interests.add((norm(station), norm(line)))

    @property
    def ready(self) -> bool:
        return bool(self._built_for) and self._built_for >= self._interests

    def _schedule_load(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._hass.async_create_background_task(
            self._async_load(), name="tcl_gtfs_load"
        )

    async def _async_load(self) -> None:
        try:
            async with self._lock:
                age = (
                    time.time() - os.path.getmtime(self._path)
                    if os.path.exists(self._path)
                    else None
                )
                if age is None or age > MAX_AGE_SECONDS:
                    await self._async_download()
                await self._hass.async_add_executor_job(self._build_index)
                self._built_for = set(self._interests)
                _LOGGER.info(
                    "Index GTFS construit : %d couples station/ligne, "
                    "%d services",
                    len(self._index),
                    len(self._services),
                )
        except Exception as err:  # noqa: BLE001 - ne jamais casser le temps réel
            _LOGGER.warning("Chargement GTFS impossible : %s", err)
        finally:
            self._loading = False

    async def _async_download(self) -> None:
        _LOGGER.info("Téléchargement du GTFS TCL (hebdomadaire)…")
        async with self._session.get(
            GTFS_URL, auth=self._auth, timeout=DOWNLOAD_TIMEOUT
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"GTFS HTTP {resp.status}")
            data = await resp.read()
        if not data[:2] == b"PK":
            raise RuntimeError("GTFS reçu invalide (pas un zip)")

        def _write() -> None:
            with open(self._path, "wb") as f:
                f.write(data)

        await self._hass.async_add_executor_job(_write)
        _LOGGER.info("GTFS TCL téléchargé : %.1f Mo", len(data) / 1e6)

    # ------------------------------------------------------------------
    # Construction de l'index (exécutée dans l'executor)
    # ------------------------------------------------------------------
    def _build_index(self) -> None:
        wanted_lines = {line for _, line in self._interests}
        wanted_stations = {station for station, _ in self._interests}
        index: dict[tuple[str, str], list[tuple[int, str, str]]] = {}
        services: dict[str, tuple[set[int], date, date, set[date], set[date]]] = {}

        with zipfile.ZipFile(self._path) as z:

            def reader(name: str):
                return csv.DictReader(
                    io.TextIOWrapper(z.open(name), encoding="utf-8-sig")
                )

            route_to_line: dict[str, str] = {}
            for row in reader("routes.txt"):
                # route_id peut différer du nom commercial (RX/"Rhônexpress")
                candidates = {
                    norm(row.get("route_short_name")),
                    norm(row.get("route_id")),
                }
                matched = candidates & wanted_lines
                if matched:
                    route_to_line[row["route_id"]] = matched.pop()

            trips: dict[str, tuple[str, str, str]] = {}
            for row in reader("trips.txt"):
                line = route_to_line.get(row.get("route_id", ""))
                if line:
                    trips[row["trip_id"]] = (
                        line,
                        row.get("service_id", ""),
                        row.get("trip_headsign", "") or "",
                    )

            stop_to_station: dict[str, str] = {}
            for row in reader("stops.txt"):
                name = norm(row.get("stop_name"))
                for station in wanted_stations:
                    if name == station or station in name or name in station:
                        stop_to_station[row["stop_id"]] = station
                        break

            for row in reader("stop_times.txt"):
                trip = trips.get(row.get("trip_id", ""))
                if trip is None:
                    continue
                station = stop_to_station.get(row.get("stop_id", ""))
                if station is None:
                    continue
                secs = _parse_gtfs_time(
                    row.get("departure_time") or row.get("arrival_time") or ""
                )
                if secs is None:
                    continue
                line, service_id, headsign = trip
                index.setdefault((station, line), []).append(
                    (secs, service_id, headsign)
                )

            try:
                for row in reader("calendar.txt"):
                    days = {
                        i
                        for i, day in enumerate(
                            (
                                "monday",
                                "tuesday",
                                "wednesday",
                                "thursday",
                                "friday",
                                "saturday",
                                "sunday",
                            )
                        )
                        if row.get(day) == "1"
                    }
                    services[row["service_id"]] = (
                        days,
                        _parse_gtfs_date(row.get("start_date")),
                        _parse_gtfs_date(row.get("end_date")),
                        set(),
                        set(),
                    )
            except KeyError:
                pass

            try:
                for row in reader("calendar_dates.txt"):
                    sid = row["service_id"]
                    if sid not in services:
                        services[sid] = (set(), date.min, date.max, set(), set())
                    day = _parse_gtfs_date(row.get("date"))
                    if row.get("exception_type") == "1":
                        services[sid][3].add(day)
                    else:
                        services[sid][4].add(day)
            except KeyError:
                pass

        for entries in index.values():
            entries.sort()
        self._index = index
        self._services = services

    def _service_active(self, service_id: str, day: date) -> bool:
        service = self._services.get(service_id)
        if service is None:
            return False
        days, start, end, added, removed = service
        if day in removed:
            return False
        if day in added:
            return True
        return start <= day <= end and day.weekday() in days

    # ------------------------------------------------------------------
    # Requête
    # ------------------------------------------------------------------
    async def async_get_departures(
        self,
        station: str,
        line_code: str,
        direction: str | None = None,
        count: int = 6,
    ) -> list[dict]:
        """Prochains départs théoriques (liste vide tant que l'index charge)."""
        self.register(station, line_code)
        if not self.ready:
            self._schedule_load()
            return []

        entries = self._index.get((norm(station), norm(line_code)), [])
        if not entries:
            return []

        now = dt_util.now(TZ_LYON)
        horizon = now + timedelta(hours=36)
        results: list[dict] = []

        for offset in (-1, 0, 1):
            day = (now + timedelta(days=offset)).date()
            base = datetime(day.year, day.month, day.day, tzinfo=TZ_LYON)
            for secs, service_id, headsign in entries:
                if offset == -1 and secs < 86400:
                    continue  # seuls les horaires >24h débordent sur aujourd'hui
                dep_dt = base + timedelta(seconds=secs)
                if dep_dt <= now or dep_dt > horizon:
                    continue
                if direction and not fuzzy_match(direction, headsign):
                    continue
                if not self._service_active(service_id, day):
                    continue
                delai = int((dep_dt - now).total_seconds() // 60)
                results.append(
                    {
                        "ligne": line_code,
                        "destination": headsign,
                        "delai": delai,
                        "delai_texte": dep_dt.strftime("%H:%M"),
                        "heure": dep_dt.isoformat(),
                        "heure_theorique": dep_dt.isoformat(),
                        "retard": None,
                        "annule": False,
                        "temps_reel": False,
                        "source": "gtfs",
                        "course": None,
                    }
                )

        results.sort(key=lambda d: d["delai"])
        return results[:count]

    def directions_for(self, station: str, line_code: str) -> list[str]:
        """Destinations connues du GTFS pour ce couple station/ligne."""
        entries = self._index.get((norm(station), norm(line_code)), [])
        seen: dict[str, None] = {}
        for _, _, headsign in entries:
            if headsign:
                seen.setdefault(headsign, None)
        return list(seen)


def _parse_gtfs_date(value: str | None) -> date:
    try:
        return datetime.strptime((value or "").strip(), "%Y%m%d").date()
    except ValueError:
        return date.min
