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

from math import atan, sin
from array import array
from micropython import const

_FONT = sans18
_TIMESTAMP = const(946684800)
_BATTERY_THRESHOLD = const(20)  # under 20% of battery, stop tracking and only keep the alarm
_AVG_SLEEP_CYCL = const(32400)  # 90 minutes, average sleep cycle duration
_OFFSETS = array("H", [0, 300, 600, 900, 1200, 1500, 1800])
_FREQ = const(5)  # get accelerometer data every X seconds, they will be averaged
_STORE_FREQ = const(300)  # number of seconds between storing average values to file written every X points
_SMART_LEN = const(1800)  # defaults 1800 = 30m

# math related :
_DEGREE = const(5729578)  # result of 180/pi*100_000, for conversion
_PIPI = const(628318)  # result of 2*pi*100_000

# page values:
_START = const(0)
_TRACKING = const(1)
_TRACKING2 = const(2)
_SETTINGS = const(3)
_RINGING = const(4)

class SleepTkApp():
    NAME = 'SleepTk'

    def __init__(self):
        gc.collect()
        self._is_computing = False
        self._wakeup_enabled = 1
        self._wakeup_smart_enabled = 0  # activate waking you up at optimal time  based on accelerometer data, at the earliest at _WU_LAT - _WU_SMART
        self._spinval_H = 7  # default wake up time
        self._spinval_M = 30
        self._conf_view = None
        self._tracking = False  # False = not tracking, True = currently tracking
        self._earlier = 0
        self._page = _START

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
        system.request_event(EventMask.TOUCH |
                             EventMask.SWIPE_UPDOWN |
                             EventMask.BUTTON)

    def sleep(self):
        """stop sleeping when calculating smart alarm time"""
        gc.collect()
        if self._is_computing:
            return False

    def background(self):
        gc.collect()

    def press(self, button, state):
        "stop ringing alarm if pressed physical button"
        if state:
            if self._page == _RINGING:
                self._disable_tracking()
                self._page = _START

    def swipe(self, event):
        "switches between start page and settings page"
        if self._page == _START:
            self._page = _SETTINGS
            self._draw()
        elif self._page == _SETTINGS:
            self._page = _START
            self._draw()

    def touch(self, event):
        """either start trackign or disable it, draw the screen in all cases"""
        gc.collect()
        no_full_draw = False
        if self._page == _START:
            if self.btn_on.touch(event):
                self._tracking = True
                # accel data not yet written to disk:
                self._buff = array("f")
                self._data_point_nb = 0  # total number of data points so far
                self._last_checkpoint = 0  # to know when to save to file
                self._offset = int(rtc.time()) + _TIMESTAMP  # makes output more compact

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
                        system.set_alarm(self._WU_a, self._smart_alarm_compute)
                self._page = _TRACKING

        elif self._page == _TRACKING or self._page == _TRACKING2:
            if self._conf_view is None:
                if self.btn_off.touch(event):
                    self._conf_view = ConfirmationView()
                    self._conf_view.draw("Stop tracking?")
                    no_full_draw = True
            else:
                if self._conf_view.touch(event):
                    if self._conf_view.value:
                        self._disable_tracking()
                        self._page = _START
                    self._conf_view = None

        elif self._page == _RINGING:
            if self.btn_al.touch(event):
                self._disable_tracking()
                self._page = _START

        elif self._page == _SETTINGS:
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
                system.cancel_alarm(self._WU_a, self._smart_alarm_compute)
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
                # strop tracking if battery low
                self._disable_tracking(keep_main_alarm=True)
                self._wakeup_smart_enabled = 0
                h, m = watch.time.localtime(time.time())[3:5]
                system.notify(watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                          "title": "Bat <20%",
                                                          "body": "Stopped \
tracking sleep at {}h{}m because your battery went below {}%. Alarm kept \
on.".format(h, m, _BATTERY_THRESHOLD)})

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
            buff.append(abs(atan(z_avg / x_avg**2 + y_avg**2)))
                    # formula from https://www.nature.com/articles/s41598-018-31266-z
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
        if self._page == _RINGING:
            if self._earlier != 0:
                msg = "WAKE UP ({}m early)".format(str(self._earlier/60)[0:2])
            else:
                msg = "WAKE UP"
            draw.string(msg, 0, 70)
            self.btn_al = Button(x=0, y=70, w=240, h=140, label="WAKE UP")
            self.btn_al.draw()
        elif self._page == _TRACKING or self._page == _TRACKING2:
            ti = watch.time.localtime(self._offset)
            draw.string('Started at {:2d}:{:2d}'.format(ti[3], ti[4]), 0, 70)
            draw.string("data points: {}".format(str(self._data_point_nb)), 0, 90)
            if self._wakeup_enabled:
                word = "Alarm at "
                if self._wakeup_smart_enabled:
                    word = "Alarm before "
                ti = watch.time.localtime(self._WU_t)
                draw.string("{}{:02d}:{:02d}".format(word, ti[3], ti[4]), 0, 130)
            self.btn_off = Button(x=0, y=200, w=240, h=40, label="Stop tracking")
            self.btn_off.draw()
        elif self._page == _START:
            self.btn_on = Button(x=0, y=200, w=240, h=40, label="Start tracking")
            self.btn_on.draw()
            draw.set_font(_FONT)
            draw.string('Sleep tracker with' , 0, 60)
            draw.string('alarm and smart alarm.' , 0, 80)
            if not self._wakeup_smart_enabled:
                # no need to remind it after the first time
                draw.string('Swipe down for settings' , 0, 100)
            else:
                draw.string('Wake you up to 30m' , 0, 120)
                draw.string('earlier.' , 0, 140)
            draw.string('PRE RELEASE.' , 0, 160)
        elif self._page == _SETTINGS:
            self.check_al = Checkbox(x=0, y=40, label="Alarm")
            self.check_al.state = self._wakeup_enabled
            self.check_al.draw()
            if self._wakeup_enabled:
                self._spin_H = Spinner(30, 120, 0, 23, 2)
                self._spin_H.value = self._spinval_H
                self._spin_H.draw()
                self._spin_M = Spinner(150, 120, 0, 59, 2)
                self._spin_M.value = self._spinval_M
                self._spin_M.draw()
                self.check_smart = Checkbox(x=0, y=80, label="Smart alarm")
                self.check_smart.state = self._wakeup_smart_enabled
                self.check_smart.draw()

        self.stat_bar = StatusBar()
        self.stat_bar.clock = True
        self.stat_bar.draw()

    def _smart_alarm_compute(self):
        """computes best wake up time from sleep data"""
        self._is_computing = True
        try:
            # stop tracking to save memory, keep the alarm just in case
            self._disable_tracking(keep_main_alarm=True)

            # get angle over time
            f = open(self.filep, "rb")
            lines = f.readlines()
            f.close()
            if len(lines) == 0:
                lines = lines[0].split(b"\n")
            data = array("f", [float(line.split(",")[4]) for line in lines])

            # center and scale
            mean = sum(data) / len(data)
            std = ((sum([x**2 for x in data]) / len(data)) - mean**2)**0.5
            for i in range(len(data)):
                data[i] = (data[i] - mean) / std
            del mean, std

            # fitting cosine of various offsets in minutes, the best fit has the
            # period indicating best wake up time:
            fits = array("f")
            omega = _PIPI / 100000 * _AVG_SLEEP_CYCL / 2  # 2 * pi * period
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
                        WU_t - 5,  # not after original wake up time
                        max(WU_t - self._earlier, int(rtc.time()) + 3)  # not before right now
                        ), self._listen_to_ticks)
            self._page = _TRACKING2
            gc.collect()
        except Exception as e:
            gc.collect()
            t = watch.time.localtime(time.time())
            msg = "Exception occured at {}h{}m: '{}'%".format(t[3], t[4], str(e))
            system.notify(watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                      "title": "Smart alarm error",
                                                      "body": msg})
            f = open("smart_alarm_error_{}.txt".format(int(time.time())), "wb")
            f.write(msg.encode())
            f.close()
        finally:
            self._is_computing = False
        gc.collect()


    def _listen_to_ticks(self):
        """listen to ticks every second, telling the watch to vibrate"""
        gc.collect()
        self._page = _RINGING
        system.wake()
        system.keep_awake()
        system.switch(self)
        self._draw()
        system.request_tick(period_ms=1000)

    def tick(self, ticks):
        """vibrate to wake you up"""
        if self._page == _RINGING:
            watch.vibrator.pulse(duty=50, ms=500)
