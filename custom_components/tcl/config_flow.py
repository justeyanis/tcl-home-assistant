"""Config flow TCL : identifiants → mode → ligne → station → direction."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import TCLApiClient, TCLApiError, TCLAuthError
from .const import (
    CONF_DEPARTURE_COUNT,
    CONF_DIRECTION,
    CONF_LINE,
    CONF_LINE_COLOR,
    CONF_LINE_NAME,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    CONF_STOP_IDS,
    CONF_USERNAME,
    DEFAULT_DEPARTURE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DIRECTION_ALL,
    DOMAIN,
    FALLBACK_COLORS,
    MAX_DEPARTURE_COUNT,
    MODES,
    get_departure_count,
)

_LOGGER = logging.getLogger(__name__)


class TCLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Assistant de configuration de l'intégration TCL."""

    VERSION = 1

    def __init__(self) -> None:
        self._client: TCLApiClient | None = None
        self._data: dict[str, Any] = {}
        self._lines: list[dict] = []
        self._stations: dict[str, list[str]] = {}
        self._directions: list[str] = []

    # ------------------------------------------------------------------
    # Étape 1 : identifiants data.grandlyon.com
    # ------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        # Ajout d'un arrêt supplémentaire : réutilise les identifiants d'une
        # entrée existante pour sauter l'étape d'authentification.
        if user_input is None:
            for entry in self._async_current_entries(include_ignore=False):
                username = entry.data.get(CONF_USERNAME)
                password = entry.data.get(CONF_PASSWORD)
                if not username or not password:
                    continue
                client = TCLApiClient(
                    async_get_clientsession(self.hass), username, password
                )
                try:
                    await client.async_validate_credentials()
                except TCLApiError:
                    break  # identifiants stockés invalides -> formulaire
                self._client = client
                self._data[CONF_USERNAME] = username
                self._data[CONF_PASSWORD] = password
                return await self.async_step_mode()

        if user_input is not None:
            self._client = TCLApiClient(
                async_get_clientsession(self.hass),
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await self._client.async_validate_credentials()
            except TCLAuthError:
                errors["base"] = "invalid_auth"
            except TCLApiError:
                errors["base"] = "cannot_connect"
            else:
                self._data.update(user_input)
                return await self.async_step_mode()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.EMAIL)
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Étape 2 : mode de transport
    # ------------------------------------------------------------------
    async def async_step_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_MODE] = user_input[CONF_MODE]
            try:
                assert self._client is not None
                self._lines = await self._client.async_get_lines(
                    user_input[CONF_MODE]
                )
            except TCLApiError:
                errors["base"] = "cannot_connect"
            else:
                if not self._lines:
                    errors["base"] = "no_lines"
                else:
                    return await self.async_step_line()

        return self.async_show_form(
            step_id="mode",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE): SelectSelector(
                        SelectSelectorConfig(
                            options=MODES,
                            mode=SelectSelectorMode.LIST,
                            translation_key="mode",
                        )
                    )
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Étape 3 : ligne
    # ------------------------------------------------------------------
    async def async_step_line(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input[CONF_LINE]
            line = next((l for l in self._lines if l["code"] == code), None)
            self._data[CONF_LINE] = code
            self._data[CONF_LINE_NAME] = line["name"] if line else code
            self._data[CONF_LINE_COLOR] = (
                (line and line["color"])
                or FALLBACK_COLORS.get(code.upper(), "#B0B0B0")
            )
            try:
                assert self._client is not None
                self._stations = await self._client.async_get_stations_for_line(code)
            except TCLApiError:
                errors["base"] = "cannot_connect"
            else:
                if not self._stations:
                    errors["base"] = "no_stations"
                else:
                    return await self.async_step_station()

        options = [
            SelectOptionDict(value=l["code"], label=f"{l['code']} — {l['name']}")
            for l in self._lines
        ]
        return self.async_show_form(
            step_id="line",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LINE): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Étape 4 : station
    # ------------------------------------------------------------------
    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            station = user_input[CONF_STATION]
            self._data[CONF_STATION] = station
            self._data[CONF_STOP_IDS] = self._stations[station]
            try:
                assert self._client is not None
                self._directions = await self._client.async_get_directions(
                    self._stations[station], self._data[CONF_LINE]
                )
            except TCLApiError as err:
                _LOGGER.warning(
                    "Impossible de récupérer les directions pour %s (%s) : %s",
                    station,
                    self._data[CONF_LINE],
                    err,
                )
                self._directions = []
            _LOGGER.info(
                "Directions proposées pour %s (%s) : %s",
                station,
                self._data[CONF_LINE],
                self._directions,
            )
            return await self.async_step_direction()

        options = [
            SelectOptionDict(value=name, label=name) for name in self._stations
        ]
        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Étape 5 : direction
    # ------------------------------------------------------------------
    async def async_step_direction(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            direction = user_input[CONF_DIRECTION]
            self._data[CONF_DIRECTION] = (
                None if direction == DIRECTION_ALL else direction
            )
            self._data[CONF_DEPARTURE_COUNT] = int(
                user_input[CONF_DEPARTURE_COUNT]
            )
            unique_id = (
                f"{self._data[CONF_LINE]}_{self._data[CONF_STATION]}_"
                f"{self._data[CONF_DIRECTION] or 'all'}"
            ).lower().replace(" ", "_")
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            direction_label = self._data[CONF_DIRECTION] or "toutes directions"
            title = (
                f"{self._data[CONF_LINE]} {self._data[CONF_STATION]}"
                f" → {direction_label}"
            )
            return self.async_create_entry(title=title, data=self._data)

        options = [SelectOptionDict(value=DIRECTION_ALL, label="Toutes les directions")]
        options += [SelectOptionDict(value=d, label=f"→ {d}") for d in self._directions]
        return self.async_show_form(
            step_id="direction",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DIRECTION, default=DIRECTION_ALL
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                    vol.Required(
                        CONF_DEPARTURE_COUNT, default=DEFAULT_DEPARTURE_COUNT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=MAX_DEPARTURE_COUNT,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            description_placeholders={
                "note": (
                    "Directions observées en ce moment. "
                    "Vide la nuit : choisissez 'Toutes les directions'."
                )
            },
        )

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------
    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "TCLOptionsFlow":
        return TCLOptionsFlow()


class TCLOptionsFlow(OptionsFlow):
    """Options : intervalle de rafraîchissement et nombre de départs."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_DEPARTURE_COUNT] = int(
                user_input[CONF_DEPARTURE_COUNT]
            )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=15,
                            max=600,
                            step=5,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_DEPARTURE_COUNT,
                        default=get_departure_count(self.config_entry),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=MAX_DEPARTURE_COUNT,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
