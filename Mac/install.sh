echo 'Installing essential command line tools'

brew install bash git coreutils pdfgrep bash-completion rename htop wget miniconda ranger tree fzf rclone gh
brew install visual-studio-code rectangle keepingyouawake spotify vlc stats avidemux languagetool
brew install font-caskaydia-cove-nerd-font  # terminal Nerd Font (icon glyphs + ligatures)
brew tap hamed-elfayome/claude-usage
brew install claude-usage-tracker mac-mouse-fix

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
