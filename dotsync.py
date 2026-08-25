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
    # Get the directory where dotsync.py is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the new Lua file in the same repository
    lua_file_path = os.path.join(script_dir, "hammerspoon_dotsync.lua")
    
    try:
        with open(lua_file_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        return "Error: hammerspoon_dotsync.lua not found in the repository."

def update_lua():
    """Isolates the config in dotsync.lua and safely imports it into init.lua."""
    lua_code = get_lua_config().strip()
    hs_dir = Path.home() / ".hammerspoon"
    init_lua = hs_dir / "init.lua"
    dotsync_lua = hs_dir / "dotsync.lua"
    
    hs_dir.mkdir(parents=True, exist_ok=True)
    changed = False

    # 1. Manage the dotsync.lua file safely
    current_dotsync = dotsync_lua.read_text().strip() if dotsync_lua.exists() else ""
    if current_dotsync != lua_code:
        dotsync_lua.write_text(lua_code + "\n")
        changed = True
        
    # 2. Ensure init.lua imports the new file
    # Note: When using require, we leave out the .lua extension[cite: 1]
    import_stmt = 'require("dotsync")'
    current_init = init_lua.read_text() if init_lua.exists() else ""
    
    if import_stmt not in current_init:
        with open(init_lua, "a") as f:
            f.write(f"\n-- Added by DotSync\n{import_stmt}\n")
        changed = True
        
    # Only trigger a reload if a file was actually modified
    if changed:
        return True, "CONFIG_UPDATED"
    return True, "NO_CHANGES"

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