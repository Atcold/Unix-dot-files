# Tab completion for Taskwarrior's project: and owner: values. Sourced by Mac/bashrc.
#
# After pro: (or project:), Tab offers every PARA project: the vault notes in md-Wiki/Projects
# that have a status: line, their subprojects (a folder's notes, as folder.note), each lesson of
# learning-with-claude as <project>.lesson, and the projects Taskwarrior already holds.
# A project's key (the key: in its note) also matches, so pro:rd offers radio.
# After pro. Tab offers the modifiers (has, is, startswith, …); after pro.has: it offers the
# parts of the names, like lesson, and after the other modifiers the whole names.
# After ow: (or owner:), Tab offers the values in uda.owner.values.
# After dep: (or depends:), Tab offers the IDs of the pending tasks.

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
        pro.*:*|proj.*:*|proje.*:*|projec.*:*|project.*:*)
            local mod=${cur%%:*} val=${cur#*:} IFS=$'\n'
            mod=${mod#*.}
            case $mod in
                has|hasnt|contains)   # a substring: offer the parts of the names, like lesson
                    COMPREPLY=($(para_task_projects | cut -f1 | tr . '\n' | sort -u |
                        awk -v v="$val" 'index($0, v) == 1' | sed "s/^/${cur%%:*}:/")) ;;
                *)
                    COMPREPLY=($(_para_task_match "$val" | sed "s/^/${cur%%:*}:/")) ;;
            esac
            __ltrim_colon_completions "$cur"
            return ;;
        pro.*|proj.*|proje.*|projec.*|project.*)
            COMPREPLY=($(compgen -W "has hasnt is isnt startswith endswith not none any" \
                -P "${cur%%.*}." -S : -- "${cur#*.}"))
            return ;;
        dep:*|depe:*|depen:*|depend:*|depends:*)
            COMPREPLY=($(compgen -W "$(task _ids)" -P "${cur%%:*}:" -- "${cur#*:}"))
            __ltrim_colon_completions "$cur"
            return ;;
        ow:*|own:*|owne:*|owner:*)
            COMPREPLY=($(compgen -W "$(task _get rc.uda.owner.values | tr , ' ')" -P "${cur%%:*}:" -- "${cur#*:}"))
            __ltrim_colon_completions "$cur"
            return ;;
    esac
    _task "$@"
}

# In ble.sh, the dep: menu shows each task's description beside its ID; every other word
# goes to the bash completion above.
if [[ ${BLE_VERSION-} ]]; then
    function ble/cmdinfo/complete:task {
        if [[ $COMPV =~ ^(dep|depe|depen|depend|depends):([0-9]*)$ ]]; then
            local pre=${BASH_REMATCH[1]}: typed=${BASH_REMATCH[2]} id desc flag_source_filter=1
            bleopt complete_menu_style=desc   # for this menu only: ble.sh scopes it to the source
            ble/complete/cand/yield.initialize word
            while IFS=: read -r id desc; do
                [[ $id == "$typed"* ]] && ble/complete/cand/yield word "$pre$id" "$desc"
            done < <(task _zshids | sort -n)
            return 0
        fi
        local cmd=task
        ble/complete/progcomp/.compgen "$1"
    }

    # Colours while typing: task's commands (add, modify, done, …) orange and name:value
    # attributes (pro:radio, depends:3) lavender, as in the slides; every other word keeps
    # ble.sh's own colour, so a quoted description stays green.
    _para_task_commands='add|annotate|append|blocked|blocking|calendar|context|count|delete|denotate|done|duplicate|edit|export|info|list|log|long|ls|minimal|modify|newest|next|oldest|prepend|projects|purge|ready|start|stop|summary|tags|undo|unblocked|waiting'
    function ble/cmdinfo/cmd:task/chroma.wattr {
        local wtxt=${text:wbeg:wlen} ret
        if [[ $wtxt =~ ^[a-z][a-z._]*: ]]; then
            ble/color/gspec2g fg=#bebada
        elif [[ $wtxt =~ ^($_para_task_commands)$ ]]; then
            ble/color/gspec2g fg=#fdb462
        else
            ble/progcolor/word:default/impl.wattr
            return
        fi
        ble/progcolor/wattr#setg "$wbeg" "$ret"
        ble/progcolor/wattr#setg "$wend" d
    }
    function ble/cmdinfo/cmd:task/chroma {
        local i "${_ble_syntax_progcolor_vars[@]/%/=}"
        for ((i = 1; i < ${#comp_words[@]}; i++)); do
            local ref=${tree_words[i]}
            [[ $ref ]] || continue
            local progcolor_iword=$i
            ble/progcolor/load-word-data "$ref"
            ble/progcolor/@wattr ble/cmdinfo/cmd:task/chroma.wattr
        done
    }
fi

# Homebrew's task completion defines _task; load it first if bash-completion has not yet.
declare -F _task >/dev/null || source "$(brew --prefix)/etc/bash_completion.d/task.sh" 2>/dev/null
complete -o nospace -F _para_task task
