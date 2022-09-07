from pathlib import Path
from fire import Fire
import pandas as pd
from tqdm import tqdm
from numpy import arctan, pi
from datetime import datetime
import matplotlib.pyplot as plt

# SETTINGS ###################################################################
##############################################################################

def plot(show_or_saveimg="both",
         local_dir="./remote_files/logs/sleep/",
         open_console=False,
         ):
    """
    simple script to import the sleep data into pandas and create plots

    Parameters
    ----------
    show_or_saveimg: str, default "show"
        must be in "show", "saveimg" or "both". Determines wether the data will be
        saved as png or shown to the user.
    local_dir: str, default "./remote_files/logs/sleep"
        path to the dir containing the csv files.
    open_console: bool, default False
        if True, opens a console at the end of the run
    """
    if isinstance(local_dir, str):
        local_dir = Path(local_dir)
    # check arguments
    assert local_dir.exists(), "Remote directory does not exist"
    assert show_or_saveimg in ["show", "saveimg", "both"], "Wrong 'show_or_saveimg' value"

    # load files
    files = [f for f in local_dir.iterdir() if str(f).endswith(".csv")]
    assert len(files) > 0, "No files found."
    print(f"{len(files)} files found.\r")

    recordings = {}  # where the df will be stored
    for file in tqdm(files, desc="Loading files"):
        # load file
        df = pd.read_csv(file)
        fig, ax = plt.subplots()

        # compute estimated arm angle
        df["arm_angle_approximation"] = arctan(df["Z"].values / (df["X"].values**2 + df["Y"].values**2))*180/pi

        # time data correction and loading
        offset = int(str(file).split("/")[-1].split(".csv")[0])
        df["UNIX_time"] = df["Timestamp"] + int(offset)
        df["date"] = [datetime.utcfromtimestamp(unix) for unix in df["UNIX_time"].tolist()]
        df.set_index("Timestamp")
        recording_date = str(datetime.fromtimestamp(offset))

        # ignoring too small files
        if len(df.index.tolist()) == 0:
            tqdm.write(f"  No data in df '{file}'. Ignoring this file.")
            continue
        elif len(df.index.tolist()) <= 5:
            tqdm.write(f"  Not enough data ({len(df.index.tolist())} elems) in df '{file}'. Ignoring this file.")
            continue

        # store df
        recordings[recording_date] = df

        # plot data and save to file
        try:
            ax.plot(df["date"], df["arm_angle_approximation"], label="Arm angle")
            ax.set_title(recording_date)
            ymin = df["arm_angle_approximation"].values.min()
            ymax = df["arm_angle_approximation"].values.max()

            # add vertical lines when touched
            vlines = []
            for ind in df.index:
                if df.loc[ind, "Touched"] == 1:
                    vlines.append(ind)
            if len(vlines) >0:
                ax.vlines(x=df.loc[vlines, "date"],
                           ymin=ymin,
                           ymax=ymax,
                           color="red",
                           linestyle="--",
                           label="Touched")
            ax.set_xlabel("Time")
            fig.legend(fontsize=10)
            if show_or_saveimg in ["saveimg", "both"]:
                fig.savefig(f"{local_dir}/{offset}.png",
                            bbox_inches="tight",
                            dpi=150)
                tqdm.write(f"Saved plot of '{file}' as png.")
            if show_or_saveimg in ["show", "both"]:
                fig.show()

        except Exception as err:
            tqdm.write(f"Error when plotting '{file}': '{err}'")
            continue

    df = recordings[list(recordings.keys())[-1]]
    if open_console:
        print("\rLoaded files as dataframe as values of dict 'recordings'. Opening console.")
        import code ;code.interact(local=locals())
    else:
        print("\rLoaded files as dataframe as values of dict 'recordings'.")
    input("Press any key to exit.")

if __name__ == "__main__":
    Fire(plot)
