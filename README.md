# SleepTk : a sleep tracker and smart alarm for wasp-os
**Goal:** privacy friendly sleep tracker with smart alarm for the [pinetime smartwatch](https://pine64.com/product/pinetime-smartwatch-sealed/) by Pine64, on python, to run on [wasp-os](https://github.com/daniel-thompson/wasp-os).

## Features:
* **sleep tracking**: logs your movement during the night, infers your sleep cycle and write it all down in a `.csv` file
* **Flexible**: does not make too many assumption regarding time to fall asleep, sleep cycle duration etc. SleepTk tries various data to see what fits best for your profile. If you still want to customize things, all the hardcoded and commented settings are easily accessible at the top of the file.
* alarm clock: wakes you up at a specific time
* **smart alarm clock**: can wake you up to 40 minutes before the set time to make sure you wake up feeling refreshed.
* **privacy friendly**: your data is not sent to anyone, it is stored and analyzed directly on the watch (but you can still download if if needed)
* open source

## **How to install**:
*(for now you need my slightly forked wasp-os that allows to use accelerometer data)*
* download the latest [forked wasp-os](https://github.com/thiswillbeyourgithub/wasp-os)
* download the latest [SleepTk.py](./SleepTk.py)
* put the latest app in `wasp-os/wasp/apps/SleepTk.py`
* compile `wasp-os`: `make submodules && make softdevice && make BOARD=pinetime all && echo "SUCCESS"`
* upload it to your pinetime: `./tools/ota-dfu/dfu.py -z build-pinetime/micropython.zip -a XX:XX:XX:XX:XX:XX --legacy`
* reboot the watch and enjoy `SleepTk`
* *optional: download your latest sleep data using the script `pull_latest_sleep_data.py`*

### Note to reader:
* If you're interested or have any kind of things to say about this, **please** open an issue and tell me all about it :)
* Status as of end of February 2022: *UI (**done**), regular alarm (**done**), smart alarm (**mostly done but untested**)*
* you can download your sleep data file using the file `pull_latest_sleep_data`. A suggested workflow to load it into [pandas](https://pypi.org/project/pandas/) can be found at the bottom of the page.

# Screenshots:
![start](./screenshots/start_page.png)
![settings](./screenshots/settings_page.png)
![tracking](./screenshots/tracking_page.png)
![night example](./screenshots/example_night.png)

## TODO
**misc**
* retake outdated UI screenshot + data sample with the right time
* pressing the back button should return to home menu
* give up on sinus fitting, use instead a simple peak finder then take the mean / median distance between peaks as the best sleep cycle
* turn off the Bluetooth connection when beginning tracking

**sleep tracking**
* infer light and deep sleep directly on the device

**Features that I'm note sure yet**
* log smart alarm data to file
* log heart rate data every 10 minutes
* should the watch ask you after waking up to rate your freshness at wake?
* ability to send in real time to Bluetooth device the current sleep stage you're probably in. For use in Targeted Memory Reactivation.

## Related links:
* article with detailed implementation : https://www.nature.com/articles/s41598-018-31266-z
* very interesting research paper on the topic : https://academic.oup.com/sleep/article/42/12/zsz180/5549536
* maybe coding a 1D convolution is a good way to extract peaks
* list of ways to find local maxima in python : https://blog.finxter.com/how-to-find-local-minima-in-1d-and-2d-numpy-arrays/ + https://pythonawesome.com/overview-of-the-peaks-dectection-algorithms-available-in-python/




## Pandas integration:
Commands the author uses to take a look a the data using pandas:

```
fname = "./logs/sleep/YOUR_TIME.csv"

import pandas as pd
from array import array
from matplotlib import pyplot as plt

df = pd.read_csv(fname, names=["angl_avg", "time", "x_avg", "y_avg", "z_avg", "battery"])
offset = int(fname.split("/")[-1].split(".csv")[0])
df["human_time"] = pd.to_datetime(df["time"]+offset, unit='s')
df["hours"] = df["human_time"].dt.time
df = df.set_index("hours")
data = array("f", df["angl_avg"].values[:-4])
df["angl_avg"].plot()
```
