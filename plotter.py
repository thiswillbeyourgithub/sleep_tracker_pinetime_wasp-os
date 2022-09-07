from pathlib import Path
import pandas as pd
from tqdm import tqdm
from numpy import arctan, pi
from datetime import datetime
import matplotlib.pyplot as plt

local_dir = Path("./remote_files/logs/sleep/")

assert local_dir.exists(), "Remote directory does not exist"

files = [f for f in local_dir.iterdir() if str(f).endswith(".csv")]
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
        tqdm.write(f"No data in df '{file}'. Ignoring this file.")
    elif len(df.index.tolist()) <= 5:
        tqdm.write(f"Not enough data ({len(df.index.tolist())} elems) in df '{file}'. Ignoring this file.")
    else:
        recordings[recording_date] = df
        try:
            plt.plot(df["date"], df["arm_angle_approximation"], label="Arm angle")
            plt.title(recording_date)
            ymin=df["arm_angle_approximation"].values.min()
            ymax=df["arm_angle_approximation"].values.max()
            # add vertical lines when touched
            vlines = []
            for ind in df.index:
                if df.loc[ind, "Touched"] == 1:
                    vlines.append(ind)
            if len(vlines) >0:
                plt.vlines(x=df.loc[vlines, "date"],
                           ymin=ymin,
                           ymax=ymax,
                           color="red",
                           linestyle="--",
                           label="Touched")
            plt.xlabel("Time")
            plt.legend(fontsize=10)
            plt.savefig(f"{local_dir}/{offset}.png",
                        bbox_inches="tight",
                        dpi=150)
            #plt.show()
        except Exception as err:
            tqdm.write(f"Error when plotting '{file}': '{err}'")

df = recordings[list(recordings.keys())[-1]]
print("Loaded files as dataframe as values of dict 'recordings'. Openning console.")
import code ;code.interact(local=locals())
