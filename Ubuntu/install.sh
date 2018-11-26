echo 'Installing Bash configurations'

echo ''                            >> ~/.bashrc
echo '# My configurations'         >> ~/.bashrc
echo source $(pwd)/bashrcAppend.sh >> ~/.bashrc
URL=https://raw.github.com/trapd00r/LS_COLORS/master/LS_COLORS
wget $URL -O $HOME/.dir_colors
# ./fix_colours.sh ???

echo 'Done.'
