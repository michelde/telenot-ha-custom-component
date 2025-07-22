"""Telenot sensor platform."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelenotDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telenot sensors from a config entry."""
    coordinator: TelenotDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    
    # Add connection status sensor
    entities.append(TelenotConnectionSensor(coordinator))
    
    # Add area status sensors
    if coordinator.data and "areas" in coordinator.data:
        for area_num, area_data in coordinator.data["areas"].items():
            entities.append(TelenotAreaStatusSensor(coordinator, area_num, area_data))

    async_add_entities(entities, update_before_add=True)


class TelenotConnectionSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Telenot connection status sensor."""

    def __init__(self, coordinator: TelenotDataUpdateCoordinator) -> None:
        """Initialize the connection sensor."""
        super().__init__(coordinator)
        self._attr_name = "Telenot Verbindung"
        self._attr_unique_id = "telenot_connection"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["connected", "disconnected", "error"]
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "master")},
            "name": "Telenot Master",
            "manufacturer": "Telenot",
            "model": "complex400",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "disconnected"
            
        connected = self.coordinator.data.get("connected", False)
        if connected:
            return "connected"
        else:
            return "disconnected"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "host": self.coordinator.host,
            "port": self.coordinator.port,
            "last_update": self.coordinator.last_update_success_time,
        }
        
        if self.coordinator.data:
            attrs.update({
                "areas_count": len(self.coordinator.data.get("areas", {})),
                "inputs_count": len(self.coordinator.data.get("inputs", {})),
                "outputs_count": len(self.coordinator.data.get("outputs", {})),
            })
        
        return attrs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True  # Connection sensor is always available

    @property
    def icon(self) -> str:
        """Return the icon for the connection sensor."""
        if self.native_value == "connected":
            return "mdi:lan-connect"
        else:
            return "mdi:lan-disconnect"


class TelenotAreaStatusSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Telenot area status sensor."""

    def __init__(
        self,
        coordinator: TelenotDataUpdateCoordinator,
        area_num: int,
        area_data: Dict[str, Any],
    ) -> None:
        """Initialize the area status sensor."""
        super().__init__(coordinator)
        self._area_num = area_num
        self._attr_name = f"Telenot Bereich {area_num} Status"
        self._attr_unique_id = f"telenot_area_{area_num}_status"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [
            "unknown",
            "disarmed",
            "armed_home",
            "armed_away",
            "triggered",
            "trouble",
        ]
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"area_{area_num}")},
            "name": f"Telenot Bereich {area_num}",
            "manufacturer": "Telenot",
            "model": "complex400",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "areas" not in self.coordinator.data:
            return "unknown"
            
        area_data = self.coordinator.data["areas"].get(self._area_num)
        if not area_data:
            return "unknown"
        
        # Check for alarm condition first
        if area_data.get("alarm", False):
            return "triggered"
        
        # Check for trouble condition
        if area_data.get("trouble", False):
            return "trouble"
        
        # Return normal state
        return area_data.get("state", "unknown")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data or "areas" not in self.coordinator.data:
            return {}
            
        area_data = self.coordinator.data["areas"].get(self._area_num, {})
        
        return {
            "area_number": self._area_num,
            "alarm": area_data.get("alarm", False),
            "trouble": area_data.get("trouble", False),
            "ready_home": area_data.get("ready_home", False),
            "ready_away": area_data.get("ready_away", False),
            "buzzer": area_data.get("buzzer", False),
            "raw_state": area_data.get("state", "unknown"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data
            and self.coordinator.data.get("connected", False)
        )

    @property
    def icon(self) -> str:
        """Return the icon for the area status sensor."""
        state = self.native_value
        if state == "triggered":
            return "mdi:shield-alert"
        elif state == "trouble":
            return "mdi:alert-circle"
        elif state in ["armed_home", "armed_away"]:
            return "mdi:shield-check"
        elif state == "disarmed":
            return "mdi:shield-off"
        else:
            return "mdi:help-circle"
