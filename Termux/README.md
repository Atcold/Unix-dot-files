# Termux settings

Settings for Termux, the Linux terminal app on Android. Clone this repository into `~/.settings` on the phone with `pkg install git`, then run `./install.sh` from this folder.

The installer adds the command line tools with `pkg`, Termux's package manager, and links `termux.properties`, the `boot` folder (run at startup by the Termux:Boot add-on, which keeps the processor awake and starts the SSH server), `colors.properties` (the palette of `Mac/Monokai.terminal`), `bashrc`, the Git configuration, and the Neovim configuration. It builds the terminal font from Cascadia's ExtraLight Nerd Font face with the pinyin patch in `Scripts/`, as on the Mac.

`bashrc` holds what applies only to Termux and loads the shared `Bash/bashrc` at the end. The prompt shows the phone's name and a user name when `$PREFIX/etc/machine-info` sets them, as `PRETTY_HOSTNAME=` and `PRETTY_USERNAME=` lines; otherwise it shows Termux's own account, such as `u0_a1`.

Two Android settings keep the phone reachable after a reboot, and a computer with USB debugging sets both. Tailscale must be the always-on VPN, `adb shell settings put secure always_on_vpn_app com.tailscale.ipn`, and both apps must be exempt from battery optimisation, `adb shell dumpsys deviceidle whitelist +com.tailscale.ipn` and the same for `com.termux`; otherwise Android holds Tailscale back after a boot until something wakes the phone.
