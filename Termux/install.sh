echo 'Installing essential command line tools'

pkg install -y git bash-completion eza fzf ripgrep htop tmux openssh neovim vim python uv ncurses-utils

echo 'Done.'


echo 'Installing Termux configurations'

mkdir -p $HOME/.termux
rm -rf $HOME/.termux/termux.properties $HOME/.termux/colors.properties
ln -s $(pwd)/termux.properties $HOME/.termux/termux.properties
ln -s $(pwd)/colors.properties $HOME/.termux/colors.properties

# Termux:Boot runs the scripts in ~/.termux/boot when the phone starts
rm -rf $HOME/.termux/boot
ln -s $(pwd)/boot $HOME/.termux/boot

# The terminal font: Cascadia's ExtraLight Nerd Font face with the pinyin patch from
# Scripts/, as on the Mac. Termux takes one font file and derives bold and italic from it.
FONT_TMP="$(mktemp -d)"
curl -L https://github.com/ryanoasis/nerd-fonts/releases/latest/download/CascadiaCode.tar.xz | tar xJf - -C "$FONT_TMP"
uv run --with fonttools --quiet python ../Scripts/patch_pinyin_font.py "$FONT_TMP/CaskaydiaCoveNerdFont-ExtraLight.ttf"
cp "$FONT_TMP/CaskaydiaCoveNerdFont-ExtraLight-pinyin.ttf" $HOME/.termux/font.ttf
rm -rf "$FONT_TMP"
termux-reload-settings

echo 'Done.'


echo 'Installing Bash configurations'

rm -rf $HOME/.bashrc
ln -s $(pwd)/bashrc $HOME/.bashrc

echo 'Done.'


echo 'Installing Git configurations'

rm -rf ~/.gitconfig
ln -s $(dirname $(pwd))/Git/gitconfig $HOME/.gitconfig

echo 'Done.'


echo 'Installing Neovim configuration'

mkdir -p ~/.config
rm -rf ~/.config/nvim
ln -s $(dirname $(pwd))/Nvim ~/.config/nvim
nvim --headless "+Lazy! sync" +qa

echo 'Done.'
