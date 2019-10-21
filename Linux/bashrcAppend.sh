# Use Vim key binding in Bash and editor
set -o vi
export EDITOR="vim"

# Some more useful ALIAs
alias ls='ls -v --color=auto'
alias ll='ls -l' # overwrite Ubuntu's ll
alias l='ls -CF'
alias l1='l -1'
alias tmux="TERM=xterm-256color $HOME/local/bin/tmux"
alias vim='TERM=xterm-256color /usr/bin/vim'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias tree='tree -C'
alias ip='ipython --no-banner'
alias pl='ip --pylab'
alias pip-update="pip install --upgrade pip && pip freeze --local | grep -v \
'^\-e' | cut -d = -f 1  | xargs -n1 pip install -U"
alias py="python"
alias weechat="$HOME/local/bin/weechat"
alias PPUU="conda activate PPUU"

# Highlight numbers when displaying text files
alias v="grep --colour=always -nTP '(?<![\w\.])[-+]?[0-9]*[\.eE]?\-?[0-9]+|$'"
# Send v output to less
function lv {
    v $1 | less -R
}
# Convert CSV to TSV and send to lv
function cv {
    column -ts, $1 | lv
}

# Fix CIMS shit
unalias mv
unalias rm
export PROMPT_COMMAND=""

# Git stuff
function parse_git_dirty {
  [[ $(git status 2> /dev/null | tail -n1) != "nothing to commit (working directory clean)" ]] && echo "*"
}
function parse_git_branch {
    git branch --no-color 2> /dev/null | sed -e '/^[^*]/d' -e "s/* \(.*\)/[\1$(parse_git_dirty)]/"
}
export PS1="\[\e[1;35m\]\u\[\e[38;5;255m\]@\[\e[1;34m\]\h \
\[\e[1;33m\]\w\[\e[0m\] \$(parse_git_branch)\n\[\e[1;32m\]$\[\e[0m\] "
export PS2="\[\e[1;31m\]>\[\e[0m\] "

# Coloured LESS (MAN) pages
export LESS_TERMCAP_mb=$(printf '\e[01;31m') # enter blinking mode – red
export LESS_TERMCAP_md=$(printf '\e[01;35m') # enter double-bright mode – bold, magenta
export LESS_TERMCAP_me=$(printf '\e[0m') # turn off all appearance modes (mb, md, so, us)
export LESS_TERMCAP_se=$(printf '\e[0m') # leave standout mode
export LESS_TERMCAP_so=$(printf '\e[01;33m') # enter standout mode – yellow
export LESS_TERMCAP_ue=$(printf '\e[0m') # leave underline mode
export LESS_TERMCAP_us=$(printf '\e[04;36m') # enter underline mode – cyan

# Better ls colouring
if [[ -f /usr/bin/dircolors && -f $HOME/.dir_colors ]]; then
    eval $(dircolors -b $HOME/.dir_colors)
fi

## CUDA
#export PATH=$PATH':/usr/local/cuda/bin'
#export LD_LIBRARY_PATH=$LD_LIBRARY_PATH':/usr/local/cuda/lib64'

# Shortcuts and aliases for NYU and CIMS machines ##############################
#Some useful EXPORTs
export NYU='nyu.edu'
export CIMS='cims.'$NYU
export CS='cs.'$NYU
export L1='lion1.'$CS
export L2='lion2.'$CS
export L3='lion3.'$CS
export L4='lion4.'$CS
export L5='lion5.'$CS
export L6='lion6.'$CS
export ACCESS="access.$CIMS"
export MYBOX="box795.$CIMS"
export CASSIO="cassio."$CS

# and corresponding ALIAs
alias L1="ssh $L1"
alias L2="ssh $L2"
alias L3="ssh $L3"
alias L4="ssh $L4"
alias L5="ssh $L5"
alias L6="ssh $L6"
alias Access="ssh $ACCESS"
alias MyBox="ssh $MYBOX"
alias Cassio="ssh $CASSIO"

# with X forwarding
alias L1X="ssh $L1 -Y"
alias L2X="ssh $L2 -Y"
alias L3X="ssh $L3 -Y"
alias L4X="ssh $L4 -Y"
alias L5X="ssh $L5 -Y"
alias L6X="ssh $L6 -Y"
alias AccessX="ssh -Y $ACCESS"
alias MyBoxX="ssh -Y $MYBOX"
alias Cassio="ssh -Y $CASSIO"

alias Gpu="srun --qos=interactive --gres=gpu:1 --exclude=rose[1-9] --pty bash"

# Run once: $ jupyter notebook password
function nb {
    echo "Exporting XDG vairable, starting up Jupyter Notebook"
    echo -ne '  > on your local machine run: \033[1;32m$\033[0m '
    echo "nb $(hostname --short)"
    export XDG_RUNTIME_DIR=""
    jupyter notebook --no-browser --ip 0.0.0.0
}

# Set correct permissions
umask 007
