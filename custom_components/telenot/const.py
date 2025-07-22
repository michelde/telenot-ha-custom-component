"""Constants for the Telenot integration."""

DOMAIN = "telenot"

# Default values
DEFAULT_PORT = 8234
DEFAULT_TIMEOUT = 10
DEFAULT_UPDATE_INTERVAL = 30

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

# Address ranges
ADDR_MASTER_INPUTS = (0x0000, 0x00AF)
ADDR_KEYPADS = (0x00B0, 0x00EF)
ADDR_COMLOCK410_0_7 = (0x00F0, 0x016F)
ADDR_COMSLAVE1 = (0x0170, 0x021F)
ADDR_COMSLAVE2 = (0x0220, 0x02CF)
ADDR_COMSLAVE3 = (0x02D0, 0x037F)
ADDR_MBT = (0x0380, 0x0397)
ADDR_COMLOCK410_8_15 = (0x0398, 0x0417)

ADDR_MASTER_OUTPUTS = (0x0500, 0x052F)
ADDR_AREA_STATUS = (0x0530, 0x056F)
ADDR_ZONE_STATUS = (0x0570, 0x066F)
ADDR_COMLOCK410_OUT_0_7 = (0x0670, 0x06AF)
ADDR_COMSLAVE1_OUT = (0x06B0, 0x06DF)
ADDR_COMSLAVE2_OUT = (0x06E0, 0x070F)
ADDR_COMSLAVE3_OUT = (0x0710, 0x073F)
ADDR_COMLOCK410_OUT_8_15 = (0x0740, 0x077F)

# Area status bit positions
AREA_STATUS_DISARMED = 0
AREA_STATUS_ARM_HOME = 1
AREA_STATUS_ARM_AWAY = 2
AREA_STATUS_ALARM = 3
AREA_STATUS_TROUBLE = 4
AREA_STATUS_ARM_HOME_READY = 5
AREA_STATUS_ARM_AWAY_READY = 6
AREA_STATUS_ALARM_BUZZER = 7

# Device types
DEVICE_TYPES = {
    "master": "Master",
    "keypad": "Bedienteil",
    "comlock410": "comlock410",
    "comslave": "comslave",
    "mbt": "Mobiles Bedienteil",
}
