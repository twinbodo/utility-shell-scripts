#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

REPO_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = REPO_DIR / "manifest.json"

def run_cmd(cmd, check=False):
    logger.debug(f"Running command: {' '.join(cmd)}")
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
    if not MANIFEST_PATH.exists():
        logger.error("manifest.json not found.")
        return False
    
    logger.info("Starting first-time setup...")
    with open(MANIFEST_PATH, "r") as f: 
        mapping = json.load(f)
        
    for repo_rel_path, target_raw in mapping.items():
        repo_file = (REPO_DIR / repo_rel_path).resolve()
        sys_file = get_sys_path(target_raw)
        
        if not repo_file.exists(): 
            logger.warning(f"Repository file not found, skipping: {repo_rel_path}")
            continue
            
        sys_file.parent.mkdir(parents=True, exist_ok=True)
        if sys_file.exists(): 
            backup_path = sys_file.with_suffix(sys_file.suffix + ".backup")
            shutil.copy2(sys_file, backup_path)
            logger.info(f"Created backup: {backup_path}")
            
        shutil.copy2(repo_file, sys_file)
        logger.info(f"Applied {repo_file.name} -> {sys_file}")
        
    return True

def sync(mode="sync"):
    if not MANIFEST_PATH.exists(): 
        return False, "manifest.json not found."
        
    logger.info(f"Running sync mode: {mode.upper()}")
    with open(MANIFEST_PATH, "r") as f: 
        mapping = json.load(f)
    synced_items = []

    if mode in ["sync", "stage"]:
        for repo_rel, target_raw in mapping.items():
            repo_file = (REPO_DIR / repo_rel).resolve()
            sys_file = get_sys_path(target_raw)
            if sys_file.exists() and get_mtime(sys_file) > get_mtime(repo_file):
                repo_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sys_file, repo_file)
                if repo_file.suffix == '.plist': 
                    run_cmd(["plutil", "-convert", "xml1", str(repo_file)])
                logger.info(f"Staged {sys_file.name}")
                synced_items.append(f"📝 Staged {sys_file.name}")
        if mode == "stage": 
            return True, ("\n".join(synced_items) + "\n\nReady for Git review." if synced_items else "NO_CHANGES")

    if mode in ["sync", "pull"]:
        logger.info("Pulling latest changes from GitHub...")
        pull_res = run_cmd(["git", "pull", "--rebase", "--autostash"])
        if pull_res.returncode != 0: 
            return False, f"Pull conflict: {pull_res.stderr.strip()}"
        if mode == "pull": 
            return True, "✅ Successfully pulled from GitHub."

    if mode in ["sync", "apply"]:
        for repo_rel, target_raw in mapping.items():
            repo_file = (REPO_DIR / repo_rel).resolve()
            sys_file = get_sys_path(target_raw)
            if repo_file.exists() and get_mtime(repo_file) > get_mtime(sys_file):
                sys_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_file, sys_file)
                logger.info(f"Applied {sys_file.name} to system")
                synced_items.append(f"⬇️ Applied {sys_file.name} to system")
        if mode == "apply": 
            return True, ("\n".join(synced_items) if synced_items else "NO_CHANGES")

    if mode in ["sync", "publish"]:
        status_res = run_cmd(["git", "status", "--porcelain"])
        if status_res.stdout.strip():
            logger.info("Changes detected. Committing and pushing to GitHub...")
            run_cmd(["git", "add", "-A"])
            run_cmd(["git", "commit", "-m", "Auto-sync config update"])
            if run_cmd(["git", "push"]).returncode != 0: 
                return False, "Push failed."
            if mode == "publish": 
                return True, "✅ Changes successfully pushed to GitHub."
            synced_items.append("⬆️ Pushed changes to GitHub.")
        elif mode == "publish": 
            return True, "NO_CHANGES"

    if synced_items: 
        return True, "\n".join(synced_items)
    return True, "NO_CHANGES"

def install_hammerspoon():
    """Checks if Hammerspoon is installed, and installs it if missing."""
    app_path = Path("/Applications/Hammerspoon.app")
    if app_path.exists():
        logger.info("Hammerspoon is already installed at /Applications/Hammerspoon.app")
        return True

    logger.info("Hammerspoon is not installed. Initiating installation...")
    
    # 1. Try installing via Homebrew first
    if shutil.which("brew"):
        logger.info("Homebrew detected. Installing via Homebrew...")
        result = subprocess.run(["brew", "install", "--cask", "hammerspoon"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ Hammerspoon successfully installed via Homebrew.")
            return True
        else:
            logger.warning("Homebrew installation failed. Falling back to direct download...")
    
    # 2. Fallback to direct download using curl and unzip
    logger.info("Downloading the latest Hammerspoon release from GitHub...")
    zip_path = Path("/tmp/Hammerspoon.zip")
    
    curl_result = subprocess.run([
        "curl", "-L", "https://github.com/Hammerspoon/hammerspoon/releases/latest/download/Hammerspoon.zip", "-o", str(zip_path)
    ], capture_output=True)
    
    if curl_result.returncode != 0:
        logger.error("Failed to download Hammerspoon.")
        return False
        
    logger.info("Extracting to /Applications...")
    unzip_result = subprocess.run(["unzip", "-qo", str(zip_path), "-d", "/Applications"], capture_output=True)
    
    # Clean up the downloaded zip file
    if zip_path.exists():
        zip_path.unlink()
        
    if unzip_result.returncode == 0 and app_path.exists():
        logger.info("Removing Apple quarantine attribute so the app can run...")
        subprocess.run(["xattr", "-cr", str(app_path)])
        logger.info("✅ Hammerspoon successfully installed via direct download.")
        return True
    
    logger.error("Installation failed. Please install Hammerspoon manually from https://hammerspoon.org/")
    return False

def get_lua_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lua_file_path = os.path.join(script_dir, "hammerspoon_dotsync.lua")
    
    try:
        with open(lua_file_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        logger.error("hammerspoon_dotsync.lua not found in the repository.")
        return "Error: hammerspoon_dotsync.lua not found in the repository."

def update_lua():
    """Isolates the config in dotsync.lua and safely imports it into init.lua."""
    logger.info("Updating Hammerspoon Lua config...")
    lua_code = get_lua_config().strip()
    if lua_code.startswith("Error:"):
        return False, lua_code

    hs_dir = Path.home() / ".hammerspoon"
    init_lua = hs_dir / "init.lua"
    dotsync_lua = hs_dir / "dotsync.lua"
    
    hs_dir.mkdir(parents=True, exist_ok=True)
    changed = False

    # 1. Ensure dotsync.lua exists and is up to date
    current_dotsync = dotsync_lua.read_text().strip() if dotsync_lua.exists() else ""
    if current_dotsync != lua_code:
        dotsync_lua.write_text(lua_code + "\n")
        logger.info("Wrote new configuration to dotsync.lua")
        changed = True
        
    # 2. Check if init.lua has the require reference, if not append it safely
    import_stmt = 'require("dotsync")'
    current_init = init_lua.read_text() if init_lua.exists() else ""
    
    if import_stmt not in current_init:
        with open(init_lua, "a") as f:
            f.write(f"\n-- Added by DotSync\n{import_stmt}\n")
        logger.info("Added dotsync require statement to init.lua")
        changed = True
        
    if changed:
        return True, "CONFIG_UPDATED"
    return True, "NO_CHANGES"

def setup_hammerspoon():
    logger.info("Setting up Hammerspoon...")
    
    # 1. Install Hammerspoon if missing
    if not install_hammerspoon():
        logger.error("Aborting configuration due to installation failure.")
        return
    
    # 2. Run the automated Lua update which creates dotsync.lua and edits init.lua
    success, message = update_lua()
    
    if success:
        logger.info("✅ Hammerspoon configuration successfully automated!")
    else:
        logger.error(f"Failed to setup Hammerspoon config: {message}")
        
    # 3. Launch Hammerspoon
    logger.info("Launching Hammerspoon application...")
    subprocess.run(["open", "-a", "Hammerspoon"])
    
    # 4. Open init.lua in default editor just for visual confirmation
    init_lua = Path.home() / ".hammerspoon" / "init.lua"
    if init_lua.exists():
        logger.info("Opening init.lua in default editor for your review...")
        subprocess.run(["open", str(init_lua)])

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    
    if action == "setup":
        apply_first_time()
        setup_hammerspoon()
    elif action == "update_lua":
        success, message = update_lua()
        if success:
            logger.info(message)
        else:
            logger.error(message)
        sys.exit(0 if success else 1)
    elif action in ["sync", "stage", "publish", "pull", "apply"]:
        success, message = sync(action)
        if success:
            if message != "NO_CHANGES":
                logger.info(f"Sync Success:\n{message}")
            else:
                logger.info("No changes required.")
        else:
            logger.error(f"Sync Failed: {message}")
        sys.exit(0 if success else 1)