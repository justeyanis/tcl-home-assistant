"""Coordinateur de mise à jour des passages TCL.

Trois sources, de la plus précise à la plus générale :
  1. SIRI Lite estimated-timetables (tous les passages suivis, retards,
     suppressions) — facultatif, le flux est irrégulier ;
  2. tclpassagearret (2 prochains passages par ligne, estimés ou théoriques) ;
  3. GTFS théorique, pour compléter (la nuit, service terminé…).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TCLApiClient, TCLApiError
from .const import (
    CONF_ALERTS,
    CONF_DIRECTION,
    CONF_LINE,
    CONF_SCAN_INTERVAL,
    CONF_SIRI,
    CONF_STATION,
    CONF_STOP_IDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DEPARTURES_ATTR,
    get_departure_count,
)
from .gtfs import TCLGtfsSchedule, fuzzy_match

_LOGGER = logging.getLogger(__name__)

# Deux passages de sources différentes à moins de 90 s, même destination,
# sont considérés comme le même véhicule (à défaut d'identifiant de course).
SAME_VEHICLE_SECONDS = 90


class TCLCoordinator(DataUpdateCoordinator[list[dict]]):
    """Récupère les prochains départs, complétés par le théorique GTFS."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TCLApiClient,
        gtfs: TCLGtfsSchedule | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.gtfs = gtfs
        self.departure_count = get_departure_count(entry)
        self.use_siri = entry.options.get(CONF_SIRI, True)
        self.use_alerts = entry.options.get(CONF_ALERTS, True)
        self.alerts: list[dict] = []

    @property
    def siri_status(self) -> dict:
        """État du flux SIRI pour la ligne de cette entrée."""
        if not self.use_siri:
            return {"etat": "désactivé dans les options"}
        line = str(self.config_entry.data.get(CONF_LINE, "")).strip().upper()
        return self.client.siri_status.get(line, {"etat": "pas encore interrogé"})
        if gtfs is not None:
            gtfs.register(entry.data[CONF_STATION], entry.data[CONF_LINE])

    async def _async_update_data(self) -> list[dict]:
        entry = self.config_entry
        stop_ids = [str(s) for s in entry.data[CONF_STOP_IDS]]
        line = entry.data.get(CONF_LINE)
        direction = entry.data.get(CONF_DIRECTION)

        realtime_error: TCLApiError | None = None
        try:
            departures = await self.client.async_get_departures(
                stop_ids, line, direction
            )
        except TCLApiError as err:
            # Les autres sources peuvent prendre le relais : ne pas rendre
            # les capteurs indisponibles tant qu'il en reste une.
            _LOGGER.warning("Temps réel TCL indisponible : %s", err)
            realtime_error = err
            departures = []

        if self.use_siri and line:
            try:
                siri = await self.client.async_get_siri_departures(
                    stop_ids, line, direction
                )
            except TCLApiError as err:
                _LOGGER.debug("SIRI indisponible : %s", err)
            except Exception:  # noqa: BLE001 - source facultative
                _LOGGER.exception("Erreur inattendue en lisant le flux SIRI")
            else:
                departures = merge_realtime(siri, departures)

        if self.use_alerts and line:
            try:
                self.alerts = await self.client.async_get_alerts(line)
            except TCLApiError as err:
                _LOGGER.debug("Alertes trafic indisponibles : %s", err)
            except Exception:  # noqa: BLE001 - jamais bloquant
                _LOGGER.exception("Erreur inattendue en lisant les alertes trafic")

        active = [d for d in departures if not d.get("annule")]
        if self.gtfs is not None and len(active) < self.departure_count:
            try:
                theoretical = await self.gtfs.async_get_departures(
                    entry.data[CONF_STATION],
                    line,
                    direction,
                    count=MAX_DEPARTURES_ATTR,
                )
            except Exception as err:  # noqa: BLE001 - jamais bloquant
                _LOGGER.debug("GTFS indisponible : %s", err)
                theoretical = []
            departures = _merge(departures, theoretical)

        if realtime_error is not None and not departures:
            raise UpdateFailed(str(realtime_error)) from realtime_error
        return departures[:MAX_DEPARTURES_ATTR]


def _when(dep: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(dep["heure"]) if dep.get("heure") else None
    except ValueError:
        return None


def _same_vehicle(a: dict, b: dict) -> bool:
    # Les identifiants de course des deux flux n'ont pas forcément le même
    # format : une égalité est concluante, une différence ne l'est pas.
    if a.get("course") and a.get("course") == b.get("course"):
        return True
    known = bool(a.get("destination") and b.get("destination"))
    if known and not fuzzy_match(a["destination"], b["destination"]):
        return False
    # Destination inconnue d'un côté : n'accepter qu'une heure quasi identique
    window = SAME_VEHICLE_SECONDS if known else 30
    ta, tb = _when(a), _when(b)
    if ta is None or tb is None:
        return known and abs(a["delai"] - b["delai"]) <= 1
    return abs((ta - tb).total_seconds()) <= window


def merge_realtime(siri: list[dict], passages: list[dict]) -> list[dict]:
    """Fusionne SIRI (prioritaire, plus riche) et tclpassagearret.

    Un passage tclpassagearret déjà couvert par SIRI est écarté ; sinon il
    est conservé (SIRI ne suit pas toutes les courses). Si SIRI n'a pas
    d'estimation mais que tclpassagearret en a une, celle-ci l'emporte.
    """
    merged = [dict(d) for d in siri]
    for passage in passages:
        twin = next((m for m in merged if _same_vehicle(m, passage)), None)
        if twin is None:
            merged.append(passage)
        elif passage.get("temps_reel") and not twin.get("temps_reel"):
            twin.update(
                {
                    "delai": passage["delai"],
                    "heure": passage["heure"] or twin["heure"],
                    "temps_reel": True,
                }
            )
    merged.sort(key=lambda d: d["delai"])
    return merged


def _merge(realtime: list[dict], theoretical: list[dict]) -> list[dict]:
    """Ajoute le théorique en évitant les doublons (même destination à ±3 min)."""
    merged = list(realtime)
    for theo in theoretical:
        theo_time = _when(theo)
        duplicate = False
        for rt in realtime:
            if not fuzzy_match(theo["destination"], rt["destination"]):
                continue
            # Un passage en retard se compare à son horaire théorique
            aimed = rt.get("heure_theorique")
            if aimed and theo_time is not None:
                try:
                    gap = abs(
                        (datetime.fromisoformat(aimed) - theo_time).total_seconds()
                    )
                except ValueError:
                    gap = None
                if gap is not None and gap <= 60:
                    duplicate = True
                    break
            if abs(theo["delai"] - rt["delai"]) <= 3:
                duplicate = True
                break
        if not duplicate:
            merged.append(theo)
    merged.sort(key=lambda d: d["delai"])
    return merged
