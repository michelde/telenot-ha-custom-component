#!/usr/bin/env python3
"""
Test script for ASCII text name queries.
This script tests querying names of individual objects from the Telenot system.
"""

import asyncio
import logging
import sys
import struct

# Import the standalone protocol implementation
from telenot_protocol_standalone import TelenotProtocol, MSG_TYPE_ASCII

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_specific_meldebereich():
    """Test the specific Meldebereich 1 with known text and name."""
    print("=== Testing Specific Meldebereich 1 ===")
    print("Expected Data:")
    print("  - MP Adresse: 0x0000")
    print("  - Bezeichnung: MA-MG-1")
    print("  - Text: Fenster KG")
    print("  - Montageort: HWR")
    print("  - Aktiv: Ja")
    print("  - Sicherungsbereich: 1:B1:")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        print(f"Connecting to {host}:{port}...")
        if await protocol.connect():
            print("✅ Connection successful!")
            
            address = 0x0000  # Meldebereich 1
            
            print(f"\n🎯 Testing Meldebereich 1 (0x{address:04X}) with multiple approaches...")
            print("=" * 60)
            
            # Try different query approaches
            approaches = [
                # Different query types and address extensions
                (0x01, 0x01, "Name query with input extension"),
                (0x01, 0x02, "Name query with output extension"), 
                (0x02, 0x01, "Description query with input extension"),
                (0x02, 0x02, "Description query with output extension"),
                (0x01, 0x73, "Name query with area info extension"),
                (0x02, 0x73, "Description query with area info extension"),
            ]
            
            successful_queries = 0
            
            for query_type, addr_ext, description in approaches:
                print(f"\n📍 {description}")
                print(f"   Query Type: 0x{query_type:02X}, Address Extension: 0x{addr_ext:02X}")
                
                try:
                    # Build custom query
                    query_data = struct.pack(">BHHBB", 
                                           0x00,  # device/area
                                           address >> 8, address & 0xFF,  # address
                                           addr_ext,  # address extension
                                           query_type)  # query type
                    
                    query_msg = struct.pack("BB", len(query_data) + 1, 0x11) + query_data
                    query_telegram = protocol._build_telegram(0x73, 0x01, query_msg)
                    
                    protocol.writer.write(query_telegram)
                    await protocol.writer.drain()
                    print(f"   📤 Query sent")
                    
                    # Wait for response with longer timeout
                    found_response = False
                    for attempt in range(15):  # Try for 15 seconds
                        response = await protocol._read_telegram(timeout=1.0)
                        if response:
                            print(f"   📥 Response received: Control=0x{response['control']:02X}")
                            
                            if response["control"] == 0x73:  # SEND_NDAT
                                await protocol.send_confirm_ack()
                                
                                # Parse response messages
                                messages = protocol._parse_message_data(response["payload"])
                                print(f"   📋 Parsed {len(messages)} messages")
                                
                                for msg in messages:
                                    print(f"      Message type: 0x{msg.get('type', 0):02X}")
                                    if msg.get("type") == MSG_TYPE_ASCII:
                                        text = msg.get("text", "").strip()
                                        if text:
                                            print(f"   ✅ ASCII text found: '{text}'")
                                            successful_queries += 1
                                            found_response = True
                                            break
                                    elif msg.get("type") == 0x11:  # Error response
                                        print(f"   ⚠️  Error response received")
                                    else:
                                        print(f"      Raw data: {msg.get('data', b'').hex()}")
                            
                            elif response["control"] == 0x40:  # SEND_NORM
                                await protocol.send_confirm_ack()
                                print(f"   📤 Sent ACK for SEND_NORM")
                            
                            elif response["control"] == 0x00:  # CONFIRM_ACK
                                print(f"   ✅ Received ACK")
                            
                            if found_response:
                                break
                        
                        await asyncio.sleep(0.1)
                    
                    if not found_response:
                        print(f"   ❌ No ASCII response received")
                
                except Exception as e:
                    print(f"   ❌ Query failed: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Delay between approaches
                await asyncio.sleep(2)
            
            print("\n" + "=" * 60)
            print(f"📊 SPECIFIC TEST SUMMARY:")
            print(f"   Total approaches: {len(approaches)}")
            print(f"   Successful: {successful_queries}")
            print(f"   Expected: Text='Fenster KG' or Name='HWR'")
            
            if successful_queries > 0:
                print("\n✅ Found text data for Meldebereich 1!")
                print("💡 ASCII text queries are working.")
            else:
                print("\n⚠️  No text data found for Meldebereich 1.")
                print("💡 May need different query format or protocol approach.")
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await protocol.disconnect()
        print("Disconnected.")

async def test_name_queries():
    """Test ASCII text name queries for specific objects."""
    print("=== Telenot ASCII Name Query Test ===")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        print(f"Connecting to {host}:{port}...")
        if await protocol.connect():
            print("✅ Connection successful!")
            
            # Focus on the known working address first
            test_addresses = [
                # Known working address
                (0x0000, 0x01, "Meldebereich 1 (Text='Fenster KG', Name='HWR')"),
                
                # Other test addresses
                (0x0001, 0x01, "Meldergruppe 2"), 
                (0x0006, 0x01, "Meldergruppe 7 (aktiv)"),
                
                # Bedienteile
                (0x00B2, 0x01, "Bedienteil 0 Keine Antwort (aktiv)"),
                
                # Bereiche (als Ausgänge)
                (0x0530, 0x02, "Bereich 1 Disarmed"),
                (0x0538, 0x02, "Bereich 2"),
                
                # Aktive Ausgänge
                (0x0500, 0x02, "ÜG TA1 (aktiv)"),
                (0x0501, 0x02, "ÜG TA2 (aktiv)"),
            ]
            
            print(f"\n🔍 Testing name queries for {len(test_addresses)} objects...")
            print("=" * 60)
            
            successful_queries = 0
            
            for address, addr_ext, description in test_addresses:
                print(f"\n📍 Testing: 0x{address:04X} ({description})")
                print(f"   Address Extension: 0x{addr_ext:02X}")
                
                try:
                    # Query the name
                    name = await protocol.query_object_name(address, addr_ext)
                    
                    if name:
                        print(f"   ✅ Name found: '{name}'")
                        successful_queries += 1
                    else:
                        print(f"   ⚪ No name returned")
                        
                        # Try alternative query methods
                        print(f"   🔄 Trying alternative text query...")
                        await protocol.send_text_query(address, 0x01)
                        
                        # Wait a bit and check for any ASCII messages
                        await asyncio.sleep(2)
                        messages = await protocol.read_messages()
                        
                        found_text = False
                        for msg in messages:
                            if msg.get("type") == MSG_TYPE_ASCII:
                                text = msg.get("text", "").strip()
                                if text:
                                    print(f"   ✅ Alternative query found: '{text}'")
                                    successful_queries += 1
                                    found_text = True
                                    break
                        
                        if not found_text:
                            print(f"   ❌ No name available")
                
                except Exception as e:
                    print(f"   ❌ Query failed: {e}")
                
                # Small delay between queries
                await asyncio.sleep(1)
            
            print("\n" + "=" * 60)
            print(f"📊 SUMMARY:")
            print(f"   Total queries: {len(test_addresses)}")
            print(f"   Successful: {successful_queries}")
            print(f"   Failed: {len(test_addresses) - successful_queries}")
            print(f"   Success rate: {(successful_queries/len(test_addresses)*100):.1f}%")
            
            if successful_queries > 0:
                print("\n✅ ASCII text queries are working!")
                print("💡 Names can be read from the Telenot system.")
            else:
                print("\n⚠️  No names were returned.")
                print("💡 Possible reasons:")
                print("   - Names not configured in Telenot programming")
                print("   - Different query format required")
                print("   - ASCII text feature not enabled")
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await protocol.disconnect()
        print("Disconnected.")

async def test_area_names():
    """Test querying area names specifically."""
    print("\n=== Testing Area Names ===")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        if await protocol.connect():
            print("✅ Connected for area name testing")
            
            # Test area addresses from your scan
            areas = [
                (1, 0x0530, "Bereich 1"),
                (2, 0x0538, "Bereich 2"), 
                (3, 0x0540, "Bereich 3"),
                (4, 0x0548, "Bereich 4"),
            ]
            
            for area_num, area_addr, description in areas:
                print(f"\n🏠 Testing {description} (0x{area_addr:04X}):")
                
                # Try different query approaches for areas
                approaches = [
                    (area_addr, 0x02, "Output address"),
                    (area_num, 0x73, "Area info extension"),
                    (area_addr, 0x01, "Input address"),
                ]
                
                for addr, ext, approach_name in approaches:
                    print(f"   🔍 {approach_name}: 0x{addr:04X} ext 0x{ext:02X}")
                    
                    try:
                        name = await protocol.query_object_name(addr, ext)
                        if name:
                            print(f"      ✅ Found: '{name}'")
                            break
                        else:
                            print(f"      ⚪ No response")
                    except Exception as e:
                        print(f"      ❌ Error: {e}")
                    
                    await asyncio.sleep(0.5)
                
                await asyncio.sleep(1)
                
    except Exception as e:
        print(f"❌ Area name test error: {e}")
        
    finally:
        await protocol.disconnect()

if __name__ == "__main__":
    print("🏷️  Telenot ASCII Name Query Test")
    print("=" * 50)
    print("This test will query names for specific objects from your Telenot system.")
    print("Focus: Meldebereich 1 (0x0000) with known Text='Fenster KG', Name='HWR'")
    print("\nPress Ctrl+C to stop the test.")
    print("=" * 50)
    
    try:
        # Run specific test first for the known working address
        asyncio.run(test_specific_meldebereich())
        
        # Then run general tests
        asyncio.run(test_name_queries())
        asyncio.run(test_area_names())
        
        print("\n🎯 Test completed!")
        print("\nNext steps:")
        print("- If names were found: Integration can use ASCII queries")
        print("- If no names found: May need configuration file approach")
        print("- Check Telenot programming for text/name settings")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
