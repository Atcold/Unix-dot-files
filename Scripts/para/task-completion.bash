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
# `task 6` (one ID alone) shows the top of `task 6 info`, its labels coloured; `task 6,7` shows
# the card report from taskrc; `task 6 info` keeps the full view.

# Taskwarrior runs its full info report for IDs alone; the shell turns that into the short views.
function task {
    if (($# == 1)) && [[ $1 =~ ^[0-9]+$ ]]; then
        command task rc.color=off rc.verbose=label rc.journal.info=0 "$1" info |
            awk 'function lab(s) { return sprintf("\033[1;38;2;128;177;211m%-13s\033[0m", s) }
                 NR == 1 {w = index($0, "Value") - 1; next}   # the label column width
                 /^-+ -+$/ {next}
                 /^$/ {exit}                                  # the urgency arithmetic follows
                 {l = substr($0, 1, w); v = substr($0, w + 1); sub(/ +$/, "", l)
                  if (l == "") { val[last] = val[last] "\n" lab("") v; next }   # an annotation
                  if (l == "Description") v = "\033[1m" v "\033[0m"
                  last = l; val[l] = v; order[++n] = l}
                 END {
                   # The project is the theme, so it comes first, then the description; the ID
                   # was typed, and the bookkeeping fields stay in info.
                   print lab("Project") val["Project"]
                   print lab("Description") val["Description"]
                   # The rest repeats what the lists show, so it sits below a gap, in grey, on one line.
                   print ""
                   rest = "Status: " val["Status"] ", Urgency: " val["Urgency"] ", Owner: " val["Owner"]
                   for (i = 1; i <= n; i++) {
                     l = order[i]
                     if (l ~ /^(ID|Project|Description|Status|Urgency|Owner|Virtual tags|UUID|Last modified)$/) continue
                     v = val[l]
                     if (l ~ /^(Entered|Start|Due|Wait|Scheduled|Until|End)/ && match(v, /\(.*\)/))
                       v = substr(v, RSTART + 1, RLENGTH - 2) " ago"   # the age, not the timestamp
                     sub(/^This task /, "", l); l = toupper(substr(l, 1, 1)) substr(l, 2)
                     rest = rest ", " l ": " v
                   }
                   print "\033[2m" rest "\033[0m"
                 }'
    elif (($# == 1)) && [[ $1 =~ ^[0-9]+([,-][0-9]+)*$ ]]; then
        command task "$1" card
    elif [[ -t 1 ]] && ! [[ " $* " =~ \ (add|annotate|append|config|context|delete|denotate|done|duplicate|edit|import|log|modify|prepend|purge|start|stop|sync|undo)\  ]]; then
        # A list on the terminal: keep Taskwarrior's colours and width through the pipe, colour
        # each annotation count [N] cyan, so a task with more to it stands out, set the header
        # in bold blue as task 6's labels with a grey rule under it in place of the dashes, which
        # first give the Deps column's width, and
        # the count of tasks at the end in grey.
        command task rc._forcecolor=on rc.defaultwidth="$COLUMNS" "$@" |
            sed -E -e $'s/ \\[([0-9]+)\\]/ \033[36m[\\1]\033[39m/g' \
                -e $'s/^[0-9]+ (tasks?|projects?)\r?$/\033[2m&\033[0m/' |
            awk '/^(ID|Project|Deps) / {
                     sub(/\r$/, ""); sub(/Urg$/, " Urg")   # right-aligned, as the numbers under it
                     # Where the Deps column starts; the dashes under the header give its width
                     ds = 0; if (match($0, /(^| )Deps( |$)/)) ds = RSTART + ($0 ~ /^Deps/ ? 0 : 1)
                     printf "\033[1;38;2;128;177;211m%s\033[0m\n\033[2m", $0
                     for (i = 0; i < length($0); i++) printf "─"
                     printf "\033[0m\n"; dashes = 1; next}
                 dashes { dashes = 0; sub(/\r$/, "")
                     if (ds) { match(substr($0, ds), /^-+/); dw = RLENGTH }
                     next}
                 ds {   # right-align the IDs in the Deps cell; colour codes take no columns
                     v = 0; b = 0; line = $0
                     for (i = 1; i <= length(line); i++) {
                         if (substr(line, i, 1) == "\033") { match(substr(line, i), /m/); i += RSTART - 1; continue }
                         if (++v == ds) { b = i; break }
                     }
                     if (b) { cell = substr(line, b, dw)
                         if (cell ~ /^[0-9,]+ +$/) { t = cell; sub(/ +$/, "", t)
                             $0 = substr(line, 1, b - 1) sprintf("%" dw "s", t) substr(line, b + dw) } }
                 }
                 {print}'
        return "${PIPESTATUS[0]}"
    else
        command task "$@"
    fi
}

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

_para_task_show_commands=(next list blocked ready summary info)
_para_task_change_commands=(add modify annotate start stop done delete)

function _para_task {
    local cur
    _get_comp_words_by_ref -n : cur
    # Offer common commands first. A typed prefix goes through Taskwarrior's completion.
    if [[ $COMP_CWORD == 1 && -z $cur ]]; then
        COMPREPLY=("${_para_task_show_commands[@]}" "${_para_task_change_commands[@]}")
        return
    fi
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
    # Draw group labels separately from the selectable completion candidates.
    function ble/complete/menu-style:para-task/construct-page {
        if ((cols < 25)); then
            local menu_style=dense-nowrap
            ble/complete/menu-style:dense-nowrap/construct-page "$@"
            return
        fi

        local -a commands=("${_para_task_show_commands[@]}" "${_para_task_change_commands[@]}")
        local show_count=${#_para_task_show_commands[@]}
        local index item label command command_width x0 drawn ret
        end=$begin x=0 y=0 esc=
        for ((index=begin; index<${#menu_items[@]}; index++)); do
            ble/complete/menu#check-cancel && return 148
            item=${menu_items[index]}
            command=${commands[index]}
            command_width=${#command}
            if ((index > begin && (index == show_count || x + 2 + command_width >= cols))); then
                ((y + 1 < lines)) || break
                esc+=$'\n'
                ((x=0, ++y))
            fi
            if ((index == begin || index == show_count)); then
                label='Show tasks:'
                ((index < show_count)) || label='Change tasks:'
                esc+=$'\e[1;38;2;128;177;211m'$label$_ble_term_sgr0'  '
                x=$((${#label} + 2))
            elif ((x > 0)); then
                esc+='  '
                ((x+=2))
            fi
            x0=$x
            ble/complete/menu#render-item "$item"
            # Keep ble.sh's selection rendering and colour the unselected command.
            drawn=${ret/"$command"/$'\e[38;2;253;180;98m'$command}
            _ble_complete_menu_style_icons[index]=$x0,$y,$x,$y,${#item},${#drawn}:$item$drawn
            esc+=$drawn
            end=$((index + 1))
        done
    }

    function ble/cmdinfo/complete:task {
        if ((comp_cword == 1)) && [[ ! $COMPV ]]; then
            local candidate flag_source_filter=1
            bleopt complete_menu_style=para-task
            ble/complete/cand/yield.initialize word
            for candidate in "${_para_task_show_commands[@]}" "${_para_task_change_commands[@]}"; do
                ble/complete/cand/yield word "$candidate"
            done
            return 0
        fi
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
