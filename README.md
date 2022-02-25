# SleepTk : a sleep tracker and smart alarm for wasp-os
**Goal:** sleep tracker and smart alarm for the [pinetime smartwatch](https://pine64.com/product/pinetime-smartwatch-sealed/) by Pine64, on python, to run on [wasp-os](https://github.com/daniel-thompson/wasp-os), that wakes you up at the best time.

## Note to reader:
* I created this repository before even receiving my pine time and despite a very busy schedule to make sure no one else starts a similar project and end up duplicating efforts for nothing :)
* If you're interested or have any kind of things to say about this, **please** open an issue and tell me all about it :)
* Status as of end of February 2022:
    * Finished the UI and the alarm but the smart alarm implementation is not at all tested.
    * **Instructions**:
    *(for now you need my forked wasp-os that exposes accelerometer data)
        * download [my wasp-os fork](https://github.com/thiswillbeyourgithub/wasp-os)
        * download the latest app : SleepTk.py
        * put the latest app in wasp-os/wasp/apps/SleepTk.py
        * compile and install wasp-os
        * run the app
        * *if you want, you can get back the data using `wasptool --pull`,  to take a look using pandas : ` df = pd.read_csv("./first.night.csv", names=["time", "x_avg", "y_avg", "z_avg", "angl_avg", "battery"])` (name and number of columns might change)*

# Screenshots:
![start](./screenshots/start_page.png)
![settings](./screenshots/settings_page.png)
![tracking](./screenshots/tracking_page.png)

## TODO
**sleep tracking**
* try to roughly infer the sleep stage directly on the device?
    * if you actually use the watch during the night, make sure to count it as wakefulness?

**misc**
* turn off the Bluetooth connection when no phone is connected?
* ability to send in real time to Bluetooth device the current sleep stage you're probably in. For use in Targeted Memory Reactivation.
* find a way to remove outliers of stored values

**Features that I'm note sure yet**
* should the watch ask you after waking up to rate your freshness at wake?

## Related links:
* article with detailed implementation : https://www.nature.com/articles/s41598-018-31266-z
* very interesting research paper on the topic : https://academic.oup.com/sleep/article/42/12/zsz180/5549536
* maybe coding a 1D convolution is a good way to extract peaks
* list of ways to find local maxima in python : https://blog.finxter.com/how-to-find-local-minima-in-1d-and-2d-numpy-arrays/ + https://pythonawesome.com/overview-of-the-peaks-dectection-algorithms-available-in-python/
