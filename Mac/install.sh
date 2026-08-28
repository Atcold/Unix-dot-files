echo 'Installing essential command line tools'

brew install bash git coreutils pdfgrep bash-completion@2 rename htop wget miniconda ranger tree fzf rclone gh eza uv
brew install visual-studio-code rectangle keepingyouawake spotify vlc stats avidemux notunes
brew install font-caskaydia-cove-nerd-font  # terminal Nerd Font (icon glyphs + ligatures)
brew tap hamed-elfayome/claude-usage
brew install claude-usage-tracker mac-mouse-fix

echo 'Done.'


echo 'Adding the pinyin letters to the terminal font'

# Cascadia Code covers U+01CD/U+01CE and then stops, so the third tone of i, o and u and
# all four tones of ü have no glyph -- the terminal substitutes a proportional face
# mid-word and the column drifts. The patch assembles them from pieces the font already
# has and writes a "... Pinyin" family beside the original, which is the family
# Monokai.terminal asks for. uv supplies fonttools without installing it system-wide.
FONT="$HOME/Library/Fonts/CaskaydiaCoveNerdFont-ExtraLight.ttf"
if [ -f "$FONT" ]; then
    uv run --with fonttools --quiet python \
        "$(dirname "$0")/../Scripts/patch_pinyin_font.py" "$FONT"
else
    echo "Skipping the pinyin patch: $FONT is not installed."
fi

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

echo 'Done.'


echo 'Installing SSH configurations'

rm -rf $HOME/.ssh/config
ln -s $(pwd)/ssh_config $HOME/.ssh/config

echo 'Done.'
