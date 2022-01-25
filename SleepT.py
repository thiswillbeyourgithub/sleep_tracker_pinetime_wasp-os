# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2021 github.com/thiswillbeyourgithub/

"""Sleep tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# https://github.com/thiswillbeyourgithub/sleep_tracker_pinetime_wasp-os

End goal:
This app is designed to track accelerometer and heart rate data periodically
during the night. It can also compute the best time to wake you up, up to
30 minutes before the alarm you set up manually.
"""

import wasp
import time
import watch
import widgets

# TODO : 
# * use one file per recording
# * handle last time of the month issue
# * 

class SleepTApp():
    NAME = 'SleepT'

    def __init__(self):
        self.filep = "sleep_tracking.txt"
        self.freq = 5  # poll accelerometer data every X minutes
        assert self.freq < 60
        try:
            f = open(self.filep, "r")
            f.close()
        except FileNotFoundError:
            f = open(self.filep, "w")
            f.write("")
            f.close()
        self.buff = ""  # accel data not yet written to disk
        self._tracking = None  # None = not tracking, else = start timestamp

    def foreground(self):
        self._draw()
        wasp.system.request_event(wasp.EventMask.TOUCH)

    def background(self):
        f = open(self.filep, "a")
        f.write(self.buff)
        self.buff = ""
        f.close()
        return True

    def _add_alarm(self):
        """
        adds an alarm to the next 5 minutes to log the accelerometer data
        once
        In the current implementation, time.mktime takes care of the modulo
        if for example the next alarm is at 4h65minutes
        """
        now = watch.rtc.get_localtime()
        yyyy = now[0]
        mm = now[1]
        dd = now[2]
        hh = now[3]
        mn = now[4] + self.freq
        self.next_al = time.mktime((yyyy, mm, dd, hh, mn, 0, 0, 0, 0))
        wasp.system.set_alarm(self.next_al, self._trackOnce)

    def touch(self, event):
        if self.btn_on:
            if self.btn_on.touch(event):
                self._tracking = watch.rtc.get_time()
                # add data point every self.freq minutes
                self._add_alarm()
        else:
            if self.btn_off.touch(event):
                self._tracking = None
                wasp.system.cancel_alarm(self.next_al, self._trackOnce)
                self._periodicSave()
        self._draw()

    def _trackOnce(self):
        if self._tracking is not None:
            acc = [str(x) for x in watch.accel.read_xyz()]
            self.buff += "\n" + str(int(watch.rtc.time())) + "," + ",".join(acc)
            self._add_alarm()
            print(self.buff)
            self._periodicSave()

    def _periodicSave(self):
        if len(self.buff.split("\n")) > self.freq:
            f = open(self.filep, "a")
            f.write(self.buff)
            self.buff = ""
            f.close()

    def _draw(self):
        draw = wasp.watch.drawable
        draw.fill(0)
        draw.string("Sleep Tracker", 40, 0)
        if self._tracking is None:
            self.btn_on = widgets.Button(x=50, y=120, w=100, h=100, label="On")
            self.btn_on.draw()
            self.btn_off = None
        else:
            self.btn_off = widgets.Button(x=50, y=120, w=100, h=100, label="Off")
            h = str(self._tracking[0])
            m = str(self._tracking[1])
            draw.string('Started at', 50, 70)
            draw.string(h + "h" + m + "m", 50, 80)
            self.btn_off.draw()
            self.btn_on = None
        wasp.system.bar.clock = True
        wasp.system.bar.battery = True
