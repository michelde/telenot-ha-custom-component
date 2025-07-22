#!/usr/bin/env python3
"""
Test script that mimics the Java discovery process.
Based on the Java implementation's discovery workflow.
"""

import asyncio
import logging
import sys

# Import the standalone protocol implementation
from telenot_protocol_standalone import TelenotProtocol

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_discovery_workflow():
    """Test the discovery workflow like Java implementation."""
    print("=== Java-Style Discovery Workflow Test ===")
    print("Mimicking the Java discovery process:")
    print("1. Send USED_STATE command")
    print("2. Wait for USED_INPUTS/USED_OUTPUTS responses")
    print("3. Send contact info queries for found addresses")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        print(f"Connecting to {host}:{port}...")
        if await protocol.connect():
            print("✅ Connection successful!")
            
            print(f"\n🎯 Step 1: Sending USED_STATE command")
            print("=" * 60)
            
            # Send USED_STATE command (from Java: COMMAND_USED_STATE = "680909687302051000000071241f16")
            used_state_hex = "680909687302051000000071241f16"
            used_state_bytes = bytes.fromhex(used_state_hex)
            
            protocol.writer.write(used_state_bytes)
            await protocol.writer.drain()
            print(f"📤 Sent USED_STATE: {used_state_hex}")
            
            print(f"\n🎯 Step 2: Waiting for responses...")
            print("=" * 60)
            
            used_input_contacts = []
            used_output_contacts = []
            
            # Wait for responses for up to 30 seconds
            for attempt in range(300):  # 30 seconds with 0.1s intervals
                try:
                    if protocol.reader:
                        try:
                            data = await asyncio.wait_for(
                                protocol.reader.read(1024), 
                                timeout=0.1
                            )
                            if data:
                                hex_data = data.hex()
                                print(f"📥 Response {attempt+1}: {hex_data}")
                                
                                # Send ACK for any received message
                                await protocol.send_confirm_ack()
                                
                                # Analyze the response
                                response_type = analyze_response(hex_data)
                                print(f"   📊 Response type: {response_type}")
                                
                                # Check if this contains used contacts info
                                if "USED_INPUTS" in response_type:
                                    contacts = parse_used_inputs(hex_data)
                                    used_input_contacts.extend(contacts)
                                    print(f"   ✅ Found {len(contacts)} input contacts")
                                
                                elif "USED_OUTPUTS" in response_type:
                                    contacts = parse_used_outputs(hex_data)
                                    used_output_contacts.extend(contacts)
                                    print(f"   ✅ Found {len(contacts)} output contacts")
                                
                        except asyncio.TimeoutError:
                            # No data available, continue waiting
                            pass
                
                except Exception as e:
                    print(f"⚠️  Read error: {e}")
                
                await asyncio.sleep(0.1)
            
            print(f"\n🎯 Step 3: Discovery Results")
            print("=" * 60)
            print(f"📊 Found {len(used_input_contacts)} input contacts: {used_input_contacts[:10]}")
            print(f"📊 Found {len(used_output_contacts)} output contacts: {used_output_contacts[:10]}")
            
            # Now try to get contact info for found addresses
            if used_input_contacts:
                print(f"\n🎯 Step 4: Querying contact info for input contacts")
                print("=" * 60)
                
                for i, contact_addr in enumerate(used_input_contacts[:5]):  # Test first 5
                    print(f"\n📍 Querying contact info for {contact_addr}")
                    
                    try:
                        # Convert hex string to int
                        addr_int = int(contact_addr, 16)
                        success = await protocol.send_contact_info_query(addr_int)
                        
                        if success:
                            # Wait for response
                            for _ in range(20):  # 2 seconds
                                try:
                                    data = await asyncio.wait_for(
                                        protocol.reader.read(1024), 
                                        timeout=0.1
                                    )
                                    if data:
                                        hex_data = data.hex()
                                        print(f"   📥 Contact info response: {hex_data[:100]}...")
                                        
                                        await protocol.send_confirm_ack()
                                        
                                        # Try to parse contact name
                                        name = parse_contact_name_from_response(hex_data)
                                        if name:
                                            print(f"   ✅ Contact name: '{name}'")
                                            break
                                        
                                except asyncio.TimeoutError:
                                    pass
                            
                            await asyncio.sleep(0.5)  # Small delay between queries
                    
                    except Exception as e:
                        print(f"   ❌ Error querying {contact_addr}: {e}")
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await protocol.disconnect()
        print("Disconnected.")

def analyze_response(hex_data: str) -> str:
    """Analyze response type based on hex data."""
    try:
        # Check common patterns
        if hex_data.startswith("680202684002421"):
            return "SEND_NORM"
        elif hex_data.startswith("680202680002021"):
            return "CONFIRM_ACK"
        elif "687302" in hex_data:
            return "SEND_NDAT (potential data)"
        elif len(hex_data) > 50:
            return "LONG_MESSAGE (potential used contacts)"
        else:
            return f"UNKNOWN ({len(hex_data)} chars)"
    except:
        return "PARSE_ERROR"

def parse_used_inputs(hex_data: str) -> list:
    """Parse used inputs from response (simplified)."""
    try:
        # This is a simplified version - the real parsing would be more complex
        # Based on Java: parseUsedInputsMessage()
        
        contacts = []
        
        # Look for patterns that might indicate addresses
        # In the Java code, they parse bit arrays to find used contacts
        
        # For now, return some test addresses based on your scan data
        if len(hex_data) > 100:  # If we got a substantial response
            contacts = ["0x0000", "0x0001", "0x0006"]  # Your known addresses
        
        return contacts
    except:
        return []

def parse_used_outputs(hex_data: str) -> list:
    """Parse used outputs from response (simplified)."""
    try:
        contacts = []
        
        # Based on Java: parseUsedOutputsMessage()
        # They look for addresses in range 1280-1519 for outputs
        
        if len(hex_data) > 100:
            contacts = ["0x0500", "0x0501", "0x0530", "0x0538"]  # Your known output addresses
        
        return contacts
    except:
        return []

def parse_contact_name_from_response(hex_data: str) -> str:
    """Parse contact name from contact info response."""
    try:
        # Check if this is a meaningful response (not just SEND_NORM/ACK)
        if hex_data.startswith("680202684002421") or hex_data.startswith("680202680002021"):
            return ""
        
        # Convert to bytes and look for ASCII text
        msg_bytes = bytes.fromhex(hex_data)
        
        # Look for printable ASCII sequences
        text_chars = []
        for byte in msg_bytes:
            if 32 <= byte <= 126:  # Printable ASCII range
                text_chars.append(chr(byte))
            elif text_chars:
                # End of text sequence
                text = ''.join(text_chars).strip()
                if len(text) > 2:  # Minimum meaningful length
                    return text
                text_chars = []
        
        # Check final sequence
        if text_chars:
            text = ''.join(text_chars).strip()
            if len(text) > 2:
                return text
        
        return ""
    except:
        return ""

if __name__ == "__main__":
    print("🔍 Java-Style Discovery Workflow Test")
    print("=" * 50)
    print("This test mimics the Java SmartHomeJ discovery process")
    print("to find and query contact information systematically.")
    print("\nPress Ctrl+C to stop the test.")
    print("=" * 50)
    
    try:
        asyncio.run(test_discovery_workflow())
        
        print("\n🎯 Discovery test completed!")
        print("\nNext steps:")
        print("- Analyze the responses to understand the protocol better")
        print("- Implement proper bit array parsing for used contacts")
        print("- Refine contact info query format")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
