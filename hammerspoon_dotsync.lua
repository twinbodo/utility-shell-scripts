require("bluetooth")
require("cursor")

local log = hs.logger.new('DotSync', 'debug')
log.i("DotSync script loading...")

-- ==========================================
-- 0. DDC TOOL SETUP (Auto-detect & Install)
-- ==========================================
local function setupDDCTool()
    local arch = hs.execute("uname -m"):gsub("%s+", "")
    local isAppleSilicon = (arch == "arm64")
    
    local brewPath = isAppleSilicon and "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
    local ddcPath = isAppleSilicon and "/opt/homebrew/bin/m1ddc" or "/usr/local/bin/ddcctl"
    local toolName = isAppleSilicon and "m1ddc" or "ddcctl"

    local function fileExists(path)
        local f = io.open(path, "r")
        if f then io.close(f) return true else return false end
    end

    if not fileExists(ddcPath) then
        log.w(toolName .. " not found at " .. ddcPath .. ". Attempting to install...")
        hs.notify.new({ title = "Installing Display Tool", informativeText = "Installing " .. toolName .. " via Homebrew in the background..." }):send()
        
        hs.task.new(brewPath, function(exitCode, stdOut, stdErr)
            if exitCode == 0 then
                log.i(toolName .. " installed successfully!")
                hs.notify.new({ title = "Install Complete", informativeText = toolName .. " installed successfully!" }):send()
            else
                log.e("Failed to install " .. toolName .. ": " .. tostring(stdErr))
                hs.notify.new({ title = "Install Failed", informativeText = "Failed to install " .. toolName }):send()
            end
        end, {"install", toolName}):start()
    end

    return isAppleSilicon, ddcPath
end

local isAppleSilicon, ddcToolPath = setupDDCTool()

hs.hotkey.bind({"cmd", "shift"}, "1", function()
    hs.execute(isAppleSilicon and (ddcToolPath .. " display 1 set input 27") or (ddcToolPath .. " -d 1 -i 27"))
    hs.alert.show("Switched to USB-C")
end)

hs.hotkey.bind({"cmd", "shift"}, "2", function()
    hs.execute(isAppleSilicon and (ddcToolPath .. " display 1 set input 17") or (ddcToolPath .. " -d 1 -i 17"))
    hs.alert.show("Switched to HDMI")
end)

-- Forward declare our sync functions so the menu can see them
local runDotSyncStage, runDotSyncPublish, runDotSyncPull, runDotSyncApply, runDotSyncFull, runDotSyncLua

-- ==========================================
-- 1. AWAKE LOGIC
-- ==========================================
local awakeStopTimer = nil
local awakeEndTime = 0
local isAwakeUnlimited = false

local function disableAwake()
    log.i("Disabling awake mode.")
    if awakeStopTimer then
        awakeStopTimer:stop()
        awakeStopTimer = nil
    end
    awakeEndTime = 0
    isAwakeUnlimited = false
    hs.caffeinate.set("displayIdle", false, true)
    hs.caffeinate.set("systemIdle", false, true)
    hs.notify.new({title = "System Awake", informativeText = "Awake mode disabled."}):send()
end

local function enableAwake(minutes)
    log.i("Enabling awake mode for: " .. tostring(minutes))
    disableAwake() -- Clean up previous timers if any
    
    hs.caffeinate.set("displayIdle", true, true)
    hs.caffeinate.set("systemIdle", true, true)
    
    if minutes == "unlimited" then
        isAwakeUnlimited = true
        hs.notify.new({title = "System Awake", informativeText = "System will stay awake indefinitely."}):send()
    else
        awakeEndTime = os.time() + (minutes * 60)
        awakeStopTimer = hs.timer.doAfter(minutes * 60, disableAwake)
        hs.notify.new({title = "System Awake", informativeText = "System will stay awake for " .. minutes .. " minutes."}):send()
    end
end

local function promptCustomAwake()
    log.d("Prompting for custom awake duration")
    local button, text = hs.dialog.textPrompt("Custom Awake", "Enter minutes to stay awake (e.g., 45, 90):", "", "Start", "Cancel")
    if button == "Start" and tonumber(text) then
        enableAwake(tonumber(text))
    end
end

local function getAwakeTitle()
    if isAwakeUnlimited then
        return "Keep System Awake (Unlimited)"
    elseif awakeEndTime > 0 then
        local remainingSeconds = awakeEndTime - os.time()
        if remainingSeconds > 0 then
            local remainingMins = math.ceil(remainingSeconds / 60)
            return "Keep System Awake (" .. remainingMins .. "m left)"
        end
    end
    return "Keep System Awake"
end

-- ==========================================
-- 2. MENU UI WITH ERROR CATCHING
-- ==========================================
local repoPath = os.getenv("HOME") .. "/work/utility-shell-scripts"
local syncScript = repoPath .. "/dotsync.py"

local dotMenu = hs.menubar.new()
local iconIdle = hs.image.imageFromName("NSRefreshTemplate")
local iconError = hs.image.imageFromName("NSCaution")

if dotMenu then 
    dotMenu:setIcon(iconIdle) 
    dotMenu:setTitle("") 
    log.d("Menubar item created successfully.")
end

if dotMenu then
    dotMenu:setMenu(function()
        log.d("Menubar clicked! Generating menu dynamically...")
        
        -- Wrap menu generation in a protected call to catch silent errors
        local status, result = pcall(function()
            local isAwakeRunning = isAwakeUnlimited or (awakeEndTime > os.time())
            log.d("Awake Status -> Unlimited: " .. tostring(isAwakeUnlimited) .. " | Running: " .. tostring(isAwakeRunning))

            local awakeSubMenu = {
                { title = "15 min", fn = function() enableAwake(15) end },
                { title = "30 min", fn = function() enableAwake(30) end },
                { title = "60 min", fn = function() enableAwake(60) end },
                { title = "2 hours", fn = function() enableAwake(120) end },
                { title = "4 hours", fn = function() enableAwake(240) end },
                { title = "Unlimited", fn = function() enableAwake("unlimited") end },
                { title = "-", disabled = true },
                { title = "Custom...", fn = promptCustomAwake },
                { title = "-", disabled = true },
                { title = "Disable Awake", fn = disableAwake, disabled = not isAwakeRunning }
            }

            local fullMenu = {
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
                { 
                    title = getAwakeTitle(), 
                    checked = isAwakeRunning, 
                    menu = awakeSubMenu
                },
                { title = "-", disabled = true },
                { title = "Open Dotfiles Repo", fn = function() hs.execute("open " .. repoPath) end }
            }
            log.d("Menu generated without Lua errors.")
            return fullMenu
        end)

        -- If it failed, show the error directly in the menu bar
        if not status then
            log.e("FATAL MENU ERROR: " .. tostring(result))
            return {
                { title = "ERROR BUILDING MENU!", disabled = true },
                { title = tostring(result), disabled = true }
            }
        end
        
        return result
    end)
end

-- ==========================================
-- 3. SYNC LOGIC
-- ==========================================
function executeSync(mode, loadingText)
    log.i("Running Sync Mode: " .. mode)
    if dotMenu then 
        dotMenu:setIcon(iconIdle)
        dotMenu:setTitle(" " .. loadingText .. "...")
    end
    
    hs.task.new(syncScript, function(exitCode, stdOut, stdErr)
        if dotMenu then dotMenu:setTitle("") end
        
        if exitCode == 0 then
            log.i("Sync Success: " .. mode)
            if dotMenu then dotMenu:setIcon(iconIdle) end
            local output = stdOut:gsub("^%s*(.-)%s*$", "%1")
            
            if output == "CONFIG_UPDATED" then
                hs.notify.new({ title = "DotSync", informativeText = "Lua Config updated! Reloading..." }):send()
                hs.timer.doAfter(2, hs.reload)
            elseif output ~= "NO_CHANGES" and output ~= "" then
                local n = hs.notify.new({ title = "Dotfiles " .. loadingText, informativeText = output })
                n:send()
                hs.timer.doAfter(5, function() n:withdraw() end)
            end
        else
            log.e("Sync Error: " .. tostring(stdErr or stdOut))
            if dotMenu then dotMenu:setIcon(iconError) end
            hs.notify.new({ title = "Sync Error", informativeText = stdErr or stdOut }):send()
        end
    end, {mode}):start()
end

runDotSyncStage = function() executeSync("stage", "Staging") end
runDotSyncPublish = function() executeSync("publish", "Pushing") end
runDotSyncPull = function() executeSync("pull", "Pulling") end
runDotSyncApply = function() executeSync("apply", "Applying") end
runDotSyncFull = function() executeSync("sync", "Syncing") end
runDotSyncLua = function() executeSync("update_lua", "Updating Lua") end

-- ==========================================
-- 4. SPOTLIGHT UI & BINDS
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

hs.hotkey.bind({"cmd", "alt"}, "D", function() dotChooser:show() end)
hs.urlevent.bind("dotsync", function(eventName, params) dotChooser:show() end)

log.i("DotSync script successfully loaded.")