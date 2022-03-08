#!/usr/local/bin/python3


import os
import subprocess
import shlex
import re

mode = "all"  # download "all" files or only "latest"

print("\n\nRunning gc.collect()...")
mem_cmd = './tools/wasptool --verbose --eval \'wasp.gc.collect()\''
subprocess.check_output(shlex.split(mem_cmd))

print("\n\nListing remote files...")
ls_cmd = './tools/wasptool --verbose --eval \'from shell import ls ; ls(\"/flash/logs/sleep/\")\''
out = subprocess.check_output(shlex.split(ls_cmd)).decode()
files = re.findall(r"\d*\.csv", out)
print(f"Found files {', '.join(files)}")


if mode == "latest":
    to_dl = files[-1]
elif mode == "all":
    to_dl = files
else:
    raise Exception("Wrong value for 'mode'")

print("\n\n")
for fi in to_dl:
    if os.path.exists(f"./logs/sleep/{fi}"):
        print(f"Skipping file {fi}: already exists")
    else:
        print(f"Downloading file '{fi}'")
        pull_cmd = f'./tools/wasptool --verbose --pull logs/sleep/{fi}'
        try:
            subprocess.check_output(shlex.split(pull_cmd))
            print(f"Succesfully downloaded to './logs/sleep/{fi}'")
        except Exception as e:
            print(f"Error happenned when donloading {fi}, deleting file")
            os.system(f"rm ./logs/sleep/{fi}")
    print("\n\n")
