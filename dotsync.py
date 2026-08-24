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
            print(f"Warning: {repo_file} not in repo. Skipping.")
            continue

        sys_file.parent.mkdir(parents=True, exist_ok=True)

        if sys_file.exists():
            backup = sys_file.with_suffix(sys_file.suffix + ".backup")
            shutil.copy2(sys_file, backup)
            print(f"Backed up existing {sys_file} to {backup}")

        # shutil.copy2 preserves timestamps so the sync logic knows they match
        shutil.copy2(repo_file, sys_file)
        print(f"Applied Git config: {repo_file.name} -> {sys_file}")
    
    return True

def sync():
    """Two-way sync based on modified timestamps."""
    if not MANIFEST_PATH.exists():
        return False, "manifest.json not found."

    with open(MANIFEST_PATH, "r") as f:
        mapping = json.load(f)

    # 1. LOCAL -> REPO: Copy any local modifications into the Git repo staging area
    for repo_rel, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel).resolve()
        sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()

        if sys_file.exists():
            sys_mtime = get_mtime(sys_file)
            repo_mtime = get_mtime(repo_file)
            
            # If the system file was modified more recently, stage it for Git
            if sys_mtime > repo_mtime:
                repo_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sys_file, repo_file)
                print(f"Staged local changes: {sys_file.name} -> repo")

    # 2. GIT PULL: Fetch changes from other Macs
    pull_res = run_cmd(["git", "pull", "--rebase", "--autostash"])
    if pull_res.returncode != 0:
        return False, f"Pull conflict: {pull_res.stderr.strip()}"

    # 3. REPO -> LOCAL: If git pull updated files, copy them out to the system
    for repo_rel, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel).resolve()
        sys_file = Path(os.path.expandvars(os.path.expanduser(target_raw))).resolve()

        if repo_file.exists():
            sys_mtime = get_mtime(sys_file)
            repo_mtime = get_mtime(repo_file)
            
            # Git pull updates file timestamps to "now", triggering this copy
            if repo_mtime > sys_mtime:
                sys_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_file, sys_file)
                print(f"Applied remote changes: repo -> {sys_file.name}")

    # 4. GIT PUSH: Commit and upload if anything changed
    status_res = run_cmd(["git", "status", "--porcelain"])
    if status_res.stdout.strip():
        run_cmd(["git", "add", "-A"])
        run_cmd(["git", "commit", "-m", "Auto-sync config update"])
        push_res = run_cmd(["git", "push"])
        if push_res.returncode != 0:
            return False, f"Push failed: {push_res.stderr.strip()}"
        return True, "Synced & pushed local changes."

    return True, "All configurations are up to date."

def setup_hammerspoon():
    hs_app = Path("/Applications/Hammerspoon.app")
    
    if not hs_app.exists():
        print("Hammerspoon not found. Attempting to install via Homebrew...")
        if run_cmd(["which", "brew"]).returncode != 0:
            print("Error: Homebrew is not installed.")
            return False
        subprocess.run(["brew", "install", "--cask", "hammerspoon"])
        print("Hammerspoon installed successfully!")
    else:
        print("Hammerspoon is already installed.")

    lua_config = f"""
-- Automatically generated Dotfiles Sync Config
local repoPath = "{REPO_DIR}"
local syncScript = repoPath .. "/dotsync.py"

local dotMenu = hs.menubar.new()
dotMenu:setTitle("⚙️")

function runDotSync()
    dotMenu:setTitle("⚙️…")
    hs.task.new(syncScript, function(exitCode, stdOut, stdErr)
        if exitCode == 0 then
            dotMenu:setTitle("⚙️")
            hs.notify.new({{title="Dotfiles Sync", informativeText="Configs synced successfully."}}):send()
        else
            dotMenu:setTitle("⚠️")
            hs.notify.new({{title="Dotfiles Sync Failed", informativeText=stdErr or stdOut}}):send()
        end
    end, {{"sync"}}):start()
end

dotMenu:setMenu({{
    {{ title = "Sync Now", fn = runDotSync }},
    {{ title = "Open Dotfiles Repo", fn = function() hs.execute("open " .. repoPath) end }}
}})

hs.hotkey.bind({{"alt", "cmd"}}, "S", runDotSync)

-- TESTING MODE: Runs every 30 seconds
local syncTimer = hs.timer.doEvery(30, runDotSync)

-- PRODUCTION MODE: Uncomment the line below and delete the 30-second timer above to run once daily at 10 AM
-- hs.timer.doAt("10:00", "1d", runDotSync)

hs.timer.doAfter(5, runDotSync)
"""

    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
    process.communicate(lua_config)
    
    print("\n" + "="*50)
    print("✅ Hammerspoon configuration copied to clipboard!")
    print("="*50)
    
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