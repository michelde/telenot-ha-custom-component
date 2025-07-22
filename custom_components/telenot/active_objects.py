"""Dynamic active object detection for Telenot integration."""
from typing import Dict, Set, Any
import logging

_LOGGER = logging.getLogger(__name__)

# Object type mapping for better categorization
OBJECT_TYPE_MAPPING: Dict[int, str] = {
    # Meldergruppen (0x0000-0x001F)
    **{i: "meldergruppe" for i in range(0x0000, 0x0020)},
    
    # Melderbus Strang 1 (0x0028-0x0066)
    **{i: "melderbus_1" for i in range(0x0028, 0x0067)},
    
    # Melderbus Strang 2 (0x0068-0x00A6)
    **{i: "melderbus_2" for i in range(0x0068, 0x00A7)},
    
    # Bedienteile (0x00B0-0x00EF)
    **{i: "bedienteil" for i in range(0x00B0, 0x00F0)},
    
    # Master outputs (0x0500-0x050F)
    **{i: "master_output" for i in range(0x0500, 0x0510)},
    
    # Area status outputs (0x0530-0x056F)
    **{i: "area_status" for i in range(0x0530, 0x0570)},
}

def is_active_from_data(address: int, entity_type: str, coordinator_data: Dict[str, Any]) -> bool:
    """Check if an object is active based on coordinator data."""
    if not coordinator_data:
        return False
    
    if entity_type == "input" and "inputs" in coordinator_data:
        input_data = coordinator_data["inputs"].get(address)
        if input_data:
            return input_data.get("active", False)
    
    elif entity_type == "output" and "outputs" in coordinator_data:
        output_data = coordinator_data["outputs"].get(address)
        if output_data:
            return output_data.get("active", False)
    
    return False

def get_active_addresses_from_data(coordinator_data: Dict[str, Any]) -> Dict[str, Set[int]]:
    """Extract active addresses from coordinator data."""
    active_inputs = set()
    active_outputs = set()
    
    if coordinator_data and "inputs" in coordinator_data:
        for address, input_data in coordinator_data["inputs"].items():
            if input_data.get("active", False):
                active_inputs.add(address)
    
    if coordinator_data and "outputs" in coordinator_data:
        for address, output_data in coordinator_data["outputs"].items():
            if output_data.get("active", False):
                active_outputs.add(address)
    
    return {
        "inputs": active_inputs,
        "outputs": active_outputs
    }

def get_discovery_addresses_from_data(coordinator_data: Dict[str, Any]) -> Set[int]:
    """Get all addresses that should be queried for names based on active status."""
    addresses = set()
    
    active_addrs = get_active_addresses_from_data(coordinator_data)
    addresses.update(active_addrs["inputs"])
    addresses.update(active_addrs["outputs"])
    
    # Add some known working addresses for testing
    known_working = {0x0000, 0x0001, 0x0006, 0x00B2}
    addresses.update(known_working)
    
    return addresses

def get_object_type(address: int) -> str:
    """Get the object type for an address."""
    return OBJECT_TYPE_MAPPING.get(address, "unknown")

def should_create_entity(address: int, entity_type: str, coordinator_data: Dict[str, Any]) -> bool:
    """Determine if an entity should be created for this address based on active status."""
    if entity_type == "output":
        # Skip area status outputs (handled by alarm control panel)
        if 0x0530 <= address <= 0x056F:
            return False
    
    return is_active_from_data(address, entity_type, coordinator_data)

def get_active_objects_summary(coordinator_data: Dict[str, Any]) -> Dict[str, int]:
    """Get summary of active objects from coordinator data."""
    active_addrs = get_active_addresses_from_data(coordinator_data)
    
    return {
        "active_inputs": len(active_addrs["inputs"]),
        "active_outputs": len(active_addrs["outputs"]),
        "discovery_addresses": len(get_discovery_addresses_from_data(coordinator_data)),
        "total_active": len(active_addrs["inputs"]) + len(active_addrs["outputs"]),
    }

# Example usage and validation
if __name__ == "__main__":
    print("Telenot Dynamic Active Objects Configuration")
    print("=" * 50)
    
    # Example data structure
    example_data = {
        "inputs": {
            6: {"active": True, "name": "Meldegruppe 7"},
            178: {"active": True, "name": "Bedienteil 0 Keine Antwort"},
            10: {"active": False, "name": "Meldegruppe 11"},
        },
        "outputs": {
            1280: {"active": True, "name": "ÜG TA1"},
            1281: {"active": True, "name": "ÜG TA2"},
            1288: {"active": False, "name": "Relais 1"},
        }
    }
    
    summary = get_active_objects_summary(example_data)
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    active_addrs = get_active_addresses_from_data(example_data)
    
    print("\nActive Input Addresses:")
    for addr in sorted(active_addrs["inputs"]):
        print(f"  0x{addr:04X} ({addr}) - {get_object_type(addr)}")
    
    print("\nActive Output Addresses:")
    for addr in sorted(active_addrs["outputs"]):
        print(f"  0x{addr:04X} ({addr}) - {get_object_type(addr)}")
    
    print("\nDiscovery Addresses:")
    for addr in sorted(get_discovery_addresses_from_data(example_data)):
        print(f"  0x{addr:04X} ({addr}) - {get_object_type(addr)}")
