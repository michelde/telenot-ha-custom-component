"""Telenot switch platform."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelenotDataUpdateCoordinator
from .active_objects import should_create_entity, get_active_objects_summary

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telenot switches from a config entry."""
    coordinator: TelenotDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    
    # Add output switches - only for active outputs
    if coordinator.data and "outputs" in coordinator.data:
        for address, output_data in coordinator.data["outputs"].items():
            if should_create_entity(address, "output", coordinator.data):
                entities.append(TelenotSwitch(coordinator, address, output_data))
                _LOGGER.info("Added active output switch: 0x%04X - %s", address, output_data.get("name", "Unknown"))

    _LOGGER.info("Created %d switch entities for active outputs", len(entities))
    async_add_entities(entities, update_before_add=True)


class TelenotSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Telenot switch."""

    def __init__(
        self,
        coordinator: TelenotDataUpdateCoordinator,
        address: int,
        output_data: Dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._address = address
        self._attr_name = output_data.get("name", f"Telenot Ausgang {address:04X}")
        self._attr_unique_id = f"telenot_output_{address:04X}"
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"output_{address:04X}")},
            "name": self._attr_name,
            "manufacturer": "Telenot",
            "model": "complex400",
            "via_device": (DOMAIN, "master"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.coordinator.data or "outputs" not in self.coordinator.data:
            return None
            
        output_data = self.coordinator.data["outputs"].get(self._address)
        if not output_data:
            return None
            
        return output_data.get("state", False)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data or "outputs" not in self.coordinator.data:
            return {}
            
        output_data = self.coordinator.data["outputs"].get(self._address, {})
        
        return {
            "address": f"0x{self._address:04X}",
            "address_decimal": self._address,
            "output_name": output_data.get("name"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data
            and self.coordinator.data.get("connected", False)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        _LOGGER.info("Turning on output 0x%04X", self._address)
        # TODO: Implement output control command
        # This would require extending the protocol to support output control
        _LOGGER.warning("Output control not yet implemented")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        _LOGGER.info("Turning off output 0x%04X", self._address)
        # TODO: Implement output control command
        # This would require extending the protocol to support output control
        _LOGGER.warning("Output control not yet implemented")

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        # Determine icon based on address/type
        if 0x0500 <= self._address <= 0x0507:  # ÜG TA outputs
            return "mdi:phone-classic"
        elif 0x0508 <= self._address <= 0x050A:  # Relais
            return "mdi:electric-switch"
        elif self._address == 0x050B:  # OSG
            return "mdi:lightbulb"
        elif self._address in [0x050C, 0x050D]:  # ASG
            return "mdi:volume-high"
        else:
            return "mdi:toggle-switch"
