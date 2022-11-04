from pathlib import Path
from fire import Fire
import pandas as pd
from tqdm import tqdm
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
from send2trash import send2trash


# SETTINGS ###################################################################
##############################################################################

def plot(show_or_saveimg="both",
         local_dir="./remote_files/logs/sleep/",
         open_console=False,
         n_last=3,
         ):
    """
    simple script to import the sleep data into pandas and create plots

    Parameters
    ----------
    show_or_saveimg: str, default "both"
        must be in "show", "saveimg" or "both". Determines wether the data will be
        saved as png or shown to the user.
    local_dir: str, default "./remote_files/logs/sleep"
        path to the dir containing the csv files.
    open_console: bool, default False
        if True, opens a console at the end of the run
    n_last: int, default 3
        number of files to actually process. For example '3' will mean 'ignore
        all files but the recordings of the last 3 nights'. This is useful if
        you have lots of recordings and want to see only the last few nights.
        None to disable.
    """
    if isinstance(local_dir, str):
        local_dir = Path(local_dir)
    # check arguments
    assert local_dir.exists(), "Remote directory does not exist"
    assert show_or_saveimg in ["show", "saveimg", "both"], "Wrong 'show_or_saveimg' value"

    # load files
    files = sorted([f for f in local_dir.iterdir() if str(f).endswith(".csv")])
    if n_last is not None:
        assert n_last > 0, "Wrong n_last value"
        files = files[-n_last - 1:]
        print(f"Processing only {n_last} most recent recordings.")
    assert len(files) > 0, "No files found."
    print(f"{len(files)} files found.\r")

    recordings = {}  # where the df will be stored
    for file in tqdm(files, desc="Loading files"):
        # load file
        df = pd.read_csv(file)

        # ignore small files
        if len(df.index.tolist()) == 0:
            tqdm.write(f"  No data in df '{file}'. Ignoring this file.")
            continue
        elif len(df.index.tolist()) <= 5:
            tqdm.write(f"  Not enough data ({len(df.index.tolist())} elems) in df '{file}'. Trashing this file.")
            try:
                send2trash(file)
            except Exception as err:
                tqdm.write(f"Exception when trashing '{file}': '{err}'")
            continue

        # detect version number and saving interval
        assert file.name.count("_") >= 2, "invalid filename"
        version = int(file.name.split("_")[2].replace(".csv", ""))
        interval = int(file.name.split("_")[1])

        # fill elipsed timestamp value
        df.iloc[0]["Timestamp"] = 1
        for i, row in df.iterrows():
            if i == 0:
                continue
            if pd.isna(df.loc[i, "Timestamp"]):
                assert not pd.isna(df.loc[i - 1, "Timestamp"]), "ERROR"
                df.loc[i, "Timestamp"] = (df.loc[i - 1, "Timestamp"] + 1)
        df["Timestamp"] *= interval
        df["Timestamp"] = df["Timestamp"].astype(int)

        # time data correction and loading
        offset = int(str(file).split("/")[-1].split("_")[0])
        df["UNIX_time"] = df["Timestamp"] + int(offset)
        df["date"] = [datetime.utcfromtimestamp(unix)
                      for unix in df["UNIX_time"].tolist()]
        df["clock"] = pd.to_datetime(df["date"]).dt.time
        df["clock"] = df["clock"].astype(str)
        recording_date = str(datetime.utcfromtimestamp(offset))

        # cast types and fill ellipsed values
        df.loc[df["Meta"].isna(), "Meta"] = 0
        df.loc[df["BPM"].isna(), "BPM"] = "?"
        df["Meta"] = df["Meta"].astype(int)

        # process motion signal
        df["Motion"] /= 1000
        df["Motion"] = df["Motion"].diff().abs()

        # replace first value that got erased by abs()
        df["Motion"].fillna(0.0, inplace=True)

        # clip values that are too high
        df["Motion"].clip(lower=0, upper=df["Motion"].quantile(0.95), inplace=True)

        # compute smoothing etc if desired
        #df["Motion"] = df["Motion"].rolling(window=4, center=True, closed='both').max()

        # store df
        recordings[recording_date] = df

        # plot data and save to file
        try:
            # init plot
            fig, ax = plt.subplots()
            ax.set_xlabel("Time")
            ax.set_title(f"{recording_date}  ({file.name})")

            # plot bpm data if present
            bpm_vals = df.loc[ df["BPM"].dropna() != "?"].index.tolist()
            if len(bpm_vals) >= 2:
                df.loc[bpm_vals, "BPM"] = df.loc[bpm_vals, "BPM"].astype(int)
                #df.loc[bpm_vals, "BPM"] = df.loc[bpm_vals, "BPM"].rolling(window=10, center=True, closed='both').mean().rolling(window=3, center=True, closed='both').mean()
                ax_bpm = ax.twinx()
                ax_bpm.set_ylabel("BPM")
                max_bpm = int(df.loc[bpm_vals, "BPM"].dropna().values.max())
                min_bpm = int(df.loc[bpm_vals, "BPM"].dropna().values.min())
                print(f"BPM range: {min_bpm}-{max_bpm}")
                ax_bpm.plot(df.loc[bpm_vals, "Timestamp"],
                            df.loc[bpm_vals, "BPM"],
                            color="red",
                            linewidth=0.5,
                            label="BPM")

            # plot motion
            ax.plot(df["Timestamp"],
                    df["Motion"],
                    color="purple",
                    linewidth=1,
                    label="Motion")

            # add hour time as xlabels only every 4 recording
            ax.set_xticks(ticks=df["Timestamp"])
            partial_clock = df["clock"].tolist()
            for i, pc in enumerate(partial_clock):
                if i % 4 != 0:
                    partial_clock[i] = ""
            ax.set_xticklabels(partial_clock, rotation=90)

            # add vertical lines depending on state
            ymin = df["Motion"].min()
            ymax = df["Motion"].max()
            assert ymin != ymax  # if equal, they are probably both np.nan

            touched_ind = []
            gradual_vib = []
            both = []
            for ind in df.index:
                if df.loc[ind, "Meta"] == 0:
                    continue
                if df.loc[ind, "Meta"] == 1:
                    touched_ind.append(ind)
                elif df.loc[ind, "Meta"] == 2:
                    gradual_vib.append(ind)
                elif df.loc[ind, "Meta"] == 3:
                    both.append(ind)
                else:
                    raise ValueError()
            if len(touched_ind) > 0:
                ax.vlines(x=df.loc[touched_ind, "Timestamp"],
                          ymin=ymin,
                          ymax=ymax,
                          color="green",
                          linestyle="dotted",
                          linewidth=2.5,
                          label="Touched")
            if len(gradual_vib) > 0:
                ax.vlines(x=df.loc[gradual_vib, "Timestamp"],
                          ymin=ymin,
                          ymax=ymax,
                          color="blue",
                          linestyle="dotted",
                          linewidth=2.5,
                          label="Small vibration")
            if len(both) > 0:
                ax.vlines(x=df.loc[both, "Timestamp"],
                          ymin=ymin,
                          ymax=ymax,
                          color="black",
                          linestyle="dotted",
                          linewidth=2.5,
                          label="Both")
            # save or show
            fig.legend(fontsize=10,
                       prop={"size": 10},
                       )
            if show_or_saveimg in ["saveimg", "both"]:
                fig.savefig(f"{local_dir}/{offset}.png",
                            bbox_inches="tight",
                            dpi=150)
                tqdm.write(f"Saved plot of '{file}' as png.")
            if show_or_saveimg in ["show", "both"]:
                fig.show()

        except Exception as err:
            tqdm.write(f"Error when plotting '{file}': '{err}'")
            raise

    df = recordings[list(recordings.keys())[-1]]
    if open_console:
        print("\rLoaded files as dataframe as values of dict 'recordings'. Opening console.")
        import code
        code.interact(local=locals())
    else:
        print("\rLoaded files as dataframe as values of dict 'recordings'.")
    if show_or_saveimg in ["show", "both"]:
        input("Press any key to exit.")  # stops the plots from exiting


if __name__ == "__main__":
    Fire(plot)
