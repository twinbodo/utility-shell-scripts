#!/bin/bash

CUR_DIR=$(pwd)

# Source all module files
DIR="$(dirname "$0")"
source "$DIR/keyboard_manager.sh"

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

setup_custom_functions() {
    FUNCTIONS_FILE="$HOME/custom_functions.sh"

    # Create the custom functions file if it doesn't exist
    if [[ ! -f "$FUNCTIONS_FILE" ]]; then
        echo "Creating $FUNCTIONS_FILE."
        touch "$FUNCTIONS_FILE"
    fi

    # Add the move function if it doesn't exist
    if ! grep -q "move() {" "$FUNCTIONS_FILE"; then
        echo "Adding move function to $FUNCTIONS_FILE."
        echo "move() {" >> "$FUNCTIONS_FILE"
        echo "    mkdir -p \"\$1\" && cd \"\$1\"" >> "$FUNCTIONS_FILE"
        echo "}" >> "$FUNCTIONS_FILE"
        echo "move function added."
    else
        echo "move function already exists in $FUNCTIONS_FILE."
    fi

    # Source the custom functions file in .zshrc if not already sourced
    if ! grep -q "source $FUNCTIONS_FILE" "$HOME/.zshrc"; then
        echo "Sourcing $FUNCTIONS_FILE in .zshrc."
        echo "source $FUNCTIONS_FILE" >> "$HOME/.zshrc"
    else
        echo "$FUNCTIONS_FILE is already sourced in .zshrc."
    fi
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

# Function to set up multiple aliases
setup_aliases() {
    ALIAS_FILE="$HOME/.zshrc"  # Change to .zshrc for Zsh users

    # Define indexed arrays for aliases and their commands
    aliases=("ll" "la" ".." "..." "setdisplay" )  # Added new alias
    commands=("ls -l" "ls -la" "cd .." "cd ../.." "displayplacer \"id:1 enabled:true scaling:on origin:(0,0) degree:0\" \"id:2 enabled:true scaling:off origin:(-250,-1200) degree:0\"")  # Added new command

    # Check if the alias file exists
    if [[ ! -f "$ALIAS_FILE" ]]; then
        echo "$ALIAS_FILE does not exist. Creating it."
        touch "$ALIAS_FILE"
    fi

    # Iterate over the aliases and set them up
    for i in "${!aliases[@]}"; do
        alias_name="${aliases[$i]}"
        alias_command="${commands[$i]}"
        # Check if the alias already exists
        if grep -q "alias $alias_name=" "$ALIAS_FILE"; then
            echo "Alias '$alias_name' already exists."
        else
            echo "Adding alias '$alias_name' to $ALIAS_FILE."
            echo "alias $alias_name='$alias_command'" >> "$ALIAS_FILE"
            echo "Alias '$alias_name' added."
        fi
    done
}

install_displayplacer() {
    echo "Checking for displayplacer..."
    if ! command -v displayplacer &> /dev/null; then
        echo "displayplacer not found, installing displayplacer..."
        brew install displayplacer
    else
        echo "displayplacer is already installed."
    fi
}

# Function to install zsh-autosuggestions
install_zsh_autosuggestions() {
    echo "Checking for zsh-autosuggestions..."
    ZSH_AUTOSUGGESTIONS_DIR="$HOME/.zsh/zsh-autosuggestions"

    if [[ -d "$ZSH_AUTOSUGGESTIONS_DIR" ]]; then
        echo "zsh-autosuggestions is already installed."
    else
        echo "Installing zsh-autosuggestions..."
        git clone https://github.com/zsh-users/zsh-autosuggestions.git "$ZSH_AUTOSUGGESTIONS_DIR"
        echo "source $ZSH_AUTOSUGGESTIONS_DIR/zsh-autosuggestions.zsh" >> "$HOME/.zshrc"
        echo "zsh-autosuggestions installed and sourced in .zshrc."
    fi
}

# Function to install Rectangle
install_rectangle() {
    echo "Checking if Rectangle is installed..."
    
    # Check if Rectangle is already installed
    if [ -d "/Applications/Rectangle.app" ]; then
        echo "Rectangle is already installed."
    else
        echo "Rectangle is not installed."
        
        # Install Rectangle via Homebrew
        echo "Installing Rectangle via Homebrew..."
        brew install --cask rectangle
        
        echo "Rectangle has been installed."
    fi
}

move_back_n_commits() {
    read -p "Enter the number of commits to move back: " n
    read -p "Do you want to perform a soft or hard reset? (soft/hard): " reset_type

    if [[ $reset_type == "soft" ]]; then
        git reset --soft HEAD~$n
        echo "Soft reset to $n commits back."
    elif [[ $reset_type == "hard" ]]; then
        git reset --hard HEAD~$n
        echo "Hard reset to $n commits back."
    else
        echo "Invalid option. Please choose 'soft' or 'hard'."
    fi
}

main() {
    echo "Starting Setup"
    install_homebrew

    read -p "Do you want to install all tools at once? (y/n): " install_all
    # Use indexed arrays for items and their corresponding functions
    items=( "Rectangle" "Keyboard Manager" "blueutil" "Maccy" "Add Github User" "Setup Aliases" "Setup Custom Functions" "Displayplacer" "Zsh Autosuggestions" )
    functions=( "install_rectangle" "setup_keyboard_manager" "install_blueutil" "add_maccy" "add_github_user" "setup_aliases" "setup_custom_functions" "install_displayplacer" "install_zsh_autosuggestions" )

    if [[ $install_all == "y" ]]; then
        # Install all tools by iterating over the functions
        for func in "${functions[@]}"; do
            $func  # Call the corresponding function
        done
    else
        for i in "${!items[@]}"; do
            read -p "Do you want to install ${items[$i]}? (y/n): " choice
            if [[ $choice == "y" ]]; then
                ${functions[$i]}  # Call the corresponding function
            else
                echo "Skipping ${items[$i]} installation."
            fi
        done
    fi

    echo "Setup complete. The script will run every 5 minutes to manage Bluetooth."
}
main