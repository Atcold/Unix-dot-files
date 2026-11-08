#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tplink-cloud-api"]
# ///
"""spark: power a machine on a Kasa smart plug on and off, from anywhere.

The plug is switched through TP-Link's cloud, as the Kasa app does it, so this
works outside the LAN too. The machine itself is reached over the tailnet.

  spark status          plug state and power; the machine on the tailnet; the service and its tunnel
  spark wattage         live wattage chart, redrawn every second ([q] quits)
  spark on [--wait]     power on; --wait: until ssh answers
  spark off             clean shutdown over ssh, then plug off
  spark restart         off, then on --wait
  spark models          the model store on the Spark: org/name, size, what is served
  spark serving         what runs on the Spark: state, uptime, image, forwarded port
  spark serve           serve a model: start it, open its tunnel, wait for its API   [<model> [server]]
  spark unserve         stop a served model, close its tunnel                        [<model> [server]]
  spark setup           names in ~/.config/spark/config.toml, login in the Keychain
"""
# The block above `"""` is inline script metadata (PEP 723): `uv run --script`
# reads it and runs the file in a cached environment with those dependencies.
import asyncio
import json
import os
import re
import textwrap
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path.home() / ".config/spark/config.toml"
# Fallbacks for a missing key: config.toml is the record of everything configurable.
# model names the default model; [models] maps each model to ["server", local, remote],
# or a list of those triples when one model is served several ways. The container name
# is derived: server + "-" + model with / written as --.
DEFAULTS = {"plug": "AlfSPARK", "host": "alfspark", "keychain": "tplink-cloud",
            "model": "nvidia/Qwen3.8-Flash-Next-FP4-Local",
            # the hf CLI on the host, from voice-lab's venv: spark models shells out to it
            "hf": "~/voice-lab/hf/.venv/bin/hf",
            "models": {"nvidia/Qwen3.8-Flash-Next-FP4-Local": ["vllm", 8000, 8000]}}
RUNNING_W = 10  # above this, the machine is running (AlfSPARK idles at ~24 W)
STANDBY_W = 5   # below this, it is shut down (its standby draw is ~1.4 W)

# Colour as in tg-mail's term.py: skipped when stdout is not a terminal or NO_COLOR is set,
# so piping the output gives text, not escape codes
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(s, *codes):
    return f"\033[{';'.join(codes)}m{s}\033[0m" if USE_COLOR else s


def bold(s): return c(s, "1")
def dim(s): return c(s, "2")
def red(s): return c(s, "1", "31")
def green(s): return c(s, "1", "32")
def yellow(s): return c(s, "33")
def cyan(s): return c(s, "1", "36")
def accent(s): return c(s, "1", "35")
def ok(msg): print(green("✓ ") + msg)
def err(msg): sys.exit(red("✗ ") + msg)


def config():
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        loaded = tomllib.loads(CONFIG.read_text())
        # [models] merges into the built-in, so the file may list only extra models
        if "models" in loaded:
            loaded["models"] = {**DEFAULTS["models"], **loaded["models"]}
        cfg.update(loaded)
    return cfg


def keychain_login(service):
    """The TP-Link email and password that `spark setup` stored in the Keychain."""
    item = subprocess.run(["security", "find-generic-password", "-s", service],
                          capture_output=True, text=True)
    if item.returncode != 0:
        err(f"No Keychain item {bold(service)}: run `spark setup` first.")
    # The item's attributes include a line like:  "acct"<blob>="me@example.com"
    email = next(l.split('"')[3] for l in item.stdout.splitlines() if '"acct"' in l)
    read = ["security", "find-generic-password", "-s", service, "-w"]
    secret = subprocess.run(read, capture_output=True, text=True)
    # 36 = errSecInteractionNotAllowed: the Keychain is locked, as it is in a fresh ssh session
    if secret.returncode == 36 and sys.stdin.isatty():
        print(dim("Keychain locked in this session: unlocking (the Mac's login password)"))
        subprocess.run(["security", "unlock-keychain"])
        secret = subprocess.run(read, capture_output=True, text=True)
    if secret.returncode != 0:
        err(f"Can't read the TP-Link password from the Keychain (security exit {secret.returncode}); "
            f"over ssh, run {cyan('security unlock-keychain')} first.")
    return email, secret.stdout.strip()


async def find_plug(cfg):
    from tplinkcloud import TPLinkDeviceManager
    email, password = keychain_login(cfg["keychain"])
    manager = TPLinkDeviceManager(email, password,
                                  mfa_callback=lambda: input("TP-Link code: "))
    await manager.async_init()
    plug = await manager.find_device(cfg["plug"])
    if plug is None:
        err(f"Plug {bold(cfg['plug'])} not found in the TP-Link account.")
    return plug


async def watts(plug):
    # On the HS110 the library's `power_mw` holds the plug's `power` key: watts
    return (await plug.get_power_usage_realtime()).power_mw


def tailnet(host):
    """The status column of `tailscale status` for host: '-', 'active; direct …', 'offline, …'."""
    try:
        out = subprocess.run(["tailscale", "status"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return "tailscale is not on the PATH"
    for line in out.splitlines():
        fields = line.split()  # address, name, user, OS, status…
        if len(fields) > 4 and fields[1] == host:
            return " ".join(fields[4:])
    return "not on the tailnet"


def ssh_up(host):
    # BatchMode: never prompt, just fail; a short timeout keeps the polling brisk
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", host, "true"],
                          capture_output=True).returncode == 0


def tunnel(port):
    """('listen-port', 'target') of the ssh -L tunnel on the port; None if nobody listens,
    a name if something other than ssh holds the port."""
    # -t: PIDs only; then ps gives the defining command line, as shown in the lesson
    r = subprocess.run(["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                       capture_output=True, text=True)
    if not r.stdout.split():
        return None
    cmd = subprocess.run(["ps", "-o", "command=", "-p", r.stdout.split()[0]],
                         capture_output=True, text=True).stdout.split()
    if not cmd or cmd[0].split("/")[-1] != "ssh" or "-L" not in cmd:
        return cmd[0].split("/")[-1] if cmd else "unknown"
    return cmd[cmd.index("-L") + 1], cmd[-1]


def mac_name():
    # Each Mac signs its own listener: the name comes from the machine, never the config,
    # which is shared through Dropbox
    return subprocess.run(["scutil", "--get", "LocalHostName"],
                          capture_output=True, text=True).stdout.strip() or "Mac"


def model_ready(port):
    # /health answers empty with exit 0 once vLLM serves; --max-time keeps status brisk
    return subprocess.run(["curl", "-s", "--max-time", "3", f"http://127.0.0.1:{port}/health"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def dur(secs):
    # Spoken units: 264 reads as nobody, "4 min 24 s" reads as how long
    m, s = divmod(int(secs), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def uptime_text(started):
    # docker inspect gives the start time in RFC 3339 UTC, nanoseconds included;
    # fromisoformat stops at microseconds, so trim to the 26 characters it can read
    t = datetime.fromisoformat(started[:26]).replace(tzinfo=timezone.utc)
    d, rem = divmod(int((datetime.now(timezone.utc) - t).total_seconds()), 86400)
    h, m = divmod(rem // 60, 60)
    return f"{d} d {h} h {m} m" if d else f"{h} h {m} m"


def dumb_plot(rows, title):
    """One gnuplot dumb-terminal render of (epoch, watts) pairs, sized to the screen."""
    cols, _ = shutil.get_terminal_size((80, 20))
    # gnuplot prints time as UTC: shift the epochs by the Mac's own offset, so the
    # axis says wall-clock time, which is what the numbers on a home gadget should be
    off = datetime.now().astimezone().utcoffset().total_seconds()
    # Colour only on a terminal (same rule as the rest): curve in Set3 blue, axis frame dim
    term = (f"set terminal dumb size {cols},14 ansirgb; set border lc rgb '#555555';"
            if USE_COLOR else f"set terminal dumb size {cols},14;")
    p = subprocess.run(
        ["gnuplot", "-e",
         term + " set datafile separator ','; unset key;"
                " set timefmt '%s'; set xdata time; set format x '%H:%M:%S'; set yrange [0:*];"
                " set style line 1 lc rgb '#80b1d3' lw 2;"
                " plot '-' using 1:2 with lines ls 1"],
        input="\n".join(f"{t + off:.0f},{w}" for t, w in rows),
        capture_output=True, text=True)
    if p.returncode:
        err("gnuplot: " + p.stderr.strip())
    # The dumb terminal cannot put its key outside the box: print the title above the chart
    return title + "\n" + p.stdout


async def live(cfg):
    from collections import deque
    import select
    import termios
    import tty
    plug = await find_plug(cfg)
    # Keep only the newest samples that fit: one per column, so the chart scrolls
    # instead of squeezing the whole history into the same width
    samples = deque(maxlen=max(30, shutil.get_terminal_size((80, 20)).columns - 12))
    # cbreak mode so a lone q quits without Return; the terminal is restored either way
    fd = sys.stdin.fileno() if sys.stdin.isatty() else None
    old = termios.tcgetattr(fd) if fd is not None else None
    if fd is not None:
        tty.setcbreak(fd)
    try:
        while True:
            w = await watts(plug)
            samples.append((time.time(), w))
            # Cursor home + erase-to-end instead of `clear`: the chart repaints in place
            # instead of wiping the screen each second, which flashed
            sys.stdout.write("\033[H\033[J")
            print(dumb_plot(list(samples), accent(f"{w:.1f} W now ([q] quits)")).rstrip())
            if fd is not None:
                # select waits up to a second for a keystroke: it is the tick and the q reader
                if select.select([sys.stdin], [], [], 1.0)[0] and sys.stdin.read(1).lower() == "q":
                    break
            else:
                await asyncio.sleep(1.0)
    finally:
        if old is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print()


async def status(cfg):
    plug = await find_plug(cfg)
    on = await plug.is_on()
    w = await watts(plug) if on else 0.0
    if not on:
        state = red("unpowered")
    elif w > RUNNING_W:
        state = green("running")
    elif w < STANDBY_W:
        state = yellow("shut down")
    else:
        state = yellow("starting or stopping")
    path = tailnet(cfg["host"])
    path = (green(path) if "direct" in path else yellow(path) if "relay" in path
            else red(path) if "offline" in path or "not on" in path else dim(path))
    print(f"{dim('plug')}    {bold(cfg['plug'])}: {green('on') if on else red('off')}, "
          f"{accent(f'{w:.1f} W')} -> {bold(cfg['host'])} {state}")
    print(f"{dim('tailnet')} {bold(cfg['host'])}: {path}")
    if on and w > RUNNING_W:
        # status answers one question: is the default model being served? What is
        # stopped is detail work for spark serving. With no service there is no pipe
        # to hold and no API to ask: service, tunnel, and api all report none.
        p = pick(cfg)
        if p is None:
            print(yellow(f"⚠ default model {bold(cfg['model'])} has no [models] triple"))
            return
        model, server, local, remote, name = p
        # One ssh asks Docker both states; the start timestamp gives d/h/m uptime,
        # finer than docker ps's coarse string. BatchMode: no password can block status.
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", cfg["host"],
                            f"docker inspect -f '{{{{.State.Status}}}} {{{{.State.StartedAt}}}}' "
                            f"{name}"],
                           capture_output=True, text=True)
        state = "" if r.returncode else r.stdout.strip().partition(" ")[0]
        if state != "running":
            for label in ("service", "tunnel", "api"):
                print(f"{dim(label.ljust(7))} {dim('none')}")
            return
        started = r.stdout.strip().partition(" ")[2]
        print(f"{dim('service')} {bold(server)} {dim(f'(model {model})')}: "
              f"{green(f'running {uptime_text(started)}')}")
        # Tunnel and API are two facts on two lines: the pipe, then what answers at its end
        t = tunnel(local)
        pair = f"{bold(mac_name())}:{accent(local)} {dim('→')} {bold(cfg['host'])}:{accent(remote)}"
        if isinstance(t, tuple):
            print(f"{dim('tunnel')}  {pair} {green('open')}")
        elif isinstance(t, str):
            print(f"{dim('tunnel')}  {pair} {red(f'held by {t}, not ssh')}")
        else:
            print(f"{dim('tunnel')}  {pair} {red('closed')}")
        api = green("ready") if model_ready(local) else red("no answer")
        print(f"{dim('api')}     {bold(mac_name())}:{accent(local)}: {api}")


async def power_on(cfg, wait):
    plug = await find_plug(cfg)
    if await plug.is_on():
        if await watts(plug) > STANDBY_W:
            ok(f"{bold(cfg['host'])} is already running")
            return
        # Plug on but machine shut down: it boots only when power comes back
        await plug.power_off()
        await asyncio.sleep(5)
    await plug.power_on()
    ok(f"plug {bold(cfg['plug'])}: {green('on')}")
    if wait:
        start = time.monotonic()
        print(dim(f"waiting for ssh {cfg['host']}…"), flush=True)
        while not ssh_up(cfg["host"]):
            if time.monotonic() - start > 300:
                err(f"{bold(cfg['host'])} not answering ssh after 5 min")
            await asyncio.sleep(1)
        ok(f"{bold(cfg['host'])} up after {accent(f'{time.monotonic() - start:.0f} s')}")


async def power_off(cfg):
    plug = await find_plug(cfg)
    if await plug.is_on() and await watts(plug) > STANDBY_W:
        print(dim(f"shutting down {cfg['host']} (sudo asks for its password)"))
        subprocess.run(["ssh", "-t", cfg["host"], "sudo poweroff"])
        # Cut power only once the draw has dropped to standby: never under a running machine
        start = time.monotonic()
        print(dim("waiting for the draw to drop to standby…"), flush=True)
        while await watts(plug) > STANDBY_W:
            if time.monotonic() - start > 180:
                err(f"{bold(cfg['host'])} still drawing power after 3 min; plug left {green('on')}")
            await asyncio.sleep(3)
        ok(f"{bold(cfg['host'])} shut down after {accent(f'{time.monotonic() - start:.0f} s')}")
    await plug.power_off()
    ok(f"plug {bold(cfg['plug'])}: {red('off')}")


async def restart(cfg):
    await power_off(cfg)
    await asyncio.sleep(5)
    await power_on(cfg, wait=True)


def ssh_docker(cfg, *docker_cmd):
    # Plain docker over ssh works for this account on the Spark; no sudo needed
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", cfg["host"],
                           "docker", *docker_cmd], capture_output=True, text=True)


def container_name(server, model):
    # The service's name is derived, never typed: server- + model with / written --
    return f"{server}-{model.replace('/', '--')}"


def model_rows(cfg, model):
    """[server, local, remote] triples for a model: the table holds one triple, or a
    list of them when one model is served several ways."""
    v = cfg["models"].get(model)
    if v is None:
        return None
    triples = v if v and isinstance(v[0], (list, tuple)) else [v]
    return [[str(t[0]), int(t[1]), int(t[2])] for t in triples]


def pick(cfg, model=None, server=None):
    """(model, server, local, remote, container) for what to serve; None if the model
    is not in [models] or the server does not serve it."""
    model = model or cfg["model"]
    rows = model_rows(cfg, model)
    if rows is None:
        return None
    if server is None:
        triple = rows[0]
    else:
        triple = next((t for t in rows if t[0] == server), None)
        if triple is None:
            return None
    return model, triple[0], triple[1], triple[2], container_name(triple[0], model)


def known_services(cfg):
    """{container: (model, server, local, remote)} for every [models] triple."""
    out = {}
    for model in cfg["models"]:
        for srv, local, remote in model_rows(cfg, model) or []:
            out[container_name(srv, model)] = (model, srv, local, remote)
    return out


def unknown_model(cfg, model, server):
    have = ", ".join(sorted(cfg["models"]))
    if server:
        head = f"{bold(server)} does not serve {bold(model)} in [models]"
    else:
        head = f"{bold(model)} is not in {bold('[models]')} in the config"
    return f"{head}; the table serves {dim(have)}"


def serving(cfg):
    if not ssh_up(cfg["host"]):
        err(f"{bold(cfg['host'])} is not answering ssh: {cyan('spark on')} first")
    # Quoted for the remote shell: the \t stays a two-character escape that docker expands
    r = ssh_docker(cfg, "ps", "-a", "--format",
                   "'{{.Names}}\\t{{.State}}\\t{{.Status}}\\t{{.Image}}'")
    if r.returncode != 0:
        err(f"docker ps: {r.stderr.strip().splitlines()[-1]}")
    rows = sorted((l.split("\t") for l in r.stdout.splitlines() if l.strip()))
    if not rows:
        print(dim(f"nothing on {cfg['host']}"))
        return
    known = known_services(cfg)
    p = pick(cfg)
    dflt = p[4] if p else None
    if dflt and dflt not in known:
        print(yellow(f"⚠ the config's default {bold(dflt)} matches no [models] triple"))
    width = max(len(n) for n, *_ in rows) + 2
    for name, state, status, image in rows:
        tag = known.get(name)
        label = (bold(name) + (dim("  (default)") if name == dflt else "")) if tag else dim(name)
        st = green(state) if state == "running" else red(state)
        fwd = (dim(f"  :{tag[3]}") + (dim(f" (Mac :{tag[2]})") if tag[2] != tag[3] else "")
               if tag else dim("  not in [models]"))
        print(f"  {label}{' ' * (width - len(name))}{st} {dim(status)}  {dim(image)}{fwd}")


def serve(cfg, model=None, server=None):
    p = pick(cfg, model, server)
    if p is None:
        err(unknown_model(cfg, model or cfg["model"], server))
    model, server, local, remote, name = p
    if not ssh_up(cfg["host"]):
        err(f"{bold(cfg['host'])} is not answering ssh: {cyan('spark on')} first")
    state = ssh_docker(cfg, "inspect", "-f", "{{.State.Status}}", name)
    if state.returncode != 0:
        err(f"{bold(name)} on {cfg['host']}: {state.stderr.strip().splitlines()[-1]} "
            f"({cyan('spark serving')} shows what exists)")
    if state.stdout.strip() == "running":
        ok(f"{bold(name)} already running")
    else:
        started = ssh_docker(cfg, "start", name)
        if started.returncode != 0:
            err(f"docker start: {started.stderr.strip().splitlines()[-1]}")
        ok(f"{bold(name)}: {green('started')}")
    if not isinstance(tunnel(local), tuple):
        # -fN backgrounds a connection with no commands: forwarding is its only job,
        # and ExitOnForwardFailure makes a lost port fail the ssh instead of idling
        r = subprocess.run(["ssh", "-fN", "-o", "ExitOnForwardFailure=yes",
                            "-o", "ServerAliveInterval=30", "-L",
                            f"127.0.0.1:{local}:127.0.0.1:{remote}", cfg["host"]],
                           capture_output=True, text=True)
        if r.returncode != 0:
            err(f"tunnel: {r.stderr.strip()}")
        ends = f":{local}" if local == remote else f":{local} → :{remote}"
        ok(f"tunnel {ends} {green('open')}")
    else:
        ok(f"tunnel :{local} already open")
    if server not in STAGE_PARSER:  # only a server spark can read is waited for
        ok(f"{bold(name)} up; {bold(server)} has no health check spark knows, "
           f"{cyan('spark serving')} to see state")
        return
    # vLLM's opening banner (block art, version, model) is the log's first thing:
    # show it as soon as it lands, so the load below is clearly this server's
    for _ in range(20):
        head = container_log(cfg, name, tail=8)
        art = [l for l in head.splitlines()[:8] if re.search(r"[▀▄█]", l)]
        if len(art) >= 3:  # the block letters have landed; their neighbours are noise
            for line in art:
                print("  " + accent(re.sub(r"^.*\]\s?", "", line)))
            break
        time.sleep(1)
    # One line per phase, kept on screen as it completes: the server's own parser turns
    # the log into a percentage and a stage word, and a new phase starts a fresh line.
    # The log is re-read every 5 s; the current line redraws every half second.
    parse = STAGE_PARSER[server]
    start, tick, shown, log_at = time.monotonic(), 0, 0, 0.0
    phase, pct, stage = "waiting", None, "waiting for the first log line"
    while not model_ready(local):
        now = time.monotonic()
        if now - start > 900:
            err(f"API not ready after {dur(900)}: {cyan('spark status')} to see where it stands")
        if now - log_at >= 5:
            new_phase, new_pct, new_stage = parse(cfg, name)
            if new_phase != phase and shown:  # freeze the finished line over the old
                # one (padded as wide, so no debris of the longer bar line survives)
                print(f"\r{accent('✓')} {dim(stage)}  {accent(dur(now - start))}"
                      .ljust(max(shown, 78)))
                shown = 0
            phase, pct, stage = new_phase, new_pct, new_stage
            log_at = now
        timer = accent(dur(now - start))
        if pct is not None:
            cells = pct // 5
            text = (f"  {accent('█' * cells + '░' * (20 - cells))} {accent(f'{pct:3d}%')} "
                    f"{dim(stage)}  {timer}")
        else:
            spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[tick % 10]
            text = f"  {accent(spin)} {dim(stage)}  {timer}"
        print("\r" + text.ljust(max(shown, 78)), end="", flush=True)
        shown, tick = len(text), tick + 1
        time.sleep(0.5)
    if shown:  # the last phase closes with the ready line; nothing is erased
        print(f"\r{accent('✓')} {dim(stage)}  {accent(dur(time.monotonic() - start))}"
              .ljust(max(shown, 78)))
    ok(f"API ready after {accent(dur(time.monotonic() - start))}")


def unserve(cfg, model=None, server=None):
    p = pick(cfg, model, server)
    if p is None:
        err(unknown_model(cfg, model or cfg["model"], server))
    model, server, local, remote, name = p
    if not ssh_up(cfg["host"]):
        ok(f"{bold(cfg['host'])} is already down")
        return
    state = ssh_docker(cfg, "inspect", "-f", "{{.State.Status}}", name)
    if state.returncode != 0:
        err(f"{bold(name)} on {cfg['host']}: {state.stderr.strip().splitlines()[-1]}")
    if state.stdout.strip() == "running":
        stopped = ssh_docker(cfg, "stop", name)
        if stopped.returncode != 0:
            err(f"docker stop: {stopped.stderr.strip().splitlines()[-1]}")
        ok(f"{bold(name)}: {red('stopped')}")
    else:
        ok(f"{bold(name)} already stopped")
    # The tunnel only exists to forward this service's pair, so unserve closes it —
    # but only when the listener really is this service's ssh, never someone else's
    held = tunnel(local)
    if isinstance(held, tuple):
        spec, target = held
        if spec == f"127.0.0.1:{local}:127.0.0.1:{remote}" and target == cfg["host"]:
            pid = subprocess.run(["lsof", "-nP", "-t", f"-iTCP:{local}", "-sTCP:LISTEN"],
                                 capture_output=True, text=True).stdout.split()[0]
            subprocess.run(["kill", pid])
            ok(f"tunnel :{local} {red('closed')}")
        else:
            ok(f"tunnel :{local} left open: not this service's ({dim(f'-L {spec} → {target}')})")
    elif isinstance(held, str):
        ok(f"tunnel :{local} left alone: {held} holds the port, not ssh")


def container_log(cfg, name, tail=None):
    # docker logs writes to stderr, so ssh_docker's stdout alone is empty: merge both.
    # The Spark's docker is too old for --no-log-prefix; strip the stamp and colour here.
    r = ssh_docker(cfg, "logs", *(["--tail", str(tail)] if tail else []), name)
    out = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
    return re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?", "", out, flags=re.M)


def vllm_b12x_stage(cfg, name):
    """(phase, percent or None, what it is doing) for the vLLM/B12X services. Each phase
    names itself in the log; the newest match wins, so the lines below are the timeline
    itself, nothing invented. A new phase id lets the caller start a fresh output line."""
    lines = [l.strip() for l in container_log(cfg, name).splitlines() if l.strip()]
    best = (-1, "waiting", None, "waiting for the first log line")
    for i, line in enumerate(lines):
        m = re.search(r"checkpoint shards: (\d+)/(\d+) shards routed, ([\d.]+) GB", line)
        if m:  # main weights and the draft model route separately: totals tell them apart
            cand = (i, f"route{m[2]}", 100 * int(m[1]) // max(int(m[2]), 1),
                    f"routing shards {m[1]}/{m[2]}, {m[3]} GB")
        elif "store kv cache" in line or "GPU KV cache size" in line:
            cand = (i, "kv", None, "allocating the KV cache")
        elif "Capturing model for speculator" in line:
            cand = (i, "spec", None, "warming up the speculator draft")
        elif "Capturing prefill CUDA graphs" in line:
            cand = (i, "cap-pre", None, "compiling prefill CUDA graphs")
        elif "Capturing decode CUDA graphs" in line:
            cand = (i, "cap-dec", None, "compiling decode CUDA graphs")
        elif "Capturing CUDA graphs" in line:
            cand = (i, "cap", None, "compiling CUDA graphs")
        elif "Started server process" in line or "Route: /v1" in line:
            cand = (i, "api", None, "starting the API server")
        else:
            continue
        if i > best[0]:
            best = cand
    return best[1:]


def generic_stage(cfg, name):
    """Unknown services get their plain newest log line, no percentage invented."""
    lines = [l.strip() for l in container_log(cfg, name, tail=3).splitlines() if l.strip()]
    return None, None, (lines[-1][:52] if lines else "waiting for the first log line")


# Each kind of server knows how to read its own startup log
STAGE_PARSER = {"vllm": vllm_b12x_stage}


def served_models(cfg):
    """Model ids the running containers were launched to serve, read off Config.Cmd."""
    served = set()
    names = ssh_docker(cfg, "ps", "--format", "{{.Names}}").stdout.split()
    for name in names:
        # quoted: the format has a space, and ssh re-joins the words for the remote shell
        raw = ssh_docker(cfg, "inspect", "-f", "'{{json .Config.Cmd}}'", name).stdout
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            continue
        # vLLM takes the id as the value of --model, or as the bare first argument
        # (["serve", "nvidia/..."]); either way it is the first token with a slash
        i = args.index("--model") + 1 if "--model" in args else 0
        id_ = next((a for a in args[i:] if "/" in a and not a.startswith("-")), None)
        if id_:
            served.add(id_)
    return served


def models(cfg):
    if not ssh_up(cfg["host"]):
        err(f"{bold(cfg['host'])} is not answering ssh: {cyan('spark on')} first")
    # The remote shell expands the ~ of the hf path
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", cfg["host"],
                        f"{cfg['hf']} cache ls --format json"], capture_output=True, text=True)
    if r.returncode != 0:
        err(f"hf cache ls: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.returncode} "
            f"(the hf path lives under {bold('hf')} in the config)")
    try:
        rows = json.loads(r.stdout)
    except json.JSONDecodeError:
        err(f"Unexpected output from {bold(cfg['hf'])}; check the {bold('hf')} key in the config")
    served = served_models(cfg)
    # The [models] table says which of these ids spark has a server ready for
    servers = {m: ", ".join(t[0] for t in model_rows(cfg, m) or []) for m in cfg["models"]}

    def weight(row):  # sort by bytes: 102.3G > 7.7G > 306.5M
        s, unit = row["size"][:-1], row["size"][-1]
        return float(s) * {"K": 1e-3, "M": 1, "G": 1e3, "T": 1e6}.get(unit, 1)

    w_id = max(len(row["repo_id"]) for row in rows) + 2
    w_sz = max(len(row["size"]) for row in rows)
    w_la = max(len(row["last_accessed"]) for row in rows)
    print("  " + dim("model".ljust(w_id) + "size".rjust(w_sz) + "  "
                     + "last access".ljust(w_la)))
    for row in sorted(rows, key=weight, reverse=True):
        rid = row["repo_id"]
        mark = (green("  ← served") if rid in served
                else accent(f"  · server: {servers[rid]}") if rid in servers else "")
        org, _, model = rid.partition("/")  # the author's hand, then the model
        print(f"  {cyan(org + '/')}{bold(model)}{' ' * (w_id - len(row['repo_id']))}"
              f"{accent(row['size'].rjust(w_sz))}  {dim(row['last_accessed'].ljust(w_la))}{mark}")
    print(dim(f"\n  {len(rows)} models on {cfg['host']}, from {cfg['hf']}"))


def setup(cfg):
    # Every question first, then the writes: a cancel half-way changes nothing
    plug = input(f"plug name [{cfg['plug']}]: ") or cfg["plug"]
    host = input(f"tailnet host [{cfg['host']}]: ") or cfg["host"]
    email = input("TP-Link email: ")
    # -U replaces an existing item; a final -w with no value makes `security` prompt for the password
    stored = subprocess.run(["security", "add-generic-password", "-U", "-s", cfg["keychain"],
                             "-a", email, "-w"])
    if stored.returncode != 0:
        err(f"Keychain item {bold(cfg['keychain'])} not updated; nothing written.")
    ok(f"TP-Link login in the Keychain, item {bold(cfg['keychain'])}")
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    # The file holds the whole picture: every setting, plus every model's serving rows
    rows = "\n".join(f'"{m}" = {json.dumps(cfg["models"][m])}' for m in cfg["models"])
    CONFIG.write_text(f'plug = "{plug}"\nhost = "{host}"\nkeychain = "{cfg["keychain"]}"\n'
                      f'model = "{cfg["model"]}"\nhf = "{cfg["hf"]}"\n\n[models]\n'
                      f'# model = [server, local, remote]: the Mac listens on local, the '
                      f'Spark serves on remote; the container name is derived from the pair\n'
                      f'{rows}\n')
    ok(f"wrote {bold(str(CONFIG))}")


# command: (what it does, [(option, what it does)]), as tg-mail's gmail lists them
COMMANDS = {
    "status": ("Plug state and power; the machine on the tailnet; the default model's service and its tunnel.", []),
    "wattage": ("Live terminal chart of the wattage, redrawn each second ([q] quits).", []),
    "on": ("Power on; boots the machine if it is shut down.",
           [("--wait", "Wait until ssh answers, and print the boot time.")]),
    "off": ("Clean shutdown over ssh, then plug off.", []),
    "restart": ("off, then on --wait.", []),
    "models": ("The model store on the Spark: org/name, size, last access, and what is served.", []),
    "serving": ("What runs on the Spark: state, uptime, image, forwarded port.", []),
    "serve": ("Serve a model: start its server, open its tunnel, wait for its API.", []),
    "unserve": ("Stop a served model, close its tunnel.", []),
    "setup": ("Once per machine: the plug, the machine, and your TP-Link login.", []),
}

# Positional slots shown in the Usage line, in order
USAGE = {"serving": "", "serve": "[<model> [server]]", "unserve": "[<model> [server]]"}


# What `spark <command> --help` adds below the one-line summary
DETAILS = {
    "setup": [
        "Asks four things, then writes:",
        f"  {cyan('plug name    ')}  the plug's name in the Kasa app {dim('(Enter:')} {accent('AlfSPARK')}{dim(')')}",
        f"  {cyan('tailnet host ')}  the machine's name on the tailnet {dim('(Enter:')} {accent('alfspark')}{dim(')')}",
        f"  {cyan('TP-Link email')}  the Kasa app's account",
        f"  {cyan('password     ')}  asked by macOS's {bold('security')}, twice",
        f"The names go to {bold('~/.config/spark/config.toml')}, the login to the Keychain",
        f"(item {bold('tplink-cloud')}). {dim('^C at any question writes nothing.')}",
    ],
}


def usage(command=""):
    """`spark`, `spark --help`, and `spark <command> --help`, coloured like gmail's."""
    width = max(len(n) for n in COMMANDS) + 2
    if command:
        what, options = COMMANDS[command]
        slots = f" {USAGE[command]}" if USAGE.get(command) else ""
        print("\n" + accent(f"spark {command}") + dim(slots + " — " + what))
        print("\n" + bold("Usage"))
        slots = USAGE.get(command, "").split() + (["[--options]"] if options else [])
        print("  " + cyan(f"spark {command}") + (dim(" " + " ".join(slots)) if slots else ""))
        if options:
            print("\n" + bold("Options"))
            for flag, does in options:
                print(f"  {cyan(flag.ljust(width))}{does}")
        if command in DETAILS:
            print("\n" + "\n".join("  " + line for line in DETAILS[command]))
    else:
        print("\n" + accent("spark") + dim(" — power a machine on a Kasa smart plug, from anywhere"))
        print(dim("The plug through TP-Link's cloud, the machine over the tailnet."))
        print("\n" + bold("Usage"))
        print("  " + cyan("spark") + dim(" <command> [--options]"))
        print("\n" + bold("Commands"))
        width = max(len(n) for n in COMMANDS) + 2
        for name, (what, options) in COMMANDS.items():
            # Arguments sit greyed right after the command name, as in a Usage line
            slot = dim(USAGE[name] + "  ") if USAGE.get(name) else ""
            # Wrap long descriptions at 80 columns, indented under the description
            col = 2 + width + (len(USAGE[name]) + 2 if USAGE.get(name) else 0)
            body = textwrap.fill(what, 80, initial_indent=" " * col,
                                 subsequent_indent=" " * col).lstrip()
            print(f"  {cyan(name.ljust(width))}{slot}{body}")
            for flag, does in options:
                print(f"      {cyan(flag)}  {does}")
    print()


def main():
    args = sys.argv[1:]
    positional = [a for a in args if not a.startswith("-")]
    command = positional[0] if positional else ""
    if command == "s":  # the one you type most
        command = "status"
    model = positional[1] if len(positional) > 1 else None  # optional model to serve
    server = positional[2] if len(positional) > 2 else None  # optional server for it
    # Bare spark and spark help list the commands; spark help <command> is --help
    if command == "help":
        usage(positional[1] if len(positional) > 1 and positional[1] in COMMANDS else "")
        return
    if not command or "-h" in args or "--help" in args:
        usage(command if command in COMMANDS else "")
        return
    if command not in COMMANDS:
        err(f"No command {bold(command)}. See {cyan('spark --help')}.")
    known = {flag for flag, _ in COMMANDS[command][1]}
    for flag in (a for a in args if a.startswith("-")):
        if flag not in known:
            err(f"{bold(flag)} is not an option of {cyan(f'spark {command}')}.")

    cfg = config()
    try:
        if command == "setup":
            setup(cfg)
        elif command == "status":
            asyncio.run(status(cfg))
        elif command == "wattage":
            asyncio.run(live(cfg))
        elif command == "on":
            asyncio.run(power_on(cfg, "--wait" in args))
        elif command == "off":
            asyncio.run(power_off(cfg))
        elif command == "restart":
            asyncio.run(restart(cfg))
        elif command == "models":
            models(cfg)
        elif command == "serving":
            serving(cfg)
        elif command == "serve":
            serve(cfg, model, server)
        elif command == "unserve":
            unserve(cfg, model, server)
    except (KeyboardInterrupt, EOFError):  # ^C, or ^D at a question: stop quietly
        print("\n" + dim("cancelled"))
        sys.exit(130)  # 128 + SIGINT, what a shell reports for ^C


if __name__ == "__main__":
    main()
