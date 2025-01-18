#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
  echo -e "${GREEN}[+] $1${NC}"
}

print_error() {
  echo -e "${RED}[!] $1${NC}"
}

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
  print_error "Please run as root (use sudo)"
  exit 1
fi

# Update system packages
print_status "Updating system packages..."
apt update
apt upgrade -y

# Install basic dependencies
print_status "Installing basic dependencies..."
apt install -y \
  git \
  curl \
  wget \
  python3 \
  python3-venv \
  python3-dev \
  python3-pip \
  libssl-dev \
  pkg-config

# 询问是否安装 gh
read -p "Do you want to install gh (y/n)? " yn
case $yn in
[Yy]*)
  echo "Installing gh..."
  # 安装 gh
  (type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) &&
    sudo mkdir -p -m 755 /etc/apt/keyrings &&
    out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg &&
    cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null &&
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg &&
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null &&
    sudo apt update &&
    sudo apt install gh -y
  ;;
[Nn]*)
  echo "Skipping gh installation..."
  break
  ;;
*)
  echo "Invalid input. Please enter 'y' or 'n'."
  exit 1
  ;;
esac

# Install podman
print_status "Installing podman..."
apt install -y podman

# Pull required containers
print_status "Pulling required containers..."
podman pull docker.io/library/redis
podman pull docker.io/library/mysql

# Install PDM
print_status "Installing PDM..."
curl -sSL https://pdm.fming.dev/install-pdm.py | python3 -
# /root/.local/bin
# ln -s /root/.local/bin/pdm /usr/bin/pdm

# Create Python virtual environment and install dependencies
print_status "Setting up Python environment..."
pdm install

print_status "Environment setup completed successfully!"
print_status "Next steps:"
echo "1. Configure your config.toml file"
echo "2. Start the required containers using 'make start-infra'"
echo "3. Run the bot using 'make run'"
