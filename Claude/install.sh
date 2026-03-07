echo 'Installing Claude configurations'

mkdir -p $HOME/.claude
rm -rf $HOME/.claude/statusline.sh
ln -s $(pwd)/statusline.sh $HOME/.claude/statusline.sh

echo 'Done.'
