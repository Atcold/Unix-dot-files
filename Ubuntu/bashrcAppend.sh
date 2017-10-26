# Use Vim key binding in Bash and editor
set -o vi
export EDITOR="vim"

# Some useful EXPORTS
export ECN='ecn.purdue.edu'
export GPU0='elab-GPU0.'$ECN
export GPU1='elab-GPU1.'$ECN
export GPU2='elab-GPU2.'$ECN
export GPU3='elab-GPU3.'$ECN
export GPU4='elab-GPU4.'$ECN
export GPU5='elab-GPU5.'$ECN
export GPU6='elab-GPU6.'$ECN
export GPU7='elab-GPU7.'$ECN
export GPU8='elab-GPU8.'$ECN
export ELAB='elab.'$ECN
export MYELAB='acanzian@'$ELAB

# and corresponding ALIAS
alias GPU0='ssh $GPU0'
alias GPU1='ssh $GPU1'
alias GPU2='ssh $GPU2'
alias GPU3='ssh $GPU3'
alias GPU4='ssh $GPU4'
alias GPU5='ssh $GPU5'
alias GPU6='ssh $GPU6'
alias GPU7='ssh $GPU7'
alias GPU8='ssh $GPU8'
alias Elab='ssh $MYELAB'
alias GPU0x='ssh -X $GPU0'
alias GPU1x='ssh -X $GPU1'
alias GPU2x='ssh -X $GPU2'
alias GPU3x='ssh -X $GPU3'
alias GPU4x='ssh -X $GPU4'
alias GPU5x='ssh -X $GPU5'
alias GPU6x='ssh -X $GPU6'
alias GPU7x='ssh -X $GPU7'
alias GPU8x='ssh -X $GPU8'
alias Elabx='ssh -X $MYELAB'

# Some more useful ALIAS
alias ll='ls -l' # overwrite Ubuntu's ll
alias tmux='TERM=xterm-256color /usr/bin/tmux'
alias vim='TERM=xterm-256color /usr/bin/vim'

# Git stuff
function parse_git_dirty {
  [[ $(git status 2> /dev/null | tail -n1) != "nothing to commit (working directory clean)" ]] && echo "*"
}
function parse_git_branch {
    git branch --no-color 2> /dev/null | sed -e '/^[^*]/d' -e "s/* \(.*\)/[\1$(parse_git_dirty)]/"
}
export PS1='\u@\h \[\033[1;33m\]\w\[\033[0m\] $(parse_git_branch)$ '

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

# CUDA
export PATH=$PATH':/usr/local/cuda/bin'
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH':/usr/local/cuda/lib64'
