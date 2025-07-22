"""Data update coordinator for Telenot integration."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    MSG_TYPE_BLOCK_STATUS,
    MSG_TYPE_STATE_CHANGE,
    ADDR_EXT_INPUTS,
    ADDR_EXT_OUTPUTS,
    ADDR_AREA_STATUS,
    AREA_STATUS_DISARMED,
    AREA_STATUS_ARM_HOME,
    AREA_STATUS_ARM_AWAY,
    AREA_STATUS_ALARM,
    AREA_STATUS_TROUBLE,
)
from .protocol import TelenotProtocol
from .active_objects import get_discovery_addresses_from_data, get_active_objects_summary

_LOGGER = logging.getLogger(__name__)


class TelenotDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Telenot system."""

    def __init__(self, hass: HomeAssistant, host: str, port: int):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        
        self.protocol = TelenotProtocol(host, port)
        self.host = host
        self.port = port
        self._areas: Dict[int, Dict[str, Any]] = {}
        self._zones: Dict[int, Dict[str, Any]] = {}
        self._inputs: Dict[int, Dict[str, Any]] = {}
        self._outputs: Dict[int, Dict[str, Any]] = {}
        self._system_info: Dict[str, Any] = {}
        self._message_listener_task: Optional[asyncio.Task] = None
        self._object_names: Dict[int, str] = {}  # Cache for object names
        self._discovery_done: bool = False
        self._scan_data: Dict[str, Any] = {}  # Loaded scan data for active status
        self._scan_data_loaded: bool = False

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Telenot system."""
        if not self.protocol.connected:
            if not await self.protocol.connect():
                raise UpdateFailed("Failed to connect to Telenot system")
            
            # Start message listener task
            if not self._message_listener_task or self._message_listener_task.done():
                self._message_listener_task = asyncio.create_task(
                    self._message_listener()
                )
            
            # Start discovery if not done yet
            if not self._discovery_done:
                asyncio.create_task(self._discover_object_names())

        try:
            # Process any pending messages
            messages = await self.protocol.read_messages()
            for message in messages:
                await self._process_message(message)
            
            return {
                "areas": self._areas,
                "zones": self._zones,
                "inputs": self._inputs,
                "outputs": self._outputs,
                "system_info": self._system_info,
                "connected": self.protocol.connected,
            }
            
        except Exception as e:
            _LOGGER.error("Error updating data: %s", e)
            raise UpdateFailed(f"Error communicating with Telenot system: {e}")

    async def _message_listener(self):
        """Listen for incoming messages from Telenot system."""
        _LOGGER.info("Starting message listener")
        
        while self.protocol.connected:
            try:
                messages = await self.protocol.read_messages()
                for message in messages:
                    await self._process_message(message)
                    # Trigger update for listeners
                    self.async_set_updated_data(self.data or {})
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                _LOGGER.error("Error in message listener: %s", e)
                await asyncio.sleep(1)  # Wait before retrying

    async def _process_message(self, message: Dict[str, Any]):
        """Process a received message."""
        msg_type = message.get("type")
        
        if msg_type == MSG_TYPE_BLOCK_STATUS:
            await self._process_block_status(message)
        elif msg_type == MSG_TYPE_STATE_CHANGE:
            await self._process_state_change(message)
        
        _LOGGER.debug("Processed message type: 0x%02x", msg_type)

    async def _process_block_status(self, message: Dict[str, Any]):
        """Process block status message."""
        start_address = message.get("start_address", 0)
        addr_extension = message.get("addr_extension", 0)
        status_bits = message.get("status_bits", [])
        
        if addr_extension == ADDR_EXT_INPUTS:
            # Process input status
            for i, bit in enumerate(status_bits):
                address = start_address + i
                self._inputs[address] = {
                    "address": address,
                    "state": bit == 0,  # 0 = active, 1 = inactive
                    "name": self._get_input_name(address),
                    "device_class": self._get_input_device_class(address),
                }
        
        elif addr_extension == ADDR_EXT_OUTPUTS:
            # Process output status
            for i, bit in enumerate(status_bits):
                address = start_address + i
                
                # Check if this is an area status address
                if ADDR_AREA_STATUS[0] <= address <= ADDR_AREA_STATUS[1]:
                    area_num = ((address - ADDR_AREA_STATUS[0]) // 8) + 1
                    status_bit = (address - ADDR_AREA_STATUS[0]) % 8
                    
                    if area_num not in self._areas:
                        self._areas[area_num] = {
                            "area": area_num,
                            "name": f"Bereich {area_num}",
                            "state": "unknown",
                            "alarm": False,
                            "trouble": False,
                            "ready_home": False,
                            "ready_away": False,
                            "buzzer": False,
                        }
                    
                    area = self._areas[area_num]
                    
                    if status_bit == AREA_STATUS_DISARMED:
                        if bit == 0:  # Active
                            area["state"] = "disarmed"
                    elif status_bit == AREA_STATUS_ARM_HOME:
                        if bit == 0:  # Active
                            area["state"] = "armed_home"
                    elif status_bit == AREA_STATUS_ARM_AWAY:
                        if bit == 0:  # Active
                            area["state"] = "armed_away"
                    elif status_bit == AREA_STATUS_ALARM:
                        area["alarm"] = bit == 0
                    elif status_bit == AREA_STATUS_TROUBLE:
                        area["trouble"] = bit == 0
                    elif status_bit == AREA_STATUS_ARM_HOME_READY:
                        area["ready_home"] = bit == 0
                    elif status_bit == AREA_STATUS_ARM_AWAY_READY:
                        area["ready_away"] = bit == 0
                    elif status_bit == AREA_STATUS_ALARM_BUZZER:
                        area["buzzer"] = bit == 0
                
                else:
                    # Regular output
                    self._outputs[address] = {
                        "address": address,
                        "state": bit == 0,  # 0 = active, 1 = inactive
                        "name": self._get_output_name(address),
                    }

    async def _process_state_change(self, message: Dict[str, Any]):
        """Process state change message."""
        address = message.get("address", 0)
        is_alarm = message.get("is_alarm", False)
        alarm_type = message.get("alarm_type", "unknown")
        text = message.get("text", "")
        
        # Update relevant entities based on address
        if ADDR_AREA_STATUS[0] <= address <= ADDR_AREA_STATUS[1]:
            area_num = ((address - ADDR_AREA_STATUS[0]) // 8) + 1
            
            if area_num not in self._areas:
                self._areas[area_num] = {
                    "area": area_num,
                    "name": f"Bereich {area_num}",
                    "state": "unknown",
                    "alarm": False,
                    "trouble": False,
                    "ready_home": False,
                    "ready_away": False,
                    "buzzer": False,
                }
            
            area = self._areas[area_num]
            
            if alarm_type == "arm_away":
                area["state"] = "armed_away" if is_alarm else "disarmed"
            elif alarm_type == "arm_home":
                area["state"] = "armed_home" if is_alarm else "disarmed"
            elif alarm_type in ["burglary", "fire", "panic"]:
                area["alarm"] = is_alarm
        
        # Log the event
        _LOGGER.info(
            "State change: Address 0x%04x, Type: %s, Alarm: %s, Text: %s",
            address, alarm_type, is_alarm, text
        )

    def _get_input_name(self, address: int) -> str:
        """Get a human-readable name for an input address."""
        # Try to get name from Telenot system first
        if hasattr(self, '_object_names') and address in self._object_names:
            return self._object_names[address]
        
        # Master inputs
        if 0x0000 <= address <= 0x001F:
            return f"Meldergruppe {address + 1}"
        elif 0x0028 <= address <= 0x0066:
            bus_addr = address - 0x0028 + 1
            return f"Melderbus Strang 1 Adresse {bus_addr}"
        elif 0x0068 <= address <= 0x00A6:
            bus_addr = address - 0x0068 + 1
            return f"Melderbus Strang 2 Adresse {bus_addr}"
        
        # Keypads
        elif 0x00B0 <= address <= 0x00EF:
            keypad_num = (address - 0x00B0) // 4
            input_type = (address - 0x00B0) % 4
            input_names = ["Deckelkontakt BT", "Deckelkontakt AT", "Keine Antwort", "Sondertaste"]
            return f"Bedienteil {keypad_num} {input_names[input_type]}"
        
        return f"Eingang 0x{address:04X}"

    def _get_input_device_class(self, address: int) -> Optional[str]:
        """Get device class for an input."""
        # Sabotage contacts
        if address in [0x0010, 0x0180, 0x0230, 0x02E0]:  # Deckelkontakt
            return "door"
        
        # Power/battery issues
        if address in [0x0014, 0x0184, 0x0234, 0x02E4]:  # Akkustörung
            return "battery"
        if address in [0x0015, 0x0185, 0x0235, 0x02E5]:  # Netzstörung
            return "power"
        
        # Motion detectors (Meldergruppen)
        if 0x0000 <= address <= 0x001F:
            return "motion"
        
        return None

    def _get_output_name(self, address: int) -> str:
        """Get a human-readable name for an output address."""
        # Master outputs
        if 0x0500 <= address <= 0x0507:
            return f"ÜG TA{address - 0x0500 + 1}"
        elif 0x0508 <= address <= 0x050A:
            return f"Relais {address - 0x0508 + 1}"
        elif address == 0x050B:
            return "OSG (Optischer Signalgeber)"
        elif address == 0x050C:
            return "ASG1 (Akustischer Signalgeber 1)"
        elif address == 0x050D:
            return "ASG2 (Akustischer Signalgeber 2)"
        
        return f"Ausgang 0x{address:04X}"

    async def async_arm_away(self, area: int = 1) -> bool:
        """Arm area in away mode."""
        try:
            success = await self.protocol.send_arm_away_command(area)
            if success:
                _LOGGER.info("Armed area %d in away mode", area)
            return success
        except Exception as e:
            _LOGGER.error("Failed to arm area %d away: %s", area, e)
            return False

    async def async_arm_home(self, area: int = 1) -> bool:
        """Arm area in home mode."""
        try:
            success = await self.protocol.send_arm_home_command(area)
            if success:
                _LOGGER.info("Armed area %d in home mode", area)
            return success
        except Exception as e:
            _LOGGER.error("Failed to arm area %d home: %s", area, e)
            return False

    async def async_disarm(self, area: int = 1) -> bool:
        """Disarm area."""
        try:
            success = await self.protocol.send_disarm_command(area)
            if success:
                _LOGGER.info("Disarmed area %d", area)
            return success
        except Exception as e:
            _LOGGER.error("Failed to disarm area %d: %s", area, e)
            return False

    async def _load_scan_data(self):
        """Load scan data to get active status information."""
        if self._scan_data_loaded:
            return
        
        try:
            # Look for scan data file in the integration directory
            scan_file = os.path.join(os.path.dirname(__file__), "..", "..", "telenot_scan_20250722_222644.json")
            if os.path.exists(scan_file):
                with open(scan_file, 'r', encoding='utf-8') as f:
                    self._scan_data = json.load(f)
                _LOGGER.info("Loaded scan data with %d inputs and %d outputs", 
                           len(self._scan_data.get("inputs", {})), 
                           len(self._scan_data.get("outputs", {})))
                self._scan_data_loaded = True
            else:
                _LOGGER.warning("Scan data file not found: %s", scan_file)
        except Exception as e:
            _LOGGER.error("Failed to load scan data: %s", e)

    def _merge_active_status(self):
        """Merge active status from scan data into current data."""
        if not self._scan_data:
            return
        
        # Merge input active status
        scan_inputs = self._scan_data.get("inputs", {})
        for addr_str, scan_input in scan_inputs.items():
            address = int(addr_str)
            if address in self._inputs:
                self._inputs[address]["active"] = scan_input.get("active", False)
        
        # Merge output active status
        scan_outputs = self._scan_data.get("outputs", {})
        for addr_str, scan_output in scan_outputs.items():
            address = int(addr_str)
            if address in self._outputs:
                self._outputs[address]["active"] = scan_output.get("active", False)

    async def _discover_object_names(self):
        """Discover object names from Telenot system for active objects only."""
        _LOGGER.info("Starting object name discovery for active objects")
        
        # Load scan data first
        await self._load_scan_data()
        
        # Merge active status into current data
        self._merge_active_status()
        
        # Wait for initial data to be available
        current_data = {
            "inputs": self._inputs,
            "outputs": self._outputs,
            "areas": self._areas,
        }
        
        # Log active objects summary
        summary = get_active_objects_summary(current_data)
        _LOGGER.info("Active objects summary: %s", summary)
        
        try:
            # Get discovery addresses from current data
            test_addresses = list(get_discovery_addresses_from_data(current_data))
            successful_queries = 0
            
            _LOGGER.info("Querying names for %d discovery addresses", len(test_addresses))
            
            for address in test_addresses:
                try:
                    name = await self.protocol.query_object_name(address)
                    if name:
                        # Clean up the name (remove extra spaces)
                        clean_name = ' '.join(name.split())
                        self._object_names[address] = clean_name
                        successful_queries += 1
                        _LOGGER.info("Discovered name for 0x%04X: '%s'", address, clean_name)
                        
                        # Update existing entities with new names
                        if address in self._inputs:
                            self._inputs[address]["name"] = clean_name
                        if address in self._outputs:
                            self._outputs[address]["name"] = clean_name
                    
                    # Small delay between queries to avoid overwhelming the system
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    _LOGGER.debug("Failed to query name for 0x%04X: %s", address, e)
            
            self._discovery_done = True
            _LOGGER.info("Object name discovery completed: %d/%d successful", 
                        successful_queries, len(test_addresses))
            
            # Trigger update to refresh entity names
            if successful_queries > 0:
                self.async_set_updated_data(self.data or {})
            
        except Exception as e:
            _LOGGER.error("Error during object name discovery: %s", e)

    async def async_shutdown(self):
        """Shutdown the coordinator."""
        if self._message_listener_task and not self._message_listener_task.done():
            self._message_listener_task.cancel()
            try:
                await self._message_listener_task
            except asyncio.CancelledError:
                pass
        
        await self.protocol.disconnect()
        _LOGGER.info("Telenot coordinator shut down")

    @property
    def areas(self) -> Dict[int, Dict[str, Any]]:
        """Get areas data."""
        return self._areas

    @property
    def inputs(self) -> Dict[int, Dict[str, Any]]:
        """Get inputs data."""
        return self._inputs

    @property
    def outputs(self) -> Dict[int, Dict[str, Any]]:
        """Get outputs data."""
        return self._outputs
