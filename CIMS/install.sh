echo 'Installing Bash configurations'

# Append, don't replace: the cluster's own ~/.bashrc sets up modules, Slurm, etc.
echo ''                       >> ~/.bashrc
echo '# My configurations'    >> ~/.bashrc
echo source $(pwd)/bashrc     >> ~/.bashrc
URL=https://raw.github.com/trapd00r/LS_COLORS/master/LS_COLORS
wget $URL -O $HOME/.dir_colors

echo 'Done.'
