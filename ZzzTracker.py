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
from wasp import watch, system, EventMask, gc
from math import atan, pow, degrees
from time import mktime
from watch import rtc, battery, accel
from widgets import Clock, BatteryMeter, Button
from shell import mkdir, cd
from fonts import sans18
from micropython import const


_POLLFREQ = const(15)  # poll accelerometer data every X seconds, they will be averaged
_WIN_L = const(300)  # number of seconds between writing average accel values
_RATIO = const(20)  # must be _WIN_L / _POLLFREQ, means that data will be written every X data points
_FONT = sans18

class ZzzTrackerApp():
    NAME = 'ZzzTrck'

    def __init__(self):
        self._tracking = False  # False = not tracking, True = currently tracking
        try:
            mkdir("logs/")
        except:  # folder already exists
            pass
        cd("logs")
        try:
            mkdir("sleep")
        except:  # folder already exists
            pass
        cd("..")

    def foreground(self):
        self._draw()
        system.request_event(EventMask.TOUCH)

    def sleep(self):
        """keep running in the background"""
        return False

    def touch(self, event):
        """either start trackign or disable it, draw the screen in all cases"""
        if self.btn_on:
            if self.btn_on.touch(event):
                self._tracking = True
                # accel data not yet written to disk:
                self.buff_x = 0
                self.buff_y = 0
                self.buff_z = 0
                self._data_point_nb = 0  # total number of data points so far
                self._last_checkpoint = 0  # to know when to save to file
                self._start_t = rtc.get_time()  # to display when recording started on screen
                self.offset = const(int(rtc.time()))  # makes output more compact

                # create one file per recording session:
                self.filep = "logs/sleep/" + str(self.offset) + ".csv"
                self._add_accel_alar()
        else:
            if self.btn_off.touch(event):
                self._tracking = False
                self.start_t = None
                system.cancel_alarm(self.next_al, self._trackOnce)
                self._periodicSave()
                self.offset = None
                self._last_checkpoint = 0
        self._draw()

    def _add_accel_alar(self):
        """set an alarm, due in _POLLFREQ minutes, to log the accelerometer data
        once"""
        self.next_al = mktime(rtc.get_localtime()) + _POLLFREQ
        system.set_alarm(self.next_al, self._trackOnce)

    def _trackOnce(self):
        """get one data point of accelerometer every _POLLFREQ seconds and
        they are then averaged and stored every _WIN_L seconds"""
        if self._tracking:
            acc = accel.read_xyz()
            self.buff_x += acc[0]
            self.buff_y += acc[1]
            self.buff_z += acc[2]
            self._data_point_nb += 1
            self._add_accel_alar()
            self._periodicSave()

    def _periodicSave(self):
        """save data after averageing over a window to file"""
        n = self._data_point_nb - self._last_checkpoint
        if n >= _RATIO:
            x_avg = self.buff_x / n
            y_avg = self.buff_y / n
            z_avg = self.buff_z / n
            self.buff_x = 0
            self.buff_y = 0
            self.buff_z = 0

            # formula from https://www.nature.com/articles/s41598-018-31266-z
            angl_avg = degrees(atan(z_avg / (pow(x_avg, 2) + pow(y_avg, 2) + 0.0000001)))

            val = []
            val.append(str(int(rtc.time() - self.offset)))
            val.append(str(x_avg)[0:6])
            val.append(str(y_avg)[0:6])
            val.append(str(z_avg)[0:6])
            val.append(str(angl_avg)[0:6])
            val.append(str(battery.level()))

            f = open(self.filep, "a")
            f.write(",".join(val) + "\n")
            f.close()
            self._last_checkpoint = self._data_point_nb
            gc.collect()

    def _draw(self):
        """GUI"""
        draw = watch.drawable
        draw.fill(0)
        draw.set_font(_FONT)
        if self._tracking:
            self.btn_off = Button(x=0, y=170, w=240, h=69, label="Stop tracking")
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
            self.btn_on = Button(x=0, y=170, w=240, h=69, label="Start tracking")
            self.btn_on.draw()
            self.btn_off = None
        self.cl = Clock(True)
        self.cl.draw()
        bat = BatteryMeter()
        bat.draw()
