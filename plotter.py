from pathlib import Path
import pandas as pd
from tqdm import tqdm
from numpy import arctan, pi
from datetime import datetime
import matplotlib.pyplot as plt

local_dir = Path("./remote_files/logs/sleep/")

assert local_dir.exists(), "Remote directory does not exist"

files = [f for f in local_dir.iterdir()]
assert len(files) > 0, "No files found."
print(f"{len(files)} files found.")

recordings = {}
for file in tqdm(files, desc="Loading files"):
    df = pd.read_csv(file)

    df["arm_angle_approximation"] = arctan(df["Z"].values / (df["X"].values**2 + df["Y"].values**2))*180/pi

    offset = int(str(file).split("/")[-1].split(".csv")[0])
    df["UNIX_time"] = df["Timestamp"] + int(offset)
    df["date"] = [datetime.utcfromtimestamp(unix) for unix in df["UNIX_time"].tolist()]
    df.set_index("Timestamp")

    recording_date = str(datetime.fromtimestamp(offset))

    if len(df.index.tolist()) == 0:
        tqdm.write(f"No data in df '{file}'")
    else:
        recordings[recording_date] = df
        plt.plot(df["date"], df["arm_angle_approximation"])
        plt.title(recording_date)
        for ind in df.index:
            if df.loc[ind, "Touched"] == 1:
                plt.axvline(x=df.loc[ind, "date"])
        plt.show()


df = recordings[recordings.keys()[-1]]
print("Loaded files as dataframe as values of dict 'recordings'. Openning console.")
import code ;code.interact(local=locals())
