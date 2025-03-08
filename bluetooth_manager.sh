#!/bin/bash

# Function to log messages with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Allow blueutil to run as root
export BLUEUTIL_ALLOW_ROOT=0

# Get detailed Bluetooth device information
bluetooth_info=$(/usr/sbin/system_profiler SPBluetoothDataType)

log_message "Bluetooth info: $bluetooth_info"

connected_section=$(echo "$bluetooth_info" | awk '/Connected:/,/Not Connected:/')
log_message "connected section: $connected_section"

# Check if any Bluetooth devices are connected
connected_devices=$(echo "$connected_section" | grep "Minor Type:")

log_message "connected_devices: $connected_devices"

if [[ -n "$connected_devices" ]]; then
    # There are devices connected, ensure Bluetooth stays on
    log_message "Devices are connected, Bluetooth will remain on. Do nothing !!"
    # /opt/homebrew/bin/blueutil -p 1
else
    # No connected devices, turn off Bluetooth
    log_message "No connected devices, turning Bluetooth off."
    /opt/homebrew/bin/blueutil -p 0
fi



# <script_file_path>/bluetooth_manager.sh >> /logfile.log 2>&1