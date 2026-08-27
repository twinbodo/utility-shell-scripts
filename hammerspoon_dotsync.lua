require("bluetooth")
require("cursor")

local log = hs.logger.new('DotSync', 'debug')

-- ==========================================
-- 0. DDC TOOL SETUP (Auto-detect & Install)
-- ==========================================
local function setupDDCTool()
    local arch = hs.execute("uname -m"):gsub("%s+", "")
    local isAppleSilicon = (arch == "arm64")
    
    local brewPath = isAppleSilicon and "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
    local ddcPath = isAppleSilicon and "/opt/homebrew/bin/m1ddc" or "/usr/local/bin/ddcctl"
    local toolName = isAppleSilicon and "m1ddc" or "ddcctl"

    -- Function to check if file exists
    local function fileExists(path)
        local f = io.open(path, "r")
        if f then io.close(f) return true else return false end
    end

    if not fileExists(ddcPath) then
        log.w(toolName .. " not found at " .. ddcPath .. ". Attempting to install...")
        hs.notify.new({ title = "Installing Display Tool", informativeText = "Installing " .. toolName .. " via Homebrew in the background..." }):send()
        
        -- Run brew install in the background to avoid freezing Hammerspoon
        hs.task.new(brewPath, function(exitCode, stdOut, stdErr)
            if exitCode == 0 then
                hs.notify.new({ title = "Install Complete", informativeText = toolName .. " installed successfully!" }):send()
                log.i(toolName .. " installed successfully.")
            else
                hs.notify.new({ title = "Install Failed", informativeText = "Failed to install " .. toolName .. ". Please install manually." }):send()
                log.e("Failed to install " .. toolName .. ": " .. (stdErr or stdOut))
            end
        end, {"install", toolName}):start()
    end

    return isAppleSilicon, ddcPath
end

local isAppleSilicon, ddcToolPath = setupDDCTool()

-- ==========================================
-- MONITOR SWITCHING BINDS
-- ==========================================

-- Switch Monitor to USB-C (Standard DDC code is 27)
hs.hotkey.bind({"cmd", "shift"}, "1", function()
    if isAppleSilicon then
        hs.execute(ddcToolPath .. " display 1 set input 27")
    else
        hs.execute(ddcToolPath .. " -d 1 -i 27")
    end
    hs.alert.show("Switched to USB-C")
end)

-- Switch Monitor to HDMI (Standard DDC code is 17)
hs.hotkey.bind({"cmd", "shift"}, "2", function()
    if isAppleSilicon then
        hs.execute(ddcToolPath .. " display 1 set input 17")
    else
        hs.execute(ddcToolPath .. " -d 1 -i 17")
    end
    hs.alert.show("Switched to HDMI")
end)

local repoPath = os.getenv("HOME") .. "/work/utility-shell-scripts"
local syncScript = repoPath .. "/dotsync.py"

local dotMenu = hs.menubar.new()

-- Use macOS native vector images for perfect menubar sizing
local iconIdle = hs.image.imageFromName("NSRefreshTemplate")
local iconError = hs.image.imageFromName("NSCaution")

if dotMenu then 
    dotMenu:setIcon(iconIdle) 
    dotMenu:setTitle("") -- Keep title empty when idle
end

local log = hs.logger.new('DotSync', 'debug')

local runDotSyncStage, runDotSyncPublish, runDotSyncPull, runDotSyncApply, runDotSyncFull, runDotSyncLua
local toggleAwakeScript

-- ==========================================
-- 1. NATIVE AWAKE LOGIC
-- ==========================================
local awakeTimer = nil

local function renderMenu()
    if not dotMenu then return end
    
    local isAwakeRunning = awakeTimer ~= nil

    dotMenu:setMenu({
        { title = "Shortcut: Cmd + Option + D", disabled = true },
        { title = "-", disabled = true },
        { title = "Stage Changes", fn = runDotSyncStage },
        { title = "Push to GitHub", fn = runDotSyncPublish },
        { title = "Pull from GitHub", fn = runDotSyncPull },
        { title = "Apply to System", fn = runDotSyncApply },
        { title = "-", disabled = true },
        { title = "Full Sync", fn = runDotSyncFull },
        { title = "Sync Lua Config", fn = runDotSyncLua },
        { title = "-", disabled = true },
        { title = "Keep System Awake", fn = toggleAwakeScript, checked = isAwakeRunning },
        { title = "-", disabled = true },
        { title = "Open Dotfiles Repo", fn = function() hs.execute("open " .. repoPath) end }
    })
end

function toggleAwakeScript()
    if awakeTimer then
        awakeTimer:stop()
        awakeTimer = nil
        
        hs.caffeinate.set("displayIdle", false, true)
        hs.caffeinate.set("systemIdle", false, true)
        
        log.i("Awake mode STOPPED.")
        hs.notify.new({ title = "System Awake", informativeText = "Awake script stopped." }):send()
        renderMenu()
    else
        log.i("Awake mode STARTING...")
        
        hs.caffeinate.set("displayIdle", true, true)
        hs.caffeinate.set("systemIdle", true, true)
        log.d("Native Caffeinate enabled.")
        
        awakeTimer = hs.timer.doEvery(60, function()
            local pt = hs.mouse.absolutePosition()
            hs.mouse.absolutePosition({x = pt.x + 1, y = pt.y})
            hs.timer.usleep(50000) 
            hs.mouse.absolutePosition({x = pt.x, y = pt.y})
            log.d("Mouse wiggled to prevent sleep.")
        end)

        log.i("Awake mode RUNNING successfully.")
        hs.notify.new({ title = "System Awake", informativeText = "System is now kept awake." }):send()
        renderMenu()
    end
end

-- ==========================================
-- 2. SYNC LOGIC
-- ==========================================
local function executeSync(mode, loadingText)
    log.i("Starting sync mode: " .. mode)
    if dotMenu then 
        dotMenu:setIcon(iconIdle)
        dotMenu:setTitle(" " .. loadingText .. "...") -- Shows e.g., " Syncing..." in menubar
    end
    
    hs.task.new(syncScript, function(exitCode, stdOut, stdErr)
        if dotMenu then dotMenu:setTitle("") end -- Clear text when done
        
        if exitCode == 0 then
            if dotMenu then dotMenu:setIcon(iconIdle) end
            local output = stdOut:gsub("^%s*(.-)%s*$", "%1")
            log.i("Sync successful. Output: " .. output)
            
            if output == "CONFIG_UPDATED" then
                hs.notify.new({ title = "DotSync", informativeText = "Lua Config updated! Reloading..." }):send()
                hs.timer.doAfter(2, hs.reload)
            elseif output ~= "NO_CHANGES" and output ~= "" then
                local n = hs.notify.new({ title = "Dotfiles " .. loadingText, informativeText = output })
                n:send()
                hs.timer.doAfter(5, function() n:withdraw() end)
            end
        else
            if dotMenu then dotMenu:setIcon(iconError) end
            local errorMsg = stdErr or stdOut
            log.e("Sync Error (Code " .. exitCode .. "): " .. errorMsg)
            hs.notify.new({ title = "Sync Error", informativeText = errorMsg }):send()
        end
    end, {mode}):start()
end

function runDotSyncStage() executeSync("stage", "Staging") end
function runDotSyncPublish() executeSync("publish", "Pushing") end
function runDotSyncPull() executeSync("pull", "Pulling") end
function runDotSyncApply() executeSync("apply", "Applying") end
function runDotSyncFull() executeSync("sync", "Syncing") end
function runDotSyncLua() executeSync("update_lua", "Updating Lua") end

-- ==========================================
-- 3. THE SPOTLIGHT UI
-- ==========================================
local dotChooser = hs.chooser.new(function(choice)
    if not choice then return end 
    if choice.id == "stage" then runDotSyncStage()
    elseif choice.id == "publish" then runDotSyncPublish()
    elseif choice.id == "pull" then runDotSyncPull()
    elseif choice.id == "apply" then runDotSyncApply()
    elseif choice.id == "full" then runDotSyncFull()
    elseif choice.id == "update_lua" then runDotSyncLua()
    end
end)

dotChooser:choices({
    { text = "1. Stage Changes", subText = "System -> Repo", id = "stage" },
    { text = "2. Push to GitHub", subText = "Repo -> GitHub", id = "publish" },
    { text = "3. Pull from GitHub", subText = "GitHub -> Repo", id = "pull" },
    { text = "4. Apply to System", subText = "Repo -> System", id = "apply" },
    { text = "5. Full Sync", subText = "Automatically do all steps", id = "full" },
    { text = "6. Sync Lua Config", subText = "Update init.lua and Reload", id = "update_lua" }
})

-- ==========================================
-- 4. INITIALIZATION & BINDS
-- ==========================================
renderMenu()

hs.hotkey.bind({"cmd", "alt"}, "D", function()
    dotChooser:show()
end)

hs.urlevent.bind("dotsync", function(eventName, params)
    dotChooser:show()
end)