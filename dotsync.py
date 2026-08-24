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

def apply_first_time():
    if not MANIFEST_PATH.exists():
        print(f"Error: {MANIFEST_PATH} not found.")
        return False
    with open(MANIFEST_PATH, "r") as f:
        mapping = json.load(f)
    for repo_rel_path, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel_path).resolve()
        sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()
        if not repo_file.exists():
            continue
        sys_file.parent.mkdir(parents=True, exist_ok=True)
        if sys_file.exists():
            backup = sys_file.with_suffix(sys_file.suffix + ".backup")
            shutil.copy2(sys_file, backup)
        shutil.copy2(repo_file, sys_file)
    return True

def sync(mode="sync"):
    if not MANIFEST_PATH.exists():
        return False, "manifest.json not found."

    with open(MANIFEST_PATH, "r") as f:
        mapping = json.load(f)

    synced_items = []

    # 1. STAGE (System -> Repo)
    if mode in ["sync", "stage"]:
        for repo_rel, target_raw in mapping.items():
            repo_file = (REPO_DIR / repo_rel).resolve()
            sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()
            
            if sys_file.exists():
                if get_mtime(sys_file) > get_mtime(repo_file):
                    repo_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sys_file, repo_file)
                    
                    if repo_file.suffix == '.plist':
                        run_cmd(["plutil", "-convert", "xml1", str(repo_file)])
                    
                    synced_items.append(f"📝 Staged {sys_file.name}")
        
        if mode == "stage":
            return True, ("\n".join(synced_items) + "\n\nReady for Git review." if synced_items else "NO_CHANGES")

    # 2. PULL (Remote -> Repo)
    if mode in ["sync", "pull"]:
        pull_res = run_cmd(["git", "pull", "--rebase", "--autostash"])
        if pull_res.returncode != 0:
            return False, f"Pull conflict: {pull_res.stderr.strip()}"
        if mode == "pull":
            return True, "✅ Successfully pulled from GitHub."

    # 3. APPLY (Repo -> System)
    if mode in ["sync", "apply"]:
        for repo_rel, target_raw in mapping.items():
            repo_file = (REPO_DIR / repo_rel).resolve()
            sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()
            
            if repo_file.exists():
                if get_mtime(repo_file) > get_mtime(sys_file):
                    sys_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(repo_file, sys_file)
                    synced_items.append(f"⬇️ Applied {sys_file.name} to system")
        
        if mode == "apply":
            return True, ("\n".join(synced_items) if synced_items else "NO_CHANGES")

    # 4. PUBLISH (Repo -> Remote)
    if mode in ["sync", "publish"]:
        status_res = run_cmd(["git", "status", "--porcelain"])
        if status_res.stdout.strip():
            run_cmd(["git", "add", "-A"])
            run_cmd(["git", "commit", "-m", "Auto-sync config update"])
            push_res = run_cmd(["git", "push"])
            if push_res.returncode != 0:
                return False, f"Push failed: {push_res.stderr.strip()}"
            
            if mode == "publish":
                return True, "✅ Changes successfully pushed to GitHub."
            synced_items.append("⬆️ Pushed changes to GitHub.")
        elif mode == "publish":
            return True, "NO_CHANGES"

    if synced_items:
        return True, "\n".join(synced_items)
    return True, "NO_CHANGES"

def setup_hammerspoon():
    hs_app = Path("/Applications/Hammerspoon.app")
    if not hs_app.exists():
        if run_cmd(["which", "brew"]).returncode == 0:
            subprocess.run(["brew", "install", "--cask", "hammerspoon"])

    try:
        rel_path = REPO_DIR.relative_to(Path.home())
        lua_repo_path = f'os.getenv("HOME") .. "/{rel_path}"'
    except ValueError:
        lua_repo_path = f'"{REPO_DIR}"'

    lua_config = f"""
local repoPath = {lua_repo_path}
local syncScript = repoPath .. "/dotsync.py"

-- ==========================================
-- CONFIGURATION
-- ==========================================
local isAutomated = false  -- Set to false for manual 4-step testing. True for full automation.
local testingMode = true   -- If automated, true = every 1 min, false = every 6 hours
-- ==========================================

local dotMenu = hs.menubar.new()
if dotMenu then
    dotMenu:setTitle("DotSync")
end

local function executeSync(mode, loadingText)
    if dotMenu then dotMenu:setTitle(loadingText .. "...") end
    
    hs.task.new(syncScript, function(exitCode, stdOut, stdErr)
        if dotMenu then dotMenu:setTitle("DotSync") end
        
        if exitCode == 0 then
            local output = stdOut:gsub("^%s*(.-)%s*$", "%1")
            if output ~= "NO_CHANGES" and output ~= "" then
                local n = hs.notify.new({{
                    title = "Dotfiles " .. loadingText,
                    informativeText = output
                }})
                n:send()
                hs.timer.doAfter(5, function() n:withdraw() end)
            end
        else
            if dotMenu then dotMenu:setTitle("Sync ⚠️") end
            local n = hs.notify.new({{
                title = "Sync Error",
                informativeText = stdErr or stdOut
            }})
            n:send()
        end
    end, {{mode}}):start()
end

local function runDotSyncStage() executeSync("stage", "Staging") end
local function runDotSyncPublish() executeSync("publish", "Pushing") end
local function runDotSyncPull() executeSync("pull", "Pulling") end
local function runDotSyncApply() executeSync("apply", "Applying") end
local function runDotSyncFull() executeSync("sync", "Syncing") end

if isAutomated then
    if dotMenu then
        dotMenu:setMenu({{
            {{ title = "Sync Now", fn = runDotSyncFull }},
            {{ title = "-", disabled = true }},
            {{ title = "Open Dotfiles Repo", fn = function() hs.execute("open " .. repoPath) end }}
        }})
    end
    
    hs.hotkey.bind({{"alt", "cmd"}}, "S", runDotSyncFull)
    
    if testingMode then
        hs.timer.doEvery(60, runDotSyncFull)
    else
        hs.timer.doEvery(6 * 60 * 60, runDotSyncFull)
    end
    hs.timer.doAfter(5, runDotSyncFull)
else
    if dotMenu then
        dotMenu:setMenu({{
            {{ title = "⬆️ UPLOAD FLOW", disabled = true }},
            {{ title = "Step 1: Stage Changes (System -> Repo)", fn = runDotSyncStage }},
            {{ title = "Step 2: Push to GitHub", fn = runDotSyncPublish }},
            {{ title = "-", disabled = true }},
            {{ title = "⬇️ DOWNLOAD FLOW", disabled = true }},
            {{ title = "Step 3: Pull from GitHub", fn = runDotSyncPull }},
            {{ title = "Step 4: Apply to System (Repo -> System)", fn = runDotSyncApply }},
            {{ title = "-", disabled = true }},
            {{ title = "Open Dotfiles Repo", fn = function() hs.execute("open " .. repoPath) end }}
        }})
    end
end
"""

    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
    process.communicate(lua_config)
    
    print("\n✅ Hammerspoon configuration copied to clipboard!")
    
    hs_config_dir = Path.home() / ".hammerspoon"
    hs_config_dir.mkdir(exist_ok=True)
    init_lua = hs_config_dir / "init.lua"
    if not init_lua.exists():
        init_lua.touch()
    subprocess.run(["open", str(init_lua)])

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if action == "setup":
        apply_first_time()
        setup_hammerspoon()
    elif action in ["sync", "stage", "publish", "pull", "apply"]:
        success, message = sync(action)
        print(message)
        sys.exit(0 if success else 1)