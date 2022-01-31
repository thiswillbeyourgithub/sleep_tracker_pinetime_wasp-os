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
from time import mktime

from watch import rtc, battery, accel
from widgets import Clock, BatteryMeter, Button
from shell import mkdir, cd
from fonts import sans18

from math import atan, pow, degrees, sqrt
from micropython import const
from array import array


_POLLFREQ = const(10)  # poll accelerometer data every X seconds, they will be averaged
_WIN_L = const(300)  # number of seconds between writing average accel values
_RATIO = const(30)  # must be _WIN_L / _POLLFREQ, means that data will be written every X data points

_WU_ON = const(0)  # const(1) to activate wake up alarm, const(0) to disable
_WU_LAT = const(28800)  # maximum seconds of sleep before waking you up, default 28800 = 8h, will compute best wake up time from _WU_LAT - _WU_ANTICIP seconds
_WU_ANT_ON = const(0)
_WU_ANTICIP = const(1800)  # default 1800 = 30 minutes

_FONT = sans18

class ZzzTrackerApp():
    NAME = 'ZzzTrck'

    def __init__(self):
        self._tracking = False  # False = not tracking, True = currently tracking
        self._WakingUp = False  # when True, watch is currently vibrating to wake you up
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
                self._buff = []
                self._data_point_nb = 0  # total number of data points so far
                self._last_checkpoint = 0  # to know when to save to file
                self._offset = int(rtc.time())  # makes output more compact

                # create one file per recording session:
                self.filep = "logs/sleep/" + str(self._offset) + ".csv"
                self._add_accel_alar()

                # alarm in _WU_LAT seconds after tracking started to wake you up
                if _WU_ON:
                    self._WU_t = self._offset + _WU_LAT
                    system.set_alarm(self._WU_t, self._listen_to_ticks)

                    # alarm in _WU_ANTICIP less seconds to compute best wake up time
                    if _WU_ANT_ON:
                        self._WU_a = self._WU_t - _WU_ANTICIP
                        system.set_alarm(self._WU_a, self._compute_best_WU)
        elif self.btn_off:
            if self.btn_off.touch(event):
                self._disable_tracking()
        elif self.btn_al:
            if self.btn_al.touch(event):
                self._WakingUp = False
                self._disable_tracking()
        self._draw()

    def _disable_tracking(self):
        """called by touching "STOP TRACKING" or when computing best alarm time
        to wake up you
        disables tracking features and alarms"""
        self._tracking = False
        system.cancel_alarm(self.next_al, self._trackOnce)
        if _WU_ON:
            system.cancel_alarm(self._WU_t, self._listen_to_ticks)
            if _WU_ANT_ON:
                system.cancel_alarm(self._WU_a, self._compute_best_WU)
        self._periodicSave()
        self._offset = None
        self._last_checkpoint = 0

    def _add_accel_alar(self):
        """set an alarm, due in _POLLFREQ minutes, to log the accelerometer data
        once"""
        self.next_al = watch.rtc.time() + _POLLFREQ
        system.set_alarm(self.next_al, self._trackOnce)

    def _trackOnce(self):
        """get one data point of accelerometer every _POLLFREQ seconds and
        they are then averaged and stored every _WIN_L seconds"""
        if self._tracking:
            self._buff.append(accel.read_xyz())
            self._data_point_nb += 1
            self._add_accel_alar()
            self._periodicSave()

    def _periodicSave(self):
        """save data after averageing over a window to file"""
        n = self._data_point_nb - self._last_checkpoint
        if n >= _RATIO:
            x_avg = sum([x[0] for x in self._buff]) / n
            y_avg = sum([x[1] for x in self._buff]) / n
            z_avg = sum([x[2] for x in self._buff]) / n
            self._buff = []

            # formula from https://www.nature.com/articles/s41598-018-31266-z
            angl_avg = degrees(atan(z_avg / (pow(x_avg, 2) + pow(y_avg, 2) + 0.0000001)))

            val = array("f")
            val.append(int(rtc.time() - self._offset))
            val.append(x_avg)
            val.append(y_avg)
            val.append(z_avg)
            val.append(angl_avg)
            val.append(battery.level())

            f = open(self.filep, "a")
            f.write(",".join([str(x)[0:8] for x in val]) + "\n")
            f.close()

            self._last_checkpoint = self._data_point_nb
            del x_avg, y_avg, z_avg, angl_avg, n, val
        gc.collect()

    def _draw(self):
        """GUI"""
        draw = watch.drawable
        draw.fill(0)
        draw.set_font(_FONT)
        if self._WakingUp:
            self.btn_al = Button(x=0, y=170, w=240, h=69, label="STOP")
            self.btn_al.draw()
            self.btn_on = None
            self.btn_off = None
        elif self._tracking:
            self.btn_off = Button(x=0, y=170, w=240, h=69, label="Stop tracking")
            self.btn_off.draw()
            draw.string('Started at ' + str(watch.time.localtime(self._offset)[3]) + ":" + str(watch.time.localtime(self._offset)[4]) , 0, 70)
            draw.string("data:" + str(self._data_point_nb), 0, 90)
            try:
                draw.string("size:" + str(stat(self.filep)[6]), 0, 110)
            except:
                pass
            if _WU_ON:
                if _WU_ANT_ON:
                    word = " bef. "
                else:
                    word = " at "
                draw.string("Wake up" + word + str(watch.time.localtime(self._offset + _WU_LAT)[3]) + ":" + str(watch.time.localtime(self._offset + _WU_LAT)[4]), 0, 130)
            self.btn_on = None
            self.btn_al = None
        else:
            draw.string('Sleep tracker' , 0, 70)
            self.btn_on = Button(x=0, y=170, w=240, h=69, label="Start tracking")
            self.btn_on.draw()
            self.btn_off = None
            self.btn_al = None
        self.cl = Clock(True)
        self.cl.draw()
        bat = BatteryMeter()
        bat.draw()

    def _compute_best_WU(self):
        """computes best wake up time from sleep data"""
        return True  # disabled for now
        # stop tracking to save memory
        self._disable_tracking()
        gc.collect()

        # get angle over time
        data = array("f")
        f = open(self.filep, "r")
        data.extend([float(line.split(",")[4]) for line in f.readlines()])
        f.close()
        del f

        # center and scale
        mean = sum(data) / len(data)
        data2 = array("f", [x**2 for x in data])
        std = sqrt((sum(data2) / len(data2)) - pow(mean, 2))
        del data2
        for i in range(len(data)):
            data[i] = (data[i] - mean) / std

        # find most appropriate cosine
        # TODO

        gc.collect()

    def _listen_to_ticks(self):
        """listen to ticks every second, telling the watch to vibrate"""
        self._WakingUp = True
        system.wake()
        system.switch(self)
        self._draw()
        system.request_tick(1000)

    def tick(self, ticks):
        """vibrate to wake you up"""
        if self._WakingUp:
            watch.vibrator.pulse(duty=50, ms=500)
            system.keep_awake()
