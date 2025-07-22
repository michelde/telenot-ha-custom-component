"""Telenot binary sensor platform."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelenotDataUpdateCoordinator
from .utils import create_entity_id_from_name, create_friendly_name_from_telenot_name
from .active_objects import should_create_entity, get_active_objects_summary

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telenot binary sensors from a config entry."""
    coordinator: TelenotDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    
    # Log active objects summary
    summary = get_active_objects_summary(coordinator.data)
    _LOGGER.info("Active objects summary: %s", summary)
    
    # Add input sensors - only for active inputs
    if coordinator.data and "inputs" in coordinator.data:
        for address, input_data in coordinator.data["inputs"].items():
            if should_create_entity(address, "input", coordinator.data):
                entities.append(TelenotBinarySensor(coordinator, address, input_data, "input"))
                _LOGGER.info("Added active input sensor: 0x%04X - %s", address, input_data.get("name", "Unknown"))
    
    # Add area trouble sensors
    if coordinator.data and "areas" in coordinator.data:
        for area_num, area_data in coordinator.data["areas"].items():
            entities.append(TelenotAreaTroubleSensor(coordinator, area_num, area_data))
            entities.append(TelenotAreaAlarmSensor(coordinator, area_num, area_data))

    input_sensors = len([e for e in entities if isinstance(e, TelenotBinarySensor)])
    _LOGGER.info("Created %d binary sensor entities (%d active inputs + %d area sensors)", 
                len(entities), input_sensors, len(entities) - input_sensors)
    
    async_add_entities(entities, update_before_add=True)


class TelenotBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Telenot binary sensor."""

    def __init__(
        self,
        coordinator: TelenotDataUpdateCoordinator,
        address: int,
        sensor_data: Dict[str, Any],
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._address = address
        self._sensor_type = sensor_type
        
        # Get name from sensor data (may include Telenot system name)
        telenot_name = sensor_data.get("name", "")
        
        # Create user-friendly entity ID and name
        if telenot_name and not telenot_name.startswith("Meldergruppe") and not telenot_name.startswith("Eingang"):
            # Use Telenot system name
            self._attr_name = create_friendly_name_from_telenot_name(telenot_name, address)
            entity_id_base = create_entity_id_from_name(telenot_name, address)
            self._attr_unique_id = f"{entity_id_base}_{sensor_type}"
        else:
            # Fallback to generic name
            self._attr_name = f"Telenot {sensor_type} {address:04X}"
            self._attr_unique_id = f"telenot_{sensor_type}_{address:04X}"
        
        # Set device class based on sensor data
        device_class = sensor_data.get("device_class")
        if device_class:
            self._attr_device_class = getattr(BinarySensorDeviceClass, device_class.upper(), None)
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{sensor_type}_{address:04X}")},
            "name": self._attr_name,
            "manufacturer": "Telenot",
            "model": "complex400",
            "via_device": (DOMAIN, "master"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data or "inputs" not in self.coordinator.data:
            return None
            
        input_data = self.coordinator.data["inputs"].get(self._address)
        if not input_data:
            return None
            
        return input_data.get("state", False)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data or "inputs" not in self.coordinator.data:
            return {}
            
        input_data = self.coordinator.data["inputs"].get(self._address, {})
        
        return {
            "address": f"0x{self._address:04X}",
            "address_decimal": self._address,
            "device_class_raw": input_data.get("device_class"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data
            and self.coordinator.data.get("connected", False)
        )


class TelenotAreaTroubleSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Telenot area trouble sensor."""

    def __init__(
        self,
        coordinator: TelenotDataUpdateCoordinator,
        area_num: int,
        area_data: Dict[str, Any],
    ) -> None:
        """Initialize the area trouble sensor."""
        super().__init__(coordinator)
        self._area_num = area_num
        self._attr_name = f"Telenot Bereich {area_num} Störung"
        self._attr_unique_id = f"telenot_area_{area_num}_trouble"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"area_{area_num}")},
            "name": f"Telenot Bereich {area_num}",
            "manufacturer": "Telenot",
            "model": "complex400",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if there is a trouble condition."""
        if not self.coordinator.data or "areas" not in self.coordinator.data:
            return None
            
        area_data = self.coordinator.data["areas"].get(self._area_num)
        if not area_data:
            return None
            
        return area_data.get("trouble", False)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data
            and self.coordinator.data.get("connected", False)
        )


class TelenotAreaAlarmSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Telenot area alarm sensor."""

    def __init__(
        self,
        coordinator: TelenotDataUpdateCoordinator,
        area_num: int,
        area_data: Dict[str, Any],
    ) -> None:
        """Initialize the area alarm sensor."""
        super().__init__(coordinator)
        self._area_num = area_num
        self._attr_name = f"Telenot Bereich {area_num} Alarm"
        self._attr_unique_id = f"telenot_area_{area_num}_alarm"
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"area_{area_num}")},
            "name": f"Telenot Bereich {area_num}",
            "manufacturer": "Telenot",
            "model": "complex400",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if there is an alarm condition."""
        if not self.coordinator.data or "areas" not in self.coordinator.data:
            return None
            
        area_data = self.coordinator.data["areas"].get(self._area_num)
        if not area_data:
            return None
            
        return area_data.get("alarm", False)

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
        """Return the icon for the alarm sensor."""
        if self.is_on:
            return "mdi:shield-alert"
        else:
            return "mdi:shield-check"
