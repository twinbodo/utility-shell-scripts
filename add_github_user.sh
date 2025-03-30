#!/bin/bash

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "git could not be found, please install it first."
    exit 1
fi

# Ensure script is executed with error handling
set -e
set -o pipefail
read -p "Please enter the email for the second github account: " SECOND_EMAIL

# Validate email format (very basic, can be enhanced)
if [[ ! "$SECOND_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
    echo "Invalid email format: $SECOND_EMAIL"
    exit 1
fi

IFS='@' read -r -a parts <<< "$SECOND_EMAIL"
username="${parts[0]}"
domain="${parts[1]}"

# Check if username is not empty
if [[ -z "$username" ]]; then
    echo "Username derived from email is empty. Please check the email format."
    exit 1
fi

SSH_KEY_FILENAME="id_rsa_github_$username"
echo "SSH_KEY_FILENAME: $SSH_KEY_FILENAME"

# Check if ssh-keygen exists
if ! command -v ssh-keygen &> /dev/null; then
    echo "ssh-keygen could not be found, please install it first."
    exit 1
fi

# Generate a new SSH key for the second GitHub account
if [[ -f "$HOME/.ssh/${SSH_KEY_FILENAME}" ]]; then
    echo "SSH key already exists at $HOME/.ssh/${SSH_KEY_FILENAME}. Choose a different name or remove the existing one."
    exit 1
else
    echo "Generating a new SSH key for the second GitHub account..."
    ssh-keygen -t rsa -b 4096 -C "$SECOND_EMAIL" -f "$HOME/.ssh/${SSH_KEY_FILENAME}" -N ""
fi

# Start the ssh-agent in the background
eval "$(ssh-agent -s)" || { echo "Failed to start ssh-agent"; exit 1; }

# Add your SSH private key to the ssh-agent
ssh-add "$HOME/.ssh/${SSH_KEY_FILENAME}" || { echo "Failed to add SSH key to ssh-agent"; exit 1; }

# Validate if the SSH key file was generated correctly
if [[ ! -f "$HOME/.ssh/${SSH_KEY_FILENAME}.pub" ]]; then
    echo "SSH public key was not created successfully."
    exit 1
fi

# Now you must manually add the SSH public key to your GitHub account
echo "Please manually add the following SSH public key to your GitHub account:"
cat "$HOME/.ssh/${SSH_KEY_FILENAME}.pub"
if command -v pbcopy &> /dev/null; then
    cat "$HOME/.ssh/${SSH_KEY_FILENAME}.pub" | pbcopy
    echo "(The key has been copied to your clipboard)"
else
    echo "(pbcopy command not found; please manually copy the key above.)"
fi

# Ensure ~/.ssh exists before making modifications
mkdir -p "$HOME/.ssh"

# Check if the ~/.ssh/config file exists; create it if not
if [[ ! -f "$HOME/.ssh/config" ]]; then
    touch "$HOME/.ssh/config"
    chmod 600 "$HOME/.ssh/config"  # Ensure the config file has the correct permissions
fi

# Create or modify the ~/.ssh/config file to use the new key for GitHub
{
    echo -e "\nHost github.com-$username"
    echo "  HostName github.com"
    echo "  User git"
    echo "  IdentityFile ~/.ssh/${SSH_KEY_FILENAME}"
} >> "$HOME/.ssh/config"

echo "Configuration complete. Remember to use the github.com-$username host in your Git commands for the second account."

read -p "If you have updated the github account with correct SSH key, press enter to continue"


# Repository level changes
# git config user.name "$username"
# git config user.email "$SECOND_EMAIL" || { echo "Failed to set Git user email"; exit 1; }
# Example to start working on the new git account
# git clone git@github.com-<username>:<username>/<repo-name>.git
echo "Script execution completed successfully."