-- Radio: replaces mpv's startup messages with coloured lines of my own.
-- Each station gets a header with its name and stream details (format, bitrate, sample rate,
-- channels, audio output), and each new piece gets a line with the time it started,
-- so the pane keeps a history of what played. Each station's name and current piece are in its own colour; details and times are dim.
local function rgb(hex, text, bold)
  local r, g, b = tonumber(hex:sub(1, 2), 16), tonumber(hex:sub(3, 4), 16), tonumber(hex:sub(5, 6), 16)
  return string.format("\27[%s38;2;%d;%d;%dm%s\27[0m", bold and "1;" or "", r, g, b, text)
end

local function dim(text) return "\27[2m" .. text .. "\27[0m" end

local function say(line)
  io.write("\r\27[K" .. line .. "\n")  -- clear the status line, print, let mpv redraw it
  io.flush()
end

-- The station's name in tg-pane's lettering: each letter is 3 pixels wide and 4 tall,
-- drawn with half blocks, so a name takes three text rows.
-- The set covers every letter and digit a station name can carry: letters b, h, j, k, y
-- and z were missing, and digits were dropped by the filter below, so Jazz24 came out as
-- JAZZ. Shapes are mine, drawn to match the set.
local GLYPHS = {
  a = {".##", "#.#", "###", "#.#"}, b = {"##.", "#.#", "##.", "##."}, c = {"###", "#..", "#..", "###"},
  d = {"##.", "#.#", "#.#", "##."}, e = {"###", "#..", "##.", "###"}, f = {"###", "#..", "##.", "#.."},
  g = {"###", "#..", "#.#", "###"}, h = {"#.#", "#.#", "###", "#.#"}, i = {"###", ".#.", ".#.", "###"},
  j = {"..#", "..#", "#.#", "###"}, k = {"#.#", "#.#", "##.", "#.#"}, l = {"#..", "#..", "#..", "###"},
  m = {"###", "###", "#.#", "#.#"}, n = {"###", "#.#", "#.#", "#.#"}, o = {"###", "#.#", "#.#", "###"}, p = {"###", "#.#", "###", "#.."},
  q = {"###", "#.#", "###", "..#"}, r = {"###", "#.#", "##.", "#.#"}, s = {"###", "#..", "..#", "###"},
  t = {"###", ".#.", ".#.", ".#."}, u = {"#.#", "#.#", "#.#", "###"}, v = {"#.#", "#.#", "#.#", ".#."},
  w = {"#.#", "#.#", "###", "###"}, x = {"#.#", ".#.", ".#.", "#.#"}, y = {"#.#", "#.#", ".#.", ".#."},
  z = {"###", "..#", ".#.", "###"}, [" "] = {"...", "...", "...", "..."},
  ["0"] = {"###", "#.#", "#.#", "###"}, ["1"] = {".#.", "##.", ".#.", "###"}, ["2"] = {"##.", "..#", ".#.", "###"},
  ["3"] = {"###", "..#", "..#", "###"}, ["4"] = {"#.#", "#.#", "###", "..#"}, ["5"] = {"###", "#..", "..#", "###"},
  ["6"] = {"###", "#..", "###", "#.#"}, ["7"] = {"###", "..#", ".#.", ".#."}, ["8"] = {"###", "#.#", "###", "#.#"},
  ["9"] = {"###", "#.#", "###", "..#"},
}
local HALF = { ["##"] = "█", ["#."] = "▀", [".#"] = "▄", [".."] = " " }

-- S and Z, and 0 and O, come out alike at three cells wide, and 2 is close enough to Z
-- that a name would read JAZZZ4: a space goes in wherever letters meet digits, so
-- Jazz24 draws as JAZZ 24.
local function blocky(word)
  word = word:lower():gsub("[^%a%d ]", "")
  word = word:gsub("(%a)(%d)", "%1 %2"):gsub("(%d)(%a)", "%1 %2")
  local rows = { string.rep(".", 4 * #word - 1) }
  for r = 1, 4 do
    local parts = {}
    for c in word:gmatch(".") do table.insert(parts, (GLYPHS[c] or GLYPHS[" "])[r]) end
    table.insert(rows, table.concat(parts, "."))
  end
  table.insert(rows, rows[1])
  local out = {}
  for i = 1, 5, 2 do
    local line = {}
    for k = 1, #rows[i] do table.insert(line, HALF[rows[i]:sub(k, k) .. rows[i + 1]:sub(k, k)]) end
    table.insert(out, table.concat(line))
  end
  return out
end

-- Each station has its own colour, ColorBrewer Set3 in order without the yellow and the grey,
-- used for its banner and for the piece on the status line.
local COLOURS = { "8dd3c7", "bebada", "fb8072", "80b1d3", "fdb462", "b3de69", "fccde5", "bc80bd", "ccebc5" }

local shown, colour = "", COLOURS[1]   -- the last real piece, and the current station's colour

local function status()
  local r, g, b = tonumber(colour:sub(1, 2), 16), tonumber(colour:sub(3, 4), 16), tonumber(colour:sub(5, 6), 16)
  mp.set_property("term-status-msg", string.format(
    "\27[38;2;%d;%d;%dm♪ %s\27[0m  \27[2m${time-pos}  ·  vol ${volume}%%\27[0m", r, g, b, shown))
end

local pending = nil
local started = false   -- the header waits until the bitrate is known
local titles = {}     -- pieces announced before the header, printed after it


mp.register_event("file-loaded", function()
  local pos = mp.get_property_number("playlist-pos-1", 1)
  local count = mp.get_property_number("playlist-count", 1)
  local name = mp.get_property("playlist/" .. (pos - 1) .. "/title") or mp.get_property("media-title", "")
  pending = { name = name, pos = pos .. "/" .. count, colour = COLOURS[(pos - 1) % #COLOURS + 1] }
  colour, shown = pending.colour, pending.name
  status()
end)

local function piece(title)
  say(dim(os.date("%H:%M")) .. "  ♪ " .. title)
end

mp.observe_property("audio-bitrate", "number", function(_, bps)
  if not (pending and bps and bps > 0) then return end
  local rate = mp.get_property_number("audio-params/samplerate", 0) / 1000
  local ch = mp.get_property_number("audio-params/channel-count", 0)
  local details = table.concat({
    pending.pos,
    mp.get_property("audio-codec-name", "?"),
    math.floor(bps / 1000 + 0.5) .. " kbps",
    string.format("%g kHz", rate),
    ch == 2 and "stereo" or (ch == 1 and "mono" or ch .. " ch"),
    mp.get_property("current-ao", "?"),
  }, "  ·  ")
  if started then
    io.write("\27[1A\r\27[K")  -- remove the status line mpv leaves behind at a switch
  else
    say("<  >" .. dim("  station   ·   ") .. "1-8 a-z" .. dim("  jump   ·   ") .. "9  0" .. dim("  volume   ·   ") .. "c" .. dim("  channels   ·   ") .. "space" .. dim("  pause   ·   ") .. "q" .. dim("  quit"))
    started = true
  end
  for _, line in ipairs(blocky(pending.name)) do say(rgb(pending.colour, line)) end
  say(dim(details))
  pending = nil
  for _, t in ipairs(titles) do piece(t) end
  titles = {}
end)

-- A piece goes into the log once it has played for 30 s on the same station, so skipping
-- through stations logs nothing. The log is a tab-separated file in the XDG data folder.
local LOG = (os.getenv("XDG_DATA_HOME") or (os.getenv("HOME") .. "/.local/share")) .. "/radio/log.tsv"
local timer = nil
local watching = nil   -- {station, title} on the 30 s watch, and the piece printed last
local logged = nil     -- {station, title} of the last row, so a piece is written once

local function log(station, title)
  os.execute("mkdir -p '" .. LOG:match("(.*)/") .. "'")
  local new = io.open(LOG, "r") == nil
  local f = io.open(LOG, "a")
  if not f then return end
  if new then f:write("date\ttime\tstation\tpiece\n") end
  f:write(os.date("%Y-%m-%d\t%H:%M") .. "\t" .. station .. "\t" .. title .. "\n")
  f:close()
end

local function on_air()
  local pos = mp.get_property_number("playlist-pos", 0)
  return mp.get_property("playlist/" .. pos .. "/title") or ""
end

local function listen(station, title)
  if timer then timer:kill() end
  watching = { station = station, title = title }
  timer = mp.add_timeout(30, function()
    if logged and logged.station == station and logged.title == title then return end
    logged = watching
    log(station, title)
  end)
end

-- The rules that decide what a piece is live in radio_core.py, shared with the phone's
-- server so both boxes agree: it undoes the double encoding Venice sends, drops the
-- {+info: site} advertisement, and calls a station's own announcement a banner. One
-- short-lived python3 per title and per menu refresh, against a title every few minutes.
local function core_path()
  local p = os.getenv("RADIO_CORE")
  if p and p ~= "" then return p end
  return mp.find_config_file("radio_core.py") or (os.getenv("HOME") .. "/.settings/Radio/radio_core.py")
end

local CORE, warned = core_path(), false
local utils = mp.utils or require "mp.utils"   -- mpv 0.42 keeps these functions in the module only

local function ask_core(args, stdin)
  local cmd = { "python3", CORE }
  for _, a in ipairs(args) do cmd[#cmd + 1] = a end
  local r = utils.subprocess({
    args = cmd, stdin_data = stdin or "", capture_stdout = true,
    playback_only = false,
  })
  local answer = r and r.status == 0 and utils.parse_json(r.stdout or "")
  if not answer and not warned then
    warned = true
    say(dim("radio_core.py unreachable: showing titles as they come"))
  end
  return answer
end

-- One path for a title from any source: clean it, drop the station's own announcements,
-- and ignore the announcement mpv repeats after a banner. Without python3 the stream is
-- unaffected, so the raw title stays on screen rather than nothing.
local function new_title(raw)
  if not raw or raw == "" then return end
  local station = on_air()
  local answer = ask_core({ "clean", station }, raw)
  local title, is_banner = raw, false
  if answer then title, is_banner = answer.title or "", answer.banner and true or false end
  if is_banner or title == "" then return end
  if watching and watching.station == station and watching.title == title then return end
  listen(station, title)
  shown = title
  status()
  if pending then table.insert(titles, title) else piece(title) end
end

-- c: channels menu. The core reads each stream's icy StreamTitle chunk, all stations at
-- once (~1 s for eight). It previews without switching; <  > then moves to the station
-- you picked.

-- Stations are picked by code: 1-8 for the first eight, then letters (skipping
-- keys this script or mpv needs). Beyond that stations are <  > only. The menu
-- prints each station's code, so a longer list stays fully reachable.
local LETTERS = { "a", "b", "d", "f", "g", "h", "j", "k", "m", "n", "t", "u", "v", "x", "y", "z" }

local function code_for(i)
  if i <= 8 then return tostring(i) end
  return LETTERS[i - 8]
end

-- The channels menu is a modal: it opens on the terminal's alternate screen, the
-- same mechanism vim uses, so the log stays untouched behind it and comes back
-- unchanged when a key closes the menu. Keys act through mpv's bindings: a code
-- jumps, c or Esc just leaves.
local modal = false

local function modal_off()
  if not modal then return end
  modal = false
  io.write("\27[?1049l")
  io.flush()
end

local function jump(i)
  if i <= mp.get_property_number("playlist-count", 0) then
    modal_off()
    mp.set_property("playlist-pos", i - 1)
  end
end

local function channels()
  local n = mp.get_property_number("playlist-count", 0)
  if n == 0 then return end
  local pos = mp.get_property_number("playlist-pos-1", 1)
  modal = true
  io.write("\27[?1049h\27[2J\27[H")
  io.flush()
  say(dim("checking " .. n .. " channels…"))
  local args = { "sniff" }
  for i = 0, n - 1 do
    args[#args + 1] = mp.get_property("playlist/" .. i .. "/title") or ""
    args[#args + 1] = mp.get_property("playlist/" .. i .. "/filename", "")
  end
  local answer = ask_core(args)
  local rows = answer and answer.titles or {}
  for i = 1, n do
    local name = mp.get_property("playlist/" .. (i - 1) .. "/title") or "?"
    local colour = COLOURS[(i - 1) % #COLOURS + 1]
    local row = rows[i]
    local title = row and row.title
    say((i == pos and rgb("b3de69", "►") or " ") .. " " .. rgb(colour, string.format("%3s", code_for(i) or "") .. "  " .. name) ..
        dim("   ") .. (title and title ~= "" and title or dim("—")))
  end
  say(dim("press a code to jump there · c or Esc close"))
end

mp.add_key_binding("c", "channels", function()
  if modal then modal_off() else channels() end
end)
mp.add_key_binding("ESC", "close-menu", modal_off)

for i = 1, 8 do
  mp.add_key_binding(tostring(i), "station-" .. i, function() jump(i) end)
end
for k, key in ipairs(LETTERS) do
  mp.add_key_binding(key, "station-" .. (8 + k), function() jump(8 + k) end)
end

-- <  > keep mpv's wrapping playlist behaviour but also close the menu. The keys'
-- live-stream uses (seek) are pointless, so taking them over costs nothing.
mp.add_key_binding("<", "station-prev", function()
  modal_off()
  local n = mp.get_property_number("playlist-count", 1)
  mp.set_property("playlist-pos", (mp.get_property_number("playlist-pos", 0) - 1) % n)
end)
mp.add_key_binding(">", "station-next", function()
  modal_off()
  local n = mp.get_property_number("playlist-count", 1)
  mp.set_property("playlist-pos", (mp.get_property_number("playlist-pos", 0) + 1) % n)
end)

mp.register_event("end-file", function()
  if timer then timer:kill() end
  watching = nil   -- a new file announces its piece again, even the same one
end)

mp.observe_property("metadata/by-key/icy-title", "string", function(_, title) new_title(title) end)

-- Audiocdn, which serves Jazz24, leaves StreamTitle empty in most metadata chunks and
-- names the piece in a single one, and mpv can miss that chunk: the property then lags by
-- about a minute. The poll reads the stream the way the phone's server does, so the pane
-- catches up by itself. mpv's property stays the fast path, and new_title decides once
-- between the two, since both end in the same watch.
mp.add_periodic_timer(20, function()
  if modal or mp.get_property_bool("pause", false) then return end
  local pos = mp.get_property_number("playlist-pos", 0)
  local url = mp.get_property("playlist/" .. pos .. "/filename", "")
  if url == "" then return end
  local answer = ask_core({ "sniff", on_air(), url })
  local row = answer and answer.titles and answer.titles[1]
  if row and not row.banner then new_title(row.title) end
end)
