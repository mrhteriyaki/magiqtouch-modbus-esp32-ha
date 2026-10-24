DOMAIN = "magiqtouch_modbus"

#Config entry data keys (kept as-is for existing entries).
CONF_URL = "HVAC URL"
CONF_ZONES = "Zones"
CONF_EVAP = "Evaporative Unit"
CONF_HEATER = "Heater Unit"

#The ESP32 module only reports and controls zones 1 and 2.
MAX_ZONES = 2

EVENT_FAN_SPEED_CHANGED = "magiqtouch_fan_speed_changed"
