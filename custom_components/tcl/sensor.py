"""Sensors TCL : un sensor par rang de départ (#0 = prochain départ)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TCLConfigEntry
from .const import (
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
    DOMAIN,
    MAX_DEPARTURES_ATTR,
    get_departure_count,
)
from .coordinator import TCLCoordinator


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

    async_add_entities(
        TCLDepartureSensor(coordinator, entry, rank) for rank in range(1, count + 1)
    )


class TCLDepartureSensor(CoordinatorEntity[TCLCoordinator], SensorEntity):
    """Départ de rang N. Nommé '#0' pour le prochain, '#1' pour le suivant…"""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:subway-variant"

    def __init__(
        self, coordinator: TCLCoordinator, entry: TCLConfigEntry, rank: int
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._rank = rank
        self._attr_unique_id = f"{entry.entry_id}_departure_{rank}"
        # Nom complet = nom de l'appareil + " #N", par ex.
        # "TCL B Debourg → Charpennes Charles Hernu #0"
        self._attr_name = f"#{rank - 1}"

        mode = entry.data.get(CONF_MODE, "")
        if mode == "bus":
            self._attr_icon = "mdi:bus"
        elif mode == "tram":
            self._attr_icon = "mdi:tram"

        line = entry.data[CONF_LINE]
        station = entry.data[CONF_STATION]
        direction = entry.data.get(CONF_DIRECTION)
        # La ligne fait partie du nom : une même station peut être desservie
        # par plusieurs lignes configurées séparément (ex. Debourg : B et T1).
        device_name = f"TCL {line} {station}"
        if direction:
            device_name += f" → {direction}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="SYTRAL / TCL",
            model=entry.data.get(CONF_LINE_NAME) or f"Ligne {line}",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _departure(self) -> dict | None:
        data = self.coordinator.data or []
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
                    "temps_reel": dep["temps_reel"],
                }
            )
        if self._rank == 1:
            # Marqueur pour l'auto-découverte par la carte tcl-biv-card
            attrs[ATTR_TCL_BIV] = True
            attrs[ATTR_DEPARTURES] = (self.coordinator.data or [])[
                :MAX_DEPARTURES_ATTR
            ]
        return attrs
