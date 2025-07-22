"""Telenot alarm control panel platform."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
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
    """Set up Telenot alarm control panel from a config entry."""
    coordinator: TelenotDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    
    # Wait for initial data
    if coordinator.data and "areas" in coordinator.data:
        for area_num, area_data in coordinator.data["areas"].items():
            entities.append(TelenotAlarmPanel(coordinator, area_num, area_data))
    
    # If no areas found yet, create a default area 1
    if not entities:
        entities.append(TelenotAlarmPanel(coordinator, 1, {
            "area": 1,
            "name": "Bereich 1",
            "state": "unknown",
            "alarm": False,
            "trouble": False,
        }))

    async_add_entities(entities, update_before_add=True)


class TelenotAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of a Telenot alarm control panel."""

    def __init__(
        self,
        coordinator: TelenotDataUpdateCoordinator,
        area_num: int,
        area_data: Dict[str, Any],
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self._area_num = area_num
        self._attr_name = area_data.get("name", f"Telenot Bereich {area_num}")
        self._attr_unique_id = f"telenot_area_{area_num}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"area_{area_num}")},
            "name": self._attr_name,
            "manufacturer": "Telenot",
            "model": "complex400",
        }
        
        # Set supported features
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )

    @property
    def state(self) -> str | None:
        """Return the state of the alarm control panel."""
        if not self.coordinator.data or "areas" not in self.coordinator.data:
            return None
            
        area_data = self.coordinator.data["areas"].get(self._area_num)
        if not area_data:
            return None
        
        # Check for alarm condition first
        if area_data.get("alarm", False):
            return STATE_ALARM_TRIGGERED
        
        # Map Telenot states to Home Assistant states
        telenot_state = area_data.get("state", "unknown")
        if telenot_state == "disarmed":
            return STATE_ALARM_DISARMED
        elif telenot_state == "armed_home":
            return STATE_ALARM_ARMED_HOME
        elif telenot_state == "armed_away":
            return STATE_ALARM_ARMED_AWAY
        
        return STATE_ALARM_DISARMED  # Default to disarmed

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data or "areas" not in self.coordinator.data:
            return {}
            
        area_data = self.coordinator.data["areas"].get(self._area_num, {})
        
        return {
            "area_number": self._area_num,
            "trouble": area_data.get("trouble", False),
            "ready_home": area_data.get("ready_home", False),
            "ready_away": area_data.get("ready_away", False),
            "buzzer": area_data.get("buzzer", False),
            "telenot_state": area_data.get("state", "unknown"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data
            and self.coordinator.data.get("connected", False)
        )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        _LOGGER.info("Disarming area %d", self._area_num)
        success = await self.coordinator.async_disarm(self._area_num)
        if not success:
            _LOGGER.error("Failed to disarm area %d", self._area_num)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        _LOGGER.info("Arming home area %d", self._area_num)
        success = await self.coordinator.async_arm_home(self._area_num)
        if not success:
            _LOGGER.error("Failed to arm home area %d", self._area_num)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        _LOGGER.info("Arming away area %d", self._area_num)
        success = await self.coordinator.async_arm_away(self._area_num)
        if not success:
            _LOGGER.error("Failed to arm away area %d", self._area_num)

    @property
    def icon(self) -> str:
        """Return the icon for the alarm panel."""
        if self.state == STATE_ALARM_TRIGGERED:
            return "mdi:shield-alert"
        elif self.state in [STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY]:
            return "mdi:shield-check"
        else:
            return "mdi:shield-off"
