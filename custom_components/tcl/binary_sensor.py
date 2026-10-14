"""Capteur binaire « Perturbation » : alertes trafic en cours sur la ligne."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TCLConfigEntry
from .api import alert_level
from .const import ATTR_ALERTS, CONF_LINE
from .coordinator import TCLCoordinator
from .entity import TCLEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TCLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée le capteur de perturbation si les alertes sont activées."""
    coordinator: TCLCoordinator = entry.runtime_data
    if coordinator.use_alerts:
        async_add_entities([TCLDisruptionBinarySensor(coordinator, entry)])


class TCLDisruptionBinarySensor(TCLEntity, BinarySensorEntity):
    """Allumé tant qu'une perturbation (hors simple information) est en cours.

    Les alertes de type « Information » (ex. ascenseur en travaux pendant
    des semaines) restent listées dans les attributs et sur la carte, mais
    n'allument pas le capteur.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "disruption"

    def __init__(self, coordinator: TCLCoordinator, entry: TCLConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_disruption"

    @property
    def is_on(self) -> bool:
        return any(alert_level(a) >= 1 for a in self.coordinator.alerts)

    @property
    def icon(self) -> str:
        return "mdi:alert" if self.is_on else "mdi:check-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        alerts = self.coordinator.alerts
        return {
            "ligne": self._entry.data[CONF_LINE],
            "nombre": len(alerts),
            "titre": alerts[0]["titre"] if alerts else None,
            ATTR_ALERTS: alerts,
        }
