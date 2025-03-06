#!/bin/bash

CUR_DIR=$(pwd)

# Function to install Homebrew if it's not installed
install_homebrew() {
    echo "Checking for Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found, installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        echo "Homebrew is already installed."
    fi
}

add_cron_job() {
    # Check if the cron job is already set
    if crontab -l | grep -q "$CUR_DIR/bluetooth_manager.sh"; then
        echo "Cron job for $cron_entry_check is already set."
    else
        echo "No existing cron job found for $cron_entry_check."
        echo "Adding the cron job..."
        (crontab -l ; echo "*/5 * * * * $CUR_DIR/bluetooth_manager.sh >> $CUR_DIR/bluetooth_manager.log 2>&1") | crontab -
        echo "Cron job added to run every 5 minutes."
    fi
}

# Function to install blueutil
install_blueutil() {
    echo "Checking for blueutil..."
    if ! command -v blueutil &> /dev/null; then
        echo "blueutil not found, installing blueutil..."
        brew install blueutil
    else
        echo "blueutil is already installed."
    fi

    SCRIPT_PATH="$CUR_DIR/bluetooth_manager.sh"
    chmod +x "$SCRIPT_PATH"
    echo "Bluetooth management script created and made executable."
    add_cron_job
}

add_github_user() {
    echo "Starting Adding Github User"
    
    # Assuming CUR_DIR is set somewhere in your script and points to the correct directory
    SCRIPT_PATH="$CUR_DIR/add_github_user.sh"
    
    # Make sure the script is executable
    chmod +x "$SCRIPT_PATH"
    
    # Execute the script
    "$SCRIPT_PATH"  # This line executes the script located at SCRIPT_PATH
    
    echo "Added Github User."
}

add_maccy() {
    echo "Checking if Maccy is installed..."

    # Check if Maccy is already installed
    if command -v maccy &> /dev/null; then
        echo "Maccy is already installed."
    else
        echo "Maccy is not installed."

        # Tap the Maccy formulae if necessary
        if ! brew list --cask | grep -q maccy; then
            echo "Installing Maccy via Homebrew..."
            brew install --cask maccy
        else
            echo "Maccy is already installed via Homebrew."
        fi
    fi
}

main() {
    install_homebrew
    install_blueutil
    add_maccy
    echo "Setup complete. The script will run every 5 minutes to manage Bluetooth."
}

main