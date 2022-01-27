# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2021 github.com/thiswillbeyourgithub/

"""Sleep tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# https://github.com/thiswillbeyourgithub/sleep_tracker_pinetime_wasp-os

End goal:
This app is designed to track accelerometer and heart rate data periodically
during the night. It can also compute the best time to wake you up, up to
30 minutes before the alarm you set up manually.

Current state:
Trying to log my sleep data for a few days prior to working on the algorithm
"""

import wasp
import time
import watch
import widgets
import shell


class SleepTApp():
    NAME = 'SleepT'

    def __init__(self):
        self.freq = 300  # poll accelerometer data every X seconds
        self._tracking = False  # False = not tracking, True = currently tracking
        try:
            shell.mkdir("sleep_accel_data")
        except:  # file exists
            pass

    def foreground(self):
        self._draw()
        wasp.system.request_event(wasp.EventMask.TOUCH)

    def background(self):
        if self._tracking is not None:
            f = open(self.filep, "a")
            f.write(self.buff)
            self.buff = ""
            f.close()

    def _add_accel_alar(self):
        """set an alarm, due in self.freq minutes, to log the accelerometer data
        once"""
        self.next_al = time.mktime(watch.rtc.get_localtime()) + self.freq
        wasp.system.set_alarm(self.next_al, self._trackOnce)

    def touch(self, event):
        if self.btn_on:
            if self.btn_on.touch(event):
                self._tracking = True
                self.buff = ""  # accel data not yet written to disk
                # create one file for each run
                tod = [str(x) for x in watch.rtc.get_localtime()[0:5]]
                self.filep = "sleep_accel_data/" + "_".join(tod) + ".txt"
                # add data point every self.freq minutes
                self._data_point_nb = 0  # tracks number of data_points so far
                self._start_t = watch.rtc.get_time()
                self._add_accel_alar()
                self._draw()
        else:
            if self.btn_off.touch(event):
                self._tracking = False
                self.start_t = None
                wasp.system.cancel_alarm(self.next_al, self._trackOnce)
                self._periodicSave(force_save=True)
                self._draw()

    def _trackOnce(self):
        """get one data point of accelerometer
        this function is called every self.freq seconds"""
        if self._tracking:
            acc = [str(x) for x in watch.accel.read_xyz()]
            self._data_point_nb += 1
            self.buff += str(self._data_point_nb) + "," + str(int(watch.rtc.time())) + "," + ",".join(acc) + "\n"
            self._add_accel_alar()
            self._periodicSave()

    def _periodicSave(self, force_save=False):
        """save data to file only every few checks"""
        if len(self.buff.split("\n")) > 20 or force_save:
            f = open(self.filep, "a")
            f.write(self.buff)
            self.buff = ""
            f.close()

    def _draw(self):
        """GUI"""
        draw = wasp.watch.drawable
        draw.fill(0)
        draw.string("Sleep Tracker", 40, 0)
        if self._tracking:
            self.btn_off = widgets.Button(x=0, y=170, w=240, h=69, label="Off")
            h = str(self._start_t[0])
            m = str(self._start_t[1])
            draw.string('Started at ' + h + ":" + m, 0, 70)
            draw.string("data:" + str(self._data_point_nb), 0, 90)
            draw.string("bat:" + str(watch.battery.level()) + "%", 0, 110)
            self.btn_off.draw()
            self.btn_on = None
        else:
            self.btn_on = widgets.Button(x=0, y=170, w=240, h=69, label="On")
            self.btn_on.draw()
            self.btn_off = None
