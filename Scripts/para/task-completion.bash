# Tab completion for Taskwarrior's project: and owner: values. Sourced by Mac/bashrc.
#
# After pro: (or project:), Tab offers every PARA project: the vault notes in md-Wiki/Projects
# that have a status: line, their subprojects (a folder's notes, as folder.note), each lesson of
# learning-with-claude as <project>.lesson, and the projects Taskwarrior already holds.
# A project's key (the key: in its note) also matches, so pro:rd offers radio.
# After ow: (or owner:), Tab offers the values in uda.owner.values.

# One line per vault project: name, a tab, and its key (empty when it has none)
function _para_task_vault {
    local vault=$HOME/md-Wiki/Projects f s d name
    for f in "$vault"/*.md "$vault"/*/*.md; do
        s=${f##*/}; s=${s%.md}; d=${f%/*}; d=${d##*/}
        if [[ $d == Projects ]]; then name=$s
        elif [[ $s == "$d" ]]; then name=$d
        else name=$d.$s
        fi
        awk -v name="$name" '
            NR == 1 && !/^---$/ {exit}
            NR > 1 && /^---$/ {if (st) print name "\t" key; exit}
            sub(/^key: */, "") {key = $0}
            /^status: / {st = 1}' "$f"
    done
}

# One line per project: the vault projects, then <project>.lesson for each lesson folder
# (or <folder>.lesson when no project has that name), then Taskwarrior's own projects
function para_task_projects {
    local lessons
    lessons=$(command ls -d "$HOME"/Work/GitHub/learning-with-claude/*/lesson.tex 2>/dev/null |
        awk -F/ '{print $(NF-1)}' | paste -sd , -)   # commas: BSD awk takes no newline in -v
    _para_task_vault | awk -F'\t' -v lessons="$lessons" '
        {print; last = $1; sub(/.*\./, "", last); proj[tolower(last)] = $1; key[$1] = $2}
        END {
            n = split(lessons, l, ",")
            for (i = 1; i <= n; i++) {
                p = proj[tolower(l[i])]
                if (p != "") print p ".lesson\t" (key[p] != "" ? key[p] ".lesson" : "")
                else print l[i] ".lesson\t"
            }
        }'
    task _projects 2>/dev/null | sed 's/$/\t/'
}

# Names whose name or key starts with $1, one per line, without repeats
function _para_task_match {
    para_task_projects |
        awk -F'\t' -v v="$1" 'index($1, v) == 1 || ($2 != "" && index($2, v) == 1) {print $1}' |
        sort -u
}

function _para_task {
    local cur
    _get_comp_words_by_ref -n : cur
    case $cur in
        pro:*|proj:*|proje:*|projec:*|project:*)
            local IFS=$'\n'
            COMPREPLY=($(_para_task_match "${cur#*:}" | sed "s/^/${cur%%:*}:/"))
            __ltrim_colon_completions "$cur"
            return ;;
        ow:*|own:*|owne:*|owner:*)
            COMPREPLY=($(compgen -W "$(task _get rc.uda.owner.values | tr , ' ')" -P "${cur%%:*}:" -- "${cur#*:}"))
            __ltrim_colon_completions "$cur"
            return ;;
    esac
    _task "$@"
}

# Homebrew's task completion defines _task; load it first if bash-completion has not yet.
declare -F _task >/dev/null || source "$(brew --prefix)/etc/bash_completion.d/task.sh" 2>/dev/null
complete -o nospace -F _para_task task
