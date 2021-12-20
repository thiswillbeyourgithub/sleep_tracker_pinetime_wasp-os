# Waspos Sleep Tracker
**Goal:** sleep tracker for the [pinetime smartwatch](https://pine64.com/product/pinetime-smartwatch-sealed/) by Pine64, on python, to run on [wasp-os](https://github.com/daniel-thompson/wasp-os).

## Note to reader:
* I'm intend to start coding around January 2022
* I created this repository before even receiving my pine time and despite a very busy schedule to make sure no one else starts a similar project and end up duplicating efforts for nothing :)
* If you're interested or have any kind of things to say about this, **please** open an issue and tell me all about it :)

## Currently planned features:
**sleep tracking**
* tracks sleep using wrist motion data and occasional heart rate monitoring
    * each night is recorded in a file that can be easily sent back to the phone
* rudimentary display of sleep graph on the device itself, with a quality score if I can find a good metric
* try to roughly infer the sleep stage *on the device itself*
    * if you actually use the watch during the night, make sure to count it as wakefulness

**alarm clock**
* setting up an alarm should suggest the most appropriate sleep duration like what [sleepyti.me](http://sleepyti.me) does
* try to optimize the wake up time based on inferred sleep stage

**settings panel**
* to specify how early the watch can wake you
* to specify a battery threshold under which it should not keep tracking sleep, to make sure you don't drain the battery and end up missing the alarm clock

**misc**
* turn off the Bluetooth connection when no phone is connected
* turn off the screen during the night
* make sure to not use more than X% of the battery in all cases
* make sure to turn off if sleep lasts more than 12h (in which case the user forgot to disable it)
* ability to send in real time to Bluetooth device the current sleep stage you're probably in. For use in Targeted Memory Reactivation.
* hardcode limits to avoid issues if heart rate is suddenly found to be through the roof or something
