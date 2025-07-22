#!/usr/bin/env python3
"""
Standalone Telenot GMS protocol implementation for testing.
This version doesn't depend on Home Assistant.
"""

import asyncio
import logging
import struct
from typing import Any, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

# Protocol constants
TELEGRAM_START = 0x68
TELEGRAM_END = 0x16

# Control field constants
SEND_NORM = 0x40
SEND_NDAT = 0x73
CONFIRM_ACK = 0x00
CONFIRM_NAK = 0x01

# Message types (Satztypen)
MSG_TYPE_STATE_CHANGE = 0x02  # Meldung Zustandsänderung
MSG_TYPE_AREA_INFO = 0x0C     # Bereich-Meldebereich
MSG_TYPE_QUERY = 0x10         # Abfrage
MSG_TYPE_ERROR = 0x11         # Fehler
MSG_TYPE_BLOCK_STATUS = 0x24  # Blockstatus
MSG_TYPE_DATETIME = 0x50      # Datum und Uhrzeit
MSG_TYPE_ASCII = 0x54         # ASCII-Zeichenfolge
MSG_TYPE_IDENT = 0x56         # Identifikations-Nummer

# Address extensions
ADDR_EXT_INPUTS = 0x01        # Meldeeingänge
ADDR_EXT_OUTPUTS = 0x02       # Schaltausgänge
ADDR_EXT_OCCUPIED_INPUTS = 0x71   # Belegtstatus Eingänge
ADDR_EXT_OCCUPIED_OUTPUTS = 0x72  # Belegtstatus Ausgänge
ADDR_EXT_AREA_INFO = 0x73     # Bereich/Meldebereich Info

# Message types (Meldungsarten)
MSG_ALARM_TYPES = {
    0x00: "message",           # Meldung
    0x10: "fire",             # Brandmeldung
    0x21: "panic",            # Überfall
    0x22: "burglary",         # Einbruch
    0x23: "sabotage",         # Sabotage
    0x30: "trouble",          # Störung
    0x32: "power_trouble",    # Störung Netz
    0x33: "battery_trouble",  # Störung Akku
    0x34: "comm_trouble",     # Störung Übertragungsweg
    0x40: "technical",        # Technische Meldung
    0x41: "technical_alarm",  # Technikalarm
    0x51: "bypass",           # Abschaltung
    0x52: "reset",            # Rücksetzen
    0x53: "restart",          # Neustart
    0x61: "arm_away",         # Sicherungsbereich scharf
    0x62: "arm_home",         # Internbereich ein
}


class TelenotProtocol:
    """Telenot GMS protocol handler."""

    def __init__(self, host: str, port: int):
        """Initialize the protocol handler."""
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to the Telenot system."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            self.connected = True
            _LOGGER.info("Connected to Telenot system at %s:%s", self.host, self.port)
            return True
        except Exception as e:
            _LOGGER.error("Failed to connect to Telenot system: %s", e)
            return False

    async def disconnect(self):
        """Disconnect from the Telenot system."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False
        _LOGGER.info("Disconnected from Telenot system")

    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate checksum for telegram data."""
        return sum(data) & 0xFF

    def _build_telegram(self, control: int, address: int, data: bytes) -> bytes:
        """Build a complete telegram."""
        # Length includes control, address and data
        length = 2 + len(data)
        
        # Build telegram without start/end markers for checksum calculation
        telegram_data = struct.pack("BB", control, address) + data
        checksum = self._calculate_checksum(telegram_data)
        
        # Build complete telegram
        telegram = (
            struct.pack("BBBB", TELEGRAM_START, length, length, TELEGRAM_START) +
            telegram_data +
            struct.pack("BB", checksum, TELEGRAM_END)
        )
        
        return telegram

    def _parse_telegram(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse a received telegram."""
        if len(data) < 8:  # Minimum telegram size
            return None

        if data[0] != TELEGRAM_START or data[-1] != TELEGRAM_END:
            _LOGGER.warning("Invalid telegram markers")
            return None

        length1 = data[1]
        length2 = data[2]
        
        if length1 != length2:
            _LOGGER.warning("Length field mismatch")
            return None

        if data[3] != TELEGRAM_START:
            _LOGGER.warning("Invalid second start marker")
            return None

        # Extract telegram data (without frame)
        telegram_data = data[4:4+length1]
        expected_checksum = data[4+length1]
        
        # Verify checksum
        calculated_checksum = self._calculate_checksum(telegram_data)
        if calculated_checksum != expected_checksum:
            _LOGGER.warning("Checksum mismatch: expected %02x, got %02x", 
                          expected_checksum, calculated_checksum)
            return None

        # Parse telegram content
        control = telegram_data[0]
        address = telegram_data[1]
        payload = telegram_data[2:]

        return {
            "control": control,
            "address": address,
            "payload": payload,
            "raw": data
        }

    def _parse_message_data(self, payload: bytes) -> List[Dict[str, Any]]:
        """Parse message payload into individual message blocks."""
        messages = []
        offset = 0
        
        while offset < len(payload):
            if offset + 2 > len(payload):
                break
                
            msg_length = payload[offset]
            msg_type = payload[offset + 1]
            
            if offset + msg_length + 1 > len(payload):
                break
                
            msg_data = payload[offset + 2:offset + msg_length + 1]
            
            message = {
                "type": msg_type,
                "length": msg_length,
                "data": msg_data
            }
            
            # Parse specific message types
            if msg_type == MSG_TYPE_STATE_CHANGE:
                message.update(self._parse_state_change(msg_data))
            elif msg_type == MSG_TYPE_BLOCK_STATUS:
                message.update(self._parse_block_status(msg_data))
            elif msg_type == MSG_TYPE_ASCII:
                message.update(self._parse_ascii_text(msg_data))
            elif msg_type == MSG_TYPE_IDENT:
                message.update(self._parse_ident(msg_data))
            elif msg_type == MSG_TYPE_DATETIME:
                message.update(self._parse_datetime(msg_data))
            
            messages.append(message)
            offset += msg_length + 1
            
        return messages

    def _parse_state_change(self, data: bytes) -> Dict[str, Any]:
        """Parse state change message (0x02)."""
        if len(data) < 5:
            return {}
            
        device_area = data[0]
        address = (data[1] << 8) | data[2]
        addr_extension = data[3]
        message_type = data[4]
        
        # Extract alarm/restore bit
        is_alarm = (message_type & 0x80) == 0
        msg_code = message_type & 0x7F
        
        return {
            "device_area": device_area,
            "address": address,
            "addr_extension": addr_extension,
            "message_type": message_type,
            "is_alarm": is_alarm,
            "alarm_type": MSG_ALARM_TYPES.get(msg_code, "unknown"),
            "raw_message_type": msg_code
        }

    def _parse_block_status(self, data: bytes) -> Dict[str, Any]:
        """Parse block status message (0x24)."""
        if len(data) < 5:
            return {}
            
        device_area = data[0]
        start_address = (data[1] << 8) | data[2]
        addr_extension = data[3]
        status_data = data[4:]
        
        # Convert status bytes to bit array
        status_bits = []
        for byte in status_data:
            for bit in range(8):
                status_bits.append((byte >> bit) & 1)
        
        return {
            "device_area": device_area,
            "start_address": start_address,
            "addr_extension": addr_extension,
            "status_bits": status_bits,
            "status_bytes": list(status_data)
        }

    def _parse_ascii_text(self, data: bytes) -> Dict[str, Any]:
        """Parse ASCII text message (0x54) with multiple encoding support."""
        # Try different encodings for German text (ü, ä, ö, ß)
        encodings = ['ascii', 'iso-8859-1', 'windows-1252', 'utf-8']
        
        for encoding in encodings:
            try:
                text = data.decode(encoding).rstrip('\x00 ')
                if text and len(text.strip()) > 0:
                    return {"text": text, "encoding": encoding}
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, return hex representation
        return {"text": data.hex(), "encoding": "hex"}

    def _parse_ident(self, data: bytes) -> Dict[str, Any]:
        """Parse identification number (0x56)."""
        if len(data) < 6:
            return {}
            
        # Convert BCD encoded identification number
        ident_str = ""
        for byte in data:
            high_nibble = (byte >> 4) & 0x0F
            low_nibble = byte & 0x0F
            
            if high_nibble != 0x0F:
                ident_str += str(high_nibble)
            if low_nibble != 0x0F:
                ident_str += str(low_nibble)
        
        return {"identification": ident_str}

    def _parse_datetime(self, data: bytes) -> Dict[str, Any]:
        """Parse date/time message (0x50)."""
        if len(data) < 7:
            return {}
            
        year = data[0]
        century_or_weekday = data[1]
        month = data[2]
        day = data[3]
        hour = data[4]
        minute = data[5]
        second = data[6]
        
        return {
            "year": year,
            "century_or_weekday": century_or_weekday,
            "month": month,
            "day": day,
            "hour": hour,
            "minute": minute,
            "second": second
        }

    async def send_confirm_ack(self) -> bool:
        """Send confirmation ACK."""
        if not self.writer:
            return False
            
        telegram = self._build_telegram(CONFIRM_ACK, 0x02, b"")
        
        try:
            self.writer.write(telegram)
            await self.writer.drain()
            _LOGGER.debug("Sent CONFIRM_ACK")
            return True
        except Exception as e:
            _LOGGER.error("Failed to send CONFIRM_ACK: %s", e)
            return False

    async def send_arm_away_command(self, area: int = 1) -> bool:
        """Send arm away command."""
        # Address for area status (0x0530 + area - 1)
        area_addr = 0x0530 + (area - 1)
        
        # Build state change message for arm away
        msg_data = struct.pack(">BHHBB", 
                              0x00,  # device/area
                              area_addr >> 8, area_addr & 0xFF,  # address
                              ADDR_EXT_OUTPUTS,  # address extension
                              0x61)  # arm away message type
        
        return await self._send_command(MSG_TYPE_STATE_CHANGE, msg_data)

    async def send_arm_home_command(self, area: int = 1) -> bool:
        """Send arm home command."""
        area_addr = 0x0530 + (area - 1)
        
        msg_data = struct.pack(">BHHBB", 
                              0x00,
                              area_addr >> 8, area_addr & 0xFF,
                              ADDR_EXT_OUTPUTS,
                              0x62)  # arm home message type
        
        return await self._send_command(MSG_TYPE_STATE_CHANGE, msg_data)

    async def send_disarm_command(self, area: int = 1) -> bool:
        """Send disarm command."""
        area_addr = 0x0530 + (area - 1)
        
        msg_data = struct.pack(">BHHBB", 
                              0x00,
                              area_addr >> 8, area_addr & 0xFF,
                              ADDR_EXT_OUTPUTS,
                              0xE1)  # disarm message type
        
        return await self._send_command(MSG_TYPE_STATE_CHANGE, msg_data)

    async def _send_command(self, msg_type: int, msg_data: bytes) -> bool:
        """Send a command to the Telenot system."""
        if not self.writer:
            return False
            
        async with self._lock:
            try:
                # Build message payload
                payload = struct.pack("BB", len(msg_data) + 1, msg_type) + msg_data
                
                # Send SEND_NORM first
                norm_telegram = self._build_telegram(SEND_NORM, 0x02, b"")
                self.writer.write(norm_telegram)
                await self.writer.drain()
                
                # Wait for ACK
                response = await self._read_telegram()
                if not response or response["control"] != CONFIRM_ACK:
                    _LOGGER.error("Did not receive ACK for SEND_NORM")
                    return False
                
                # Send command data
                data_telegram = self._build_telegram(SEND_NDAT, 0x01, payload)
                self.writer.write(data_telegram)
                await self.writer.drain()
                
                # Wait for ACK
                response = await self._read_telegram()
                if not response or response["control"] != CONFIRM_ACK:
                    _LOGGER.error("Did not receive ACK for command")
                    return False
                
                _LOGGER.debug("Command sent successfully")
                return True
                
            except Exception as e:
                _LOGGER.error("Failed to send command: %s", e)
                return False

    async def _read_telegram(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Read a telegram from the connection."""
        if not self.reader:
            return None
            
        try:
            # Read until we find a start marker
            while True:
                byte = await asyncio.wait_for(self.reader.read(1), timeout=timeout)
                if not byte:
                    return None
                if byte[0] == TELEGRAM_START:
                    break
            
            # Read length fields
            length_data = await asyncio.wait_for(self.reader.read(3), timeout=timeout)
            if len(length_data) != 3:
                return None
                
            length1, length2, start2 = length_data
            if length1 != length2 or start2 != TELEGRAM_START:
                return None
            
            # Read remaining telegram data
            remaining = await asyncio.wait_for(
                self.reader.read(length1 + 2), timeout=timeout
            )
            if len(remaining) != length1 + 2:
                return None
            
            # Reconstruct complete telegram
            telegram = bytes([TELEGRAM_START]) + length_data + remaining
            
            return self._parse_telegram(telegram)
            
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout reading telegram")
            return None
        except Exception as e:
            _LOGGER.error("Error reading telegram: %s", e)
            return None

    async def read_messages(self) -> List[Dict[str, Any]]:
        """Read and parse incoming messages."""
        messages = []
        
        try:
            telegram = await self._read_telegram()
            if not telegram:
                return messages
            
            # Handle different telegram types
            if telegram["control"] == SEND_NORM:
                # Send ACK for SEND_NORM
                await self.send_confirm_ack()
                
                # Send query to request data
                await self._send_query_request()
                
                # Try to read the response
                response = await self._read_telegram(timeout=2.0)
                if response and response["control"] == SEND_NDAT:
                    # Send ACK for data telegram
                    await self.send_confirm_ack()
                    
                    # Parse message content
                    parsed_messages = self._parse_message_data(response["payload"])
                    messages.extend(parsed_messages)
            
            elif telegram["control"] == SEND_NDAT:
                # Send ACK for received telegram
                await self.send_confirm_ack()
                
                # Parse message content
                parsed_messages = self._parse_message_data(telegram["payload"])
                messages.extend(parsed_messages)
            
        except Exception as e:
            _LOGGER.error("Error reading messages: %s", e)
        
        return messages

    async def _send_query_request(self) -> bool:
        """Send a query request to get status data."""
        try:
            # Build query message for block status
            # Query all inputs (0x0000-0x00FF) with address extension 0x01
            query_inputs = struct.pack(">BHHB", 0x00, 0x00, 0x00, 0x01)
            query_msg_inputs = struct.pack("BB", len(query_inputs) + 1, 0x10) + query_inputs
            
            # Query all outputs (0x0500-0x05FF) with address extension 0x02  
            query_outputs = struct.pack(">BHHB", 0x00, 0x05, 0x00, 0x02)
            query_msg_outputs = struct.pack("BB", len(query_outputs) + 1, 0x10) + query_outputs
            
            # Combine queries
            combined_query = query_msg_inputs + query_msg_outputs
            
            # Send query telegram
            query_telegram = self._build_telegram(SEND_NDAT, 0x01, combined_query)
            self.writer.write(query_telegram)
            await self.writer.drain()
            
            _LOGGER.debug("Sent query request")
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to send query request: %s", e)
            return False

    async def send_contact_info_query(self, address: int) -> bool:
        """Send contact info query based on Java implementation."""
        try:
            # Based on Java: getContactInfo(String address)
            # Format: "680909687302051000" + hex + "730C" + checksum + "16"
            
            hex_addr = f"{address:04x}"
            msg_base = "680909687302051000" + hex_addr + "730C"
            
            # Calculate checksum (based on Java implementation)
            checksum = self._calculate_java_checksum(msg_base)
            
            # Build complete message
            msg_hex = msg_base + f"{checksum:02x}" + "16"
            msg_bytes = bytes.fromhex(msg_hex)
            
            self.writer.write(msg_bytes)
            await self.writer.drain()
            
            _LOGGER.debug("Sent contact info query for address 0x%04X: %s", address, msg_hex)
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to send contact info query: %s", e)
            return False

    def _calculate_java_checksum(self, hex_string: str) -> int:
        """Calculate checksum using Java algorithm."""
        # Java algorithm from TelenotCommand.checksum()
        data_length = int(hex_string[2:4], 16)  # Get length from position 2-4
        x = 0
        a = 8  # Start at position 8
        
        for i in range(data_length):
            x += int(hex_string[a:a+2], 16)
            a += 2
        
        # Return last 2 hex digits
        return x & 0xFF

    async def query_object_name(self, address: int, addr_extension: int = 0x01) -> Optional[str]:
        """Query the name of a specific object."""
        try:
            # Send text query
            query_data = struct.pack(">BHHBB", 
                                   0x00,  # device/area
                                   address >> 8, address & 0xFF,  # address
                                   addr_extension,  # address extension
                                   0x01)  # name query type
            
            query_msg = struct.pack("BB", len(query_data) + 1, 0x11) + query_data
            query_telegram = self._build_telegram(SEND_NDAT, 0x01, query_msg)
            
            self.writer.write(query_telegram)
            await self.writer.drain()
            
            # Wait for response
            for _ in range(10):  # Try for 10 seconds
                response = await self._read_telegram(timeout=1.0)
                if response and response["control"] == SEND_NDAT:
                    await self.send_confirm_ack()
                    
                    # Parse response messages
                    messages = self._parse_message_data(response["payload"])
                    for msg in messages:
                        if msg.get("type") == MSG_TYPE_ASCII:
                            name = msg.get("text", "").strip()
                            if name:
                                _LOGGER.info("Found name for 0x%04X: %s", address, name)
                                return name
                
                await asyncio.sleep(0.1)
            
            _LOGGER.warning("No name response for address 0x%04X", address)
            return None
            
        except Exception as e:
            _LOGGER.error("Failed to query object name: %s", e)
            return None
