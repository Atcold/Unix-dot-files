echo 'Installing Bash configurations'

cat bashrcAppend >> ~/.bashrc
./fix_colours.sh

echo 'Done.'
