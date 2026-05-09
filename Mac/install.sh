echo 'Installing essential command line tools'

brew install git coreutils pdfgrep bash-completion rename htop wget miniconda ranger tree rclone gh
brew install visual-studio-code rectangle keepingyouawake spotify vlc stats avidemux languagetool
brew tap hamed-elfayome/claude-usage
brew install claude-usage-tracker mac-mouse-fix

echo 'Done.'


echo 'Installing Bash configurations'

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
