echo 'Installing essential command line tools'

sudo apt-get update
sudo apt-get install -y bash-completion git htop wget tree fzf eza bat ranger rclone gh pipx  # Neovim: Nvim/install.sh

echo 'Done.'


echo 'Installing Bash configurations'

rm -rf $HOME/.bashrc
ln -s $(pwd)/bashrc $HOME/.bashrc

# Get decent ls colours
wget "https://github.com/trapd00r/LS_COLORS/raw/master/LS_COLORS" -O $HOME/.dir_colors

# Make broken symlinks readable (default ORPHAN is near-black on red, very ugly)
sed -i 's|^ORPHAN[[:space:]].*|ORPHAN                38;5;167            # core (was 48;5;196;38;5;232;1)|' $HOME/.dir_colors

# ble.sh: line editor that bashrc sources (colouring, menu completion, fuller vi mode)
BLE_TMP="$(mktemp -d)"
curl -L https://github.com/akinomyoga/ble.sh/releases/download/nightly/ble-nightly.tar.xz | tar xJf - -C "$BLE_TMP"
bash "$BLE_TMP/ble-nightly/ble.sh" --install "$HOME/.local/share"
rm -rf "$BLE_TMP"

echo 'Done.'
