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

def sync():
    if not MANIFEST_PATH.exists():
        return False, "manifest.json not found."

    with open(MANIFEST_PATH, "r") as f:
        mapping = json.load(f)

    synced_items = []

    # 1. LOCAL -> REPO
    for repo_rel, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel).resolve()
        sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()

        if sys_file.exists():
            if get_mtime(sys_file) > get_mtime(repo_file):
                repo_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sys_file, repo_file)
                synced_items.append(f"⬆️ Pushed {sys_file.name}")

    # 2. GIT PULL
    pull_res = run_cmd(["git", "pull", "--rebase", "--autostash"])
    if pull_res.returncode != 0:
        return False, f"Pull conflict: {pull_res.stderr.strip()}"

    # 3. REPO -> LOCAL
    for repo_rel, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel).resolve()
        sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()

        if repo_file.exists():
            if get_mtime(repo_file) > get_mtime(sys_file):
                sys_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_file, sys_file)
                synced_items.append(f"⬇️ Pulled {sys_file.name}")

    # 4. GIT PUSH
    status_res = run_cmd(["git", "status", "--porcelain"])
    if status_res.stdout.strip():
        run_cmd(["git", "add", "-A"])
        run_cmd(["git", "commit", "-m", "Auto-sync config update"])
        push_res = run_cmd(["git", "push"])
        if push_res.returncode != 0:
            return False, f"Push failed: {push_res.stderr.strip()}"

    if synced_items:
        return True, "\n".join(synced_items)
    return True, "NO_CHANGES"

def setup_hammerspoon():
    lua_config = f"""
local repoPath = "{REPO_DIR}"
local syncScript = repoPath .. "/dotsync.py"

-- CONFIGURATION
local testingMode = false -- Set to false to run every 6 hours instead of every minute

local dotMenu = hs.menubar.new()
dotMenu:setTitle("⚙️")

function runDotSync()
    dotMenu:setTitle("⚙️…")
    hs.task.new(syncScript, function(exitCode, stdOut, stdErr)
        dotMenu:setTitle("⚙️")
        
        if exitCode == 0 then
            local output = stdOut:gsub("^%s*(.-)%s*$", "%1") -- trim whitespace
            
            -- Only notify if actual changes were pushed or pulled
            if output ~= "NO_CHANGES" and output ~= "" then
                local n = hs.notify.new({{
                    title = "Dotfiles Synced",
                    informativeText = output
                }})
                n:send()
                -- Force silent dismissal after 4 seconds
                hs.timer.doAfter(4, function() n:withdraw() end)
            end
        else
            dotMenu:setTitle("⚠️")
            local n = hs.notify.new({{
                title = "Dotfiles Sync Error",
                informativeText = stdErr or stdOut
            }})
            n:send()
        end
    end, {{"sync"}}):start()
end

dotMenu:setMenu({{
    {{ title = "Sync Now", fn = runDotSync }},
    {{ title = "Open Dotfiles Repo", fn = function() hs.execute("open " .. repoPath) end }}
}})

hs.hotkey.bind({{"alt", "cmd"}}, "S", runDotSync)

-- SCHEDULE LOGIC
if testingMode then
    hs.timer.doEvery(60, runDotSync) -- Every 1 minute for testing
else
    hs.timer.doEvery(6 * 60 * 60, runDotSync) -- Every 6 hours for production
end

hs.timer.doAfter(5, runDotSync)
"""

    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
    process.communicate(lua_config)
    print("✅ Hammerspoon configuration copied to clipboard!")
    
    hs_config_dir = Path.home() / ".hammerspoon"
    init_lua = hs_config_dir / "init.lua"
    if not init_lua.exists():
        init_lua.touch()
    subprocess.run(["open", str(init_lua)])

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if action == "setup":
        apply_first_time()
        setup_hammerspoon()
    elif action == "apply":
        apply_first_time()
    elif action == "sync":
        success, message = sync()
        print(message)
        sys.exit(0 if success else 1)