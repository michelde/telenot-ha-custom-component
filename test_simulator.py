#!/usr/bin/env python3
"""
Telenot complex400 simulator for testing.
This simulator implements the GMS protocol and can be used to test the integration.
"""

import asyncio
import logging
import struct
import time
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

_LOGGER = logging.getLogger(__name__)

# Protocol constants
TELEGRAM_START = 0x68
TELEGRAM_END = 0x16
SEND_NORM = 0x40
SEND_NDAT = 0x73
CONFIRM_ACK = 0x00
CONFIRM_NAK = 0x01

# Message types
MSG_TYPE_STATE_CHANGE = 0x02
MSG_TYPE_BLOCK_STATUS = 0x24
MSG_TYPE_DATETIME = 0x50
MSG_TYPE_ASCII = 0x54
MSG_TYPE_IDENT = 0x56

# Address extensions
ADDR_EXT_INPUTS = 0x01
ADDR_EXT_OUTPUTS = 0x02


class TelenotSimulator:
    """Telenot complex400 simulator."""

    def __init__(self, host: str = "localhost", port: int = 8234):
        """Initialize the simulator."""
        self.host = host
        self.port = port
        self.server = None
        self.clients = []
        
        # Simulated system state
        self.areas = {
            1: {"state": "disarmed", "alarm": False, "trouble": False},
            2: {"state": "disarmed", "alarm": False, "trouble": False},
        }
        
        # Simulated inputs (32 detector groups)
        self.inputs = {}
        for i in range(32):
            self.inputs[i] = {
                "address": i,
                "active": False,
                "name": f"Meldergruppe {i + 1}"
            }
        
        # Simulated outputs
        self.outputs = {}
        for i in range(0x0500, 0x0510):
            self.outputs[i] = {
                "address": i,
                "active": False,
                "name": self._get_output_name(i)
            }
        
        # Area status outputs (0x0530-0x056F)
        for area in range(1, 9):  # 8 areas max
            for bit in range(8):
                addr = 0x0530 + (area - 1) * 8 + bit
                self.outputs[addr] = {
                    "address": addr,
                    "active": False,
                    "name": f"Bereich {area} Bit {bit}"
                }
        
        self.last_status_send = 0
        self.last_alarm_simulation = 0

    def _get_output_name(self, address: int) -> str:
        """Get output name."""
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

    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate checksum."""
        return sum(data) & 0xFF

    def _build_telegram(self, control: int, address: int, data: bytes) -> bytes:
        """Build a complete telegram."""
        length = 2 + len(data)
        telegram_data = struct.pack("BB", control, address) + data
        checksum = self._calculate_checksum(telegram_data)
        
        telegram = (
            struct.pack("BBBB", TELEGRAM_START, length, length, TELEGRAM_START) +
            telegram_data +
            struct.pack("BB", checksum, TELEGRAM_END)
        )
        
        return telegram

    def _parse_telegram(self, data: bytes) -> Optional[Dict]:
        """Parse received telegram."""
        if len(data) < 8:
            return None

        if data[0] != TELEGRAM_START or data[-1] != TELEGRAM_END:
            return None

        length1 = data[1]
        length2 = data[2]
        
        if length1 != length2 or data[3] != TELEGRAM_START:
            return None

        telegram_data = data[4:4+length1]
        expected_checksum = data[4+length1]
        
        calculated_checksum = self._calculate_checksum(telegram_data)
        if calculated_checksum != expected_checksum:
            return None

        control = telegram_data[0]
        address = telegram_data[1]
        payload = telegram_data[2:]

        return {
            "control": control,
            "address": address,
            "payload": payload,
        }

    def _build_block_status_message(self, start_addr: int, addr_ext: int, 
                                   status_data: List[int]) -> bytes:
        """Build block status message."""
        msg_data = struct.pack(">BHHB", 0x00, start_addr >> 8, start_addr & 0xFF, addr_ext)
        msg_data += bytes(status_data)
        
        msg_length = len(msg_data) + 1
        return struct.pack("BB", msg_length, MSG_TYPE_BLOCK_STATUS) + msg_data

    def _build_state_change_message(self, address: int, msg_type: int) -> bytes:
        """Build state change message."""
        msg_data = struct.pack(">BHHBB", 0x00, address >> 8, address & 0xFF, 
                              ADDR_EXT_OUTPUTS, msg_type)
        
        msg_length = len(msg_data) + 1
        return struct.pack("BB", msg_length, MSG_TYPE_STATE_CHANGE) + msg_data

    def _build_identification_message(self) -> bytes:
        """Build identification message."""
        # BCD encoded identification: 123456
        ident_data = bytes([0x12, 0x34, 0x56, 0xFF, 0xFF, 0xFF])
        
        msg_length = len(ident_data) + 1
        return struct.pack("BB", msg_length, MSG_TYPE_IDENT) + ident_data

    def _build_ascii_message(self, text: str) -> bytes:
        """Build ASCII text message."""
        text_data = text.encode('ascii')[:32]  # Max 32 chars
        text_data = text_data.ljust(32, b'\x00')  # Pad with nulls
        
        msg_length = len(text_data) + 1
        return struct.pack("BB", msg_length, MSG_TYPE_ASCII) + text_data

    def _get_input_status_bytes(self) -> List[int]:
        """Get input status as bytes."""
        status_bytes = []
        
        # Pack 32 inputs into 4 bytes
        for byte_idx in range(4):
            byte_val = 0
            for bit_idx in range(8):
                input_idx = byte_idx * 8 + bit_idx
                if input_idx < len(self.inputs):
                    if self.inputs[input_idx]["active"]:
                        byte_val |= (1 << bit_idx)
                    else:
                        byte_val |= (0 << bit_idx)  # Inactive = 1, Active = 0
                else:
                    byte_val |= (1 << bit_idx)  # Non-existent = 1
            
            # Invert because Telenot uses inverted logic (0 = active)
            status_bytes.append(~byte_val & 0xFF)
        
        return status_bytes

    def _get_area_status_bytes(self) -> List[int]:
        """Get area status as bytes."""
        status_bytes = []
        
        # Each area uses 8 bits (1 byte)
        for area_num in range(1, 9):  # 8 areas max
            byte_val = 0xFF  # Default all bits to 1 (inactive)
            
            if area_num in self.areas:
                area = self.areas[area_num]
                
                # Bit 0: Disarmed
                if area["state"] == "disarmed":
                    byte_val &= ~(1 << 0)  # Set bit to 0 (active)
                
                # Bit 1: Armed Home
                if area["state"] == "armed_home":
                    byte_val &= ~(1 << 1)
                
                # Bit 2: Armed Away
                if area["state"] == "armed_away":
                    byte_val &= ~(1 << 2)
                
                # Bit 3: Alarm
                if area["alarm"]:
                    byte_val &= ~(1 << 3)
                
                # Bit 4: Trouble
                if area["trouble"]:
                    byte_val &= ~(1 << 4)
                
                # Bit 5: Ready Home (always ready for demo)
                byte_val &= ~(1 << 5)
                
                # Bit 6: Ready Away (always ready for demo)
                byte_val &= ~(1 << 6)
            
            status_bytes.append(byte_val)
        
        return status_bytes

    def _get_output_status_bytes(self) -> List[int]:
        """Get output status as bytes."""
        status_bytes = []
        
        # Master outputs (0x0500-0x050F) = 16 outputs = 2 bytes
        for byte_idx in range(2):
            byte_val = 0xFF  # Default all bits to 1 (inactive)
            
            for bit_idx in range(8):
                addr = 0x0500 + byte_idx * 8 + bit_idx
                if addr in self.outputs and self.outputs[addr]["active"]:
                    byte_val &= ~(1 << bit_idx)  # Set bit to 0 (active)
            
            status_bytes.append(byte_val)
        
        return status_bytes

    async def _send_status_messages(self, writer):
        """Send periodic status messages."""
        try:
            messages = []
            
            # Send input status
            input_status = self._get_input_status_bytes()
            messages.append(self._build_block_status_message(0x0000, ADDR_EXT_INPUTS, input_status))
            
            # Send area status
            area_status = self._get_area_status_bytes()
            messages.append(self._build_block_status_message(0x0530, ADDR_EXT_OUTPUTS, area_status))
            
            # Send output status
            output_status = self._get_output_status_bytes()
            messages.append(self._build_block_status_message(0x0500, ADDR_EXT_OUTPUTS, output_status))
            
            # Send identification (occasionally)
            if time.time() % 30 < 3:  # Every 30 seconds for 3 seconds
                messages.append(self._build_identification_message())
                messages.append(self._build_ascii_message("Telenot complex400 Simulator"))
            
            # Combine all messages
            combined_payload = b''.join(messages)
            
            # Send as SEND_NDAT telegram
            telegram = self._build_telegram(SEND_NDAT, 0x01, combined_payload)
            writer.write(telegram)
            await writer.drain()
            
            _LOGGER.debug("Sent status messages to client")
            
        except Exception as e:
            _LOGGER.error("Error sending status messages: %s", e)

    async def _simulate_alarm(self, writer):
        """Simulate periodic alarms."""
        try:
            # Simulate alarm on detector group 1
            self.inputs[0]["active"] = True
            
            # Send state change message
            state_change = self._build_state_change_message(0x0000, 0x22)  # Burglary alarm
            telegram = self._build_telegram(SEND_NDAT, 0x01, state_change)
            writer.write(telegram)
            await writer.drain()
            
            _LOGGER.info("🚨 Simulated alarm on Meldergruppe 1")
            
            # Reset after 5 seconds
            await asyncio.sleep(5)
            self.inputs[0]["active"] = False
            
            # Send restore message
            state_change = self._build_state_change_message(0x0000, 0xA2)  # Restore (0x22 | 0x80)
            telegram = self._build_telegram(SEND_NDAT, 0x01, state_change)
            writer.write(telegram)
            await writer.drain()
            
            _LOGGER.info("✅ Alarm restored on Meldergruppe 1")
            
        except Exception as e:
            _LOGGER.error("Error simulating alarm: %s", e)

    async def _handle_command(self, telegram: Dict, writer):
        """Handle received command."""
        try:
            if telegram["control"] == SEND_NDAT:
                payload = telegram["payload"]
                if len(payload) >= 2:
                    msg_length = payload[0]
                    msg_type = payload[1]
                    
                    if msg_type == MSG_TYPE_STATE_CHANGE and len(payload) >= 7:
                        # Parse state change command
                        device_area = payload[2]
                        address = (payload[3] << 8) | payload[4]
                        addr_ext = payload[5]
                        command = payload[6]
                        
                        _LOGGER.info("Received command: Address 0x%04X, Command 0x%02X", address, command)
                        
                        # Handle area commands
                        if 0x0530 <= address <= 0x056F:
                            area_num = ((address - 0x0530) // 8) + 1
                            
                            if area_num in self.areas:
                                if command == 0x61:  # Arm away
                                    self.areas[area_num]["state"] = "armed_away"
                                    _LOGGER.info("Area %d armed away", area_num)
                                elif command == 0x62:  # Arm home
                                    self.areas[area_num]["state"] = "armed_home"
                                    _LOGGER.info("Area %d armed home", area_num)
                                elif command == 0xE1:  # Disarm
                                    self.areas[area_num]["state"] = "disarmed"
                                    self.areas[area_num]["alarm"] = False
                                    _LOGGER.info("Area %d disarmed", area_num)
            
            # Send ACK
            ack_telegram = self._build_telegram(CONFIRM_ACK, 0x02, b"")
            writer.write(ack_telegram)
            await writer.drain()
            
        except Exception as e:
            _LOGGER.error("Error handling command: %s", e)

    async def _handle_client(self, reader, writer):
        """Handle client connection."""
        client_addr = writer.get_extra_info('peername')
        _LOGGER.info("Client connected: %s", client_addr)
        
        self.clients.append(writer)
        
        try:
            # Send initial identification
            await asyncio.sleep(1)
            ident_msg = self._build_identification_message()
            telegram = self._build_telegram(SEND_NDAT, 0x01, ident_msg)
            writer.write(telegram)
            await writer.drain()
            
            while True:
                # Check for incoming data
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=0.1)
                    if not data:
                        break
                    
                    # Parse telegram
                    telegram = self._parse_telegram(data)
                    if telegram:
                        await self._handle_command(telegram, writer)
                
                except asyncio.TimeoutError:
                    pass
                
                # Send periodic status messages
                current_time = time.time()
                if current_time - self.last_status_send >= 3:  # Every 3 seconds
                    await self._send_status_messages(writer)
                    self.last_status_send = current_time
                
                # Simulate alarms occasionally
                if current_time - self.last_alarm_simulation >= 30:  # Every 30 seconds
                    await self._simulate_alarm(writer)
                    self.last_alarm_simulation = current_time
                
                await asyncio.sleep(0.1)
                
        except Exception as e:
            _LOGGER.error("Client error: %s", e)
        finally:
            if writer in self.clients:
                self.clients.remove(writer)
            writer.close()
            await writer.wait_closed()
            _LOGGER.info("Client disconnected: %s", client_addr)

    async def start(self):
        """Start the simulator server."""
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        _LOGGER.info("🏭 Telenot Simulator started on %s:%s", addr[0], addr[1])
        _LOGGER.info("📡 Simulating complex400 with:")
        _LOGGER.info("   - 2 Areas (Bereiche)")
        _LOGGER.info("   - 32 Detector Groups (Meldergruppen)")
        _LOGGER.info("   - Various outputs (Relais, Signalgeber)")
        _LOGGER.info("   - Automatic alarm simulation every 30s")
        _LOGGER.info("   - Status updates every 3s")
        
        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        """Stop the simulator."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            _LOGGER.info("Simulator stopped")


async def main():
    """Main function."""
    simulator = TelenotSimulator()
    
    try:
        await simulator.start()
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down simulator...")
        await simulator.stop()


if __name__ == "__main__":
    print("🏭 Telenot complex400 Simulator")
    print("================================")
    print("This simulator provides a realistic Telenot complex400 environment for testing.")
    print("It will run on localhost:8234 and simulate:")
    print("- 2 alarm areas")
    print("- 32 detector groups")
    print("- Various outputs")
    print("- Automatic status updates and alarm simulation")
    print("\nPress Ctrl+C to stop the simulator.")
    print("================================")
    
    asyncio.run(main())
