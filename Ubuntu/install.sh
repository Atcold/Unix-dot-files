echo 'Installing Bash configurations'

echo ''                            >> ~/.bashrc
echo '# My configurations'         >> ~/.bashrc
echo source $(pwd)/bashrcAppend.sh >> ~/.bashrc
./fix_colours.sh

echo 'Done.'
