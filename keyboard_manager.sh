#!/bin/bash

setup_keyboard_manager() {
    echo "Setting up keyboard manager..."

    # Check if Karabiner-Elements is already installed
    if brew list --cask | grep -q karabiner-elements; then
        echo "Karabiner-Elements is already installed."
    else
        echo "Installing Karabiner-Elements..."
        brew install --cask karabiner-elements
    fi

}

