"""Entité de base TCL : appareil commun à toutes les entités d'une entrée."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DIRECTION, CONF_LINE, CONF_LINE_NAME, CONF_STATION, DOMAIN
from .coordinator import TCLCoordinator


class TCLEntity(CoordinatorEntity[TCLCoordinator]):
    """Entité rattachée à l'appareil « TCL <ligne> <station> → <direction> »."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TCLCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        line = entry.data[CONF_LINE]
        direction = entry.data.get(CONF_DIRECTION)
        # La ligne fait partie du nom : une même station peut être desservie
        # par plusieurs lignes configurées séparément (ex. Debourg : B et T1).
        device_name = f"TCL {line} {entry.data[CONF_STATION]}"
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
    def active_departures(self) -> list[dict]:
        """Départs non supprimés (les suppressions restent dans l'attribut)."""
        return [d for d in (self.coordinator.data or []) if not d.get("annule")]
