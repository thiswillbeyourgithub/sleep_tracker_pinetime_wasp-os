#!/usr/local/bin/python3

import time
from pathlib import Path
import subprocess
import shlex
import re
from tqdm import tqdm
from pprint import pprint
from plyer import notification

class download_sleep_data:
    """
    simple script to download the latest sleep data from the pinetime
    """
    def __init__(self,
                 local_dir="remote_files/logs/sleep",
                 delete_after_dl=True,
                 delete_empty_remote_files=True,
                 auto_reboot=False,
                 device=None,
                 ):
        """
        Parameters
        ----------
        local_dir: str, default "remote_files/logs/sleep"
            location of the directory where the files will be stored
        delete_after_dl: bool, default True
            if True, will delete the files on the pinetime after they have
            been downloaded. If both files are not the same size, the local
            file will be removed and a notification shown on the computer.
        delete_empty_remote_files: bool, default True
            if True, will remove remote files whose size is 0
        auto_reboot: bool, default False
            if True, will reboot the watch before every download to avoid
            memory errors.
        """
        assert device, "device bluetooth ID has to be set"
        # checking if watch is nearby and bluetooth is on
        self.n(f"Starting")
        try:
            subprocess.check_output(
                shlex.split(
                    'bluetooth on')).decode()
            time.sleep(3)
            subprocess.check_output(
                shlex.split(
                    f'./tools/wasptool --device {device} --verbose --battery')).decode()
        except Exception as err:
            self.n(f"Watch is not nearby?\rException:\r\r'{err}'")
            raise SystemExit()

        # garbage collection
        self.n("\n\nRunning gc.collect()...", do_notify=False)
        subprocess.check_output(
            shlex.split(
                f'./tools/wasptool --device {device} --verbose --eval \'wasp.gc.collect()\'')).decode()

        # checking if SleepTk is running
        out = subprocess.check_output(
                shlex.split(f'./tools/wasptool --device {device} --verbose --eval \"if hasattr(wasp, \'_SleepTk_tracking\') and wasp._SleepTk_tracking == 1: print(\'SleepTk is tracking\')\"'
                )).decode()
        if "SleepTk is tracking" in out.split("\r\r\n"):
            self.n(f"Watch is currently recording Sleep data. Exiting.")
            raise SystemExit()

        # listing remote files
        self.n("\n\nListing remote files...", do_notify=False)
        out = subprocess.check_output(
            shlex.split(
                f'./tools/wasptool --device {device} --verbose --eval \'from shell import ls ; ls(\"/flash/logs/sleep/\")\''
                )).decode()
        flines = [l.strip().split(" ") for l in out.split("\r\r\n") if l.endswith(".csv")]
        if len(flines) <= 0:
            self.n(f"No remote files found!")
            raise SystemExit()

        # getting remote file size
        size_dict = {l[1]: int(l[0]) for l in flines}
        self.n(f"Found {len(size_dict.keys())} remote files")
        pprint(size_dict)

        # remote empty remote files
        if 0 in size_dict.values() and delete_empty_remote_files:
            to_remove = []
            for file, size in tqdm(size_dict.items(),
                                   desc="Removing empty remote files"):
                if size == 0:
                    self.n(f"Removing '{file}'", do_notify=False)
                    try:
                        out = subprocess.check_output(
                            shlex.split(
                                f'./tools/wasptool --device {device} --verbose --eval \'from shell import rm ; rm(\"/flash/logs/sleep/{file}\")\''
                                )).decode()
                    except Exception as err:
                        self.n(f"Watch reported error: '{err}'")
                        breakpoint()
                    to_remove.append(file)
                    self.n(f"Removed remote file: '{file}'")
            for tr in to_remove:
                size_dict.pop(tr)

        if len(size_dict.keys()) == 0:
            self.n("No remote files to download.")
            raise SystemExit()
        else:
            to_dl = size_dict.keys()

        # download remote files
        print("\n\n")
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        for fi in tqdm(to_dl):
            lfi = Path(f"{local_dir}/{fi}")

            # remove local file if already exists and size is 0
            if lfi.exists() and lfi.stat().st_size == 0:
                lfi.unlink()

            if lfi.exists():
                tqdm.write(f"File '{fi}' already exists, you should investigate")
                continue
            else:
                if auto_reboot:
                    tqdm.write("Restarting watch and waiting 10s...")
                    out = subprocess.check_output(
                        shlex.split(
                            f'./tools/wasptool --device {device} --verbose --reset'
                            ))
                    time.sleep(10)
                tqdm.write(f"Downloading file '{fi}'")
                try:
                    out = subprocess.check_output(
                        shlex.split(
                            f'./tools/wasptool --device {device} --verbose --pull "logs/sleep/{fi}" --as "{local_dir}/{fi}"'
                            ))
                    if b"MemoryError" in out:
                        raise Exception("Memory error from watch.")
                    if b"Watch reported error" in out:
                        raise Exception("Watch reported error")
                    tqdm.write(f"Succesfully downloaded to './logs/sleep/{fi}'")
                except Exception as err:
                    tqdm.write(f"Error happened while downloading {fi}, deleting local incomplete file: '{err}'")
                    if lfi.exists():
                        lfi.unlink()
                    breakpoint()

                remote_size = size_dict[fi]
                local_size = lfi.stat().st_size
                if remote_size != local_size:
                    tqdm.write(f"Size mismatch for '{fi}':\rlocal: '{local_size}'\rremote: '{remote_size}'\rDeleting local file.")
                    if lfi.exists():
                        lfi.unlink()
                else:
                    if delete_after_dl:
                        tqdm.write(f"Downloaded remote file: '{fi}'")
                        out = subprocess.check_output(
                            shlex.split(
                                f'./tools/wasptool --device {device} --verbose --eval \'from shell import rm ; rm(\"/flash/logs/sleep/{fi}\")\''
                                )).decode()
                        tqdm.write(f"Deleted remote: '{fi}'")

            self.n("Running gc.collect()...", do_notify=False)
            subprocess.check_output(
                shlex.split(
                    f'./tools/wasptool --device {device} --verbose --eval \'wasp.gc.collect()\'')).decode()

            print("\n\n")

    def n(self, message, do_print=True, do_notify=True):
        "create notification to computer"
        try:
            if do_print:
                tqdm.write(message)
            if do_notify:
                notification.notify(title="SleepTk pull",
                                    message=message,
                                    timeout=5)
        except Exception as err:
            tqdm.write(f"Exception when creating notification: '{err}'")

if __name__ == "__main__":
    import fire
    fire.Fire(download_sleep_data)
