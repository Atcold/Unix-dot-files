echo 'Installing Bash configurations'

echo ''                            >> ~/.bashrc
echo '# My configurations'         >> ~/.bashrc
echo source $(pwd)/bashrcAppend.sh >> ~/.bashrc
ln -s $(pwd)/dircolors.monokai $HOME/.dir_colors
#./fix_colours.sh

echo 'Done.'
