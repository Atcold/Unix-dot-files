echo 'Installing essential command line tools'

brew install git coreutils pdfgrep bash-completion rename htop wget miniconda ranger tree rclone gh
brew install visual-studio-code rectangle keepingyouawake spotify vlc stats avidemux languagetool

echo 'Done.'


echo 'Installing Bash configurations'

rm -rf $HOME/.bashrc
ln -s $(pwd)/bashrc $HOME/.bashrc

# Get decent ls colours
wget "https://github.com/trapd00r/LS_COLORS/raw/master/LS_COLORS" -O $HOME/.dir_colors

echo 'Done.'


echo 'Installing SSH configurations'

rm -rf $HOME/.ssh/config
ln -s $(pwd)/ssh_config $HOME/.ssh/config

echo 'Done.'
