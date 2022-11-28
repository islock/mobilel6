"""Support for Broadlink lights."""
import logging

import  sys
sys.path.append('/comfig/custom_components/broadlink1/')

from .broadlinkdiy.exceptions import BroadlinkException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BroadlinkEntity

_LOGGER = logging.getLogger(__name__)

BROADLINK_COLOR_MODE_RGB = 0
BROADLINK_COLOR_MODE_WHITE = 1
BROADLINK_COLOR_MODE_SCENES = 2


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink light."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    lights = []

    if device.api.type in {"LB1", "LB2"}:
        lights.append(BroadlinkLight(device))

    async_add_entities(lights)


class BroadlinkLight(BroadlinkEntity, LightEntity):
    """Representation of a Broadlink light."""

    def __init__(self, device):
        """Initialize the light."""
        super().__init__(device)
        self._attr_name = f"{device.name} Light"
        self._attr_unique_id = device.unique_id
        self._attr_supported_color_modes = set()

        data = self._coordinator.data

        if {"hue", "saturation"}.issubset(data):
            self._attr_supported_color_modes.add(ColorMode.HS)
        if "colortemp" in data:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
        if not self.supported_color_modes:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        self._update_state(data)

    def _update_state(self, data):
        """Update the state of the entity."""
        if "pwr" in data:
            self._attr_is_on = bool(data["pwr"])

        if "brightness" in data:
            self._attr_brightness = round(data["brightness"] * 2.55)

        if self.supported_color_modes == {ColorMode.BRIGHTNESS}:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            return

        if {"hue", "saturation"}.issubset(data):
            self._attr_hs_color = [data["hue"], data["saturation"]]

        if "colortemp" in data:
            self._attr_color_temp = round((data["colortemp"] - 2700) / 100 + 153)

        if "bulb_colormode" in data:
            if data["bulb_colormode"] == BROADLINK_COLOR_MODE_RGB:
                self._attr_color_mode = ColorMode.HS
            elif data["bulb_colormode"] == BROADLINK_COLOR_MODE_WHITE:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            else:
                # Scenes are not yet supported.
                self._attr_color_mode = ColorMode.UNKNOWN

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        state = {"pwr": 1}

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            state["brightness"] = round(brightness / 2.55)

        if self.supported_color_modes == {ColorMode.BRIGHTNESS}:
            state["bulb_colormode"] = BROADLINK_COLOR_MODE_WHITE

        elif ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            state["hue"] = int(hs_color[0])
            state["saturation"] = int(hs_color[1])
            state["bulb_colormode"] = BROADLINK_COLOR_MODE_RGB

        elif ATTR_COLOR_TEMP in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP]
            state["colortemp"] = (color_temp - 153) * 100 + 2700
            state["bulb_colormode"] = BROADLINK_COLOR_MODE_WHITE

        elif ATTR_COLOR_MODE in kwargs:
            color_mode = kwargs[ATTR_COLOR_MODE]
            if color_mode == ColorMode.HS:
                state["bulb_colormode"] = BROADLINK_COLOR_MODE_RGB
            elif color_mode == ColorMode.COLOR_TEMP:
                state["bulb_colormode"] = BROADLINK_COLOR_MODE_WHITE
            else:
                # Scenes are not yet supported.
                state["bulb_colormode"] = BROADLINK_COLOR_MODE_SCENES

        await self._async_set_state(state)

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        await self._async_set_state({"pwr": 0})

    async def _async_set_state(self, state):
        """Set the state of the light."""
        device = self._device

        try:
            state = await device.async_request(device.api.set_state, **state)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to set state: %s", err)
            return

        self._update_state(state)
        self.async_write_ha_state()
