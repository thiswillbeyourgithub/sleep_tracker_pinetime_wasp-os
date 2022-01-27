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

from os import stat
import wasp
from math import atan, pi, pow
import time
import watch
import widgets
from shell import mkdir
import fonts
from micropython import const

_RAD = 180/pi
_OFFSET = const(1600000000)


class ZzzTrackerApp():
    NAME = 'ZzzTrck'

    def __init__(self):
        self.freq = 300  # poll accelerometer data every X seconds
        self._tracking = False  # False = not tracking, True = currently tracking
        self.font = fonts.sans18
        try:
            mkdir("logs/")
        except:  # folder already exists
            pass
        try:
            mkdir("logs/sleep")
        except:  # folder exists
            pass

    def foreground(self):
        self._draw()
        wasp.system.request_event(wasp.EventMask.TOUCH)

    def sleep(self):
        """keep running in the background"""
        return False

    def touch(self, event):
        if self.btn_on:
            if self.btn_on.touch(event):
                self._tracking = True
                self.buff = ""  # accel data not yet written to disk
                self._data_point_nb = 0  # tracks number of data_points so far
                self._start_t = watch.rtc.get_time()

                # create one file per recording session:
                self.filep = "logs/sleep/" + "_".join(map(str, watch.rtc.get_localtime()[0:5])) + ".csv"
                self._add_accel_alar()
        else:
            if self.btn_off.touch(event):
                self._tracking = False
                self.start_t = None
                wasp.system.cancel_alarm(self.next_al, self._trackOnce)
                self._periodicSave(force_save=True)
        self._draw()

    def _add_accel_alar(self):
        """set an alarm, due in self.freq minutes, to log the accelerometer data
        once"""
        self.next_al = time.mktime(watch.rtc.get_localtime()) + self.freq
        wasp.system.set_alarm(self.next_al, self._trackOnce)

    def _trackOnce(self):
        """get one data point of accelerometer
        this function is called every self.freq seconds
        I kept only the first 5 digits of some values to save space"""
        if self._tracking:
            acc = watch.accel.read_xyz()
            self._data_point_nb += 1
            # formula from https://www.nature.com/articles/s41598-018-31266-z
            angle = atan(acc[2] / (pow(acc[0], 2) + pow(acc[1], 2) + 0.0000001)) * _RAD

            val = []
            val.append(str(self._data_point_nb))
            val.append(str(int(watch.rtc.time() - _OFFSET)))  # more compact
            val.extend([str(x * _RAD)[0:5] for x in acc])
            val.append(str(angle)[0:5])
            val.append(str(watch.battery.level()))
            #print(val)

            self.buff += ",".join(val) + "\n"
            self._add_accel_alar()
            self._periodicSave(force_save=True)

    def _periodicSave(self, force_save=False):
        """save data to file only every few checks"""
        if len(self.buff.split("\n")) > 5 or force_save:
            f = open(self.filep, "a")
            f.write(self.buff)
            self.buff = ""
            f.close()
            wasp.gc.collect()

    def _draw(self):
        """GUI"""
        draw = wasp.watch.drawable
        draw.fill(0)
        draw.set_font(self.font)
        if self._tracking:
            self.btn_off = widgets.Button(x=0, y=170, w=240, h=69, label="Stop tracking")
            self.btn_off.draw()
            h = str(self._start_t[0])
            m = str(self._start_t[1])
            draw.string('Started at ' + h + ":" + m, 0, 70)
            draw.string("data:" + str(self._data_point_nb), 0, 90)
            try:
                draw.string("size:" + str(stat(self.filep)[6]), 0, 110)
            except:
                pass
            self.btn_on = None
        else:
            draw.string('Track your sleep' , 0, 70)
            self.btn_on = widgets.Button(x=0, y=170, w=240, h=69, label="Start tracking")
            self.btn_on.draw()
            self.btn_off = None
        self.cl = widgets.Clock(True)
        self.cl.draw()
        bat = widgets.BatteryMeter()
        bat.draw()
