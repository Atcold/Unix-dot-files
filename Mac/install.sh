echo 'Installing essential command line tools'

brew install bash git coreutils pdfgrep bash-completion@2 rename htop wget miniconda ranger tree fzf rclone gh eza uv pipx
brew install visual-studio-code rectangle keepingyouawake spotify vlc stats avidemux notunes
brew install font-caskaydia-cove-nerd-font  # terminal Nerd Font (icon glyphs + ligatures)
brew tap hamed-elfayome/claude-usage
brew install claude-usage-tracker mac-mouse-fix
pipx install python-kasa  # kasa: Kasa smart plugs over the LAN
mkdir -p $HOME/.local/bin  # spark: AlfSPARK on/off from anywhere (Scripts/README.md)
ln -sf "$(cd "$(dirname "$0")/.." && pwd)/Scripts/spark.py" $HOME/.local/bin/spark

echo 'Done.'


echo 'Adding the pinyin letters to the terminal font'

# Cascadia Code covers U+01CD/U+01CE and then stops, so the third tone of i, o and u and
# all four tones of ü have no glyph -- the terminal substitutes a proportional face
# mid-word and the column drifts. The patch assembles them from pieces the font already
# has and writes a "... Pinyin" family beside the original, which is the family
# Monokai.terminal asks for. It also turns off the <= and <<= ligatures, drawn as
# less-or-equal where Verilog means assignment. uv supplies fonttools without installing
# it system-wide. Every face Terminal draws with is patched, the italic and bold ones
# too, or the Pinyin family has none and Terminal loses italics.
for FACE in ExtraLight ExtraLightItalic Bold BoldItalic; do
    FONT="$HOME/Library/Fonts/CaskaydiaCoveNerdFont-$FACE.ttf"
    if [ -f "$FONT" ]; then
        uv run --with fonttools --quiet python \
            "$(dirname "$0")/../Scripts/patch_pinyin_font.py" "$FONT"
    else
        echo "Skipping the pinyin patch: $FONT is not installed."
    fi
done

echo 'Done.'


echo 'Installing Bash configurations'

# macOS ships bash 3.2 (2007); use Homebrew bash 5.x as the login shell so
# modern readline features (menu-complete-backward, etc.) work.
BREW_BASH="$(brew --prefix)/bin/bash"
if ! grep -qx "$BREW_BASH" /etc/shells; then
    echo "$BREW_BASH" | sudo tee -a /etc/shells
fi
chsh -s "$BREW_BASH"
# NOTE: Terminal.app also needs Settings → General → "Shells open with" set
# to "Default login shell" (otherwise it execs /bin/bash directly, ignoring chsh).

rm -rf $HOME/.bashrc
ln -s $(pwd)/bashrc $HOME/.bashrc

rm -rf $HOME/.profile
ln -s $(pwd)/profile $HOME/.profile

# Get decent ls colours
wget "https://github.com/trapd00r/LS_COLORS/raw/master/LS_COLORS" -O $HOME/.dir_colors

# Make broken symlinks readable (default ORPHAN is near-black on red, very ugly)
sed -i '' 's|^ORPHAN[[:space:]].*|ORPHAN                38;5;167            # core (was 48;5;196;38;5;232;1)|' $HOME/.dir_colors

# ble.sh: line editor that bashrc sources (colouring, menu completion, fuller vi mode)
BLE_TMP="$(mktemp -d)"
curl -L https://github.com/akinomyoga/ble.sh/releases/download/nightly/ble-nightly.tar.xz | tar xJf - -C "$BLE_TMP"
bash "$BLE_TMP/ble-nightly/ble.sh" --install "$HOME/.local/share"
rm -rf "$BLE_TMP"

echo 'Done.'


echo 'Keeping the computer name'

# Only AlfMAC5 gets renamed by NYU's BigFix. The script is copied, root-owned, out of
# the repo: a root daemon must not run a file the user can edit.
if [ "$(scutil --get LocalHostName)" = AlfMAC5 ]; then
    sudo install -d /usr/local/sbin
    sudo install -o root -g wheel -m 755 keepname.sh /usr/local/sbin/keepname
    sudo install -o root -g wheel -m 644 com.atcold.keepname.plist /Library/LaunchDaemons/
    sudo launchctl bootout system/com.atcold.keepname 2>/dev/null
    sudo launchctl bootstrap system /Library/LaunchDaemons/com.atcold.keepname.plist
else
    echo 'Skipping: this is not AlfMAC5.'
fi

echo 'Done.'


echo 'Installing SSH configurations'

rm -rf $HOME/.ssh/config
ln -s $(pwd)/ssh_config $HOME/.ssh/config

echo 'Done.'


echo 'Installing Karabiner configurations'

# Karabiner may miss edits made through the link; restart its user server to reload:
# launchctl kickstart -k gui/$(id -u)/org.pqrs.service.agent.Karabiner-Console-User-Server
mkdir -p $HOME/.config/karabiner
rm -rf $HOME/.config/karabiner/karabiner.json
ln -s $(pwd)/karabiner.json $HOME/.config/karabiner/karabiner.json

echo 'Done.'
