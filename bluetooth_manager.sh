#!/bin/bash

# Allow blueutil to run as root
export BLUEUTIL_ALLOW_ROOT=1

# Check if any Bluetooth devices are connected
connected_devices=$(/usr/sbin/system_profiler SPBluetoothDataType | grep 'Connected: Yes')

if [ -z "$connected_devices" ]; then
    # No connected devices, turn off Bluetooth
    /opt/homebrew/bin/blueutil -p 0
else
    # Devices are connected, ensure Bluetooth is on
    /opt/homebrew/bin/blueutil -p 1
fi