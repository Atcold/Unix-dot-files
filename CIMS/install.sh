echo 'Installing Bash configurations'

# Append, don't replace: the cluster's own ~/.bashrc sets up modules, Slurm, etc.
echo ''                       >> ~/.bashrc
echo '# My configurations'    >> ~/.bashrc
echo source $(pwd)/bashrc     >> ~/.bashrc
URL=https://raw.github.com/trapd00r/LS_COLORS/master/LS_COLORS
wget $URL -O $HOME/.dir_colors

# No root on the cluster: eza (the `ls`/`l`/`ll` in Bash/bashrc) as a static binary
mkdir -p $HOME/.local/bin
curl -L https://github.com/eza-community/eza/releases/latest/download/eza_x86_64-unknown-linux-musl.tar.gz \
    | tar xzf - -C $HOME/.local/bin

# ble.sh: line editor that bashrc sources (colouring, menu completion, fuller vi mode)
BLE_TMP="$(mktemp -d)"
curl -L https://github.com/akinomyoga/ble.sh/releases/download/nightly/ble-nightly.tar.xz | tar xJf - -C "$BLE_TMP"
bash "$BLE_TMP/ble-nightly/ble.sh" --install "$HOME/.local/share"
rm -rf "$BLE_TMP"

echo 'Done.'
