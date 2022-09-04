from pathlib import Path
import pandas as pd
from tqdm import tqdm
from numpy import arctan, pi

local_dir = Path("./remote_files/logs/sleep/")

assert local_dir.exists(), "Remote directory does not exist"

files = [f for f in local_dir.iterdir()]
assert len(files) > 0, "No files found."
print(f"{len(files)} files found.")

df_list = []
for file in tqdm(files, desc="Loading files"):
    df = pd.read_csv(file)

    df["arm_angle_approximation"] = arctan(df["Z"].values / (df["X"].values**2 + df["Y"].values**2))*180/pi

    offset = str(file).split("/")[-1].split(".csv")[0]
    df["UNIX_time"] = df["Timestamp"] + int(offset) * 10e8
    df["date"] = pd.to_datetime(df["UNIX_time"])
    df.set_index("UNIX_time")

    df_list.append(df)

print("Loaded files as dataframe as element of list 'df_list'. Openning console.")
import code ;code.interact(local=locals())
