-- =====================================================================
-- Hammerspoon Bluetooth Sleep/Wake Automation
-- =====================================================================

local wasBluetoothOn = false

-- Function to locate or auto-install blueutil
local function getBlueutilPath()
    -- 1. Try finding it dynamically via system PATH
    local output, status = hs.execute("which blueutil")
    if status and output and output ~= "" then
        -- Trim trailing whitespace/newlines
        local path = output:match("^%s*(.-)%s*$")
        if path ~= "" then
            return path
        end
    end

    -- 2. Fallback to standard Homebrew installation paths
    local possiblePaths = {
        "/opt/homebrew/bin/blueutil", -- Apple Silicon Macs
        "/usr/local/bin/blueutil",   -- Intel Macs
        "/usr/bin/blueutil"
    }

    for _, path in ipairs(possiblePaths) do
        if hs.fs.attributes(path) ~= nil then
            return path
        end
    end

    -- 3. If still not found, try installing it via Homebrew automatically
    hs.notify.show("Hammerspoon", "Setup", "blueutil not found. Installing via Homebrew...")
    
    local brewPath = nil
    if hs.fs.attributes("/opt/homebrew/bin/brew") ~= nil then
        brewPath = "/opt/homebrew/bin/brew"
    elseif hs.fs.attributes("/usr/local/bin/brew") ~= nil then
        brewPath = "/usr/local/bin/brew"
    end

    if brewPath then
        hs.execute(brewPath .. " install blueutil")
        -- Re-check after installation
        for _, path in ipairs(possiblePaths) do
            if hs.fs.attributes(path) ~= nil then
                hs.notify.show("Hammerspoon", "Setup Complete", "blueutil installed successfully!")
                return path
            end
        end
    end

    hs.notify.show("Hammerspoon", "Error", "Homebrew is missing. Please install blueutil manually.")
    return nil
end

-- Locate blueutil on load
local blueutilPath = getBlueutilPath()
print("BT Automation: Using blueutil at: " .. tostring(blueutilPath))

-- Main Sleep/Wake Event Handler
local function toggleBluetooth(eventType)
    if not blueutilPath then
        blueutilPath = getBlueutilPath()
        if not blueutilPath then return end
    end

    if eventType == hs.caffeinate.watcher.systemWillSleep then
        print("BT Automation: Mac is going to sleep. Checking Bluetooth...")
        
        local output = hs.execute(blueutilPath .. " -p")
        print("BT Automation: Current status output: " .. tostring(output))
        
        if output and string.match(output, "1") then
            wasBluetoothOn = true
            print("BT Automation: Bluetooth was ON. Turning it OFF for mobile pairing.")
            hs.execute(blueutilPath .. " -p 0")
        else
            wasBluetoothOn = false
            print("BT Automation: Bluetooth was already OFF. Doing nothing.")
        end

    elseif eventType == hs.caffeinate.watcher.systemDidWake then
        print("BT Automation: Mac woke up.")
        if wasBluetoothOn then
            print("BT Automation: Restoring Bluetooth to ON state.")
            hs.execute(blueutilPath .. " -p 1")
        else
            print("BT Automation: Bluetooth was OFF before sleep. Leaving it OFF.")
        end
    end
end

-- Initialize and start the watcher
sleepWatcher = hs.caffeinate.watcher.new(toggleBluetooth)
sleepWatcher:start()
print("BT Automation: Sleep watcher successfully started!")