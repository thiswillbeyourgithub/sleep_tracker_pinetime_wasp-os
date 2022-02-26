#!/usr/local/bin/python3


import os
import subprocess
import shlex
import re

ls_cmd = './tools/wasptool --verbose --eval \'from shell import ls ; ls(\"logs/sleep\")\''
ls_cmd = shlex.split(ls_cmd)  # properly split args
print("Listing remote files...")
out = subprocess.check_output(ls_cmd).decode()
files = re.findall(r"\d*\.csv", out)
print(f"Found files {', '.join(files)}")
latest = files[-1]
print(f"Most recent file is: {latest}")

pull_cmd = f'./tools/wasptool --verbose --pull logs/sleep/{latest}'
os.system(pull_cmd)

print(f"Succesfully downloaded file to 'logs/sleep/{latest}'")
