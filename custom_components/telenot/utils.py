"""Utility functions for Telenot integration."""
import re
from typing import Optional


def create_entity_id_from_name(name: str, address: int) -> str:
    """Create a user-friendly entity ID from object name."""
    if not name or name.startswith("Eingang") or name.startswith("Ausgang"):
        # Fallback to address-based ID
        return f"telenot_0x{address:04x}"
    
    # Clean up the name for entity ID
    # Remove special characters and convert to lowercase
    clean_name = re.sub(r'[^\w\s-]', '', name.lower())
    
    # Replace spaces and multiple separators with underscores
    clean_name = re.sub(r'[\s-]+', '_', clean_name)
    
    # Remove leading/trailing underscores
    clean_name = clean_name.strip('_')
    
    # Limit length and ensure it's not empty
    if not clean_name or len(clean_name) < 2:
        return f"telenot_0x{address:04x}"
    
    # Truncate if too long
    if len(clean_name) > 30:
        clean_name = clean_name[:30].rstrip('_')
    
    return f"telenot_{clean_name}"


def create_friendly_name_from_telenot_name(name: str, address: int) -> str:
    """Create a friendly name from Telenot object name."""
    if not name or name.startswith("Eingang") or name.startswith("Ausgang"):
        # Fallback to address-based name
        return f"Telenot 0x{address:04X}"
    
    # Clean up extra spaces but keep the original structure
    clean_name = ' '.join(name.split())
    
    # If it looks like "Text Location" format, use it as is
    if len(clean_name) > 0:
        return clean_name
    
    return f"Telenot 0x{address:04X}"


def parse_telenot_name_parts(name: str) -> tuple[Optional[str], Optional[str]]:
    """Parse Telenot name into text and location parts."""
    if not name:
        return None, None
    
    # Clean up the name
    clean_name = ' '.join(name.split())
    
    # Try to split into text and location
    # Common patterns: "Fenster KG      HWR" -> ("Fenster KG", "HWR")
    parts = clean_name.split()
    
    if len(parts) >= 3:
        # Look for a pattern where the last part might be a location
        # and the first parts are the description
        
        # Simple heuristic: if last part is short (<=4 chars), it might be location
        if len(parts[-1]) <= 4 and len(parts[-1]) >= 2:
            text_parts = parts[:-1]
            location = parts[-1]
            text = ' '.join(text_parts)
            return text, location
    
    # If we can't split meaningfully, return the whole thing as text
    return clean_name, None


# Example usage and test cases
if __name__ == "__main__":
    test_names = [
        ("Fenster KG      HWR", 0x0000),
        ("Fenster KG      Fitness", 0x0001),
        ("Fenster EG      Küche", 0x0006),
        ("Service-Bedient.", 0x00B2),
        ("", 0x0010),
        ("Meldergruppe 1", 0x0000),
    ]
    
    print("Testing entity ID creation:")
    for name, addr in test_names:
        entity_id = create_entity_id_from_name(name, addr)
        friendly_name = create_friendly_name_from_telenot_name(name, addr)
        text, location = parse_telenot_name_parts(name)
        
        print(f"Name: '{name}' (0x{addr:04X})")
        print(f"  Entity ID: {entity_id}")
        print(f"  Friendly: {friendly_name}")
        print(f"  Parsed: text='{text}', location='{location}'")
        print()
