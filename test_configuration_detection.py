#!/usr/bin/env python3
"""Test script to detect configured vs unconfigured Telenot objects."""

import asyncio
import logging
from telenot_protocol_standalone import TelenotProtocol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)

# Test addresses based on your examples
TEST_ADDRESSES = {
    # Should be configured/active
    0x028: "Meldebus 1 Busteilnehmer 1 - PIR KG EMA (should be configured)",
    0x010: "Meldegruppe 1 - Fenster KG HWR (should be configured)",
    
    # Should be unconfigured/inactive  
    0x02D: "Meldebus 1 Busteilnehmer 6 (should be unconfigured)",
    0x017: "Meldegruppe 17 (should be unconfigured)",
    
    # Additional test addresses
    0x000: "Meldegruppe 1 (alternative address)",
    0x006: "Meldegruppe 7 - known working",
    0x00B2: "Bedienteil - known working",
}

async def test_configuration_detection():
    """Test different methods to detect if objects are configured."""
    protocol = TelenotProtocol("vh-telenot-serial.waldsteg.home", 8234)
    
    try:
        if not await protocol.connect():
            _LOGGER.error("Failed to connect")
            return
        
        _LOGGER.info("Testing configuration detection methods...")
        
        results = {}
        
        # Method 1: Try to query names (configured objects might respond)
        _LOGGER.info("\n=== METHOD 1: Name Query Test ===")
        for address, description in TEST_ADDRESSES.items():
            _LOGGER.info(f"Testing 0x{address:04X}: {description}")
            
            try:
                name = await protocol.query_object_name(address)
                has_name = name is not None and name.strip() != ""
                results[address] = {"has_name": has_name, "name": name}
                _LOGGER.info(f"  Result: has_name={has_name}, name='{name}'")
            except Exception as e:
                results[address] = {"has_name": False, "name": None, "error": str(e)}
                _LOGGER.info(f"  Result: Error - {e}")
            
            await asyncio.sleep(0.5)
        
        # Method 2: Analyze block status patterns
        _LOGGER.info("\n=== METHOD 2: Block Status Analysis ===")
        
        # Listen for several block status messages
        block_data = {}
        for attempt in range(5):
            try:
                messages = await protocol.read_messages()
                for message in messages:
                    if message.get("type") == 0x24:  # Block status
                        start_addr = message.get("start_address", 0)
                        addr_ext = message.get("addr_extension", 0)
                        status_bits = message.get("status_bits", [])
                        
                        if addr_ext == 0x01:  # Inputs
                            for i, bit in enumerate(status_bits):
                                address = start_addr + i
                                if address in TEST_ADDRESSES:
                                    if address not in block_data:
                                        block_data[address] = []
                                    block_data[address].append(bit)
                
                await asyncio.sleep(2)
            except Exception as e:
                _LOGGER.debug(f"No messages in attempt {attempt + 1}: {e}")
        
        # Analyze block status patterns
        for address in TEST_ADDRESSES:
            if address in block_data:
                bits = block_data[address]
                _LOGGER.info(f"0x{address:04X}: Block status bits over time: {bits}")
                
                # Update results
                if address in results:
                    results[address]["block_bits"] = bits
                    results[address]["consistent_bit"] = len(set(bits)) == 1
                else:
                    results[address] = {"block_bits": bits, "consistent_bit": len(set(bits)) == 1}
        
        # Method 3: Try to trigger a response (if possible)
        _LOGGER.info("\n=== METHOD 3: Response Test ===")
        # This would require specific commands that might trigger responses
        # For now, we'll skip this as it might affect the alarm system
        
        # Summary and analysis
        _LOGGER.info("\n=== ANALYSIS SUMMARY ===")
        for address, description in TEST_ADDRESSES.items():
            _LOGGER.info(f"\n0x{address:04X}: {description}")
            
            if address in results:
                result = results[address]
                _LOGGER.info(f"  Has name: {result.get('has_name', 'Unknown')}")
                if result.get('name'):
                    _LOGGER.info(f"  Name: '{result['name']}'")
                if 'block_bits' in result:
                    _LOGGER.info(f"  Block bits: {result['block_bits']}")
                    _LOGGER.info(f"  Consistent: {result['consistent_bit']}")
                
                # Try to determine if configured
                has_name = result.get('has_name', False)
                has_block_data = 'block_bits' in result
                
                # Heuristic: Objects with names OR that appear in block status are likely configured
                likely_configured = has_name or has_block_data
                _LOGGER.info(f"  LIKELY CONFIGURED: {likely_configured}")
            else:
                _LOGGER.info("  No data collected")
        
        # Final recommendation
        _LOGGER.info("\n=== CONFIGURATION DETECTION STRATEGY ===")
        _LOGGER.info("Based on the analysis, configured objects can be detected by:")
        _LOGGER.info("1. Objects that respond to name queries")
        _LOGGER.info("2. Objects that appear in block status messages")
        _LOGGER.info("3. Objects that have consistent behavior patterns")
        
        configured_addresses = []
        for address, result in results.items():
            if result.get('has_name') or 'block_bits' in result:
                configured_addresses.append(address)
        
        _LOGGER.info(f"Detected configured addresses: {[f'0x{addr:04X}' for addr in sorted(configured_addresses)]}")
        
    except Exception as e:
        _LOGGER.error(f"Error during testing: {e}")
    
    finally:
        await protocol.disconnect()

if __name__ == "__main__":
    asyncio.run(test_configuration_detection())
