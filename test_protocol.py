#!/usr/bin/env python3
"""
Test script for Telenot protocol implementation.
This script can be used to test the protocol without Home Assistant.
"""

import asyncio
import logging
import sys
import os
import json
import csv
from datetime import datetime

# Import the standalone protocol implementation
from telenot_protocol_standalone import TelenotProtocol, MSG_TYPE_STATE_CHANGE, MSG_TYPE_BLOCK_STATUS

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_connection():
    """Test basic connection to Telenot system."""
    print("=== Telenot Protocol Test ===")
    
    # Use your actual connection details
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        print(f"Connecting to {host}:{port}...")
        if await protocol.connect():
            print("✅ Connection successful!")
            
            # Test reading messages
            print("\nReading messages for 30 seconds...")
            for i in range(30):  # Read for 30 seconds
                messages = await protocol.read_messages()
                if messages:
                    print(f"📨 Received {len(messages)} messages:")
                    for msg in messages:
                        print(f"  - Type: 0x{msg.get('type', 0):02X}")
                        if msg.get('type') == MSG_TYPE_STATE_CHANGE:
                            print(f"    Address: 0x{msg.get('address', 0):04X}")
                            print(f"    Alarm Type: {msg.get('alarm_type', 'unknown')}")
                            print(f"    Is Alarm: {msg.get('is_alarm', False)}")
                        elif msg.get('type') == MSG_TYPE_BLOCK_STATUS:
                            print(f"    Start Address: 0x{msg.get('start_address', 0):04X}")
                            print(f"    Address Extension: 0x{msg.get('addr_extension', 0):02X}")
                            print(f"    Status Bits: {len(msg.get('status_bits', []))}")
                
                await asyncio.sleep(1)
            
            print("\n✅ Connection test completed successfully!")
            print("Note: Command testing disabled to avoid activating real alarm system.")
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        await protocol.disconnect()
        print("Disconnected.")

async def test_message_parsing():
    """Test message parsing with sample data."""
    print("\n=== Testing Message Parsing ===")
    
    protocol = TelenotProtocol("localhost", 1234)  # Dummy connection
    
    # Test parsing a state change message (example from documentation)
    sample_state_change = bytes([
        0x05, 0x02, 0x01, 0x00, 0x01, 0x01, 0x22  # Alarm message
    ])
    
    messages = protocol._parse_message_data(sample_state_change)
    if messages:
        msg = messages[0]
        print(f"✅ Parsed state change message:")
        print(f"  - Address: 0x{msg.get('address', 0):04X}")
        print(f"  - Alarm Type: {msg.get('alarm_type', 'unknown')}")
        print(f"  - Is Alarm: {msg.get('is_alarm', False)}")
    
    # Test parsing block status
    sample_block_status = bytes([
        0x06, 0x24, 0x00, 0x00, 0x00, 0x01, 0xFF, 0xFF  # Block status
    ])
    
    messages = protocol._parse_message_data(sample_block_status)
    if messages:
        msg = messages[0]
        print(f"✅ Parsed block status message:")
        print(f"  - Start Address: 0x{msg.get('start_address', 0):04X}")
        print(f"  - Status Bits: {len(msg.get('status_bits', []))}")

async def test_read_all_zones():
    """Test reading all zones and detector groups."""
    print("=== Reading All Zones and Detector Groups ===")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        print(f"Connecting to {host}:{port}...")
        if await protocol.connect():
            print("✅ Connection successful!")
            
            # Dictionary to store discovered zones and inputs
            discovered_inputs = {}
            discovered_areas = {}
            discovered_outputs = {}
            
            print("\n📡 Listening for zone and detector group data...")
            print("This will run for 60 seconds to collect comprehensive data...")
            
            for i in range(60):  # Listen for 60 seconds
                messages = await protocol.read_messages()
                
                if messages:
                    print(f"📨 Received {len(messages)} messages at second {i+1}")
                
                for msg in messages:
                    msg_type = msg.get('type')
                    print(f"🔍 Processing message type: 0x{msg_type:02X}")
                    
                    if msg_type == MSG_TYPE_BLOCK_STATUS:
                        start_addr = msg.get('start_address', 0)
                        addr_ext = msg.get('addr_extension', 0)
                        status_bits = msg.get('status_bits', [])
                        
                        if addr_ext == 0x01:  # Inputs
                            for bit_idx, bit_val in enumerate(status_bits):
                                addr = start_addr + bit_idx
                                if addr not in discovered_inputs:
                                    discovered_inputs[addr] = {
                                        'address': addr,
                                        'name': get_input_name(addr),
                                        'type': get_input_type(addr),
                                        'active': bit_val == 0
                                    }
                                else:
                                    discovered_inputs[addr]['active'] = bit_val == 0
                        
                        elif addr_ext == 0x02:  # Outputs
                            for bit_idx, bit_val in enumerate(status_bits):
                                addr = start_addr + bit_idx
                                
                                # Check if this is an area status
                                if 0x0530 <= addr <= 0x056F:
                                    area_num = ((addr - 0x0530) // 8) + 1
                                    bit_pos = (addr - 0x0530) % 8
                                    
                                    if area_num not in discovered_areas:
                                        discovered_areas[area_num] = {
                                            'area': area_num,
                                            'name': f'Bereich {area_num}',
                                            'status_bits': {}
                                        }
                                    
                                    discovered_areas[area_num]['status_bits'][bit_pos] = bit_val == 0
                                
                                else:
                                    if addr not in discovered_outputs:
                                        discovered_outputs[addr] = {
                                            'address': addr,
                                            'name': get_output_name(addr),
                                            'active': bit_val == 0
                                        }
                                    else:
                                        discovered_outputs[addr]['active'] = bit_val == 0
                    
                    elif msg_type == MSG_TYPE_STATE_CHANGE:
                        addr = msg.get('address', 0)
                        alarm_type = msg.get('alarm_type', 'unknown')
                        is_alarm = msg.get('is_alarm', False)
                        
                        print(f"🚨 State Change: Address 0x{addr:04X}, Type: {alarm_type}, Alarm: {is_alarm}")
                
                # Progress indicator
                if i % 10 == 0:
                    print(f"⏱️  Progress: {i}/60 seconds...")
                
                await asyncio.sleep(1)
            
            # Print comprehensive results
            print("\n" + "="*60)
            print("📊 COMPREHENSIVE ZONE AND DETECTOR GROUP REPORT")
            print("="*60)
            
            # Areas/Zones
            if discovered_areas:
                print(f"\n🏠 DISCOVERED AREAS ({len(discovered_areas)}):")
                for area_num, area_data in sorted(discovered_areas.items()):
                    print(f"  Area {area_num}: {area_data['name']}")
                    status_bits = area_data['status_bits']
                    
                    states = []
                    if status_bits.get(0, False):  # Disarmed
                        states.append("Disarmed")
                    if status_bits.get(1, False):  # Armed Home
                        states.append("Armed Home")
                    if status_bits.get(2, False):  # Armed Away
                        states.append("Armed Away")
                    if status_bits.get(3, False):  # Alarm
                        states.append("ALARM")
                    if status_bits.get(4, False):  # Trouble
                        states.append("TROUBLE")
                    
                    print(f"    Status: {', '.join(states) if states else 'Unknown'}")
            
            # Inputs/Detector Groups
            if discovered_inputs:
                print(f"\n🔍 DISCOVERED INPUTS/DETECTOR GROUPS ({len(discovered_inputs)}):")
                
                # Group by type
                input_groups = {}
                for addr, input_data in discovered_inputs.items():
                    input_type = input_data['type']
                    if input_type not in input_groups:
                        input_groups[input_type] = []
                    input_groups[input_type].append((addr, input_data))
                
                for input_type, inputs in input_groups.items():
                    print(f"\n  📍 {input_type.upper()}:")
                    for addr, input_data in sorted(inputs):
                        status = "🟢 ACTIVE" if input_data['active'] else "⚪ Inactive"
                        print(f"    0x{addr:04X} ({addr:4d}): {input_data['name']} - {status}")
            
            # Outputs
            if discovered_outputs:
                print(f"\n🔌 DISCOVERED OUTPUTS ({len(discovered_outputs)}):")
                for addr, output_data in sorted(discovered_outputs.items()):
                    status = "🟢 ACTIVE" if output_data['active'] else "⚪ Inactive"
                    print(f"  0x{addr:04X} ({addr:4d}): {output_data['name']} - {status}")
            
            print("\n" + "="*60)
            print("✅ Zone and detector group scan completed!")
            
            # Export results
            await export_results(discovered_inputs, discovered_areas, discovered_outputs)
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await protocol.disconnect()
        print("Disconnected.")

async def export_results(discovered_inputs, discovered_areas, discovered_outputs):
    """Export scan results to various formats."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("\n📤 EXPORTING RESULTS...")
    
    # 1. Export to JSON
    json_filename = f"telenot_scan_{timestamp}.json"
    json_data = {
        "scan_info": {
            "timestamp": datetime.now().isoformat(),
            "host": "vh-telenot-serial.waldsteg.home",
            "port": 8234,
            "duration_seconds": 60
        },
        "areas": discovered_areas,
        "inputs": discovered_inputs,
        "outputs": discovered_outputs,
        "summary": {
            "total_areas": len(discovered_areas),
            "total_inputs": len(discovered_inputs),
            "total_outputs": len(discovered_outputs),
            "active_inputs": sum(1 for inp in discovered_inputs.values() if inp.get('active', False)),
            "active_outputs": sum(1 for out in discovered_outputs.values() if out.get('active', False))
        }
    }
    
    try:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON export: {json_filename}")
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
    
    # 2. Export inputs to CSV
    csv_inputs_filename = f"telenot_inputs_{timestamp}.csv"
    try:
        with open(csv_inputs_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Address_Hex', 'Address_Dec', 'Name', 'Type', 'Active', 'Status'])
            
            for addr, input_data in sorted(discovered_inputs.items()):
                writer.writerow([
                    f"0x{addr:04X}",
                    addr,
                    input_data['name'],
                    input_data['type'],
                    input_data['active'],
                    "ACTIVE" if input_data['active'] else "Inactive"
                ])
        print(f"✅ Inputs CSV export: {csv_inputs_filename}")
    except Exception as e:
        print(f"❌ Inputs CSV export failed: {e}")
    
    # 3. Export areas to CSV
    csv_areas_filename = f"telenot_areas_{timestamp}.csv"
    try:
        with open(csv_areas_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Area_Number', 'Name', 'Disarmed', 'Armed_Home', 'Armed_Away', 'Alarm', 'Trouble', 'Status_Summary'])
            
            for area_num, area_data in sorted(discovered_areas.items()):
                status_bits = area_data['status_bits']
                states = []
                
                disarmed = status_bits.get(0, False)
                armed_home = status_bits.get(1, False)
                armed_away = status_bits.get(2, False)
                alarm = status_bits.get(3, False)
                trouble = status_bits.get(4, False)
                
                if disarmed:
                    states.append("Disarmed")
                if armed_home:
                    states.append("Armed Home")
                if armed_away:
                    states.append("Armed Away")
                if alarm:
                    states.append("ALARM")
                if trouble:
                    states.append("TROUBLE")
                
                writer.writerow([
                    area_num,
                    area_data['name'],
                    disarmed,
                    armed_home,
                    armed_away,
                    alarm,
                    trouble,
                    ', '.join(states) if states else 'Unknown'
                ])
        print(f"✅ Areas CSV export: {csv_areas_filename}")
    except Exception as e:
        print(f"❌ Areas CSV export failed: {e}")
    
    # 4. Export outputs to CSV
    csv_outputs_filename = f"telenot_outputs_{timestamp}.csv"
    try:
        with open(csv_outputs_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Address_Hex', 'Address_Dec', 'Name', 'Active', 'Status'])
            
            for addr, output_data in sorted(discovered_outputs.items()):
                writer.writerow([
                    f"0x{addr:04X}",
                    addr,
                    output_data['name'],
                    output_data['active'],
                    "ACTIVE" if output_data['active'] else "Inactive"
                ])
        print(f"✅ Outputs CSV export: {csv_outputs_filename}")
    except Exception as e:
        print(f"❌ Outputs CSV export failed: {e}")
    
    # 5. Export filtered data for Home Assistant configuration
    ha_config_filename = f"telenot_ha_config_{timestamp}.json"
    try:
        # Filter for likely relevant components
        relevant_inputs = {}
        for addr, input_data in discovered_inputs.items():
            # Include active inputs and known important types
            if (input_data['active'] or 
                input_data['type'] in ['meldergruppen', 'melderbus'] or
                addr <= 0x001F):  # Always include first 32 detector groups
                relevant_inputs[addr] = input_data
        
        relevant_outputs = {}
        for addr, output_data in discovered_outputs.items():
            # Include master outputs and active outputs
            if addr < 0x0520 or output_data['active']:
                relevant_outputs[addr] = output_data
        
        ha_config = {
            "scan_info": json_data["scan_info"],
            "recommended_for_ha": {
                "areas": discovered_areas,
                "inputs": relevant_inputs,
                "outputs": relevant_outputs
            },
            "filtering_notes": {
                "inputs": "Included active inputs, detector groups (0x0000-0x001F), and detector bus components",
                "outputs": "Included master outputs (0x0500-0x051F) and active outputs",
                "areas": "All discovered areas included"
            }
        }
        
        with open(ha_config_filename, 'w', encoding='utf-8') as f:
            json.dump(ha_config, f, indent=2, ensure_ascii=False)
        print(f"✅ HA Config export: {ha_config_filename}")
    except Exception as e:
        print(f"❌ HA Config export failed: {e}")
    
    # 6. Create summary report
    summary_filename = f"telenot_summary_{timestamp}.txt"
    try:
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write("TELENOT COMPLEX400 SCAN SUMMARY\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Host: vh-telenot-serial.waldsteg.home:8234\n")
            f.write(f"Duration: 60 seconds\n\n")
            
            f.write("SUMMARY STATISTICS:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Total Areas: {len(discovered_areas)}\n")
            f.write(f"Total Inputs: {len(discovered_inputs)}\n")
            f.write(f"Total Outputs: {len(discovered_outputs)}\n")
            f.write(f"Active Inputs: {sum(1 for inp in discovered_inputs.values() if inp.get('active', False))}\n")
            f.write(f"Active Outputs: {sum(1 for out in discovered_outputs.values() if out.get('active', False))}\n\n")
            
            # Input breakdown by type
            f.write("INPUT BREAKDOWN BY TYPE:\n")
            f.write("-" * 25 + "\n")
            input_types = {}
            for input_data in discovered_inputs.values():
                input_type = input_data['type']
                if input_type not in input_types:
                    input_types[input_type] = {'total': 0, 'active': 0}
                input_types[input_type]['total'] += 1
                if input_data['active']:
                    input_types[input_type]['active'] += 1
            
            for input_type, counts in sorted(input_types.items()):
                f.write(f"{input_type.upper()}: {counts['total']} total, {counts['active']} active\n")
            
            f.write(f"\nRECOMMENDATIONS FOR HOME ASSISTANT:\n")
            f.write("-" * 35 + "\n")
            f.write(f"- Configure {len(discovered_areas)} alarm control panels\n")
            f.write(f"- Monitor {len([inp for inp in discovered_inputs.values() if inp['type'] == 'meldergruppen'])} detector groups\n")
            f.write(f"- Consider {len([inp for inp in discovered_inputs.values() if inp['active']])} active inputs for binary sensors\n")
            f.write(f"- Review {len(discovered_outputs)} outputs for switch entities\n")
            
        print(f"✅ Summary report: {summary_filename}")
    except Exception as e:
        print(f"❌ Summary report failed: {e}")
    
    print(f"\n📁 All files exported with timestamp: {timestamp}")
    print("📋 Files created:")
    print(f"   • {json_filename} - Complete data (JSON)")
    print(f"   • {csv_inputs_filename} - Inputs (CSV)")
    print(f"   • {csv_areas_filename} - Areas (CSV)")
    print(f"   • {csv_outputs_filename} - Outputs (CSV)")
    print(f"   • {ha_config_filename} - Filtered for HA (JSON)")
    print(f"   • {summary_filename} - Summary report (TXT)")
    print("\n💡 Use these files to analyze and filter your Telenot configuration!")

def get_input_name(address: int) -> str:
    """Get a human-readable name for an input address."""
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

def get_input_type(address: int) -> str:
    """Get the type category for an input."""
    if 0x0000 <= address <= 0x001F:
        return "meldergruppen"
    elif 0x0028 <= address <= 0x00A6:
        return "melderbus"
    elif 0x00B0 <= address <= 0x00EF:
        return "bedienteile"
    elif 0x00F0 <= address <= 0x016F:
        return "comlock410_0_7"
    elif 0x0170 <= address <= 0x037F:
        return "comslave"
    elif 0x0398 <= address <= 0x0417:
        return "comlock410_8_15"
    else:
        return "unknown"

def get_output_name(address: int) -> str:
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

async def test_raw_messages():
    """Test raw message reception for debugging."""
    print("=== Raw Message Debug Test ===")
    
    host = "vh-telenot-serial.waldsteg.home"
    port = 8234
    
    protocol = TelenotProtocol(host, port)
    
    try:
        print(f"Connecting to {host}:{port}...")
        if await protocol.connect():
            print("✅ Connection successful!")
            
            print("\n🔍 Raw message debugging with protocol logic for 30 seconds...")
            print("This will show the complete protocol exchange...")
            
            for i in range(30):
                try:
                    # Use the full protocol logic
                    messages = await protocol.read_messages()
                    if messages:
                        print(f"\n📨 Protocol exchange completed at second {i+1}:")
                        print(f"   Received {len(messages)} parsed messages:")
                        for msg in messages:
                            print(f"     - Type: 0x{msg.get('type', 0):02X}")
                            if msg.get('type') == 0x24:  # Block status
                                print(f"       Start addr: 0x{msg.get('start_address', 0):04X}")
                                print(f"       Addr ext: 0x{msg.get('addr_extension', 0):02X}")
                                print(f"       Status bits: {len(msg.get('status_bits', []))}")
                                if len(msg.get('status_bits', [])) > 0:
                                    active_bits = [i for i, bit in enumerate(msg.get('status_bits', [])) if bit == 0]
                                    if active_bits:
                                        print(f"       Active addresses: {[hex(msg.get('start_address', 0) + i) for i in active_bits[:10]]}")
                            elif msg.get('type') == 0x02:  # State change
                                print(f"       Address: 0x{msg.get('address', 0):04X}")
                                print(f"       Alarm type: {msg.get('alarm_type', 'unknown')}")
                    else:
                        if i % 5 == 0:
                            print(f"⏱️  No data received at second {i+1}")
                
                except Exception as e:
                    print(f"❌ Error at second {i+1}: {e}")
                    import traceback
                    traceback.print_exc()
                
                await asyncio.sleep(1)
            
            print("\n✅ Raw message debug completed!")
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await protocol.disconnect()
        print("Disconnected.")

if __name__ == "__main__":
    print("Telenot Protocol Test")
    print("1. Connection Test (requires actual Telenot connection)")
    print("2. Message Parsing Test (offline)")
    print("3. Read All Zones and Detector Groups (comprehensive scan)")
    print("4. Raw Message Debug (shows exactly what is received)")
    
    choice = input("Choose test (1, 2, 3, or 4): ").strip()
    
    if choice == "1":
        asyncio.run(test_connection())
    elif choice == "2":
        asyncio.run(test_message_parsing())
    elif choice == "3":
        asyncio.run(test_read_all_zones())
    elif choice == "4":
        asyncio.run(test_raw_messages())
    else:
        print("Invalid choice")
