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

from watch import rtc, battery, accel
from widgets import Clock, BatteryMeter, Button
from shell import mkdir, cd
from fonts import sans18

from math import atan, pow, degrees, sqrt, sin, pi
from micropython import const
from array import array

_FONT = sans18

# to activate DEBUG MODE : comment the next paragraph and uncomment DEBUG BLOCK

_POLLFREQ = const(5)  # get accelerometer data every X seconds, they will
# be averaged
_WIN_L = const(300)  # number of seconds between storing average values to file
# written every X points

_WU_ON = const(1)  # const(1) to activate wake up alarm, const(0) to disable
_WU_LAT = const(27000)  # maximum seconds of sleep before waking you up,
# default 27000 = 7h30
_WU_ANT_ON = const(0)  # set to 1 to activate waking you up at optimal time
# based on accelerometer data, at the earliest at _WU_LAT - _WU_ANTICIP
_WU_ANTICIP = const(1800)  # default 1800 = 30 minutes


# DEBUG BLOCK:
#_POLLFREQ = const(1)
#_WIN_L = const(5)
#_WU_ON = const(1)
#_WU_LAT = const(30)
#_WU_ANT_ON = const(1)
#_WU_ANTICIP = const(5)


class ZzzTrackerApp():
    NAME = 'ZzzTrck'

    def __init__(self):
        self._tracking = False  # False = not tracking, True = currently tracking
        self._WakingUp = False  # when True, watch is currently vibrating to wake you up
        self._earlier = 0
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
                self._buff = array("f")
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
                if self._tracking:
                    self._disable_tracking()
        elif self.btn_al:
            if self.btn_al.touch(event):
                self._WakingUp = False
                if self._tracking:
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
            [self._buff.append(x) for x in accel.read_xyz()]
            self._data_point_nb += 1
            self._add_accel_alar()
            self._periodicSave()

    def _periodicSave(self):
        """save data after averageing over a window to file"""
        if self._data_point_nb - self._last_checkpoint >= _WIN_L / _POLLFREQ:
            x_avg = sum([self._buff[i] for i in range(0, len(self._buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            y_avg = sum([self._buff[i] for i in range(1, len(self._buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            z_avg = sum([self._buff[i] for i in range(2, len(self._buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            self._buff = array("f")  # reseting array
            self._buff.append(int(rtc.time() - self._offset))
            self._buff.append(x_avg)
            self._buff.append(y_avg)
            self._buff.append(z_avg)
            self._buff.append(degrees(atan(z_avg / (pow(x_avg, 2) + pow(y_avg, 2) + 0.0000001)))) # formula from https://www.nature.com/articles/s41598-018-31266-z
            self._buff.append(degrees(atan(x_avg / (pow(y_avg, 2) + pow(z_avg, 2) + 0.0000001))))
            self._buff.append(degrees(atan(y_avg / (pow(z_avg, 2) + pow(x_avg, 2) + 0.0000001))))
            del x_avg, y_avg, z_avg
            self._buff.append(battery.voltage_mv())  # currently more accurate than percent

            f = open(self.filep, "a")
            f.write(",".join([str(x)[0:8] for x in self._buff]) + "\n")
            f.close()

            self._last_checkpoint = self._data_point_nb
            self._buff = array("f")
        gc.collect()

    def _draw(self):
        """GUI"""
        draw = watch.drawable
        draw.fill(0)
        draw.set_font(_FONT)
        if self._WakingUp:
            self.btn_on = None
            self.btn_off = None
            if self._earlier != 0:
                msg = "WAKE UP (" + str(self._earlier/60)[0:2] + "m early)"
            else:
                msg = "WAKE UP"
            draw.string(msg, 0, 70)
            self.btn_al = Button(x=0, y=170, w=240, h=69, label="STOP")
            self.btn_al.draw()
        elif self._tracking:
            draw.string('Started at ' + ":".join([str(x) for x in watch.time.localtime(self._offset)[3:5]]), 0, 70)
            draw.string("data points:" + str(self._data_point_nb), 0, 90)
            if _WU_ON:
                if _WU_ANT_ON:
                    word = " before "
                else:
                    word = " at "
                draw.string("Wake up" + word + ":".join([str(x) for x in watch.time.localtime(self._offset + _WU_LAT)[3:5]]), 0, 130)
            self.btn_on = None
            self.btn_al = None
            self.btn_off = Button(x=0, y=170, w=240, h=69, label="Stop tracking")
            self.btn_off.draw()
        else:
            draw.string('Sleep tracker' , 0, 70)
            self.btn_off = None
            self.btn_al = None
            self.btn_on = Button(x=0, y=170, w=240, h=69, label="Start tracking")
            self.btn_on.draw()
        self.cl = Clock(True)
        self.cl.draw()
        bat = BatteryMeter()
        bat.draw()

    def _compute_best_WU(self):
        """computes best wake up time from sleep data"""
        # stop tracking to save memory
        self._disable_tracking()
        gc.collect()

        # get angle over time
        f = open(self.filep, "r")
        lines = f.readlines()
        f.close()
        if len(lines) == 1:
            lines = lines[0].split("\n")
        data = array("f", [float(line.split(",")[4]) for line in lines])

        # center and scale
        mean = sum(data) / len(data)
        std = sqrt((sum([x**2 for x in data]) / len(data)) - pow(mean, 2))
        for i in range(len(data)):
            data[i] = (data[i] - mean) / std
        del mean, std

        # fitting cosine of various offsets in minutes, the best fit has the
        # period indicating best wake up time:
        fits = array("f")
        offsets = [0, 300, 600, 900, 1200, 1500, 1800]
        omega = 2 * pi / 324000  # 90 minutes, average sleep cycle duration
        for cnt, offset in enumerate(offsets):  # least square regression
            fits.append(
                    sum([sin(omega * t * _WIN_L + offset) * data[t] for t in range(len(data))])
                    -sum([(sin(omega * t * _WIN_L + offset) - data[t])**2 for t in range(len(data))])
                    )
            if fits[-1] == min(fits):
                best_offset = offsets[cnt]
        del fits, offset, offsets, cnt

        # finding how early to wake up:
        max_sin = 0
        for t in range(self._WU_t, self._WU_t - _WU_ANTICIP, -300):  # counting backwards from original wake up time, steps of 5 minutes
            s = sin(omega * t + best_offset)
            if s > max_sin:
                max_sin = s
                self._earlier = -t  # number of seconds earlier than wake up time
        del max_sin, s

        print(self._earlier)
        system.set_alarm(
                min(
                    max(self._WU_t - self._earlier, int(rtc.time()) + 3),  # not before right now
                    self._WU_t - 5  # not after original wake up time
                    ), self._listen_to_ticks)
        system.cancel_alarm(self._WU_t, self._listen_to_ticks)  # cancel original alarm

        gc.collect()

    def _listen_to_ticks(self):
        """listen to ticks every second, telling the watch to vibrate"""
        self._WakingUp = True
        system.wake()
        system.keep_awake()
        system.switch(self)
        self._draw()
        system.request_tick(period_ms=1000)

    def tick(self, ticks):
        """vibrate to wake you up"""
        if self._WakingUp:
            watch.vibrator.pulse(duty=50, ms=500)
