echo 'Installing mpv configurations'

mkdir -p $HOME/.config/mpv
rm -rf $HOME/.config/mpv/mpv.conf
ln -s $(pwd)/mpv.conf $HOME/.config/mpv/mpv.conf

echo 'Done.'
