# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2021 github.com/thiswillbeyourgithub/

"""Sleep tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# https://github.com/thiswillbeyourgithub/sleep_tracker_pinetime_wasp-os

SleepTk is designed to track accelerometer data throughout the night. It can
also compute the best time to wake you up, up to 30 minutes before the
alarm you set up manually.

"""

import time
from wasp import watch, system, EventMask, gc

from watch import rtc, battery, accel
from widgets import Button, Spinner, Checkbox, StatusBar, ConfirmationView
from shell import mkdir, cd
from fonts import sans18

from math import atan, pow, degrees, sqrt, sin, pi
from array import array
from micropython import const

_FONT = sans18
_BATTERY_THRESHOLD = const(20)  # under 20% of battery, stop tracking and only keep the alarm
_AVG_SLEEP_CYCL = const(32400)  # 90 minutes, average sleep cycle duration
_OFFSETS = array("H", [0, 300, 600, 900, 1200, 1500, 1800])
_FREQ = const(5)  # get accelerometer data every X seconds, they will be averaged
_STORE_FREQ = const(300)  # number of seconds between storing average values to file written every X points
_SMART_LEN = const(1800)  # defaults 1800 = 30m

class SleepTkApp():
    NAME = 'SleepTk'

    def __init__(self):
        gc.collect()
        self._wakeup_enabled = 1
        self._wakeup_smart_enabled = 1  # activate waking you up at optimal time  based on accelerometer data, at the earliest at _WU_LAT - _WU_SMART
        self._spinval_H = 7  # default wake up time
        self._spinval_M = 30
        self._conf_view = None
        self._tracking = False  # False = not tracking, True = currently tracking
        self._earlier = 0
        self._page = b"STA" # can be START / TRACKING / TRA2 = tracking but with early wake up time computed / SETTINGS / RINGING

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
        self._conf_view = None
        gc.collect()
        self._draw()
        system.request_event(EventMask.TOUCH)

    def sleep(self):
        """keep running in the background"""
        gc.collect()
        return False

    def touch(self, event):
        """either start trackign or disable it, draw the screen in all cases"""
        gc.collect()
        no_full_draw = False
        if self._page == b"STA":
            if self.btn_on.touch(event):
                self._tracking = True
                # accel data not yet written to disk:
                self._buff = array("f")
                self._data_point_nb = 0  # total number of data points so far
                self._last_checkpoint = 0  # to know when to save to file
                self._offset = int(rtc.time())  # makes output more compact

                # create one file per recording session:
                self.filep = "logs/sleep/{}.csv".format(str(self._offset))
                self._add_accel_alar()

                # setting up alarm
                if self._wakeup_enabled:
                    now = rtc.get_localtime()
                    yyyy = now[0]
                    mm = now[1]
                    dd = now[2]
                    HH = self._spinval_H
                    MM = self._spinval_M
                    if HH < now[3] or (HH == now[3] and MM <= now[4]):
                        dd += 1
                    self._WU_t = time.mktime((yyyy, mm, dd, HH, MM, 0, 0, 0, 0))
                    system.set_alarm(self._WU_t, self._listen_to_ticks)

                    # alarm in _SMART_LEN less seconds to compute best wake up time
                    if self._wakeup_smart_enabled:
                        self._WU_a = self._WU_t - _SMART_LEN
                        system.set_alarm(self._WU_a, self._compute_best_WU)
                self._page = b"TRA"
            elif self.btn_set.touch(event):
                self._page = b"SET"

        elif self._page.startswith(b"TRA"):
            if self._conf_view is None:
                no_full_draw = True
                if self.btn_off.touch(event):
                    self._conf_view = ConfirmationView()
                    self._conf_view.draw("Stop tracking?")
            else:
                if self._conf_view.touch(event):
                    if self._conf_view.value:
                        self._disable_tracking()
                        self._page = b"STA"
                    self._conf_view = None

        elif self._page == b"RNG":
            if self.btn_al.touch(event):
                self._disable_tracking()
                self._page = b"STA"

        elif self._page == b"SET":
            no_full_draw = True
            disable_all = False
            if self.check_al.touch(event):
                if self._wakeup_enabled == 1:
                    self._wakeup_enabled = 0
                    disable_all = True
                else:
                    self._wakeup_enabled = 1
                    no_full_draw = False
                self.check_al.state = self._wakeup_enabled
                self.check_al.update()

                if disable_all:
                    self._wakeup_smart_enabled = 0
                    self.check_smart.state = self._wakeup_smart_enabled
                    self._check_smart = None
                    self._draw()

            elif self.check_smart.touch(event):
                if self._wakeup_smart_enabled == 1:
                    self._wakeup_smart_enabled = 0
                    self.check_smart.state = self._wakeup_smart_enabled
                    self._check_smart = None
                elif self._wakeup_enabled == 1:
                    self._wakeup_smart_enabled = 1
                    self.check_smart.state = self._wakeup_smart_enabled
                    self.check_smart.update()
                    self.check_smart.draw()
            elif self._spin_H.touch(event):
                self._spinval_H = self._spin_H.value
                self._spin_H.update()
            elif self._spin_M.touch(event):
                self._spinval_M = self._spin_M.value
                self._spin_M.update()
            elif self.btn_set_end.touch(event):
                self._page = b"STA"
                self._draw()

        if no_full_draw is False:
            self._draw()

    def _disable_tracking(self, keep_main_alarm=False):
        """called by touching "STOP TRACKING" or when computing best alarm time
        to wake up you disables tracking features and alarms"""
        self._tracking = False
        system.cancel_alarm(self.next_al, self._trackOnce)
        if self._wakeup_enabled:
            if keep_main_alarm is False:  # to keep the alarm when stopping because of low battery
                system.cancel_alarm(self._WU_t, self._listen_to_ticks)
            if self._wakeup_smart_enabled:
                system.cancel_alarm(self._WU_a, self._compute_best_WU)
        self._periodicSave()
        gc.collect()

    def _add_accel_alar(self):
        """set an alarm, due in _FREQ minutes, to log the accelerometer data
        once"""
        self.next_al = watch.rtc.time() + _FREQ
        system.set_alarm(self.next_al, self._trackOnce)

    def _trackOnce(self):
        """get one data point of accelerometer every _FREQ seconds and
        they are then averaged and stored every _STORE_FREQ seconds"""
        if self._tracking:
            [self._buff.append(x) for x in accel.read_xyz()]
            self._data_point_nb += 1
            self._add_accel_alar()
            self._periodicSave()
            if battery.level() <= _BATTERY_THRESHOLD:
                self._disable_tracking(keep_main_alarm=True)
        gc.collect()

    def _periodicSave(self):
        """save data after averageing over a window to file"""
        buff = self._buff
        if self._data_point_nb - self._last_checkpoint >= _STORE_FREQ / _FREQ:
            x_avg = sum([buff[i] for i in range(0, len(buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            y_avg = sum([buff[i] for i in range(1, len(buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            z_avg = sum([buff[i] for i in range(2, len(buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            buff = array("f")  # reseting array
            buff.append(int(rtc.time() - self._offset))
            buff.append(x_avg)
            buff.append(y_avg)
            buff.append(z_avg)
            buff.append(degrees(atan(z_avg / (pow(x_avg, 2) + pow(y_avg, 2) + 0.0000001)))) # formula from https://www.nature.com/articles/s41598-018-31266-z
            del x_avg, y_avg, z_avg
            buff.append(battery.voltage_mv())  # currently more accurate than percent

            f = open(self.filep, "ab")
            f.write(b",".join([str(x)[0:8].encode() for x in buff]) + b"\n")
            f.close()

            self._last_checkpoint = self._data_point_nb
            self._buff = array("f")

    def _draw(self):
        """GUI"""
        draw = watch.drawable
        draw.fill(0)
        draw.set_font(_FONT)
        if self._page == b"RNG":
            if self._earlier != 0:
                msg = "WAKE UP ({}m early)".format(str(self._earlier/60)[0:2])
            else:
                msg = "WAKE UP"
            draw.string(msg, 0, 70)
            self.btn_al = Button(x=0, y=170, w=240, h=40, label="STOP")
            self.btn_al.draw()
        elif self._page.startswith(b"TRA"):
            draw.string('Started at {}'.format(":".join([str(x) for x in watch.time.localtime(self._offset)[3:5]])), 0, 70)
            draw.string("data points: {}".format(str(self._data_point_nb)), 0, 90)
            if self._wakeup_enabled:
                word = "Alarm at "
                if self._wakeup_smart_enabled:
                    word = "Alarm before "
                ti = [str(x) for x in watch.time.localtime(self._WU_t)[3:5]]
                draw.string("{:2}{:2}".format(word, ":".join(ti)), 0, 130)
            self.btn_off = Button(x=0, y=200, w=240, h=40, label="Stop tracking")
            self.btn_off.draw()
        elif self._page == b"STA":
            draw.string('Sleep tracker with' , 0, 60)
            draw.string('alarm and smart alarm.' , 0, 80)
            draw.string('Wake you up to 30m' , 0, 100)
            draw.string('before alarm.' , 0, 120)
            draw.string('ALPHA SOFTWARE.' , 0, 140)
            self.btn_on = Button(x=0, y=200, w=200, h=40, label="Start tracking")
            self.btn_on.draw()
            self.btn_set = Button(x=201, y=200, w=39, h=40, label="S")
            self.btn_set.draw()
        elif self._page == b"SET":
            self.btn_set_end = Button(x=201, y=200, w=39, h=40, label="X")
            self.btn_set_end.draw()

            if self._wakeup_enabled:
                self._spin_H = Spinner(10, 140, 0, 23, 2)
                self._spin_H.value = self._spinval_H
                self._spin_H.draw()
                self._spin_M = Spinner(100, 140, 0, 59, 2)
                self._spin_M.value = self._spinval_M
                self._spin_M.draw()

            self.check_al = Checkbox(x=0, y=40, label="Alarm")
            self.check_al.state = self._wakeup_enabled
            self.check_al.draw()
            if self.check_al.state == 1:
                self.check_smart = Checkbox(x=0, y=80, label="Smart alarm")
                self.check_smart.state = self._wakeup_smart_enabled
                self.check_smart.draw()

        self.stat_bar = StatusBar()
        self.stat_bar.clock = True
        self.stat_bar.draw()

    def _compute_best_WU(self):
        """computes best wake up time from sleep data"""
        # stop tracking to save memory
        self._disable_tracking()

        # get angle over time
        f = open(self.filep, "rb")
        lines = f.readlines()
        f.close()
        if b"\n" in lines:
            lines = lines[0].split(b"\n")
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
        omega = 2 * pi / _AVG_SLEEP_CYCL
        for cnt, offset in enumerate(_OFFSETS):  # least square regression
            fits.append(
                    sum([sin(omega * t * _STORE_FREQ + offset) * data[t] for t in range(len(data))])
                    -sum([(sin(omega * t * _STORE_FREQ + offset) - data[t])**2 for t in range(len(data))])
                    )
            if fits[-1] == min(fits):
                best_offset = _OFFSETS[cnt]
        del fits, offset, cnt

        # finding how early to wake up:
        max_sin = 0
        WU_t = self._WU_t
        for t in range(WU_t, WU_t - _SMART_LEN, -300):  # counting backwards from original wake up time, steps of 5 minutes
            s = sin(omega * t + best_offset)
            if s > max_sin:
                max_sin = s
                self._earlier = -t  # number of seconds earlier than wake up time
        del max_sin, s

        system.set_alarm(
                min(
                    max(WU_t - self._earlier, int(rtc.time()) + 3),  # not before right now
                    WU_t - 5  # not after original wake up time
                    ), self._listen_to_ticks)
        self._page = b"TRA2"
        gc.collect()


    def _listen_to_ticks(self):
        """listen to ticks every second, telling the watch to vibrate"""
        gc.collect()
        self._page = b"RNG"
        system.wake()
        system.keep_awake()
        system.switch(self)
        self._draw()
        system.request_tick(period_ms=1000)

    def tick(self, ticks):
        """vibrate to wake you up"""
        if self._page == b"RNG":
            watch.vibrator.pulse(duty=50, ms=500)
