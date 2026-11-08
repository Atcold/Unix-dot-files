#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tplink-cloud-api"]
# ///
"""spark: power a machine on a Kasa smart plug on and off, from anywhere.

The plug is switched through TP-Link's cloud, as the Kasa app does it, so this
works outside the LAN too. The machine itself is reached over the tailnet.

  spark status          plug state and power; the machine on the tailnet; the model and its tunnel
  spark wattage         live wattage chart, redrawn every second ([q] quits)
  spark on [--wait]     power on; --wait: until ssh answers
  spark off             clean shutdown over ssh, then plug off
  spark restart         off, then on --wait
  spark setup           names in ~/.config/spark/config.toml, login in the Keychain
"""
# The block above `"""` is inline script metadata (PEP 723): `uv run --script`
# reads it and runs the file in a cached environment with those dependencies.
import asyncio
import os
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path.home() / ".config/spark/config.toml"
DEFAULTS = {"plug": "AlfSPARK", "host": "alfspark", "keychain": "tplink-cloud",
            "container": "Qwen3.8-Flash-Next", "port": 8000}
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
        cfg.update(tomllib.loads(CONFIG.read_text()))
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


def tunnel_open(port):
    # The tunnel is an ssh with a Mac listener on the port: the listener is its visible half
    r = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                       capture_output=True, text=True)
    return "ssh" in r.stdout


def model_ready(port):
    # /health answers empty with exit 0 once vLLM serves; --max-time keeps status brisk
    return subprocess.run(["curl", "-s", "--max-time", "3", f"http://127.0.0.1:{port}/health"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


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
        # One ssh asks Docker both states; the start timestamp gives d/h/m uptime,
        # finer than docker ps's coarse string. BatchMode: no password can block status.
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", cfg["host"],
                            f"docker inspect -f '{{{{.State.Status}}}} {{{{.State.StartedAt}}}}' "
                            f"{cfg['container']}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            gone = "No such" in r.stderr or "not found" in r.stderr
            print(f"{dim('model')}   {bold(cfg['container'])}: "
                  f"{red('stopped') if gone else red('ssh refused')}")
        else:
            state, _, started = r.stdout.strip().partition(" ")
            if state == "running":
                print(f"{dim('model')}   {bold(cfg['container'])}: "
                      f"{green(f'running {uptime_text(started)}')}")
            else:
                print(f"{dim('model')}   {bold(cfg['container'])}: {yellow(state)}")
        if tunnel_open(cfg["port"]):
            api = green("ready") if model_ready(cfg["port"]) else yellow("still loading")
            print(f"{dim('llm')}     :{cfg['port']} {bold('open')}, API {api}")
        else:
            print(f"{dim('llm')}     :{cfg['port']} {red('no tunnel')}")


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
    CONFIG.write_text(f'plug = "{plug}"\nhost = "{host}"\nkeychain = "{cfg["keychain"]}"\n')
    ok(f"wrote {bold(str(CONFIG))}")


# command: (what it does, [(option, what it does)]), as tg-mail's gmail lists them
COMMANDS = {
    "status": ("Plug state and power; the machine on the tailnet; the model and its tunnel.", []),
    "wattage": ("Live terminal chart of the wattage, redrawn each second ([q] quits).", []),
    "on": ("Power on; boots the machine if it is shut down.",
           [("--wait", "Wait until ssh answers, and print the boot time.")]),
    "off": ("Clean shutdown over ssh, then plug off.", []),
    "restart": ("off, then on --wait.", []),
    "setup": ("Once per machine: the plug, the machine, and your TP-Link login.", []),
}

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
        print("\n" + accent(f"spark {command}") + dim(" — ") + what)
        if command in DETAILS:
            print("\n" + "\n".join("  " + line for line in DETAILS[command]))
        print("\n" + bold("Usage"))
        print("  " + cyan(f"spark {command}") + (dim(" [--options]") if options else ""))
        if options:
            print("\n" + bold("Options"))
            for flag, does in options:
                print(f"  {cyan(flag.ljust(width))}{does}")
    else:
        print("\n" + accent("spark") + dim(" — power a machine on a Kasa smart plug, from anywhere"))
        print(dim("The plug through TP-Link's cloud, the machine over the tailnet."))
        print("\n" + bold("Usage"))
        print("  " + cyan("spark") + dim(" <command> [--options]"))
        print("\n" + bold("Commands"))
        for name, (what, options) in COMMANDS.items():
            print(f"  {cyan(name.ljust(width))}{what}")
            for flag, does in options:
                print(f"      {cyan(flag)}  {does}")
    print()


def main():
    args = sys.argv[1:]
    command = next((a for a in args if not a.startswith("-")), "")
    if not command or command == "help" or "-h" in args or "--help" in args:
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
    except (KeyboardInterrupt, EOFError):  # ^C, or ^D at a question: stop quietly
        print("\n" + dim("cancelled"))
        sys.exit(130)  # 128 + SIGINT, what a shell reports for ^C


if __name__ == "__main__":
    main()
