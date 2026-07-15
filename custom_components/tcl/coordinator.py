"""Coordinateur de mise à jour des passages TCL (temps réel + GTFS)."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TCLApiClient, TCLApiError
from .const import (
    CONF_DIRECTION,
    CONF_LINE,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    CONF_STOP_IDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DEPARTURES_ATTR,
    get_departure_count,
)
from .gtfs import TCLGtfsSchedule, fuzzy_match

_LOGGER = logging.getLogger(__name__)


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
        if gtfs is not None:
            gtfs.register(entry.data[CONF_STATION], entry.data[CONF_LINE])

    async def _async_update_data(self) -> list[dict]:
        entry = self.config_entry
        realtime_error: TCLApiError | None = None
        try:
            departures = await self.client.async_get_departures(
                [str(s) for s in entry.data[CONF_STOP_IDS]],
                entry.data.get(CONF_LINE),
                entry.data.get(CONF_DIRECTION),
            )
        except TCLApiError as err:
            # Le théorique GTFS peut prendre le relais : ne pas rendre
            # les capteurs indisponibles tant qu'il reste une source.
            _LOGGER.warning("Temps réel TCL indisponible : %s", err)
            realtime_error = err
            departures = []

        if self.gtfs is not None and len(departures) < self.departure_count:
            try:
                theoretical = await self.gtfs.async_get_departures(
                    entry.data[CONF_STATION],
                    entry.data[CONF_LINE],
                    entry.data.get(CONF_DIRECTION),
                    count=MAX_DEPARTURES_ATTR,
                )
            except Exception as err:  # noqa: BLE001 - jamais bloquant
                _LOGGER.debug("GTFS indisponible : %s", err)
                theoretical = []
            departures = _merge(departures, theoretical)

        if realtime_error is not None and not departures:
            raise UpdateFailed(str(realtime_error)) from realtime_error
        return departures[:MAX_DEPARTURES_ATTR]


def _merge(realtime: list[dict], theoretical: list[dict]) -> list[dict]:
    """Fusionne en évitant les doublons (même destination à ±3 min)."""
    merged = list(realtime)
    for theo in theoretical:
        duplicate = any(
            fuzzy_match(theo["destination"], rt["destination"])
            and abs(theo["delai"] - rt["delai"]) <= 3
            for rt in realtime
        )
        if not duplicate:
            merged.append(theo)
    merged.sort(key=lambda d: d["delai"])
    return merged
