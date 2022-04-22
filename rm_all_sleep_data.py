#!/usr/local/bin/python3

import time
import subprocess
import shlex
import re

print("\n\nRunning gc.collect()...")
mem_cmd = './tools/wasptool --verbose --eval \'wasp.gc.collect()\''
subprocess.check_output(shlex.split(mem_cmd))

print("\n\nListing remote files...")
ls_cmd = './tools/wasptool --verbose --eval \'from shell import ls ; ls(\"/flash/logs/sleep/\")\''
out = subprocess.check_output(shlex.split(ls_cmd)).decode()
files = re.findall(r"\d*\.csv", out)
print(f"Found files {', '.join(files)}")

reset_cmd = './tools/wasptool --verbose --reset'

to_rm = files

print("\n\n")
for fi in to_rm:
    print(f"Removing file '{fi}'")
    rm_cmd = f'./tools/wasptool --verbose --eval \'from shell import rm ; rm(\"logs/sleep/{fi}\")\''
    try:
        out = subprocess.check_output(shlex.split(rm_cmd))
        if b"Watch reported error" in out:
            raise Exception("Watch reported error")
        print(f"Succesfully removed to './logs/sleep/{fi}'")
    except Exception as e:
        print(f"Error happened while removing {fi}")

    print("Restarting watch.")
    out = subprocess.check_output(shlex.split(reset_cmd))
    time.sleep(10)

    print("\n\n")
