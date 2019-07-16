# Script for installing tmux on systems where you don't have root access.
# tmux will be installed in $HOME/local/bin.
# It's assumed that wget and a C/C++ compiler are installed.

# Exit on error
set -e

TMUX_VERSION=2.9a
LIBEVENT_VERSION=2.1.8
NCURSES_VERSION=6.0

# Create our directories
mkdir -p $HOME/local $HOME/tmux_tmp
cd $HOME/tmux_tmp

# Download source files for tmux, libevent, and ncurses
wget https://github.com/tmux/tmux/releases/download/${TMUX_VERSION}/tmux-${TMUX_VERSION}.tar.gz
wget https://github.com/libevent/libevent/releases/download/release-${LIBEVENT_VERSION}-stable/libevent-${LIBEVENT_VERSION}-stable.tar.gz
wget ftp://ftp.gnu.org/gnu/ncurses/ncurses-${NCURSES_VERSION}.tar.gz

# Extract files, configure, and compile

############
# libevent #
############
tar xvzf libevent-${LIBEVENT_VERSION}-stable.tar.gz
cd libevent-${LIBEVENT_VERSION}-stable
./configure --prefix=$HOME/local --disable-shared
make
make install
cd ..

############
# ncurses  #
############
tar xvzf ncurses-${NCURSES_VERSION}.tar.gz
cd ncurses-${NCURSES_VERSION}
./configure --prefix=$HOME/local
make
make install
cd ..

############
# tmux     #
############
tar xvzf tmux-${TMUX_VERSION}.tar.gz
cd tmux-${TMUX_VERSION}
./configure CFLAGS="-I$HOME/local/include -I$HOME/local/include/ncurses" LDFLAGS="-L$HOME/local/lib -L$HOME/local/include/ncurses -L$HOME/local/include"
CPPFLAGS="-I$HOME/local/include -I$HOME/local/include/ncurses" LDFLAGS="-static -L$HOME/local/include -L$HOME/local/include/ncurses -L$HOME/local/lib" make
cp tmux $HOME/local/bin
cd ..

# Cleanup
rm -rf $HOME/tmux_tmp

# Add alias to local installation
echo ''                                                        >> ~/.bashrc
echo '# Local Tmux installation'                               >> ~/.bashrc
echo alias tmux=\'TERM=xterm-256color '$HOME'/local/bin/tmux\' >> ~/.bashrc

# Make others (not Tmux) think 256 colours are available
sed -i '1i\# Fool others to think TERM=screen-256color in Tmux' ~/.bashrc
sed -i '2i\[ -n $TMUX ] && export TERM=screen-256color' ~/.bashrc
sed -i '3i\\' ~/.bashrc
