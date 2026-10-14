"""Intégration TCL (Transports en Commun Lyonnais) pour Home Assistant.

Données temps réel (tclpassagearret + SIRI Lite), alertes trafic et horaires
théoriques GTFS : data.grandlyon.com (compte gratuit requis). Sert et
enregistre aussi la carte Lovelace `tcl-biv-card` automatiquement (aucune
ressource à déclarer à la main).
"""
from __future__ import annotations

import logging
from pathlib import Path

import aiohttp

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import TCLApiClient
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import TCLCoordinator
from .gtfs import TCLGtfsSchedule

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
CARD_URL_BASE = "/tcl-biv-card"
CARD_FILENAME = "tcl-biv-card.js"

TCLConfigEntry = ConfigEntry

# Configuration uniquement via l'interface (pas de YAML)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Sert la carte Lovelace et l'enregistre comme ressource."""
    integration = await async_get_integration(hass, DOMAIN)
    card_url = f"{CARD_URL_BASE}/{CARD_FILENAME}?v={integration.version}"

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_URL_BASE,
                str(Path(__file__).parent / "www"),
                # Pas de cache long : si l'URL versionnée n'a pas pu être
                # mise à jour, le navigateur doit quand même recharger la carte.
                cache_headers=False,
            )
        ]
    )

    try:
        await _async_register_lovelace_resource(hass, card_url)
    except Exception as err:  # noqa: BLE001 - la carte ne doit pas bloquer le reste
        _LOGGER.warning(
            "Impossible d'enregistrer la ressource Lovelace %s : %s "
            "(ajoutez-la manuellement dans Paramètres → Tableaux de bord "
            "→ Ressources)",
            card_url,
            err,
        )
    return True


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Ajoute (ou met à jour) la ressource module de la carte.

    Uniquement en mode "storage" (tableaux de bord gérés par l'interface) ;
    en mode YAML, la ressource doit être déclarée dans la configuration.
    L'objet `lovelace` a été une dict puis une dataclass selon les versions
    de HA : on accède aux deux formes de façon tolérante.
    """
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        _LOGGER.debug("Lovelace pas encore initialisé : ressource non gérée")
        return

    def _attr(obj: object, name: str):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    # `resource_mode` depuis HA 2025 (l'ancien attribut `mode` a disparu)
    mode = _attr(lovelace, "resource_mode") or _attr(lovelace, "mode")
    if mode != "storage":
        _LOGGER.debug("Lovelace en mode YAML : ressource %s non gérée", url)
        return

    resources = _attr(lovelace, "resources")
    if resources is None:
        return
    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True

    base = f"{CARD_URL_BASE}/{CARD_FILENAME}"
    for item in list(resources.async_items()):
        if base in (item.get("url") or ""):
            if item["url"] != url:
                await resources.async_update_item(item["id"], {"url": url})
                _LOGGER.info("Ressource Lovelace mise à jour : %s", url)
            return

    await resources.async_create_item({"res_type": "module", "url": url})
    _LOGGER.info("Ressource Lovelace enregistrée : %s", url)


async def async_setup_entry(hass: HomeAssistant, entry: TCLConfigEntry) -> bool:
    """Initialise une entrée de configuration TCL."""
    session = async_get_clientsession(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})

    # Un client par compte, partagé entre les entrées : ses caches (arrêts,
    # alertes, flux SIRI par ligne) évitent les requêtes en double.
    clients: dict = domain_data.setdefault("clients", {})
    credentials = (entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    client = clients.get(credentials)
    if client is None:
        client = clients[credentials] = TCLApiClient(session, *credentials)

    # Instance GTFS partagée entre toutes les entrées
    if "gtfs" not in domain_data:
        domain_data["gtfs"] = TCLGtfsSchedule(
            hass,
            session,
            aiohttp.BasicAuth(
                entry.data[CONF_USERNAME],
                entry.data[CONF_PASSWORD],
                encoding="utf-8",
            ),
        )

    coordinator = TCLCoordinator(hass, entry, client, domain_data["gtfs"])
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: TCLConfigEntry) -> None:
    """Recharge l'entrée quand les options changent."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TCLConfigEntry) -> bool:
    """Décharge une entrée de configuration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
