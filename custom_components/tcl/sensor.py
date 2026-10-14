"""Sensors TCL : un sensor par rang de départ (#0 = prochain départ)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TCLConfigEntry
from .const import (
    ATTR_ALERTS,
    ATTR_DEPARTURES,
    ATTR_DIRECTION,
    ATTR_LINE,
    ATTR_LINE_COLOR,
    ATTR_LINE_NAME,
    ATTR_MODE,
    ATTR_STATION,
    ATTR_TCL_BIV,
    CONF_DIRECTION,
    CONF_LINE,
    CONF_LINE_COLOR,
    CONF_LINE_NAME,
    CONF_MODE,
    CONF_STATION,
    MAX_DEPARTURES_ATTR,
    get_departure_count,
)
from .coordinator import TCLCoordinator
from .entity import TCLEntity

MODE_ICONS = {
    "bus": "mdi:bus",
    "tram": "mdi:tram",
    "funiculaire": "mdi:gondola",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TCLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les sensors de départ (nombre configurable)."""
    coordinator = entry.runtime_data
    count = get_departure_count(entry)

    # Purge les entités excédentaires si le nombre a été réduit
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_departure_"
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if not reg_entry.unique_id.startswith(prefix):
            continue
        suffix = reg_entry.unique_id.removeprefix(prefix)
        if suffix.isdigit() and int(suffix) > count:
            registry.async_remove(reg_entry.entity_id)

    entities: list[SensorEntity] = [
        TCLDepartureSensor(coordinator, entry, rank) for rank in range(1, count + 1)
    ]
    entities.append(TCLNextDepartureTimeSensor(coordinator, entry))
    async_add_entities(entities)


class TCLDepartureSensor(TCLEntity, SensorEntity):
    """Départ de rang N. Nommé '#0' pour le prochain, '#1' pour le suivant…"""

    _attr_native_unit_of_measurement = "min"

    def __init__(
        self, coordinator: TCLCoordinator, entry: TCLConfigEntry, rank: int
    ) -> None:
        super().__init__(coordinator, entry)
        self._rank = rank
        self._attr_unique_id = f"{entry.entry_id}_departure_{rank}"
        # Nom complet = nom de l'appareil + " #N", par ex.
        # "TCL B Debourg → Charpennes Charles Hernu #0"
        self._attr_name = f"#{rank - 1}"
        self._attr_icon = MODE_ICONS.get(
            entry.data.get(CONF_MODE, ""), "mdi:subway-variant"
        )

    @property
    def _departure(self) -> dict | None:
        data = self.active_departures
        if len(data) >= self._rank:
            return data[self._rank - 1]
        return None

    @property
    def native_value(self) -> int | None:
        dep = self._departure
        return dep["delai"] if dep else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        entry = self._entry
        attrs: dict[str, Any] = {
            ATTR_STATION: entry.data[CONF_STATION],
            ATTR_LINE: entry.data[CONF_LINE],
            ATTR_LINE_NAME: entry.data.get(CONF_LINE_NAME),
            ATTR_LINE_COLOR: entry.data.get(CONF_LINE_COLOR),
            ATTR_MODE: entry.data.get(CONF_MODE),
            ATTR_DIRECTION: entry.data.get(CONF_DIRECTION),
            "rang": self._rank - 1,
        }
        dep = self._departure
        if dep:
            attrs.update(
                {
                    "destination": dep["destination"],
                    "delai_texte": dep["delai_texte"],
                    "heure": dep["heure"],
                    "heure_theorique": dep.get("heure_theorique"),
                    "retard": dep.get("retard"),
                    "temps_reel": dep["temps_reel"],
                    "source": dep.get("source"),
                }
            )
        if self._rank == 1:
            # Marqueur pour l'auto-découverte par la carte tcl-biv-card
            attrs[ATTR_TCL_BIV] = True
            attrs[ATTR_DEPARTURES] = [
                {k: v for k, v in d.items() if k != "course"}
                for d in (self.coordinator.data or [])[:MAX_DEPARTURES_ATTR]
            ]
            attrs[ATTR_ALERTS] = self.coordinator.alerts
            attrs["temps_reel_siri"] = self.coordinator.siri_status
        return attrs


class TCLNextDepartureTimeSensor(TCLEntity, SensorEntity):
    """Heure du prochain départ (horodatage) : pratique pour les automatisations."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_departure"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: TCLCoordinator, entry: TCLConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_time"

    @property
    def native_value(self) -> datetime | None:
        for dep in self.active_departures:
            if dep.get("heure"):
                try:
                    return datetime.fromisoformat(dep["heure"])
                except ValueError:
                    continue
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dep = next(iter(self.active_departures), None)
        if not dep:
            return {}
        return {
            "destination": dep["destination"],
            "retard": dep.get("retard"),
            "temps_reel": dep["temps_reel"],
        }
