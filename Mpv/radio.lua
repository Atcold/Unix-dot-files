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
local GLYPHS = {
  a = {".##", "#.#", "###", "#.#"}, c = {"###", "#..", "#..", "###"}, d = {"##.", "#.#", "#.#", "##."},
  e = {"###", "#..", "##.", "###"}, f = {"###", "#..", "##.", "#.."}, g = {"###", "#..", "#.#", "###"},
  i = {"###", ".#.", ".#.", "###"}, l = {"#..", "#..", "#..", "###"}, m = {"###", "###", "#.#", "#.#"},
  n = {"###", "#.#", "#.#", "#.#"}, o = {"###", "#.#", "#.#", "###"}, p = {"###", "#.#", "###", "#.."},
  q = {"###", "#.#", "###", "..#"}, r = {"###", "#.#", "##.", "#.#"}, s = {"###", "#..", "..#", "###"},
  t = {"###", ".#.", ".#.", ".#."}, u = {"#.#", "#.#", "#.#", "###"}, v = {"#.#", "#.#", "#.#", ".#."},
  w = {"#.#", "#.#", "###", "###"}, x = {"#.#", ".#.", ".#.", "#.#"}, [" "] = {"...", "...", "...", "..."},
}
local HALF = { ["##"] = "█", ["#."] = "▀", [".#"] = "▄", [".."] = " " }

local function blocky(word)
  word = word:lower():gsub("[^%a ]", "")
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

local function status(hex)
  local r, g, b = tonumber(hex:sub(1, 2), 16), tonumber(hex:sub(3, 4), 16), tonumber(hex:sub(5, 6), 16)
  mp.set_property("term-status-msg", string.format(
    "\27[38;2;%d;%d;%dm♪ ${metadata/by-key/icy-title}\27[0m  \27[2m${time-pos}  ·  vol ${volume}%%\27[0m", r, g, b))
end

local pending = nil
local started = false   -- the header waits until the bitrate is known
local titles = {}     -- pieces announced before the header, printed after it


mp.register_event("file-loaded", function()
  local pos = mp.get_property_number("playlist-pos-1", 1)
  local count = mp.get_property_number("playlist-count", 1)
  local name = mp.get_property("playlist/" .. (pos - 1) .. "/title") or mp.get_property("media-title", "")
  pending = { name = name, pos = pos .. "/" .. count, colour = COLOURS[(pos - 1) % #COLOURS + 1] }
  status(pending.colour)
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
    say("<  >" .. dim("  station   ·   ") .. "9  0" .. dim("  volume   ·   ") .. "space" .. dim("  pause   ·   ") .. "q" .. dim("  quit"))
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

local function log(station, title)
  os.execute("mkdir -p '" .. LOG:match("(.*)/") .. "'")
  local new = io.open(LOG, "r") == nil
  local f = io.open(LOG, "a")
  if not f then return end
  if new then f:write("date\ttime\tstation\tpiece\n") end
  f:write(os.date("%Y-%m-%d\t%H:%M") .. "\t" .. station .. "\t" .. title .. "\n")
  f:close()
end

local function listen(title)
  if timer then timer:kill() end
  local pos = mp.get_property_number("playlist-pos", 0)
  local station = mp.get_property("playlist/" .. pos .. "/title") or ""
  timer = mp.add_timeout(30, function() log(station, title) end)
end

-- Venice double-encodes its StreamTitle (UTF-8 bytes encoded as UTF-8 again),
-- so accents arrive mangled: undo it by decoding two-byte sequences once more,
-- only when the tell-tale Ã (0xC3 0x83) appears in the string.
local function unmangle(s)
  if not s:find("\195\131", 1, true) then return s end
  return (s:gsub("[\194\195][\128-\191]", function(b)
    local c1, c2 = b:byte(1, 2)
    local cp = (c1 - 192) * 64 + (c2 - 128)
    if cp >= 128 and cp <= 255 then return string.char(cp) end
    return b
  end))
end

mp.register_event("end-file", function() if timer then timer:kill() end end)

mp.observe_property("metadata/by-key/icy-title", "string", function(_, title)
  if not title or title == "" then return end
  title = unmangle(title)
  listen(title)
  if pending then table.insert(titles, title) else piece(title) end
end)
