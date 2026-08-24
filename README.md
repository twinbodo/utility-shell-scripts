# utility-shell-scripts

# Managing Multiple GitHub Accounts on One Machine

This guide explains how to set up, authenticate, and configure Git to use a secondary GitHub account on the same machine without conflicting with your primary account.

## Overview
Git uses **SSH** to authenticate you with GitHub (allowing you to pull/push), and it uses **Git Config** to stamp your commits with your name and email. To successfully use a second account, you must configure **both**.

---

## Step 1: Run the Automated SSH Setup Script

This one-liner script automates the SSH authentication setup. It will:
1. Ask for your secondary GitHub email.
2. Generate a new SSH key specifically for that account.
3. Add the key to your SSH agent.
4. Copy the public key to your clipboard.
5. Create a custom host alias in your `~/.ssh/config` file.

Copy and paste this into your terminal and press **Enter**:

```bash
bash -c 'if ! command -v git &> /dev/null; then echo "git could not be found, please install it first."; exit 1; fi; set -e; set -o pipefail; read -p "Please enter the email for the second github account: " SECOND_EMAIL; if [[ ! "$SECOND_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then echo "Invalid email format: $SECOND_EMAIL"; exit 1; fi; IFS="@" read -r -a parts <<< "$SECOND_EMAIL"; username="${parts[0]}"; if [[ -z "$username" ]]; then echo "Username derived from email is empty."; exit 1; fi; SSH_KEY_FILENAME="id_rsa_github_$username"; echo "SSH_KEY_FILENAME: $SSH_KEY_FILENAME"; if ! command -v ssh-keygen &> /dev/null; then echo "ssh-keygen could not be found."; exit 1; fi; if [[ -f "$HOME/.ssh/${SSH_KEY_FILENAME}" ]]; then echo "SSH key already exists at $HOME/.ssh/${SSH_KEY_FILENAME}."; exit 1; else echo "Generating new SSH key..."; ssh-keygen -t rsa -b 4096 -C "$SECOND_EMAIL" -f "$HOME/.ssh/${SSH_KEY_FILENAME}" -N ""; fi; eval "$(ssh-agent -s)" || { echo "Failed to start ssh-agent"; exit 1; }; ssh-add "$HOME/.ssh/${SSH_KEY_FILENAME}" || { echo "Failed to add SSH key"; exit 1; }; if [[ ! -f "$HOME/.ssh/${SSH_KEY_FILENAME}.pub" ]]; then echo "SSH public key failed to create."; exit 1; fi; echo "Please manually add this SSH public key to your GitHub account:"; cat "$HOME/.ssh/${SSH_KEY_FILENAME}.pub"; if command -v pbcopy &> /dev/null; then cat "$HOME/.ssh/${SSH_KEY_FILENAME}.pub" | pbcopy; echo "(Copied to clipboard)"; else echo "(pbcopy not found; please manually copy)"; fi; mkdir -p "$HOME/.ssh"; if [[ ! -f "$HOME/.ssh/config" ]]; then touch "$HOME/.ssh/config"; chmod 600 "$HOME/.ssh/config"; fi; { echo -e "\nHost github.com-$username"; echo "  HostName github.com"; echo "  User git"; echo "  IdentityFile ~/.ssh/${SSH_KEY_FILENAME}"; } >> "$HOME/.ssh/config"; echo "Configuration complete. Use the github.com-$username host for this account."; read -p "Press enter when done updating GitHub to continue"; echo "Script execution completed successfully."'
```

---

## Step 2: Add the SSH Key to GitHub

The script automatically copies your new public SSH key to your clipboard. 
1. Log in to your **secondary** GitHub account in your browser.
2. Go to **Settings** > **SSH and GPG keys**.
3. Click **New SSH key**.
4. Give it a descriptive title (e.g., "MacBook - Work") and paste the key.

---

## Step 3: Cloning a Repository

To ensure Git uses the correct SSH key for your secondary account, you **must use the custom host alias** created by the script (e.g., `github.com-<username>`) instead of the standard `github.com`.

**Standard Clone Command (DO NOT USE):**
```bash
git clone git@github.com:twinbodo/my-repo.git
```

**Correct Clone Command:**
```bash
git clone git@github.com-twinbodo:twinbodo/my-repo.git
```
*(Replace `twinbodo` with your actual username/alias)*

---

## Step 4: Setting Git Config (Commit Identity)

After cloning the repository, navigate into the project folder. You must tell Git to use your secondary account details for commits in this specific repository. If you skip this, Git will use your primary/global account details.

```bash
cd my-repo
git config user.name "Your Name or Username"
git config user.email "your.second.email@example.com"
```

To verify the setup:
```bash
git config user.name
git config user.email
```
## Troubleshooting: Updating an Existing Repository

If you already cloned a repository but it is trying to use your primary account, you need to update the remote URL and set your local config.

1. **Update the Remote URL:**
   ```bash
   git remote set-url origin git@github.com-<username>:<github-username>/<repo-name>.git
   ```
   *Example:* `git remote set-url origin git@github.com-twinbodo:twinbodo/utility-shell-scripts.git`

2. **Update the Commit Identity:**
   ```bash
   git config user.name "tw"
   git config user.email "tw@tw.com"
   ```

---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# ⚙️ Dotfiles Sync Engine

A decentralized, copy-based automated sync tool for macOS configuration files.

Instead of relying on messy symlinks, this tool uses a two-way sync engine based on file modification timestamps. It automatically stages, commits, pushes, and pulls your configuration files via Git. Background automation, menu bar controls, and silent desktop notifications are handled entirely by [Hammerspoon](https://www.hammerspoon.org/).

## ✨ Features

* **No Symlinks:** Files stay exactly where macOS expects them. The Git repo acts as a transport layer.
* **Intelligent Two-Way Sync:** Automatically detects if a local file is newer than the repo, or if the repo is newer than the local file, and copies accordingly.
* **Fully Automated:** Runs quietly in the background every 6 hours (configurable).
* **Smart Notifications:** Only triggers a silent, auto-dismissing notification when a file is actually pushed or pulled.
* **Dynamic Paths:** Handles user paths automatically across different Macs (e.g., `/Users/username/...`).

---

## 🛠️ Prerequisites

* **macOS** (Tested on multiple Macs)
* **Git** installed and authenticated with GitHub (SSH recommended)
* **Homebrew** (The setup script uses Homebrew to automatically install Hammerspoon if you don't have it).

---

## 🚀 Setup: Mac 1 (The Source)

Run these steps on the Mac that currently holds all your actual configuration files.

1. **Create the repository:**
```bash
mkdir ~/my-dotfiles
cd ~/my-dotfiles
git init
mkdir files

```


2. **Create the configuration files:**
* Create `dotsync.py` and paste the sync script.
* Make it executable: `chmod +x dotsync.py`
* Create `manifest.json` and map the files you want to track (see Manifest section below).


3. **Link to GitHub:**
```bash
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/my-dotfiles.git

```


4. **Run the Initial Sync:**
Because your system files are newer than the empty repository, running `sync` will copy your system configs into the repo and push them to GitHub.
```bash
python3 dotsync.py sync

```


5. **Install & Configure Hammerspoon:**
```bash
python3 dotsync.py setup

```


*This copies the Lua configuration to your clipboard and opens `init.lua`. Paste the contents, save, and click **Reload Config** in the Hammerspoon menu bar.*

---

## 💻 Setup: Mac 2+ (The Destinations)

Run these steps on any new Mac you want to sync your settings to.

1. **Clone the repository:**
```bash
git clone git@github.com:YOUR_USERNAME/my-dotfiles.git ~/my-dotfiles
cd ~/my-dotfiles

```


2. **Run the Setup Command:**
```bash
chmod +x dotsync.py
python3 dotsync.py setup

```


*This will automatically pull the files from the Git repo, back up any existing local configs, overwrite them with your tracked configs, and install Hammerspoon.*
3. **Configure Hammerspoon:**
Paste the configuration that was automatically copied to your clipboard into the opened `init.lua` file, save, and hit **Reload Config** in the menu bar.

---

## 📂 The `manifest.json` File

This file tells the script which files to track and where they belong on the system.

* **Key:** The relative path inside this Git repository (must start with `files/`).
* **Value:** The absolute path on your Mac. You can safely use `~` or `$USER`; the script will expand them automatically based on the current machine.

**Example:**

```json
{
  "files/zshrc": "~/.zshrc",
  "files/com.googlecode.iterm2.plist": "~/Library/Preferences/com.googlecode.iterm2.plist",
  "files/nvim": "~/.config/nvim"
}

```

---

## ➕ How to Track a New File

To start tracking a new configuration file across your Macs:

1. Open `manifest.json` on any Mac and add the new key-value pair.
2. Make a small change to that configuration file on your Mac (or just wait, if you've recently modified it).
3. The background sync will notice the system file is newer than the repo (which doesn't have it yet), copy it into the `files/` directory, and push it to GitHub.
4. Your other Macs will automatically pull it down on their next sync cycle!

---

## 🕹️ Hammerspoon Controls

Once Hammerspoon is running, you can control the sync engine via:

* **Menu Bar:** Click the ⚙️ icon to run a manual sync or open the repository folder.
* **Global Hotkey:** Press `Option + Cmd + S` from anywhere to trigger an immediate sync.

### Testing vs. Production Mode

By default, the script generates the Hammerspoon config in **Testing Mode**, running every 1 minute.

To switch to **Production Mode** (runs every 6 hours):

1. Open your Hammerspoon config (`~/.hammerspoon/init.lua`).
2. Change `local testingMode = true` to `local testingMode = false`.
3. Save the file and select **Reload Config** from the Hammerspoon menu bar.


--------------------------------------------------------------------------------------------------------------------------------------------------------------------------

To see the cron jobs for the current user: `crontab -l`
To edit the cron jobs for the current user: `crontab -e`

In the crontab entry you provided, the first few asterisks (*/5 * * * *) represent the scheduling pattern for the cron job. The five fields represent:

Minutes (0-59): */5 means "every 5 minutes." The * is a wildcard that matches every minute, and the /5 modifies it to run every 5 minutes (0, 5, 10, 15, 20, ..., 55).
Hours (0-23): * means "every hour."
Days of the month (1-31): * means "every day of the month."
Months (1-12): * means "every month."
Days of the week (0-7, where 0 or 7 is Sunday): * means "every day of the week."

To save editor use - `:wq!` command

If we want to run the script in every 4 hour, then we can update the script like this - `0 */4 * * *`
<br />
How to edit the keybindings?
1. you can navigate through the menu by selecting File (or Code on macOS) > Preferences > Keyboard Shortcuts.
2. Access Keybindings JSON:
    In the Keyboard Shortcuts editor, you’ll see an icon for opening keybindings.json in the top right corner.
3. Copy the file from the gitrepo and paste it there, Just done.

`displayplacer "id:1 enabled:true scaling:on origin:(0,0) degree:0" "id:2 enabled:true scaling:off origin:(-250,-1200) degree:0"`


Sample key keyboard manager object
`{
   "devices": [
       {
           "identifiers": {
               "is_keyboard": true,
               "product_id": 13330,
               "vendor_id": 14
           },
           "simple_modifications": [
               {
                   "from": { "key_code": "left_command" },
                   "to": [{ "key_code": "left_option" }]
               }
           ]
       },
       {
           "identifiers": {
               "is_keyboard": true,
               "product_id": 13330,
               "vendor_id": 14
           },
           "simple_modifications": [
               {
                   "from": { "key_code": "left_option" },
                   "to": [{ "key_code": "left_command" }]
               }
           ]
       }
   ],
   "name": "New profile custom",
   "selected": true,
   "virtual_hid_keyboard": { "keyboard_type_v2": "ansi" }
}

`
