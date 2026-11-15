#!/usr/bin/env python3
"""Install cucina's command and optional boot entry on this machine."""
import argparse
import json
import os
from pathlib import Path
import sys

here=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',help='service URL used by the terminal picker')
parser.add_argument('--host',help='address on which to serve')
parser.add_argument('--port',type=int,default=8082)
parser.add_argument('--boot',action='store_true')
args=parser.parse_args()
for standard,leaf in [('.config','config'),('.cache','cache'),('.local/share','data')]:
    directory=Path.home()/standard/'cucina'
    if sys.platform=='darwin' and not directory.exists():
        target=Path.home()/'Dropbox/Apps/cucina'/leaf
        target.mkdir(parents=True,exist_ok=True)
        directory.parent.mkdir(parents=True,exist_ok=True)
        directory.symlink_to(target,target_is_directory=True)
    else:
        directory.mkdir(parents=True,exist_ok=True)
configfile=Path.home()/'.config/cucina/config.json'
try:config=json.loads(configfile.read_text())
except (OSError,ValueError):config={}
if args.url:config['url']=args.url
if args.host:config['host']=args.host
config.setdefault('port',args.port)
configfile.write_text(json.dumps(config,indent=2)+'\n')
binpath=Path(os.environ.get('PREFIX',str(Path.home()/'.local')))/'bin'
binpath.mkdir(parents=True,exist_ok=True)
command=binpath/'cucina'
if command.is_symlink():command.unlink()
elif command.exists():raise SystemExit('Existing command preserved: '+str(command))
command.symlink_to(here/'cucina')
(here/'cucina').chmod(0o755)
if args.boot:
    boot=Path.home()/'.termux/boot/cucina'
    boot.parent.mkdir(parents=True,exist_ok=True)
    # A relative link also works when Termux's boot directory is itself a link.
    if boot.is_symlink():boot.unlink()
    if not boot.exists():
        boot.symlink_to(here/'boot-cucina')
print('Installed cucina · '+str(command))
