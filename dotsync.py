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
    """First-time setup: Copies files from the Git repo to your system paths."""
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
            print(f"Backed up existing {sys_file} to {backup}")
        shutil.copy2(repo_file, sys_file)
        print(f"Applied Git config: {repo_file.name} -> {sys_file}")
    
    return True

def sync():
    """Two-way sync based on modified timestamps."""
    if not MANIFEST_PATH.exists():
        return False, "manifest.json not found."

    with open(MANIFEST_PATH, "r") as f:
        mapping = json.load(f)

    synced_items = []

    # 1. LOCAL -> REPO (Check if system files are newer)
    for repo_rel, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel).resolve()
        sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()

        if sys_file.exists():
            if get_mtime(sys_file) > get_mtime(repo_file):
                repo_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sys_file, repo_file)
                
                # Convert Apple binary plists to readable XML for GitHub
                if repo_file.suffix == '.plist':
                    run_cmd(["plutil", "-convert", "xml1", str(repo_file)])
                
                synced_items.append(f"⬆️ Pushed {sys_file.name}")

    # 2. GIT PULL (Fetch changes from other Macs)
    pull_res = run_cmd(["git", "pull", "--rebase", "--autostash"])
    if pull_res.returncode != 0:
        return False, f"Pull conflict: {pull_res.stderr.strip()}"

    # 3. REPO -> LOCAL (Check if Git just pulled newer files)
    for repo_rel, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel).resolve()
        sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()

        if repo_file.exists():
            if get_mtime(repo_file) > get_mtime(sys_file):
                sys_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_file, sys_file)
                synced_items.append(f"⬇️ Pulled {sys_file.name}")

    # 4. GIT PUSH (Commit and upload if anything changed locally)
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
    hs_app = Path("/Applications/Hammerspoon.app")
    
    # 1. Install Hammerspoon if not present
    if not hs_app.exists():
        print("Hammerspoon not found. Attempting to install via Homebrew...")
        if run_cmd(["which", "brew"]).returncode != 0:
            print("Error: Homebrew is not installed. Please install Homebrew or manually install Hammerspoon.")
            return False
        subprocess.run(["brew", "install", "--cask", "hammerspoon"])
        print("Hammerspoon installed successfully!")
    else:
        print("Hammerspoon is already installed.")

    # 2. Calculate the repository path relative to the user's home directory dynamically
    try:
        rel_path = REPO_DIR.relative_to(Path.home())
        lua_repo_path = f'os.getenv("HOME") .. "/{rel_path}"'
    except ValueError:
        lua_repo_path = f'"{REPO_DIR}"'

    # 3. Generate the Lua configuration dynamically
    lua_config = f"""
-- Automatically generated Dotfiles Sync Config
local repoPath = {lua_repo_path}
local syncScript = repoPath .. "/dotsync.py"

-- CONFIGURATION
local testingMode = true -- Set to false to run every 6 hours instead of every minute

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

-- Run once on startup
hs.timer.doAfter(5, runDotSync)
"""

    # 4. Copy to macOS clipboard using pbcopy
    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
    process.communicate(lua_config)
    
    print("\n" + "="*50)
    print("✅ Hammerspoon configuration copied to clipboard!")
    print("="*50)
    print("Next steps:")
    print("1. Paste the contents of your clipboard into the init.lua file and save.")
    print("2. Click 'Reload Config' in the Hammerspoon menu.")
    
    # 5. Try to open the config file automatically
    hs_config_dir = Path.home() / ".hammerspoon"
    hs_config_dir.mkdir(exist_ok=True)
    init_lua = hs_config_dir / "init.lua"
    if not init_lua.exists():
        init_lua.touch()
    subprocess.run(["open", str(init_lua)])

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    
    if action == "setup":
        print("Starting setup process...")
        apply_first_time()
        setup_hammerspoon()
    elif action == "apply":
        apply_first_time()
    elif action == "sync":
        success, message = sync()
        print(message)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown command: {action}")
        print("Available commands: setup, apply, sync")