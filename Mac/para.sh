#!/usr/bin/env bash
# p, a, r: jump into ~/PARA (projects, areas, resources). Sourced by Mac/bashrc after Bash/bashrc,
# so ble.sh is loaded by then.

# Jump to a project (p), area (a) or resource (r) in ~/PARA; Tab completes names.
# An entry also answers to a key: the key: in its note.md frontmatter (or in md-Wiki/<dir>/<name>.md
# when it has no note.md), or its line in the folder's
# .keys (key name per line). p, a or r alone, or with list, lists the entries as [key] name in
# ColorBrewer Set3: projects under their area, in the area's colour; areas and resources each in
# their own colour, in sort order.
_para_set3=(8dd3c7 ffffb3 bebada fb8072 80b1d3 fdb462 b3de69 fccde5 d9d9d9 bc80bd ccebc5 ffed6f)
declare -A _para_dirs=([p]=Projects [a]=Areas [r]=Resources)
declare -A _para_kinds=([p]=project [a]=area [r]=resource)
# One line per entry of ~/PARA/<dir>: name, key, area, colour (hex), separated by \037
function _para_entries {
    local dir=$HOME/PARA/$1 d
    local note
    for d in "$dir"/*/; do d=${d%/}; note=$d/note.md
        [[ -e $note ]] || note=$HOME/md-Wiki/$1/${d##*/}.md   # no note.md link: the vault note of that name
        printf '%s\t%s\n' "${d##*/}" "$note"
    done |
        while IFS=$'\t' read -r name note; do
            printf '%s\t' "$name"
            awk 'NR==1 && /^---$/ {f=1; next} f && /^---$/ {exit}
                 f && sub(/^key: */, "") {k=$0} f && sub(/^area: */, "") {a=$0}
                 END {printf "%s\t%s\n", k, a}' "$note" 2>/dev/null || printf '\t\n'
        done |
        awk -F'\t' -v keys="$dir/.keys" -v set3="${_para_set3[*]}" '
            BEGIN {OFS="\t"; while ((getline l < keys) > 0) {split(l, kv, " "); key[kv[2]]=kv[1]}}
            $2 == "" && $1 in key {$2=key[$1]}
            {line[NR]=$0; if ($3 != "") areas[$3]=1}
            END {n=split(set3, c, " "); m=asorti_(areas, s)
                 for (i=1; i<=NR; i++) {split(line[i], f, "\t")
                     hex = m ? ((f[3] in rank) ? c[(rank[f[3]]-1)%n+1] : "") : c[(i-1)%n+1]
                     printf "%s\t%s\t%s\t%s\n", f[1], f[2], f[3], hex}}
            function asorti_(a, s,   k, i, j, t, n) {n=0; for (k in a) s[++n]=k
                for (i=2; i<=n; i++) {t=s[i]; for (j=i-1; j>0 && s[j]>t; j--) s[j+1]=s[j]; s[j+1]=t}
                for (i=1; i<=n; i++) rank[s[i]]=i; return n}' |
        sort -t $'\t' -k3,3 -k1,1 | awk -F'\t' '$3 == "" {rest = rest $0 "\n"; next} {print} END {printf "%s", rest}' |
        tr '\t' '\037'   # a separator read keeps when a field is empty; a tab would collapse
}
# _para <p|a|r> [list|name|key]: list the entries, or cd into one
function _para {
    local cmd=$1 dir=$HOME/PARA/${_para_dirs[$1]} name key area hex lines
    lines=$(_para_entries "${_para_dirs[$cmd]}")
    if [[ -z ${2-} || $2 == list ]]; then
        local last=- color grouped= indent= keyw=0
        [[ $(cut -d $'\037' -f3 <<<"$lines") == *[![:space:]]* ]] && grouped=1 indent='  '
        [[ $(cut -d $'\037' -f2 <<<"$lines") == *[![:space:]]* ]] && keyw=7
        while IFS=$'\037' read -r name key area hex; do
            color=; [[ $hex ]] && printf -v color '\e[38;2;%d;%d;%dm' 0x${hex:0:2} 0x${hex:2:2} 0x${hex:4:2}
            if [[ $grouped && $area != "$last" ]]; then
                [[ $last != - ]] && echo
                printf '%s\e[1m%s\e[0m\n' "$color" "${area:-other}"; last=$area
            fi
            printf '%s%-*s%s%s\e[0m\n' "$indent" "$keyw" "${key:+[$key]}" "$color" "$name"
        done <<<"$lines"
        return
    fi
    [[ -d $dir/$2 ]] && { cd "$dir/$2"; return; }
    while IFS=$'\037' read -r name key area hex; do
        [[ $key && $key == "$2" ]] && { cd "$dir/$name"; return; }
    done <<<"$lines"
    echo "$cmd: no ${_para_kinds[$cmd]} or key '$2'" >&2; return 1
}
function p { _para p "$@"; }
function a { _para a "$@"; }
function r { _para r "$@"; }

function _para_complete {
    COMPREPLY=($(compgen -W "$(command ls "$HOME/PARA/${_para_dirs[$1]}")" -- "$2"))
}
complete -F _para_complete p a r

# In ble.sh, the menu shows one item per entry, [key] name, and matches the key or the name;
# projects are sorted by area, the area named on its first project's item, all in its colour
function ble/complete/action:para/initialize { ble/complete/action:word/initialize; }
function ble/complete/action:para/initialize.batch { ble/complete/action:word/initialize.batch; }
function ble/complete/action:para/complete { ble/complete/action:word/complete; }
function ble/complete/action:para/init-menu-item {
    local key lead fill hex
    IFS=: read -r key lead fill hex <<<"$DATA"
    printf -v show '%-*s' "$fill" "$show"   # one width for all, so the menu lines up in columns
    # ble.sh draws the prefix uncoloured, so with areas the area and key go into the coloured part;
    # the area column opens each row (lead is "-" for a row's first item that names no area)
    if ((_para_areaw)); then
        [[ $lead ]] && printf -v lead '%-*s' "$_para_areaw" "${lead#-}"
        show=$lead$(printf '%-7s' "${key:+[$key]}")$show
    elif ((_para_keyw)); then
        printf -v prefix '%-7s' "${key:+[$key]}"
    fi
    [[ $hex ]] && { local ret; ble/color/gspec2g "fg=#$hex"; g=$ret; }
}
function _para_menu {
    local flag_source_filter=1 name key area hex last=- lead i n
    comp_opts=${comp_opts//:ble\/default:/:}   # no match: offer nothing, not the files here
    local -a names keys areas hexes
    _para_width=0 _para_keyw=0 _para_areaw=0
    while IFS=$'\037' read -r name key area hex; do
        [[ $name == "$COMPV"* || ( $key && $key == "$COMPV"* ) ]] || continue
        names+=("$name") keys+=("$key") areas+=("$area") hexes+=("$hex")
        ((${#name} > _para_width)) && _para_width=${#name}
        [[ $key ]] && _para_keyw=7
        [[ $area ]] && ((${#area} + 3 > _para_areaw)) && _para_areaw=$((${#area} + 3))
    done < <(_para_entries "${_para_dirs[$1]}")
    # Items pack tight, one space apart; all are padded to one width, so they still form columns.
    bleopt complete_menu_style=dense-nowrap   # for this menu only: ble.sh scopes it to the source
    ble/complete/cand/yield.initialize para
    n=${#names[@]}
    if ((!_para_areaw)); then
        for ((i = 0; i < n; i++)); do
            ble/complete/cand/yield para "${names[i]}" "${keys[i]}::$_para_width:${hexes[i]}"
        done
        return
    fi
    # With areas, the area column comes only on a row's first item, and each area opens a row:
    # its last item stretches to the end of the row
    local x=0 w0=$((_para_areaw + 7 + _para_width)) w1=$((7 + _para_width)) w fill
    for ((i = 0; i < n; i++)); do
        lead=; [[ ${areas[i]} != "$last" ]] && lead=${areas[i]}; last=${areas[i]}
        ((x > 0 && x + 1 + w1 >= COLUMNS)) && x=0                 # no room left: a new row
        ((x == 0)) && { lead=${lead:--}; w=$w0; } || w=$w1
        fill=$_para_width
        if ((i + 1 < n)) && [[ ${areas[i+1]} != "${areas[i]}" ]]; then
            fill=$((COLUMNS - 1 - x - (w - _para_width)))              # stretch to the row's end
            x=0
        else
            ((x += (x > 0) + w))
        fi
        ble/complete/cand/yield para "${names[i]}" "${keys[i]}:$lead:$fill:${hexes[i]}"
    done
}
# The key stays uncoloured: after ble.sh draws a p item, its [key] gets the default colour back.
# Installed once ble.sh loads its completion module (below).
function _para_ble_setup {
    declare -F _para_render_item >/dev/null && return   # wrapped already (a reload)
    eval "function _para_render_item $(declare -f ble/complete/menu-complete.class/render-item | tail -n +2)"
    function ble/complete/menu-complete.class/render-item {
        _para_render_item "$@"; local ext=$?
        if [[ $1 == para:* ]] && ((_para_areaw)); then
            local "${_ble_complete_cand_varnames[@]/%/=}"; ble/complete/cand/unpack "$1"
            local key=${DATA%%:*} hex=${DATA##*:} sgr=$'\e[39m'
            [[ $hex ]] && printf -v sgr '\e[38;2;%d;%d;%dm' 0x${hex:0:2} 0x${hex:2:2} 0x${hex:4:2}
            [[ $key ]] && ret=${ret/"[$key]"/$'\e[39m'"[$key]"$sgr}
        fi
        return "$ext"
    }
}
function ble/cmdinfo/complete:p { _para_menu p; }
function ble/cmdinfo/complete:a { _para_menu a; }
function ble/cmdinfo/complete:r { _para_menu r; }

# ble.sh: the menu, and the uncoloured key ##################################
if [[ ${BLE_VERSION-} ]]; then
    # A space right after p, a or r opens the menu; Tab walks it
    blehook/eval-after-load complete _para_ble_setup
    function ble/widget/blerc/space-para-menu {
        ble/widget/magic-space
        case $_ble_edit_str in 'p '|'a '|'r ') ble/widget/complete show_menu ;; esac
        return 0
    }
    function blerc/vi-space-para {
        ble-bind -m vi_imap -f 'SP' 'blerc/space-para-menu'
    }
    blehook/eval-after-load keymap_vi blerc/vi-space-para
fi
