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

-- Venice double-encodes its StreamTitle (UTF-8 bytes encoded as UTF-8 again),
-- so accents arrive mangled: undo it by decoding two-byte sequences once more,
-- only when the tell-tale Ã (0xC3 0x83) appears in the string. Venice also
-- trails a {+info: site} advertisement onto some titles: that goes too.
local function unmangle(s)
  s = (s:gsub("%s*{%+info:[^}]*}", ""))
  if not s:find("\195\131", 1, true) then return s end
  return (s:gsub("[\194\195][\128-\191]", function(b)
    local c1, c2 = b:byte(1, 2)
    local cp = (c1 - 192) * 64 + (c2 - 128)
    if cp >= 128 and cp <= 255 then return string.char(cp) end
    return b
  end))
end

-- Radio Swiss announces itself between pieces and sends that announcement as the title:
-- "Radio Swiss Classic - www.radioswissclassic.ch". A title that names its own station or
-- carries a URL is a station banner rather than a piece, so it gets no line and no log row.
-- The piece around a banner keeps its own 30 s watch, and mpv then announces that piece
-- again; a title repeating the piece on watch is the same piece coming back, so it is
-- ignored too, and each piece prints and logs once.
local function banner(station, title)
  local t = title:lower():gsub("^%s+", "")
  local name = station:lower():gsub("[%(%)%.%%%+%-%*%?%[%]%^%$]", "%%%0")
  if t:find("^" .. name) then return true end
  return t:find("www%.") ~= nil or t:find("https?://") ~= nil
end

-- c: channels menu. A python probe reads each stream's icy StreamTitle chunk with
-- all stations sniffed concurrently (~4 s). It previews without switching;
-- <  > then moves to the station you picked.
local PY_SNIFF = [[
import sys, threading, urllib.request, re
def sniff(i, url, out):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={
            "User-Agent": "AlfDROID radio", "Icy-MetaData": "1"}), timeout=4)
        intv = int(r.headers.get("icy-metaint", "0") or 0)
        title = ""
        if intv:
            for _ in range(3):
                r.read(intv)
                ln = r.read(1)
                if not ln:
                    break
                blob = r.read(ln[0] * 16).rstrip(b"\0").decode("utf-8", "replace")
                m = re.search(r"StreamTitle='(.*?)';", blob) or re.search(r"StreamTitle='([^']*)'", blob)
                if m and m.group(1).strip():
                    title = m.group(1).strip()
                    break
        r.close()
        if not title:
            h = urllib.request.urlopen(urllib.request.Request(url, method="HEAD",
                headers={"User-Agent": "AlfDROID radio"}), timeout=3)
            title = (h.headers.get("icy-title") or "").strip()
        out[i - 1] = title
    except Exception:
        pass
urls = sys.argv[1:]
out = [""] * len(urls)
ts = [threading.Thread(target=sniff, args=(i, u, out), daemon=True) for i, u in enumerate(urls, 1)]
for t in ts:
    t.start()
for t in ts:
    t.join(6)
for i, t in enumerate(out, 1):
    print(f"{i}\t{t}")
]]

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
  local urls = {}
  for i = 0, n - 1 do urls[i + 1] = mp.get_property("playlist/" .. i .. "/filename", "") end
  local q = {}
  for i, u in ipairs(urls) do q[i] = string.format("%q", u) end
  local py = os.tmpname()
  local f = io.open(py, "w")
  f:write(PY_SNIFF)
  f:close()
  local out = io.popen("python3 " .. py .. " " .. table.concat(q, " ") .. " 2>/dev/null")
  local text = out and out:read("a") or ""
  if out then out:close() end
  os.remove(py)
  local titles_by = {}
  for line in text:gmatch("[^\n]+") do
    local i, t = line:match("^(%d+)\t(.*)$")
    if i and t then titles_by[tonumber(i)] = unmangle(t) end
  end
  for i = 1, n do
    local name = mp.get_property("playlist/" .. (i - 1) .. "/title") or "?"
    local colour = COLOURS[(i - 1) % #COLOURS + 1]
    local title = titles_by[i]
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

mp.observe_property("metadata/by-key/icy-title", "string", function(_, title)
  if not title or title == "" then return end
  title = unmangle(title)
  local station = on_air()
  if banner(station, title) then return end
  if watching and watching.station == station and watching.title == title then return end
  listen(station, title)
  shown = title   -- the bottom line follows the real pieces only, so a banner leaves it alone
  status()
  if pending then table.insert(titles, title) else piece(title) end
end)
