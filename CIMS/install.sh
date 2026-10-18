echo 'Installing Bash configurations'

# Append, don't replace: the cluster's own ~/.bashrc sets up modules, Slurm, etc.
echo ''                       >> ~/.bashrc
echo '# My configurations'    >> ~/.bashrc
echo source $(pwd)/bashrc     >> ~/.bashrc
URL=https://raw.github.com/trapd00r/LS_COLORS/master/LS_COLORS
wget $URL -O $HOME/.dir_colors

# No root on the cluster: eza (the `ls`/`l`/`ll` in Bash/bashrc) as a static binary
mkdir -p $HOME/.local/bin
curl -L https://github.com/eza-community/eza/releases/latest/download/eza_x86_64-unknown-linux-musl.tar.gz \
    | tar xzf - -C $HOME/.local/bin

echo 'Done.'
