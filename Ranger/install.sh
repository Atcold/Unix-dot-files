echo 'Installing Ranger configurations'

mkdir -p $HOME/.config/ranger

for f in rc.conf colorschemes plugins; do
    rm -rf $HOME/.config/ranger/$f
    ln -s $(pwd)/$f $HOME/.config/ranger/$f
done

# Homebrew installs ranger via virtualenv and leaves the man pages stranded
# inside libexec/share/man, which brew's man-linker never visits. Linux
# distros (apt/dnf) put them in /usr/share/man, already on the manpath.
if command -v brew >/dev/null && brew --prefix ranger >/dev/null 2>&1; then
    mkdir -p $HOME/.local/share/man/man1
    for page in ranger.1 rifle.1; do
        ln -sf $(brew --prefix ranger)/libexec/share/man/man1/$page \
               $HOME/.local/share/man/man1/$page
    done
fi

echo 'Done.'
