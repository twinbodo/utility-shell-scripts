#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import shutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = REPO_DIR / "manifest.json"

def run_cmd(cmd, check=False):
    return subprocess.run(cmd, cwd=REPO_DIR, text=True, capture_output=True, check=check)

def get_mtime(path):
    return path.stat().st_mtime if path.exists() else 0

def get_sys_path(raw_path):
    import getpass
    username = getpass.getuser()
    parsed_path = raw_path.replace("{$User}", username).replace("{$USER}", username).replace("{User}", username)
    if parsed_path.startswith("Users/"):
        parsed_path = "/" + parsed_path
    return Path(os.path.expandvars(os.path.expanduser(parsed_path))).resolve()

def apply_first_time():
    if not MANIFEST_PATH.exists(): return False
    with open(MANIFEST_PATH, "r") as f: mapping = json.load(f)
    for repo_rel_path, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel_path).resolve()
        sys_file = get_sys_path(target_raw)
        if not repo_file.exists(): continue
        sys_file.parent.mkdir(parents=True, exist_ok=True)
        if sys_file.exists(): shutil.copy2(sys_file, sys_file.with_suffix(sys_file.suffix + ".backup"))
        shutil.copy2(repo_file, sys_file)
    return True

def sync(mode="sync"):
    if not MANIFEST_PATH.exists(): return False, "manifest.json not found."
    with open(MANIFEST_PATH, "r") as f: mapping = json.load(f)
    synced_items = []

    if mode in ["sync", "stage"]:
        for repo_rel, target_raw in mapping.items():
            repo_file = (REPO_DIR / repo_rel).resolve()
            sys_file = get_sys_path(target_raw)
            if sys_file.exists() and get_mtime(sys_file) > get_mtime(repo_file):
                repo_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sys_file, repo_file)
                if repo_file.suffix == '.plist': run_cmd(["plutil", "-convert", "xml1", str(repo_file)])
                synced_items.append(f"📝 Staged {sys_file.name}")
        if mode == "stage": return True, ("\n".join(synced_items) + "\n\nReady for Git review." if synced_items else "NO_CHANGES")

    if mode in ["sync", "pull"]:
        pull_res = run_cmd(["git", "pull", "--rebase", "--autostash"])
        if pull_res.returncode != 0: return False, f"Pull conflict: {pull_res.stderr.strip()}"
        if mode == "pull": return True, "✅ Successfully pulled from GitHub."

    if mode in ["sync", "apply"]:
        for repo_rel, target_raw in mapping.items():
            repo_file = (REPO_DIR / repo_rel).resolve()
            sys_file = get_sys_path(target_raw)
            if repo_file.exists() and get_mtime(repo_file) > get_mtime(sys_file):
                sys_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_file, sys_file)
                synced_items.append(f"⬇️ Applied {sys_file.name} to system")
        if mode == "apply": return True, ("\n".join(synced_items) if synced_items else "NO_CHANGES")

    if mode in ["sync", "publish"]:
        status_res = run_cmd(["git", "status", "--porcelain"])
        if status_res.stdout.strip():
            run_cmd(["git", "add", "-A"])
            run_cmd(["git", "commit", "-m", "Auto-sync config update"])
            if run_cmd(["git", "push"]).returncode != 0: return False, "Push failed."
            if mode == "publish": return True, "✅ Changes successfully pushed to GitHub."
            synced_items.append("⬆️ Pushed changes to GitHub.")
        elif mode == "publish": return True, "NO_CHANGES"

    if synced_items: return True, "\n".join(synced_items)
    return True, "NO_CHANGES"

def get_lua_config():
    """Generates the master Lua string"""
    try:
        rel_path = REPO_DIR.relative_to(Path.home())
        lua_repo_path = f'os.getenv("HOME") .. "/{rel_path}"'
    except ValueError:
        lua_repo_path = f'"{REPO_DIR}"'

    return f"""
require("bluetooth")
require("cursor")
-- Switch Monitor to USB-C (Standard DDC code is 27)
hs.hotkey.bind({{"cmd", "shift"}}, "1", function()
    hs.execute("/opt/homebrew/bin/m1ddc display 1 set input 27")
    hs.alert.show("Switched to USB-C")
end)

-- Switch Monitor to HDMI (Standard DDC code is 17)
hs.hotkey.bind({{"cmd", "shift"}}, "2", function()
    hs.execute("/opt/homebrew/bin/m1ddc display 1 set input 17")
    hs.alert.show("Switched to HDMI")
end)

local repoPath = {lua_repo_path}
local syncScript = repoPath .. "/dotsync.py"

local dotMenu = hs.menubar.new()
if dotMenu then dotMenu:setTitle("🔄") end

local function executeSync(mode, loadingText)
    if dotMenu then dotMenu:setTitle("⏳") end
    hs.task.new(syncScript, function(exitCode, stdOut, stdErr)
        if dotMenu then dotMenu:setTitle("🔄") end
        if exitCode == 0 then
            local output = stdOut:gsub("^%s*(.-)%s*$", "%1")
            
            -- Special handling for Lua updates
            if output == "CONFIG_UPDATED" then
                hs.notify.new({{ title = "DotSync", informativeText = "Lua Config updated! Reloading..." }}):send()
                hs.timer.doAfter(2, hs.reload)
            elseif output ~= "NO_CHANGES" and output ~= "" then
                local n = hs.notify.new({{ title = "Dotfiles " .. loadingText, informativeText = output }})
                n:send()
                hs.timer.doAfter(5, function() n:withdraw() end)
            end
        else
            if dotMenu then dotMenu:setTitle("⚠️") end
            hs.notify.new({{ title = "Sync Error", informativeText = stdErr or stdOut }}):send()
        end
    end, {{mode}}):start()
end

local function runDotSyncStage() executeSync("stage", "Staging") end
local function runDotSyncPublish() executeSync("publish", "Pushing") end
local function runDotSyncPull() executeSync("pull", "Pulling") end
local function runDotSyncApply() executeSync("apply", "Applying") end
local function runDotSyncFull() executeSync("sync", "Syncing") end
local function runDotSyncLua() executeSync("update_lua", "Updating Lua") end

-- 1. THE SPOTLIGHT UI
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

dotChooser:choices({{
    {{ text = "1. Stage Changes", subText = "System -> Repo", id = "stage" }},
    {{ text = "2. Push to GitHub", subText = "Repo -> GitHub", id = "publish" }},
    {{ text = "3. Pull from GitHub", subText = "GitHub -> Repo", id = "pull" }},
    {{ text = "4. Apply to System", subText = "Repo -> System", id = "apply" }},
    {{ text = "5. Full Sync", subText = "Automatically do all steps", id = "full" }},
    {{ text = "6. Sync Lua Config", subText = "Update init.lua and Reload", id = "update_lua" }}
}})

-- 2. THE MENU BAR ICON
if dotMenu then
    dotMenu:setMenu({{
        {{ title = "Shortcut: Cmd + Option + D", disabled = true }},
        {{ title = "-", disabled = true }},
        {{ title = "Stage Changes", fn = runDotSyncStage }},
        {{ title = "Push to GitHub", fn = runDotSyncPublish }},
        {{ title = "Pull from GitHub", fn = runDotSyncPull }},
        {{ title = "Apply to System", fn = runDotSyncApply }},
        {{ title = "-", disabled = true }},
        {{ title = "Full Sync", fn = runDotSyncFull }},
        {{ title = "Sync Lua Config", fn = runDotSyncLua }},
        {{ title = "-", disabled = true }},
        {{ title = "Open Dotfiles Repo", fn = function() hs.execute("open " .. repoPath) end }}
    }})
end

-- 3. THE KEYBOARD SHORTCUT
hs.hotkey.bind({{"cmd", "alt"}}, "D", function()
    dotChooser:show()
end)

-- 4. THE URL LISTENER
hs.urlevent.bind("dotsync", function(eventName, params)
    dotChooser:show()
end)
"""

def update_lua():
    """Checks if the master config is in init.lua. If not, appends it and triggers reload."""
    lua_code = get_lua_config().strip()
    init_lua = Path.home() / ".hammerspoon" / "init.lua"
    
    current_code = ""
    if init_lua.exists():
        current_code = init_lua.read_text()
        
    # 1. Check if this exact configuration block is already inside the file
    if lua_code in current_code:
        return True, "NO_CHANGES"
    
    # 2. If it is NOT present, append it to the bottom of the file
    init_lua.parent.mkdir(parents=True, exist_ok=True)
    with open(init_lua, "a") as f:
        # Add a couple of newlines just in case the previous line didn't end cleanly
        f.write("\n\n-- ==========================================\n")
        f.write("-- DOTSYNC AUTO-GENERATED CONFIG\n")
        f.write("-- ==========================================\n")
        f.write(lua_code + "\n")
        
    return True, "CONFIG_UPDATED"

def setup_hammerspoon():
    lua_config = get_lua_config()
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
    process.communicate(lua_config)
    print("\n✅ Hammerspoon configuration copied to clipboard!")
    subprocess.run(["open", str(Path.home() / ".hammerspoon" / "init.lua")])

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if action == "setup":
        apply_first_time()
        setup_hammerspoon()
    elif action == "update_lua":
        success, message = update_lua()
        print(message)
        sys.exit(0 if success else 1)
    elif action in ["sync", "stage", "publish", "pull", "apply"]:
        success, message = sync(action)
        print(message)
        sys.exit(0 if success else 1)