#!/usr/bin/env python3
"""Test script to determine active status of Telenot objects."""

import asyncio
import logging
import sys
import os

# Use the standalone protocol
from telenot_protocol_standalone import TelenotProtocol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)

# Test addresses from your examples
TEST_ADDRESSES = [
    # Your specific examples
    0x028,  # Meldebus 1 Busteilnehmer 1 - PIR KG EMA (should be active)
    0x02D,  # Meldebus 1 Busteilnehmer 6 (should be inactive)
    0x010,  # Meldegruppe 1 - Fenster KG HWR (should be active) 
    0x017,  # Meldegruppe 17 (should be inactive)
    
    # Additional test addresses
    0x000,  # Meldegruppe 1 (alternative address)
    0x006,  # Meldegruppe 7 - known working
    0x00B2, # Bedienteil - known working
]

async def test_object_status():
    """Test reading object status from Telenot system."""
    protocol = TelenotProtocol("vh-telenot-serial.waldsteg.home", 8234)
    
    try:
        # Connect to system
        if not await protocol.connect():
            _LOGGER.error("Failed to connect to Telenot system")
            return
        
        _LOGGER.info("Connected to Telenot system")
        
        # Test each address
        for address in TEST_ADDRESSES:
            _LOGGER.info(f"\n=== Testing address 0x{address:04X} ({address}) ===")
            
            try:
                # Try to query the object name first
                name = await protocol.query_object_name(address)
                if name:
                    _LOGGER.info(f"Name: '{name}'")
                else:
                    _LOGGER.info("No name response")
                
                # Small delay between queries
                await asyncio.sleep(1.0)
                
            except Exception as e:
                _LOGGER.error(f"Error querying address 0x{address:04X}: {e}")
        
        # Now let's try to read some block status messages to understand the structure
        _LOGGER.info("\n=== Reading block status messages ===")
        
        for attempt in range(10):  # Try to read 10 messages
            try:
                messages = await protocol.read_messages()
                for message in messages:
                    _LOGGER.info(f"Received message: {message}")
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                _LOGGER.debug(f"No messages received (attempt {attempt + 1}): {e}")
        
    except Exception as e:
        _LOGGER.error(f"Error during testing: {e}")
    
    finally:
        await protocol.disconnect()
        _LOGGER.info("Disconnected from Telenot system")

async def analyze_block_status():
    """Analyze block status messages to understand active/inactive detection."""
    protocol = TelenotProtocol("vh-telenot-serial.waldsteg.home", 8234)
    
    try:
        if not await protocol.connect():
            _LOGGER.error("Failed to connect")
            return
        
        _LOGGER.info("Analyzing block status messages...")
        
        # Listen for messages for 30 seconds
        start_time = asyncio.get_event_loop().time()
        input_status = {}
        output_status = {}
        
        while (asyncio.get_event_loop().time() - start_time) < 30:
            try:
                messages = await protocol.read_messages()
                
                for message in messages:
                    msg_type = message.get("type")
                    
                    if msg_type == 0x24:  # MSG_TYPE_BLOCK_STATUS
                        start_addr = message.get("start_address", 0)
                        addr_ext = message.get("addr_extension", 0)
                        status_bits = message.get("status_bits", [])
                        
                        _LOGGER.info(f"Block status: start=0x{start_addr:04X}, ext=0x{addr_ext:02X}, bits={len(status_bits)}")
                        
                        # Check if this covers our test addresses
                        for i, bit in enumerate(status_bits):
                            address = start_addr + i
                            
                            if address in TEST_ADDRESSES:
                                if addr_ext == 0x01:  # Inputs
                                    input_status[address] = {
                                        "bit_value": bit,
                                        "interpreted_as_active": bit == 0,  # 0 = active for inputs
                                        "address_hex": f"0x{address:04X}"
                                    }
                                    _LOGGER.info(f"INPUT 0x{address:04X}: bit={bit}, active={bit==0}")
                                
                                elif addr_ext == 0x02:  # Outputs  
                                    output_status[address] = {
                                        "bit_value": bit,
                                        "interpreted_as_active": bit == 0,  # 0 = active for outputs
                                        "address_hex": f"0x{address:04X}"
                                    }
                                    _LOGGER.info(f"OUTPUT 0x{address:04X}: bit={bit}, active={bit==0}")
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                _LOGGER.debug(f"No messages: {e}")
                await asyncio.sleep(0.5)
        
        # Summary
        _LOGGER.info("\n=== SUMMARY ===")
        _LOGGER.info("Input Status:")
        for addr, status in input_status.items():
            _LOGGER.info(f"  0x{addr:04X}: {status}")
        
        _LOGGER.info("Output Status:")
        for addr, status in output_status.items():
            _LOGGER.info(f"  0x{addr:04X}: {status}")
            
    except Exception as e:
        _LOGGER.error(f"Error: {e}")
    
    finally:
        await protocol.disconnect()

async def main():
    """Main test function."""
    _LOGGER.info("Starting Telenot active status detection test")
    _LOGGER.info("Testing addresses:")
    for addr in TEST_ADDRESSES:
        _LOGGER.info(f"  0x{addr:04X} ({addr})")
    
    # First test: Try to query names
    _LOGGER.info("\n" + "="*50)
    _LOGGER.info("PHASE 1: Testing object name queries")
    _LOGGER.info("="*50)
    await test_object_status()
    
    # Second test: Analyze block status
    _LOGGER.info("\n" + "="*50)
    _LOGGER.info("PHASE 2: Analyzing block status messages")
    _LOGGER.info("="*50)
    await analyze_block_status()

if __name__ == "__main__":
    asyncio.run(main())
