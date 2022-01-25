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
import watch
import widgets


class SleepTrackerApp():
    NAME = 'SleepT'

    def __init__(self):
        self.filep = "sleep_tracking.txt"
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

    def touch(self, event):
        if self.btn_on:
            if self.btn_on.touch(event):
                self._tracking = watch.rtc.get_time()
                wasp.system.request_tick(300000)  # every 5 minutes
        else:
            if self.btn_off.touch(event):
                self._tracking = None
        self._draw()

    def tick(self, ticks):
        if self._tracking is not None:
            acc = [str(x) for x in watch.accel.read_xyz()]
            self.buff += "\n" + watch.rtc.time() + ",".join(acc)
            self._periodicSave()

    def _periodicSave(self):
        if len(self.buff.split("\n")) > 30:
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
