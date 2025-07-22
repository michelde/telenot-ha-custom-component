#!/usr/bin/env python3
"""
Test script based on Java SmartHomeJ implementation.
This script mimics the Java approach for getting contact info.
"""

import asyncio
import logging
import sys

# Import the standalone protocol implementation
from telenot_protocol_standalone import TelenotProtocol, MSG_TYPE_ASCII

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_java_style_contact_info():
    """Test contact info queries using Java-style approach."""
    print("=== Java-Style Contact Info Test ===")
    print("Testing Meldebereich 1 (0x0000)")
    print("Expected: Text='Fenster KG', Name='HWR'")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        print(f"Connecting to {host}:{port}...")
        if await protocol.connect():
            print("✅ Connection successful!")
            
            # Test the specific address from your configuration
            address = 0x0000  # Meldebereich 1
            
            print(f"\n🎯 Testing Java-style contact info query for 0x{address:04X}")
            print("=" * 60)
            
            # Send contact info query using Java format
            print("📤 Sending Java-style contact info query...")
            success = await protocol.send_contact_info_query(address)
            
            if success:
                print("✅ Query sent successfully")
                
                # Wait for response
                print("⏳ Waiting for response...")
                found_response = False
                
                for attempt in range(30):  # Try for 30 seconds
                    try:
                        # Read raw data from stream
                        if protocol.reader:
                            # Try to read with timeout
                            try:
                                data = await asyncio.wait_for(
                                    protocol.reader.read(1024), 
                                    timeout=1.0
                                )
                                if data:
                                    hex_data = data.hex()
                                    print(f"📥 Raw response: {hex_data}")
                                    
                                    # Try to parse as contact info message
                                    # Based on Java UsedContactInfoMessage parsing
                                    if len(hex_data) > 24:  # Minimum length check
                                        try:
                                            # Send ACK first
                                            await protocol.send_confirm_ack()
                                            
                                            # Parse the message
                                            name = parse_contact_info_message(hex_data)
                                            if name:
                                                print(f"✅ Contact name found: '{name}'")
                                                found_response = True
                                                break
                                            else:
                                                print("⚪ No name in response")
                                        except Exception as parse_error:
                                            print(f"⚠️  Parse error: {parse_error}")
                                    
                            except asyncio.TimeoutError:
                                # No data available, continue waiting
                                pass
                    
                    except Exception as e:
                        print(f"⚠️  Read error: {e}")
                    
                    await asyncio.sleep(0.1)
                
                if not found_response:
                    print("❌ No contact info response received")
                    print("💡 Possible reasons:")
                    print("   - Contact info not available for this address")
                    print("   - Different message format required")
                    print("   - System not configured for text queries")
            else:
                print("❌ Failed to send query")
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await protocol.disconnect()
        print("Disconnected.")

def parse_contact_info_message(hex_msg: str) -> str:
    """Parse contact info message based on Java implementation."""
    try:
        print(f"🔍 Analyzing message: {hex_msg[:100]}...")
        
        # Convert hex to bytes
        msg_bytes = bytes.fromhex(hex_msg)
        
        # Check if this is a SEND_NORM response (68020268400242166)
        if hex_msg.startswith("680202684002421"):
            print("   ⚪ SEND_NORM response - no contact info")
            return ""
        
        # Check if this is an ACK response
        if hex_msg.startswith("680202680002021"):
            print("   ⚪ ACK response - no contact info")
            return ""
        
        # Look for actual data messages (different pattern)
        if len(hex_msg) > 20:
            # Try to identify message structure
            print(f"   📊 Message length: {len(hex_msg)} chars ({len(msg_bytes)} bytes)")
            print(f"   📊 First 20 bytes: {' '.join(f'{b:02x}' for b in msg_bytes[:20])}")
            
            # Check for specific patterns that might contain text
            # Based on Java: msg.substring(20 + stateMsgLength, 20 + stateMsgLength + nameMsgLength)
            
            # Try Java-style parsing
            if len(hex_msg) >= 24:  # Minimum for Java parsing
                try:
                    # Java: String stringLen = msg.substring(12, 14);
                    if len(hex_msg) > 14:
                        string_len_hex = hex_msg[12:14]
                        state_msg_length = int(string_len_hex, 16) * 2
                        print(f"   📊 State msg length: {state_msg_length}")
                        
                        # Java: stringLen = msg.substring(16 + stateMsgLength, 16 + stateMsgLength + 2);
                        name_len_pos = 16 + state_msg_length
                        if len(hex_msg) > name_len_pos + 2:
                            name_len_hex = hex_msg[name_len_pos:name_len_pos + 2]
                            name_msg_length = int(name_len_hex, 16) * 2
                            print(f"   📊 Name msg length: {name_msg_length}")
                            
                            # Java: String contactNameHex = msg.substring(20 + stateMsgLength, 20 + stateMsgLength + nameMsgLength);
                            contact_start = 20 + state_msg_length
                            contact_end = contact_start + name_msg_length
                            
                            if len(hex_msg) >= contact_end:
                                contact_name_hex = hex_msg[contact_start:contact_end]
                                print(f"   📊 Contact name hex: {contact_name_hex}")
                                
                                # Convert hex to text with multiple encoding attempts
                                if contact_name_hex:
                                    contact_bytes = bytes.fromhex(contact_name_hex)
                                    
                                    # Try different encodings for German text (Windows-1252 first for ü)
                                    encodings = ['ascii', 'windows-1252', 'iso-8859-1', 'utf-8']
                                    
                                    for encoding in encodings:
                                        try:
                                            contact_name = contact_bytes.decode(encoding).strip('\x00 ')
                                            if contact_name and len(contact_name.strip()) > 0:
                                                print(f"   ✅ Decoded name with {encoding}: '{contact_name}'")
                                                return contact_name
                                        except UnicodeDecodeError:
                                            continue
                                    
                                    # If all encodings fail, show hex for debugging
                                    print(f"   ⚠️  Failed to decode hex with any encoding: {contact_name_hex}")
                                    print(f"   📊 Raw bytes: {[hex(b) for b in contact_bytes]}")
                except Exception as e:
                    print(f"   ⚠️  Java-style parsing failed: {e}")
        
        # Fallback: Look for any printable ASCII sequences
        print("   🔄 Trying fallback ASCII extraction...")
        text_chars = []
        for i, byte in enumerate(msg_bytes):
            if 32 <= byte <= 126:  # Printable ASCII range
                text_chars.append(chr(byte))
            elif text_chars:
                # End of text sequence
                text = ''.join(text_chars).strip()
                if len(text) > 2:  # Minimum meaningful length
                    print(f"   📝 Found ASCII at pos {i-len(text)}: '{text}'")
                    return text
                text_chars = []
        
        # Check final sequence
        if text_chars:
            text = ''.join(text_chars).strip()
            if len(text) > 2:
                print(f"   📝 Found final ASCII: '{text}'")
                return text
        
        print("   ❌ No readable text found")
        return ""
        
    except Exception as e:
        print(f"   ❌ Parse error: {e}")
        return ""

async def test_multiple_addresses():
    """Test multiple addresses to find working ones."""
    print("\n=== Testing Multiple Addresses ===")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        if await protocol.connect():
            print("✅ Connected for multi-address test")
            
            # Test various addresses that might have names
            test_addresses = [
                0x0000,  # Your specific address
                0x0001,  # Next address
                0x0006,  # Active address from scan
                0x00B2,  # Bedienteil
            ]
            
            for addr in test_addresses:
                print(f"\n🔍 Testing address 0x{addr:04X}")
                
                try:
                    success = await protocol.send_contact_info_query(addr)
                    if success:
                        # Wait for response
                        for _ in range(10):
                            try:
                                data = await asyncio.wait_for(
                                    protocol.reader.read(1024), 
                                    timeout=0.5
                                )
                                if data:
                                    hex_data = data.hex()
                                    print(f"   📥 Response: {hex_data[:50]}...")
                                    
                                    await protocol.send_confirm_ack()
                                    
                                    name = parse_contact_info_message(hex_data)
                                    if name:
                                        print(f"   ✅ Found: '{name}'")
                                        break
                                    
                            except asyncio.TimeoutError:
                                break
                        else:
                            print(f"   ⚪ No response")
                    
                    await asyncio.sleep(1)  # Delay between queries
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    
        await protocol.disconnect()
        
    except Exception as e:
        print(f"❌ Multi-address test error: {e}")

if __name__ == "__main__":
    print("🔍 Java-Style Telenot Contact Info Test")
    print("=" * 50)
    print("This test mimics the Java SmartHomeJ implementation")
    print("for querying contact information from Telenot systems.")
    print("\nPress Ctrl+C to stop the test.")
    print("=" * 50)
    
    try:
        # Run the Java-style test
        asyncio.run(test_java_style_contact_info())
        
        # Also test multiple addresses
        asyncio.run(test_multiple_addresses())
        
        print("\n🎯 Test completed!")
        print("\nResults analysis:")
        print("- If names were found: Java-style queries work")
        print("- If no names found: May need different approach")
        print("- Check raw response data for clues")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
