# Mac

## Keeping the Mac's name

NYU's BigFix ("NYU IT EE | Rename Computer (macOS)") renames my office Mac to its asset tag, `CIMS-CFAC-AP5`, which then shows up in AirDrop and Find My.
`keepname.sh` puts `ComputerName` and `LocalHostName` back to `AlfMAC5`, and the LaunchDaemon `com.atcold.keepname.plist` runs it as root at boot and whenever `/Library/Preferences/SystemConfiguration/preferences.plist` changes.
`install.sh` installs both on `AlfMAC5` only, copying the script root-owned to `/usr/local/sbin/keepname`; after editing the script, reinstall, since the daemon runs the copy.

To install (or reinstall) only the daemon, from `Mac/`:

```bash
sudo install -d /usr/local/sbin
sudo install -o root -g wheel -m 755 keepname.sh /usr/local/sbin/keepname
sudo install -o root -g wheel -m 644 com.atcold.keepname.plist /Library/LaunchDaemons/
sudo launchctl bootout system/com.atcold.keepname 2>/dev/null
sudo launchctl bootstrap system /Library/LaunchDaemons/com.atcold.keepname.plist
```

To uninstall:

```bash
sudo launchctl bootout system/com.atcold.keepname
sudo rm /Library/LaunchDaemons/com.atcold.keepname.plist /usr/local/sbin/keepname
```

Each reset is logged:

```bash
log show --last 1d --predicate 'process == "logger"' | grep 'reset to'
```
