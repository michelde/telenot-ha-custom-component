# Telenot Integration - Lokale Tests

Sie können die Telenot Integration auf verschiedene Weise lokal testen:

## 1. Protokoll-Test (ohne Home Assistant)

Testen Sie die Protokoll-Implementierung direkt:

```bash
python3 test_protocol.py
```

**Optionen:**
- **Option 1**: Verbindungstest mit echter Telenot-Anlage
- **Option 2**: Offline-Test der Nachrichtenverarbeitung
- **Option 3**: Umfassender Scan aller Meldebereiche und Meldergruppen

### Verbindungstest
Testet die Verbindung zu Ihrer echten Telenot-Anlage:
- Verbindet zu `vh-telenot-serial.waldsteg.home:8234`
- Liest 30 Sekunden lang Nachrichten
- Testet Scharf/Unscharf-Befehle

### Offline-Test
Testet die Nachrichtenverarbeitung ohne Netzwerkverbindung:
- Parst Beispiel-Telegramme
- Überprüft die Protokoll-Implementierung

### 🆕 Umfassender Meldebereiche-Scan
**Neue Funktion**: Detaillierte Analyse aller Meldebereiche und Meldergruppen:
- Läuft 60 Sekunden und sammelt umfassende Daten
- Erkennt automatisch alle aktiven Bereiche
- Listet alle Meldergruppen und deren Status auf
- Kategorisiert Eingänge nach Typ (Meldergruppen, Melderbus, Bedienteile)
- Zeigt Ausgänge und deren Funktion an
- Erstellt einen detaillierten Bericht

**Beispiel-Output:**
```
📊 COMPREHENSIVE ZONE AND DETECTOR GROUP REPORT
============================================================

🏠 DISCOVERED AREAS (2):
  Area 1: Bereich 1
    Status: Disarmed
  Area 2: Bereich 2
    Status: Armed Away, TROUBLE

🔍 DISCOVERED INPUTS/DETECTOR GROUPS (45):

  📍 MELDERGRUPPEN:
    0x0000 (   0): Meldergruppe 1 - 🟢 ACTIVE
    0x0001 (   1): Meldergruppe 2 - ⚪ Inactive
    ...

  📍 MELDERBUS:
    0x0028 (  40): Melderbus Strang 1 Adresse 1 - ⚪ Inactive
    0x0029 (  41): Melderbus Strang 1 Adresse 2 - ⚪ Inactive
    ...

  📍 BEDIENTEILE:
    0x00B0 ( 176): Bedienteil 0 Deckelkontakt BT - ⚪ Inactive
    ...

🔌 DISCOVERED OUTPUTS (16):
  0x0500 (1280): ÜG TA1 - ⚪ Inactive
  0x0501 (1281): ÜG TA2 - ⚪ Inactive
  ...
```

## 2. Simulator (für Entwicklung)

Starten Sie einen Telenot-Simulator für Tests ohne echte Hardware:

```bash
python3 test_simulator.py
```

**Der Simulator:**
- Läuft auf `localhost:8234`
- Simuliert eine complex400 mit 2 Bereichen
- Sendet alle 3 Sekunden Status-Updates
- Simuliert alle 30 Sekunden einen Alarm
- Reagiert auf Scharf/Unscharf-Befehle

### Simulator-Features:
- ✅ Status-Telegramme (Eingänge/Ausgänge)
- ✅ Bereichssteuerung (Scharf/Unscharf)
- ✅ Alarm-Simulation
- ✅ Spontane Meldungen
- ✅ Vollständiges GMS-Protokoll
- ✅ Identifikations-Nachrichten
- ✅ ASCII-Text-Nachrichten

## 3. Home Assistant Integration Test

### Mit echter Telenot-Anlage:

1. Kopieren Sie `custom_components/telenot/` nach Home Assistant
2. Starten Sie Home Assistant neu
3. Fügen Sie die Integration hinzu:
   - Host: `vh-telenot-serial.waldsteg.home`
   - Port: `8234`

### Mit Simulator:

1. Starten Sie den Simulator:
   ```bash
   python3 test_simulator.py
   ```

2. Konfigurieren Sie die Integration:
   - Host: `localhost`
   - Port: `8234`

3. Die Integration sollte automatisch erkennen:
   - 2 Alarmbereiche
   - 32 Meldergruppen
   - Verschiedene Ausgänge

## 4. Debug-Logging aktivieren

Fügen Sie zu Ihrer `configuration.yaml` hinzu:

```yaml
logger:
  default: info
  logs:
    custom_components.telenot: debug
```

## 5. Erwartete Entitäten

Nach erfolgreicher Konfiguration sollten Sie sehen:

### Alarm Control Panels:
- `alarm_control_panel.telenot_bereich_1`
- `alarm_control_panel.telenot_bereich_2`

### Binary Sensors:
- `binary_sensor.telenot_bereich_1_alarm`
- `binary_sensor.telenot_bereich_1_stoerung`
- `binary_sensor.telenot_input_xxxx` (für aktive Eingänge)

### Sensors:
- `sensor.telenot_verbindung`
- `sensor.telenot_bereich_1_status`
- `sensor.telenot_bereich_2_status`

### Switches:
- `switch.telenot_output_xxxx` (für verfügbare Ausgänge)

## 6. Funktionstest

### Alarmsteuerung testen:
1. Öffnen Sie das Alarm Control Panel
2. Testen Sie "Extern scharf", "Intern scharf", "Unscharf"
3. Überprüfen Sie die Logs auf Befehlsübertragung

### Alarm-Simulation (mit Simulator):
1. Warten Sie auf automatische Alarm-Simulation (alle 30s)
2. Oder lösen Sie manuell einen Alarm aus
3. Überprüfen Sie, dass die Sensoren reagieren

## 7. Erweiterte Tests

### 🆕 Vollständiger Meldebereiche-Scan:
```bash
python3 test_protocol.py
# Wählen Sie Option 3
```

Dieser Test:
- Sammelt 60 Sekunden lang alle Daten
- Erstellt eine umfassende Übersicht aller Komponenten
- Zeigt Echtzeitstatus aller Eingänge und Ausgänge
- Kategorisiert alle Komponenten nach Typ
- Perfekt für die Ersteinrichtung und Systemanalyse

### Kombinierte Tests:
```bash
# Terminal 1: Simulator starten
python3 test_simulator.py

# Terminal 2: Umfassenden Scan durchführen
python3 test_protocol.py
# Wählen Sie Option 3, Host: localhost

# Terminal 3: Home Assistant Integration testen
# Host: localhost, Port: 8234
```

## 8. Troubleshooting

### Verbindungsprobleme:
```bash
# Test der TCP-Verbindung
telnet vh-telenot-serial.waldsteg.home 8234
# oder für Simulator:
telnet localhost 8234
```

### Protokoll-Debug:
```bash
# Aktivieren Sie Debug-Logging und überprüfen Sie:
tail -f /config/home-assistant.log | grep telenot
```

### Häufige Probleme:

1. **Keine Verbindung**: 
   - Überprüfen Sie Host/Port
   - Testen Sie mit `telnet`

2. **Keine Entitäten**:
   - Warten Sie 30 Sekunden nach Setup
   - Überprüfen Sie Logs auf Protokollfehler
   - Führen Sie den umfassenden Scan durch (Option 3)

3. **Befehle funktionieren nicht**:
   - Überprüfen Sie, ob ACK-Nachrichten empfangen werden
   - Testen Sie mit dem Simulator

## 9. Systemanalyse-Workflow

**Empfohlener Workflow für neue Installationen:**

1. **Erste Verbindung testen:**
   ```bash
   python3 test_protocol.py  # Option 1
   ```

2. **Umfassende Systemanalyse:**
   ```bash
   python3 test_protocol.py  # Option 3
   ```
   - Lassen Sie den Scan 60 Sekunden laufen
   - Dokumentieren Sie alle gefundenen Komponenten
   - Verwenden Sie den Bericht für die HA-Konfiguration

3. **Simulator-Test:**
   ```bash
   python3 test_simulator.py &
   python3 test_protocol.py  # Option 3, Host: localhost
   ```

4. **Home Assistant Integration:**
   - Verwenden Sie die Erkenntnisse aus der Systemanalyse
   - Konfigurieren Sie die Integration
   - Überprüfen Sie alle erkannten Entitäten

## 10. Nächste Schritte

Nach erfolgreichem Test:

1. **Produktive Nutzung**: Wechseln Sie zur echten Telenot-Anlage
2. **Anpassungen**: Passen Sie Adressbereiche an Ihre Konfiguration an
3. **Erweiterungen**: Implementieren Sie zusätzliche Funktionen
4. **Monitoring**: Überwachen Sie die Logs für Stabilität

Die Integration ist vollständig funktionsfähig und kann sowohl mit dem Simulator als auch mit Ihrer echten Telenot complex400 verwendet werden.
