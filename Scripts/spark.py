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
  spark models          the model store on the Spark: number, org/name, size, what is served
  spark model <n|id>    what the Hub records for one of them: quantization, parameters, base model, licence
  spark serving         what runs on the Spark: state, uptime, image, forwarded port
  spark speed           tokens per second from a live probe: first token, prompt processing, generation   [<model> [server]]
  spark serve           serve a model: start it, open its tunnel, wait for its API   [<model> [server] | tunnel]
  spark unserve         stop a served model, close its tunnel                        [<model> [server] | tunnel]
  spark setup           names in ~/.config/spark/config.toml, login in the Keychain or a private file
"""
# The block above `"""` is inline script metadata (PEP 723): `uv run --script`
# reads it and runs the file in a cached environment with those dependencies.
import asyncio
import getpass
import json
import os
import re
import signal
import textwrap
import shutil
import socket
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path.home() / ".config/spark/config.toml"
# Off macOS there is no Keychain to hand the login to, so the TP-Link pair lives in
# a sibling file of its own, mode 600, kept out of config.toml which stays shareable
CREDENTIALS = CONFIG.with_name("credentials.toml")
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


def fact(label, value):
    # One aligned label and its value: status, model_info and speed all answer in this shape
    print(f"  {dim(label.ljust(13))}{value}")


def width(s):
    # printed characters, not bytes: a coloured line carries many more bytes than
    # it shows, and padding or wrapping counted on those wrote past the pane edge
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


def wrap(s, cols, initial_indent="", subsequent_indent=""):
    # textwrap.fill measures bytes too, which wraps a coloured line early: place
    # the words by hand and measure them as printed. Every colour helper closes
    # what it opens, so a line break between words never splits a style
    lines, cur, indent = [], "", initial_indent
    for word in s.split(" "):
        if cur and width(indent + cur + " " + word) > cols:
            lines.append(indent + cur)
            indent = subsequent_indent
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    lines.append(indent + cur)
    return "\n".join(lines)


def short(p):
    # Paths print as ~/... below the home: Termux spells its home
    # /data/data/com.termux/files/home, which buries the part that matters
    home = str(Path.home())
    s = str(p)
    return "~" + s[len(home):] if s.startswith(home + os.sep) else s


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


def login(cfg):
    """The TP-Link email and password that `spark setup` stored on this machine."""
    if sys.platform == "darwin":
        return keychain_login(cfg["keychain"])
    if not CREDENTIALS.exists():
        err(f"No {bold(short(CREDENTIALS))}: run {cyan('spark setup')} first.")
    creds = tomllib.loads(CREDENTIALS.read_text())
    try:
        return creds["email"], creds["password"]
    except KeyError:
        err(f"{bold(short(CREDENTIALS))} has no email or password: run {cyan('spark setup')} again.")


async def find_plug(cfg):
    from tplinkcloud import TPLinkDeviceManager
    email, password = login(cfg)
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
    """The status column of `tailscale status` for host: '-', 'active; direct …', 'offline, …'.

    On a device without the CLI (Termux, where Tailscale is an Android app rather
    than a command) the same question goes to the network stack itself: whether a
    route to the machine's ssh port exists from here. Auth is a different question,
    for the next line to answer."""
    try:
        out = subprocess.run(["tailscale", "status"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        try:
            socket.create_connection((host, 22), timeout=3).close()
            return "active; port 22 answers"
        except OSError:
            return "offline"
    for line in out.splitlines():
        fields = line.split()  # address, name, user, OS, status…
        if len(fields) > 4 and fields[1] == host:
            return " ".join(fields[4:])
    return "not on the tailnet"


def ssh_up(host):
    # BatchMode: never prompt, just fail; a short timeout keeps the polling brisk
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", host, "true"],
                          capture_output=True).returncode == 0


def tunnel_lsof(port):
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


def ssh_tunnel_pid(port):
    """(pid, argv) of this machine's spark-style ssh -fN -L tunnel on port, found among
    this uid's processes. Android denies an app the kernel's socket tables (lsof shows
    no listeners, /proc/net reads empty), so the command line is the record."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmd = [c.decode() for c in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if c]
        except OSError:
            continue
        if (len(cmd) > 3 and cmd[0].split("/")[-1] == "ssh" and "-L" in cmd
                and cmd[cmd.index("-L") + 1].startswith(("127.0.0.1:", "localhost:"))
                and f":{port}:" in cmd[cmd.index("-L") + 1]):
            return pid, cmd
    return None


def tunnel_proc(port):
    t = ssh_tunnel_pid(port)
    if t:
        cmd = t[1]
        return cmd[cmd.index("-L") + 1], cmd[-1]
    # No ssh of ours on the port: the bind is the only probe the sandbox leaves.
    # A collision says someone else holds it; whose is not readable from an app.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", port))
        return None
    except OSError:
        return "unknown"
    finally:
        probe.close()


def close_tunnel(port):
    """Terminate this machine's tunnel on the port — only ever the ssh spark opens,
    never another holder of the port. True when one was alive."""
    if sys.platform == "darwin":
        r = subprocess.run(["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                           capture_output=True, text=True)
        for pid in r.stdout.split():
            cmd = subprocess.run(["ps", "-o", "command=", "-p", pid],
                                 capture_output=True, text=True).stdout.split()
            if cmd and cmd[0].split("/")[-1] == "ssh" and "-L" in cmd:
                os.kill(int(pid), signal.SIGTERM)
                return True
        return False
    t = ssh_tunnel_pid(port)
    if not t:
        return False
    os.kill(int(t[0]), signal.SIGTERM)
    return True


def tunnel(port):
    """('listen-port', 'target') of the ssh -L tunnel on the port; None if nobody listens,
    a name if something other than ssh holds the port."""
    return tunnel_lsof(port) if sys.platform == "darwin" else tunnel_proc(port)


def ensure_tunnel(cfg, local, remote):
    """This machine's ssh pipe for the port pair, opened if it is not up yet. serve and
    speed both need the far end reachable, and neither should fail where it could just
    open the pipe. -fN backgrounds a connection with no commands: forwarding is its only
    job, and ExitOnForwardFailure makes a lost port fail the ssh instead of idling."""
    if isinstance(tunnel(local), tuple):
        ok(f"tunnel :{local} already open")
        return
    r = subprocess.run(["ssh", "-fN", "-o", "ExitOnForwardFailure=yes",
                        "-o", "ServerAliveInterval=30", "-L",
                        f"127.0.0.1:{local}:127.0.0.1:{remote}", cfg["host"]],
                       capture_output=True, text=True)
    if r.returncode != 0:
        err(f"tunnel: {r.stderr.strip()}")
    ends = f":{local}" if local == remote else f":{local} → :{remote}"
    ok(f"tunnel {ends} {green('open')}")


def device_name():
    # Each machine signs its own listener: the name comes from the machine, never the config,
    # which is shared through Dropbox
    if sys.platform == "darwin":
        return subprocess.run(["scutil", "--get", "LocalHostName"],
                              capture_output=True, text=True).stdout.strip() or "Mac"
    if os.environ.get("TERMUX_VERSION"):  # Termux's hostname is Android's "localhost"
        # The name the person chose, from the same file the Termux bashrc takes
        # the prompt's $name from; getprop's model (ONEPLUS A6003) is a factory
        # code nobody picked, so it only speaks when machine-info is missing
        info = Path(os.environ.get("PREFIX", "")) / "etc/machine-info"
        for line in info.read_text().splitlines() if info.exists() else []:
            if line.startswith("PRETTY_HOSTNAME="):
                chosen = line.partition("=")[2].strip('"')
                if chosen:
                    return chosen
        model = subprocess.run(["getprop", "ro.product.model"],
                               capture_output=True, text=True).stdout.strip()
        if model:
            return model
    return socket.gethostname() or "device"


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


def package_install(pkgs):
    """The platform's package manager command for pkgs, or None if this machine has none.

    Termux and Debian both carry apt, so the order reads outward from the guest:
    a Debian root filesystem first, then Android's Termux wrapper, then brew."""
    if os.path.exists("/etc/debian_version"):  # a Debian guest, root or not: apt is the way
        cmd = ["apt-get", "install", "-y", *pkgs]
        return (["sudo"] + cmd if os.geteuid() else cmd), None
    if os.environ.get("TERMUX_VERSION") and shutil.which("pkg"):
        return ["pkg", "install", *pkgs], None  # pkg wraps apt and stays non-interactive
    if sys.platform == "darwin" and shutil.which("brew"):
        # HOMEBREW_NO_ASK drops brew 7's ask-mode [y/n] gate: the decision to install
        # is made here, and the prompt would hang the chart when gnuplot arrives as a
        # surprise with dependencies (it pulls qt)
        return ["brew", "install", *pkgs], {**os.environ, "HOMEBREW_NO_ASK": "1"}
    return None


def gnuplot():
    """The gnuplot binary's path, installed through this machine's package manager if missing.

    The wattage chart is the only feature that needs it, so the one-time install
    happens at use rather than in a setup script, where a new machine would miss it
    and spark wattage would die in a traceback."""
    exe = shutil.which("gnuplot")
    if exe:
        return exe
    plan = package_install(["gnuplot"])
    if plan is None:
        err("gnuplot is missing and this machine has no package manager spark knows "
            "(brew, pkg or apt-get): install gnuplot and put it on the PATH")
    cmd, env = plan
    print(dim(f"gnuplot missing: running {' '.join(cmd)}, one time…"))
    # the manager's own progress stays visible: the user watches the one-time install
    if subprocess.run(cmd, env=env).returncode != 0:
        err(f"{bold(cmd[0])} could not install gnuplot: run {cyan(' '.join(cmd))} "
            f"and check its output")
    exe = shutil.which("gnuplot")
    if exe is None:  # the manager succeeded but the binary is still off PATH
        err("gnuplot installed but is not on PATH: check how this machine links it")
    return exe


def dumb_plot(rows, title):
    """One gnuplot dumb-terminal render of (epoch, watts) pairs, sized to the screen."""
    exe = gnuplot()
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
    path = (green(path) if "direct" in path or "answers" in path else yellow(path) if "relay" in path
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
        if r.returncode == 255:
            # ssh itself failed (no key, no route): that fact belongs to this line
            # alone, the tunnel and the API are local facts this device can answer
            # regardless, so they still get their own lines below
            print(f"{dim('service')} {bold(server)} {dim(f'(model {model})')}: "
                  f"{red('no ssh access to ' + cfg['host'])}")
        else:
            state = "" if r.returncode else r.stdout.strip().partition(" ")[0]
            if state != "running":
                print(f"{dim('service')} {bold(server)} {dim(f'(model {model})')}: "
                      f"{yellow(state or 'container not found')}")
            else:
                started = r.stdout.strip().partition(" ")[2]
                print(f"{dim('service')} {bold(server)} {dim(f'(model {model})')}: "
                      f"{green(f'running {uptime_text(started)}')}")
        # Tunnel and API are two facts on two lines: the pipe, then what answers at its end
        t = tunnel(local)
        pair = f"{bold(device_name())}:{accent(local)} {dim('→')} {bold(cfg['host'])}:{accent(remote)}"
        if isinstance(t, tuple):
            print(f"{dim('tunnel')}  {pair} {green('open')}")
        elif isinstance(t, str):
            print(f"{dim('tunnel')}  {pair} {red(f'held by {t}, not ssh')}")
        else:
            print(f"{dim('tunnel')}  {pair} {red('closed')}")
        # With no pipe open there is nothing to ask at the far end: none, not a
        # "no answer" that blames a server nobody reached
        api = dim("none") if t is None else (green("ready") if model_ready(local)
                                             else red("no answer"))
        print(f"{dim('api')}     {bold(device_name())}:{accent(local)}: {api}")


async def plug_state(cfg):
    # (plug, on, watts) for callers outside status: serve asks the plug before
    # blaming the machine, and watts tells off from a machine mid-boot
    plug = await find_plug(cfg)
    on = await plug.is_on()
    return plug, on, (await watts(plug) if on else 0.0)


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
    # `spark serve tunnel`: join a shared service rather than run one. Once the
    # Spark serves, any machine just wants its own pipe open, and bringing a
    # service down or up stays the call of whoever keeps it alive.
    tunnel_only = model == "tunnel"
    if tunnel_only:
        model, server = None, None
    p = pick(cfg, model, server)
    if p is None:
        err(unknown_model(cfg, model or cfg["model"], server))
    model, server, local, remote, name = p
    # the cursor goes away the moment Enter is pressed, not when the repaint
    # block starts: everything below either prints lines or waits, never asks
    sys.stdout.write("\033[?25l")
    try:
        if tunnel_only:
            # joining a service, not making one: ssh answering is a precondition here,
            # not something to wait out, and a powered-off Spark is the server's problem
            if not ssh_up(cfg["host"]):
                err(f"{bold(cfg['host'])} is not answering ssh: {cyan('spark serve')} "
                    f"brings the service up first")
        elif not ssh_up(cfg["host"]):
            # Ask the plug before blaming the machine: off at the plug is the common
            # case, and only a machine already drawing power deserves the wait
            _, on, w = asyncio.run(plug_state(cfg))
            if on and w > RUNNING_W:
                # Drawing real power without ssh: it is mid-boot, or sshd is asleep.
                # Wait it out with the same 5 min window `spark on --wait` allows.
                print(dim(f"waiting for ssh {cfg['host']}…"), flush=True)
                start = time.monotonic()
                while not ssh_up(cfg["host"]):
                    if time.monotonic() - start > 300:
                        err(f"{bold(cfg['host'])} powered on but not answering ssh after {dur(300)}: "
                            f"{cyan('spark status')} and {cyan('spark serving')} say more")
                    time.sleep(1)
                ok(f"{bold(cfg['host'])} up after {accent(f'{time.monotonic() - start:.0f} s')}")
            else:
                if not sys.stdin.isatty():
                    err(f"{bold(cfg['host'])} is powered off: {cyan('spark on')} first")
                sys.stdout.write("\033[?25h")  # a question is asked: cursor back
                answer = input(f"{bold(cfg['host'])} is powered off. Turn it on? [y] ")
                sys.stdout.write("\033[?25l")
                if answer.strip().lower() not in ("", "y", "yes"):
                    err(f"{bold(cfg['host'])} is powered off: {cyan('spark on')} first")
                asyncio.run(power_on(cfg, wait=True))
        state = ssh_docker(cfg, "inspect", "-f", "{{.State.Status}}", name)
        if state.returncode != 0:
            err(f"{bold(name)} on {cfg['host']}: {state.stderr.strip().splitlines()[-1]} "
                f"({cyan('spark serving')} shows what exists)")
        if state.stdout.strip() == "running":
            ok(f"{bold(name)} already running")
            # attaching to a boot already in flight: its start lines are not this
            # command's to claim, so no banner is looked for and only readiness is waited
            run_since = None
        elif tunnel_only:
            # a service that exists but stands stopped is the server owner's call
            err(f"{bold(name)} is stopped on {cfg['host']}: {cyan('spark serve')} starts the "
                f"service; {cyan('spark serve tunnel')} only opens this machine's pipe")
        else:
            # the run's own window in the log, told by the clock the daemon itself
            # stamps. A reused container holds every earlier start, and reading the
            # whole log lets an old run answer for the new one; a line-count cursor
            # drifts when the daemon rotates or merges streams. --since filters where
            # both slip.
            run_since = subprocess.run(["ssh", cfg["host"], "date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                       capture_output=True, text=True).stdout.strip()
            started = ssh_docker(cfg, "start", name)
            if started.returncode != 0:
                err(f"docker start: {started.stderr.strip().splitlines()[-1]}")
            ok(f"{bold(name)}: {green('started')}")
        ensure_tunnel(cfg, local, remote)
        if server not in STAGE_PARSER:  # only a server spark can read is waited for
            ok(f"{bold(name)} up; {bold(server)} has no health check spark knows, "
               f"{cyan('spark serving')} to see state")
            return
        # Nothing to watch when the far end already answers: an attach to a model
        # that is serving prints its line and leaves. The frame is for a boot in
        # flight, and running it over a full log replays a check per phase of a
        # start this command never began (what spark serve showed on the phone)
        if model_ready(local):
            ok(f"{bold(name)} serving on {bold(f':{local}')}, {green('api ready')}")
            return
        # One line per phase, kept on screen as it completes: the server's own parser turns
        # the log into a percentage and a stage word, and a new phase starts a fresh line.
        # The frame never waits on the network: the log read and the health probe run in a
        # thread every 5 s (a health probe can idle for seconds behind a busy tunnel, and
        # a frame that stalls on one makes the timer freeze and jump). The main loop only
        # repaints four times a second: the spinner turns every pass, the timer text is
        # rewritten on its own second boundary, and the bar changes only when a fetch
        # brought new numbers.
        parse = STAGE_PARSER[server]
        start = time.monotonic()
        stop_fetch = threading.Event()
        live = {"phase": "waiting", "pct": None, "stage": "waiting for the first log line",
                "last": "", "art": None, "ready": False, "all": []}

        def fetch_loop():
            # one read feeds everything: the phases, the health answer, and vLLM's opening
            # banner (block art, version, model), which lands some seconds after docker
            # start and is searched for in the run's window until it appears. run_since
            # None (attaching to a boot already in flight) keeps the whole log for the
            # phases and skips the banner: an earlier one is not this run's.
            while not stop_fetch.is_set():
                log = container_log(cfg, name, since=run_since).splitlines()
                live["phase"], live["pct"], live["stage"], live["all"] = parse(cfg, name, log)
                if run_since and live["art"] is None:
                    live["art"] = banner_lines(log)
                live["ready"] = model_ready(local)
                stop_fetch.wait(5)

        threading.Thread(target=fetch_loop, daemon=True).start()

        def pad_to(s, w):
            # ljust would count the escape bytes and add nothing to a coloured line,
            # leaving the tail of the line it overwrites: pad on printed characters
            return s + " " * max(0, w - width(s))

        # no line, and no padding of one, may reach the pane's last column: a line that
        # wraps leaves its overflow on the next row, where a later single-row redraw
        # cannot erase it (the leftover tails on screen were exactly this)
        term = max(60, shutil.get_terminal_size((100, 24)).columns - 2)

        def elapsed(at=None):
            return accent(dur((time.monotonic() if at is None else at) - start))

        # one ordered list drives the whole screen — banner, a check per finished phase,
        # one live line — and every pass repaints the block. No line is ever erased,
        # reused or closed by hand: the earlier attempts kept that bookkeeping in
        # variables (freeze flags, wipe-on-change, emitted sets) and every bug this
        # session lived in it. The wattage chart repaints its whole block per tick and
        # has never misbehaved; this is the same shape.
        phase, pct, stage = live["phase"], live["pct"], live["stage"]
        tick, timer_shown = 0, "0 s"
        finished, seen_at, painted, painted_w = [], {}, 0, 0
        stage_of = {}  # every stage text ever seen per phase: a check must not depend on

        def check_rows(now):  # the current log read still holding the line it came from
            rows = [accent(re.sub(r"^.*\]\s?", "", a)) for a in (live["art"] or [])]
            for pid in finished:
                rows.append(f"{accent('✓')} {dim(stage_of.get(pid, 'done'))}  {elapsed(seen_at.get(pid, now))}")
            return rows

        sys.stdout.write("\033[?25l")  # the block owns the screen: hide the cursor,
        try:                            # restore it whatever way we leave (finally)
            while not live["ready"]:
                now = time.monotonic()
                if now - start > 900:
                    err(f"API not ready after {dur(900)}: {cyan('spark status')} to see where it stands")
                if live["phase"] == phase:  # within a phase the live line updates in place
                    pct, stage = live["pct"], live["stage"]
                else:
                    phase, pct, stage = live["phase"], live["pct"], live["stage"]
                for pid, _, st in live["all"]:
                    stage_of[pid] = st
                    seen_at.setdefault(pid, now)
                    if pid == live["phase"] and pid not in finished:
                        seen_at[pid] = now  # still running: its time is its latest sighting
                ids = [pid for pid, _, _ in live["all"]]
                for pid in ids[:ids.index(live["phase"])] if live["phase"] in ids else []:
                    if pid not in finished:
                        finished.append(pid)  # a later phase in the log means this one is over
                tick += 1
                if tick % 4 == 0:
                    timer_shown = accent(dur(now - start))
                if pct is not None and pct < 100:
                    cells = pct // 5
                    live_line = (f"  {accent('█' * cells + '░' * (20 - cells))} {accent(f'{pct:3d}%')} "
                                 f"{dim(stage)}  {timer_shown}")
                else:
                    spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[tick % 10]
                    wait = "waiting for the next phase" if pct == 100 else stage
                    live_line = f"  {accent(spin)} {dim(wait)}  {timer_shown}"
                    if pct == 100 and phase not in finished:
                        finished.append(phase)  # the bar reached its end: the check stands
                rows = check_rows(now) + [live_line]
                w = min(max(78, painted_w, max(width(r) for r in rows)), term)
                if painted:
                    print("\r" + "\033[A" * (painted - 1), end="")
                print("\033[J", end="")
                print("\n".join(pad_to(r, w) for r in rows), end="", flush=True)
                painted, painted_w = len(rows), w
                time.sleep(0.25)
        finally:
            stop_fetch.set()
            sys.stdout.write("\033[?25h")
        for pid, _, _ in live["all"]:  # ready: every phase the log mentions stands checked
            if pid not in finished:
                finished.append(pid)
        rows = check_rows(time.monotonic())
        if painted:
            print("\r" + "\033[A" * (painted - 1), end="")
        print("\033[J", end="")
        for r in rows:
            print(r)
        ok(f"API ready after {accent(dur(time.monotonic() - start))}")
    finally:
        sys.stdout.write("\033[?25h")


def unserve(cfg, model=None, server=None):
    # `spark unserve tunnel`: close just this machine's pipe. The service belongs to
    # whoever keeps it alive, so a joining machine never takes it down.
    tunnel_only = model == "tunnel"
    if tunnel_only:
        model, server = None, None
    p = pick(cfg, model, server)
    if p is None:
        err(unknown_model(cfg, model or cfg["model"], server))
    model, server, local, remote, name = p
    if tunnel_only:
        if close_tunnel(local):
            ok(f"tunnel :{local} {red('closed')}")
        else:
            ok(f"tunnel :{local} already closed")
        return
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
            close_tunnel(local)  # the pair matched ours, so this is ours to close
            ok(f"tunnel :{local} {red('closed')}")
        else:
            ok(f"tunnel :{local} left open: not this service's ({dim(f'-L {spec} → {target}')})")
    elif isinstance(held, str):
        ok(f"tunnel :{local} left alone: {held} holds the port, not ssh")


def banner_lines(lines):
    """The first run of three or more consecutive block-art lines, as vLLM prints
    its opening banner in one block; None while it has not landed. tqdm progress
    bars (CUDA graphs, shard routing) also draw block characters: the percent
    sign and it/s tell them apart from the banner."""
    run = []
    for line in lines:
        if re.search(r"[▀▄█]", line) and not re.search(r"%|\||it/s", line):
            run.append(line)
        elif len(run) >= 3:
            return run
        else:
            run = []
    return run if len(run) >= 3 else None


def container_log(cfg, name, tail=None, since=None):
    # docker logs writes to stderr, so ssh_docker's stdout alone is empty: merge both.
    # The Spark's docker is too old for --no-log-prefix; strip the stamp and colour here.
    opts = (["--tail", str(tail)] if tail else []) + (["--since", since] if since else [])
    r = ssh_docker(cfg, "logs", *opts, name)
    out = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
    return re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?", "", out, flags=re.M)


def vllm_b12x_stage(cfg, name, lines=None):
    """(phase id, percent or None, what it is doing, [(id, percent, stage) per phase in
    log order]) for the vLLM/B12X services. Each phase names itself in the log; the
    newest match decides which phase is current, while every phase keeps its own
    last-seen state, so one that finished between two reads still shows its ending and
    the caller can print lines for phases it never saw current. A new phase id lets the
    caller start a fresh output line, so ids must be stable within a phase: the routing
    id names the set (all shards or the MTP head's filtered three), never the progress.
    lines: a whole log already read this pass, so a caller that fetched it reads once."""
    lines = [l.strip() for l in (lines if lines is not None else container_log(cfg, name).splitlines()) if l.strip()]
    seen, newest, best = {}, -1, {}
    for i, line in enumerate(lines):
        m = re.search(r"Safetensors index filter selected \d+/\d+ checkpoint shards", line)
        if m:
            seen["filtered"] = i
            continue
        m = re.search(r"checkpoint shards: (\d+)/(\d+) shards routed, ([\d.]+) GB", line)
        if m:  # the full checkpoint and the MTP head read separately: the filter line tells which
            head = seen.get("filtered", -1) != -1 and i > seen["filtered"]
            label = ("routing shards (MTP head) " if head else "routing shards ") \
                    + f"{m[1]}/{m[2]}, {m[3]} GB"
            cand = ("route-mtp" if head else f"route-main-{m[2]}",
                    100 * int(m[1]) // max(int(m[2]), 1), label)
        elif "GPU KV cache size" in line or "KV cache layout" in line:
            # the allocation itself: the fp8 store-dtype message is a config print, not the event
            cand = ("kv", None, "allocating the KV cache")
        elif "Capturing model for speculator" in line:
            cand = ("spec", None, "warming up the speculator head")
        elif "Capturing prefill CUDA graphs" in line:
            cand = ("cap-pre", None, "compiling prefill CUDA graphs")
        elif "Capturing decode CUDA graphs" in line:
            cand = ("cap-dec", None, "compiling decode CUDA graphs")
        elif "Capturing CUDA graphs" in line:
            cand = ("cap", None, "compiling CUDA graphs")
        elif "Started server process" in line or "Route: /v1" in line:
            cand = ("api", None, "starting the API server")
        else:
            continue
        pid, pct, stage = cand
        if i >= best.get(pid, (-1,))[0]:
            best[pid] = (i, pct, stage)
        if i > newest:
            newest, current = i, pid
    if newest < 0:
        return "waiting", None, "waiting for the first log line", []
    states = [(pid, v[1], v[2]) for pid, v in sorted(best.items(), key=lambda kv: kv[1][0])]
    return (current,) + best[current][1:] + (states,)


def generic_stage(cfg, name, lines=None, model=None):
    """Unknown services get their plain newest log line, no percentage invented."""
    if lines is None:
        lines = container_log(cfg, name, tail=3).splitlines()
    lines = [l.strip() for l in lines if l.strip()]
    last = lines[-1][:52] if lines else "waiting for the first log line"
    return None, None, last, [(None, None, last)]


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


def cache_rows(cfg):
    """The model store on the Spark as rows from `hf cache ls`, heaviest first: the one
    listing behind `spark models` and behind the numbers `spark model <n>` reads, so the
    number you see is the number you type."""
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

    def weight(row):  # sort by bytes: 102.3G > 7.7G > 306.5M
        s, unit = row["size"][:-1], row["size"][-1]
        return float(s) * {"K": 1e-3, "M": 1, "G": 1e3, "T": 1e6}.get(unit, 1)

    return sorted(rows, key=weight, reverse=True)


def models(cfg):
    rows = cache_rows(cfg)
    served = served_models(cfg)
    # The [models] table says which of these ids spark has a server ready for
    servers = {m: ", ".join(t[0] for t in model_rows(cfg, m) or []) for m in cfg["models"]}

    w_id = max(len(row["repo_id"]) for row in rows) + 2
    w_sz = max(len(row["size"]) for row in rows)
    w_la = max(len(row["last_accessed"]) for row in rows)
    w_n = len(str(len(rows)))  # the number column fits the largest row
    print("  " + " " * (w_n + 2) + dim("model".ljust(w_id) + "size".rjust(w_sz) + "  "
                                        + "last access".ljust(w_la)))
    for i, row in enumerate(rows, 1):
        rid = row["repo_id"]
        mark = (green("  ← served") if rid in served
                else accent(f"  · server: {servers[rid]}") if rid in servers else "")
        org, _, model = rid.partition("/")  # the author's hand, then the model
        print(f"  {dim(f'{i:>{w_n}}')}  {cyan(org + '/')}{bold(model)}"
              f"{' ' * (w_id - len(row['repo_id']))}"
              f"{accent(row['size'].rjust(w_sz))}  {dim(row['last_accessed'].ljust(w_la))}{mark}")
    print(dim(f"\n  {len(rows)} models on {cfg['host']}, from {cfg['hf']}"
              f" — {cyan('spark model')} <n> asks the Hub about one"))


# Tags the Hub gives a quantized checkpoint: the formats (nvfp4, fp4, mxfp8, int4),
# the bit widths, and the tools that wrote them (Model Optimizer, compressed-tensors)
QUANT_TAG = re.compile(r"^(?:nv)?fp\d+(?:e\d+m\d+)?$|^\d+-bit$|^int\d$|^mxfp\d$|"
                       r"^modelopt$|^model optimizer$|^compressed-tensors$|^gptq$|^awq$|^quantized$",
                       re.I)


def people(n):
    # Counts as they read: 45305 is 45.3k, 96486615005 is 96.5B. Lowercase k, as
    # everywhere. Below 1k the value prints as written, and a float keeps one decimal
    # at most: rates arrive as floats (42.7 tok/s), counters as whole 473.0s
    for lim, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "k")):
        if n >= lim:
            return f"{n / lim:.1f}".rstrip("0").rstrip(".") + unit
    if isinstance(n, float):
        return f"{n:.1f}".rstrip("0").rstrip(".")
    return str(n)


def hub_size(n):
    # The Hub reports bytes; the smaller units keep a 289.5k repo from reading "0.0 GB"
    for lim, unit in ((1e12, "TB"), (1e9, "GB"), (1e6, "MB"), (1e3, "KB")):
        if n >= lim:
            return f"{n / lim:.1f} {unit}"
    return f"{n} B"


def hf_get(repo_id):
    """The Hub API's record for one model, or None when it answers nothing: a missing,
    renamed or gated repo. A public card needs no token."""
    r = subprocess.run(["curl", "-s", "--max-time", "15",
                        f"https://huggingface.co/api/models/{repo_id}"],
                       capture_output=True, text=True)
    try:
        info = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    return info if isinstance(info, dict) and "error" not in info else None


def quant_facts(info):
    """Parts of the quantization line, in the order they are worth reading: the method
    config.json names, the bit widths the compressed-tensors groups record, then the
    Hub's format tags. A bare `quantized` tag speaks only when nothing else does."""
    qc = (info.get("config") or {}).get("quantization_config") or {}
    parts = []
    if qc.get("quant_method"):
        parts.append(str(qc["quant_method"]))
    bits = {g["weights"]["num_bits"] for g in (qc.get("config_groups") or {}).values()
            if isinstance(g, dict) and isinstance(g.get("weights"), dict)
            and isinstance(g["weights"].get("num_bits"), int)}
    parts += [f"{b}-bit" for b in sorted(bits)]

    def key(s):  # Model Optimizer signs its cards two ways, tool name in config.json
        s = s.lower().replace(" ", "")  # and tag, and they must collapse to one entry
        return "modelopt" if s == "modeloptimizer" else s

    seen = {key(p) for p in parts}
    tags = []
    for t in info.get("tags") or []:
        if QUANT_TAG.match(t) and key(t) not in seen:
            seen.add(key(t))
            tags.append(t)
    if parts or len(tags) > 1:
        tags = [t for t in tags if t.lower() != "quantized"]
    return parts + tags


def model_info(cfg, arg):
    """`spark model <n | org/name>`: what the Hub records about one model — quantization,
    parameter count, the model it was made from, licence, popularity. A number is the row
    `spark models` printed, so both commands read the same listing."""
    if not arg:
        err(f"which model? {cyan('spark models')} numbers them, then {cyan('spark model')} <n>")
    row, rid = None, arg
    if arg.isdigit():
        rows = cache_rows(cfg)
        if not 1 <= int(arg) <= len(rows):
            err(f"No model number {bold(arg)}: {cyan('spark models')} lists {len(rows)}")
        row = rows[int(arg) - 1]
        rid = row["repo_id"]
    info = hf_get(rid)
    if info is None:
        err(f"The Hub answers nothing for {bold(rid)}: it is missing, renamed, or gated "
            f"behind a login")

    org, _, name = rid.partition("/")
    head = f"{cyan(org + '/')}{bold(name)}"
    if info.get("sha"):
        head += dim(f"  rev {info['sha'][:7]}")
    print()
    fact("model", head)
    task = " · ".join(x for x in (info.get("pipeline_tag"), info.get("library_name")) if x)
    if task:
        fact("task", task)
    quant = quant_facts(info)
    if quant:
        fact("quantization", accent(" · ".join(quant)))
    st = info.get("safetensors") or {}
    if st.get("total"):
        # the element count the Hub itself prints; the dtypes say what holds them, and
        # a packed quantized store (U8 for FP4 codes) is where these outrun the model's
        # own parameter count — the base model line below carries the honest number
        fact("parameters", accent(people(st["total"])) + " tensor elements, "
             + dim(", ".join(f"{d} {people(n)}"
                             for d, n in sorted((st.get("parameters") or {}).items(),
                                                key=lambda kv: -kv[1]))))
    base = (info.get("cardData") or {}).get("base_model")
    if isinstance(base, list):
        base = base[0] if base else None
    if base:
        line = bold(base)
        binfo = hf_get(base)  # the original's card gives the parameter count a quantized store cannot
        if binfo and (binfo.get("safetensors") or {}).get("total"):
            # a base that is itself a quantization (one checkpoint made from another)
            # holds packed bytes too: only an original's element count is a parameter count
            noun = "parameters" if not quant_facts(binfo) else "tensor elements"
            line += dim(f"  ·  {people(binfo['safetensors']['total'])} {noun}")
        fact("base model", line)
    card = info.get("cardData") or {}
    if card.get("license_name") or card.get("license"):
        fact("licence", card.get("license_name") or card["license"])
    hub = [f"{people(info.get('downloads') or 0)} downloads",
           f"{people(info.get('likes') or 0)} likes"]
    if info.get("lastModified"):
        hub.append(f"updated {info['lastModified'][:10]}")
    if info.get("usedStorage"):
        hub.append(f"{hub_size(info['usedStorage'])} on the Hub")
    if info.get("gated"):
        hub.append("gated")
    fact("Hub", " · ".join(hub))
    if row:
        fact("Spark", f"{accent(row['size'])} cached  {dim('·  last access ' + row['last_accessed'])}")
    print()


def setup(cfg):
    # Every question first, then the writes: a cancel half-way changes nothing
    plug = input(f"plug name [{cfg['plug']}]: ") or cfg["plug"]
    host = input(f"tailnet host [{cfg['host']}]: ") or cfg["host"]
    email = input("TP-Link email: ")
    if sys.platform == "darwin":
        # -U replaces an existing item; a final -w with no value makes `security` prompt for the password
        stored = subprocess.run(["security", "add-generic-password", "-U", "-s", cfg["keychain"],
                                 "-a", email, "-w"])
        if stored.returncode != 0:
            err(f"Keychain item {bold(cfg['keychain'])} not updated; nothing written.")
        ok(f"TP-Link login in the Keychain, item {bold(cfg['keychain'])}")
    else:
        password = getpass.getpass("TP-Link password: ")
        if password != getpass.getpass("TP-Link password again: "):
            err("The two passwords differ; nothing written.")
        # json.dumps escapes as TOML's own basic strings do, so any symbol survives
        CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS.write_text(f'email = {json.dumps(email)}\n'
                               f'password = {json.dumps(password)}\n')
        os.chmod(CREDENTIALS, 0o600)  # the file holds a cloud login: owner only
        ok(f"TP-Link login in {bold(short(CREDENTIALS))}, mode {bold('600')}")
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    # The file holds the whole picture: every setting, plus every model's serving rows
    rows = "\n".join(f'"{m}" = {json.dumps(cfg["models"][m])}' for m in cfg["models"])
    CONFIG.write_text(f'plug = "{plug}"\nhost = "{host}"\nkeychain = "{cfg["keychain"]}"\n'
                      f'model = "{cfg["model"]}"\nhf = "{cfg["hf"]}"\n\n[models]\n'
                      f'# model = [server, local, remote]: the Mac listens on local, the '
                      f'Spark serves on remote; the container name is derived from the pair\n'
                      f'{rows}\n')
    ok(f"wrote {bold(short(CONFIG))}")


def _completion(port, prompt, max_tokens, timeout=180):
    """One /v1/completions call through urllib, so the clock wraps only the request:
    returns (seconds, prompt_tokens, completion_tokens) with the token counts the
    server itself counted, not an estimate of ours."""
    body = json.dumps({"prompt": prompt, "max_tokens": max_tokens,
                       "temperature": 0}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            answer = json.loads(r.read())
    except urllib.error.HTTPError as e:
        err(f"api :{port} refused the probe ({e.code}): {e.read().decode()[:120]}")
    except OSError as e:
        err(f"api :{port} no answer ({e}): {cyan('spark serve')} to bring the model up")
    return time.perf_counter() - t0, answer["usage"]["prompt_tokens"], answer["usage"]["completion_tokens"]


def metric_sums(port, names):
    """Sums of the named vLLM counters from /metrics, as {name: total}. A server
    without the endpoint, or a build that renamed them, just answers {}."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as r:
            body = r.read().decode()
    except OSError:
        return {}
    out = {}
    for line in body.splitlines():
        for n in names:
            if line.startswith((n + "{", n + " ")):
                out[n] = out.get(n, 0.0) + float(line.rsplit(" ", 1)[1])
    return out


def speed(cfg, model=None, server=None):
    """`spark speed`: how fast the served model answers, measured now. Three probes
    through the model's own API, each carrying a fresh nonce so vLLM's prefix cache
    answers none of them from an earlier run: a short request for the first token, a
    long one for prompt processing, and 256 generated tokens for the decode rate."""
    p = pick(cfg, model, server)
    if p is None:
        err(unknown_model(cfg, model or cfg["model"], server))
    model, server, local, remote, name = p
    ensure_tunnel(cfg, local, remote)
    if not model_ready(local):
        err(f"api {bold(f':{local}')} no answer: {cyan('spark serve')} to bring the model up")
    print(dim(f"probing {bold(model)} on {bold(f'{device_name()}:{local}')}…"))
    nonce = os.urandom(8).hex()
    t_first, _, _ = _completion(local, f"Count to five, {nonce}:", 1)
    fact("first token", accent(f"{t_first:.2f} s") + dim("  (short prompt)"))
    probe = f"{nonce} notes. " + "The quick brown fox jumps over the lazy dog. " * 200
    t_pre, pt, _ = _completion(local, probe, 1)
    fact("prefill", accent(f"{people(pt / t_pre)} tok/s") + dim(f"  ({people(pt)} tokens in {t_pre:.2f} s)"))
    t_gen, _, ct = _completion(local, f"Write a short story about a machine, {nonce}.", 256)
    # the request's own prefill rides inside t_gen: the first probe measured that cost
    # for a prompt of this size, so subtracting it leaves the token-to-token rate
    fact("generation", accent(f"{people(ct / max(t_gen - t_first, 0.1))} tok/s")
         + dim(f"  ({ct} tokens in {t_gen:.1f} s)"))
    counters = metric_sums(local, ("vllm:generation_tokens_total", "vllm:prompt_tokens_total",
                                   "vllm:request_success_total"))
    if counters:
        gen = counters.get("vllm:generation_tokens_total", 0)
        pre = counters.get("vllm:prompt_tokens_total", 0)
        req = counters.get("vllm:request_success_total", 0)
        fact("served", f"{people(gen)} tokens generated, {people(pre)} prompt tokens,"
             f" {people(req)} requests  {dim('since the service started')}")
    print(dim("  one sequence each: several requests share the GPU, so totals differ"))
    print()


# command: (what it does, [(option, what it does)]), as tg-mail's gmail lists them
COMMANDS = {
    "status": ("Plug state and power; the machine on the tailnet; the default model's service and its tunnel.", []),
    "wattage": ("Live terminal chart of the wattage, redrawn each second ([q] quits).", []),
    "on": ("Power on; boots the machine if it is shut down.",
           [("--wait", "Wait until ssh answers, and print the boot time.")]),
    "off": ("Clean shutdown over ssh, then plug off.", []),
    "restart": ("off, then on --wait.", []),
    "models": ("The model store on the Spark: number, org/name, size, last access, and what is served.", []),
    "model": ("What the Hub records for one model: quantization, parameter count, the base "
              "model it was made from, licence, popularity. The number is spark models' row.", []),
    "serving": ("What runs on the Spark: state, uptime, image, forwarded port.", []),
    "speed": ("Tokens per second from a live probe: first token, prompt processing, "
              "generation, and what the service has served in total.", []),
    "serve": ("Serve a model: start its server, open its tunnel, wait for its API. "
              "With tunnel, open just this machine's pipe.", []),
    "unserve": ("Stop a served model, close its tunnel. With tunnel, close just "
                "this machine's pipe and leave the service running.", []),
    "setup": ("Once per machine: the plug, the machine, and your TP-Link login.", []),
}

# Positional slots shown in the Usage line, in order
USAGE = {"serving": "", "serve": "[<model> [server] | tunnel]",
         "unserve": "[<model> [server] | tunnel]", "model": "<n | org/name>",
         "speed": "[<model> [server]]"}


# What `spark <command> --help` adds below the one-line summary
DETAILS = {
    "setup": [
        "Asks four things, then writes:",
        f"  {cyan('plug name    ')}  the plug's name in the Kasa app {dim('(Enter:')} {accent('AlfSPARK')}{dim(')')}",
        f"  {cyan('tailnet host ')}  the machine's name on the tailnet {dim('(Enter:')} {accent('alfspark')}{dim(')')}",
        f"  {cyan('TP-Link email')}  the Kasa app's account",
        f"  {cyan('password     ')}  "
        + (f"asked by macOS's {bold('security')}, twice" if sys.platform == "darwin"
           else "asked twice here, hidden, and confirmed"),
        f"The names go to {bold('~/.config/spark/config.toml')}, the login to "
        + (f"the Keychain (item {bold('tplink-cloud')})" if sys.platform == "darwin"
           else f"{bold('~/.config/spark/credentials.toml')} (mode {bold('600')})")
        + f". {dim('^C at any question writes nothing.')}",
    ],
    "serve": [
        f"The service is shared: {bold('tunnel')} opens only this machine's pipe to a",
        "model already serving, no power and no container start, for any machine",
        f"that just wants to reach the Spark. {cyan('spark unserve tunnel')} closes",
        "the pipe and leaves the service to whoever keeps it alive.",
    ],
    "model": [
        f"The number is {cyan('spark models')}' row, heaviest first: both commands read",
        "one listing, so the number you see is the number you type. An org/name is",
        "looked up on the Hub directly, which is how a base model's own card opens.",
        "The facts come from the Hub's API for the repo: its config.json, tags, and",
        "card. A quantized store counts packed bytes as elements, so the honest",
        "parameter count rides on the base model's line.",
    ],
    "speed": [
        "Three timed probes reach the served model over its tunnel: a one-token",
        "request for time to first token, a long prompt for how fast it reads, and a",
        "256-token request for how fast it writes.",
        f"The {dim('served')} line is vLLM's own counters, so it counts every request",
        f"since the service started, not just this probe. {cyan('spark serving')} shows",
        "how long that is.",
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
            cols = min(80, shutil.get_terminal_size((80, 20)).columns)
            print()
            for line in DETAILS[command]:
                # item lines hang their text under the description column, prose
                # keeps a plain left margin; the margin rides on initial_indent
                # because the word split would drop it from the text itself
                if line.startswith("  "):
                    print(wrap(line, cols, "  ", " " * 17))
                else:
                    print(wrap(line, cols, "  ", "  "))
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
        elif command == "model":
            model_info(cfg, model)
        elif command == "serving":
            serving(cfg)
        elif command == "speed":
            speed(cfg, model, server)
        elif command == "serve":
            serve(cfg, model, server)
        elif command == "unserve":
            unserve(cfg, model, server)
    except (KeyboardInterrupt, EOFError):  # ^C, or ^D at a question: stop quietly
        print("\n" + dim("cancelled"))
        sys.exit(130)  # 128 + SIGINT, what a shell reports for ^C


if __name__ == "__main__":
    main()
