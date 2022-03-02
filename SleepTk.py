# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2021 github.com/thiswillbeyourgithub/

"""Sleep tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# https://github.com/thiswillbeyourgithub/sleep_tracker_pinetime_wasp-os

SleepTk is designed to track accelerometer data throughout the night. It can
also compute the best time to wake you up, up to 40 minutes before the
alarm you set up manually.

"""

import time
import wasp
import widgets
import shell
import fonts
import math
import array
import micropython

# HARDCODED VARIABLES:
_START = micropython.const(0)  # page values:
_TRACKING = micropython.const(1)
_TRACKING2 = micropython.const(2)
_SETTINGS = micropython.const(3)
_RINGING = micropython.const(4)
_FONT = fonts.sans18
_TIMESTAMP = micropython.const(946684800)  # unix time and time used by wasp os don't have the same reference date
_FREQ = micropython.const(30)  # get accelerometer data every X seconds, but process and store them only every _STORE_FREQ seconds
_STORE_FREQ = micropython.const(300)  # process data and store to file every X seconds
_BATTERY_THRESHOLD = micropython.const(20)  # under X% of battery, stop tracking and only keep the alarm

# user might want to edit this:
_ANTICIPATE_ALLOWED = micropython.const(2400)  # number of seconds SleepTk can wake you up before the alarm clock you set
_GRADUAL_WAKE = array.array("H", [1, 2, 3, 4, 5, 8, 13, 20])  # nb of minutes before alarm to send a tiny vibration to make a smoother wake up


class SleepTkApp():
    NAME = 'SleepTk'

    def __init__(self):
        wasp.gc.collect()
        self._wakeup_enabled = 1
        self._wakeup_smart_enabled = 0  # activate waking you up at optimal time  based on accelerometer data, at the earliest at _WU_LAT - _WU_SMART
        self._spinval_H = 7  # default wake up time
        self._spinval_M = 30
        self._conf_view = None
        self._is_tracking = False
        self._earlier = 0
        self._page = _START
        self._old_notification_level = wasp.system.notify_level

        try:
            shell.mkdir("logs/")
        except:  # folder already exists
            pass
        try:
            shell.mkdir("logs/sleep")
        except:  # folder already exists
            pass

    def foreground(self):
        self._conf_view = None
        wasp.gc.collect()
        self._draw()
        wasp.system.request_event(wasp.EventMask.TOUCH |
                                  wasp.EventMask.SWIPE_UPDOWN |
                                  wasp.EventMask.BUTTON)

    def background(self):
        wasp.gc.collect()

    def press(self, button, state):
        "stop ringing alarm if pressed physical button"
        if state:
            if self._page == _RINGING:
                self._disable_tracking()
                self._page = _START
            else:
                wasp.system.navigate(wasp.EventType.HOME)

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
        wasp.gc.collect()
        no_full_draw = False
        if self._page == _START:
            if self.btn_on.touch(event):
                self._is_tracking = True
                # accel data not yet written to disk:
                self._buff = array.array("f")
                self._data_point_nb = 0  # total number of data points so far
                self._last_checkpoint = 0  # to know when to save to file
                self._offset = int(wasp.watch.rtc.time())  # makes output more compact

                # create one file per recording session:
                self.filep = "logs/sleep/{}.csv".format(str(self._offset + _TIMESTAMP))
                self._add_accel_alar()

                # setting up alarm
                if self._wakeup_enabled:
                    now = wasp.watch.rtc.get_localtime()
                    yyyy = now[0]
                    mm = now[1]
                    dd = now[2]
                    HH = self._spinval_H
                    MM = self._spinval_M
                    if HH < now[3] or (HH == now[3] and MM <= now[4]):
                        dd += 1
                    self._WU_t = time.mktime((yyyy, mm, dd, HH, MM, 0, 0, 0, 0))
                    wasp.system.set_alarm(self._WU_t, self._listen_to_ticks)

                    # also set alarm to vibrate a tiny bit before wake up time
                    # to wake up gradually
                    for t in _GRADUAL_WAKE:
                        wasp.system.set_alarm(self._WU_t - t*60, self._tiny_vibration)

                    # wake up SleepTk 2min before earliest possible wake up
                    if self._wakeup_smart_enabled:
                        self._WU_a = self._WU_t - _ANTICIPATE_ALLOWED - 120
                        wasp.system.set_alarm(self._WU_a, self._smart_alarm_compute)
                wasp.system.notify_level = 1  # silent notifications
                self._page = _TRACKING

        elif self._page == _TRACKING or self._page == _TRACKING2:
            if self._conf_view is None:
                if self.btn_off.touch(event):
                    self._conf_view = widgets.ConfirmationView()
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

            if self.check_al.state:
                if self.check_smart.touch(event):
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
        self._is_tracking = False
        wasp.system.cancel_alarm(self.next_al, self._trackOnce)
        if self._wakeup_enabled:
            if keep_main_alarm is False:  # to keep the alarm when stopping because of low battery
                wasp.system.cancel_alarm(self._WU_t, self._listen_to_ticks)
            if self._wakeup_smart_enabled:
                wasp.system.cancel_alarm(self._WU_a, self._smart_alarm_compute)
        self._periodicSave()
        wasp.gc.collect()

    def _add_accel_alar(self):
        """set an alarm, due in _FREQ minutes, to log the accelerometer data
        once"""
        self.next_al = wasp.watch.rtc.time() + _FREQ
        wasp.system.set_alarm(self.next_al, self._trackOnce)

    def _trackOnce(self):
        """get one data point of accelerometer every _FREQ seconds and
        they are then averaged and stored every _STORE_FREQ seconds"""
        if self._is_tracking:
            [self._buff.append(x) for x in wasp.watch.accel.read_xyz()]
            self._data_point_nb += 1
            self._add_accel_alar()
            self._periodicSave()
            if wasp.watch.battery.level() <= _BATTERY_THRESHOLD:
                # strop tracking if battery low
                self._disable_tracking(keep_main_alarm=True)
                self._wakeup_smart_enabled = 0
                h, m = watch.time.localtime(wasp.watch.rtc.time())[3:5]
                wasp.system.notify(wasp.watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                          "title": "Bat <20%",
                                                          "body": "Stopped \
tracking sleep at {}h{}m because your battery went below {}%. Alarm kept \
on.".format(h, m, _BATTERY_THRESHOLD)})

        wasp.gc.collect()

    def _periodicSave(self):
        """save data after averageing over a window to file"""
        buff = self._buff
        if self._data_point_nb - self._last_checkpoint >= _STORE_FREQ / _FREQ:
            x_avg = sum([buff[i] for i in range(0, len(buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            y_avg = sum([buff[i] for i in range(1, len(buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            z_avg = sum([buff[i] for i in range(2, len(buff), 3)]) / (self._data_point_nb - self._last_checkpoint)
            buff = array.array("f")  # reseting array
            buff.append(abs(math.atan(z_avg / (x_avg**2 + y_avg**2))))
            # formula from https://www.nature.com/articles/s41598-018-31266-z
            # note: math.atan() is faster than using a taylor serie
            buff.append(int(wasp.watch.rtc.time() - self._offset))
            buff.append(x_avg)
            buff.append(y_avg)
            buff.append(z_avg)
            del x_avg, y_avg, z_avg
            buff.append(int(wasp.watch.battery.voltage_mv()))  # currently more accurate than percent

            f = open(self.filep, "ab")
            for x in buff[:-1]:
                f.write("{:7f}".format(x).encode())
                f.write(b",")
            f.write("{:7f}".format(buff[-1]).encode())
            f.write(b"\n")
            f.close()

            self._last_checkpoint = self._data_point_nb
            self._buff = array.array("f")

    def _draw(self):
        """GUI"""
        draw = wasp.watch.drawable
        draw.fill(0)
        draw.set_font(_FONT)
        if self._page == _RINGING:
            if self._earlier != 0:
                msg = "WAKE UP ({}m early)".format(str(self._earlier/60)[0:2])
            else:
                msg = "WAKE UP"
            draw.string(msg, 0, 70)
            self.btn_al = widgets.Button(x=0, y=70, w=240, h=140, label="WAKE UP")
            self.btn_al.draw()
        elif self._page == _TRACKING or self._page == _TRACKING2:
            ti = wasp.watch.time.localtime(self._offset)
            draw.string('Started at {:02d}:{:02d}'.format(ti[3], ti[4]), 0, 70)
            draw.string("data points: {}".format(str(self._data_point_nb)), 0, 90)
            if self._wakeup_enabled:
                word = "Alarm at "
                if self._wakeup_smart_enabled:
                    word = "Alarm before "
                ti = wasp.watch.time.localtime(self._WU_t)
                draw.string("{}{:02d}:{:02d}".format(word, ti[3], ti[4]), 0, 130)
            else:
                draw.string("No alarm set", 0, 130)
            self.btn_off = widgets.Button(x=0, y=200, w=240, h=40, label="Stop tracking")
            self.btn_off.draw()
        elif self._page == _START:
            self.btn_on = widgets.Button(x=0, y=200, w=240, h=40, label="Start tracking")
            self.btn_on.draw()
            draw.set_font(_FONT)
            draw.string('Sleep tracker with' , 0, 60)
            draw.string('alarm and smart alarm.' , 0, 80)
            if not self._wakeup_smart_enabled:
                # no need to remind it after the first time
                draw.string('Swipe down for settings' , 0, 100)
            else:
                draw.string('Wake you up to 40m' , 0, 120)
                draw.string('earlier.' , 0, 140)
            draw.string('PRE RELEASE.' , 0, 160)
        elif self._page == _SETTINGS:
            self.check_al = widgets.Checkbox(x=0, y=40, label="Alarm")
            self.check_al.state = self._wakeup_enabled
            self.check_al.draw()
            if self._wakeup_enabled:
                self._spin_H = widgets.Spinner(30, 120, 0, 23, 2)
                self._spin_H.value = self._spinval_H
                self._spin_H.draw()
                self._spin_M = widgets.Spinner(150, 120, 0, 59, 2, 5)
                self._spin_M.value = self._spinval_M
                self._spin_M.draw()
                self.check_smart = widgets.Checkbox(x=0, y=80, label="Smart alarm")
                self.check_smart.state = self._wakeup_smart_enabled
                self.check_smart.draw()

        self.stat_bar = widgets.StatusBar()
        self.stat_bar.clock = True
        self.stat_bar.draw()

    def _signal_processing(self, data):
        """signal processing over the data read from the local file"""

        # remove outliers:
        for x in range(len(data)):
            data[x] = min(0.0008, data[x])
        del x
        wasp.gc.collect()
        wasp.system.keep_awake()

        # smoothen several times
        for j in range(3):
            for i in range(1, len(data)-1):
                data[i] += data[i-1]
                data[i] /= 2
        del i, j
        wasp.gc.collect()
        wasp.system.keep_awake()

        # center data
        mean = sum(data) / len(data)
        for i in range(len(data)):
            data[i] = data[i] - mean
        del mean, i
        wasp.gc.collect()
        wasp.system.keep_awake()

        # find local maximas
        x_maximas = array.array("f")
        y_maximas = array.array("f")
        window = int(60*60/_STORE_FREQ)  # over 60 minutes
        for start_w in range(len(data)) - window:
            m = max(data[start_w:start_w+window])
            for i in range(start_w, start_w + window):
                if data[i] == m:
                    if i+start_w not in x_maximas:
                        x_maximas.append(i + start_w)
                        y_maximas.append(m)
        del window, start_w, i, m
        wasp.gc.collect()
        wasp.system.keep_awake()

        # remove all peaks found in the first 60 minutes:
        for i, x in enumerate(x_maximas):
            if x*_STORE_FREQ < 3600:
                y_maximas.remove(y_maximas[i])
                x_maximas.remove(x)
        del i, x
        wasp.gc.collect()
        wasp.system.keep_awake()

        # merge the smallest peaks while there are more than N peaks
        N = 4
        while len(x_maximas) > N:
            y_min = min(y_maximas)  # find minimum
            for i, y in y_maximas:  # find location of minimum
                if y == y_min:
                    x_min_idx = i
            if x_min_idx == len(x_maximas):  # min is last, merging it with penultimate
                closest = x_min_idx-1
            elif x_min_idx == 0:  # min is first, merging it with 2nd
                closest = x_min_idx+1
            else:  # merge with closest
                if x_maximas[x_min_idx-1] - x_maximas[x_min_idx] < x_maximas[x_min_idx+1] - x_maximas[x_min_idx]:
                    closest = x_min_idx-1
                else:
                    closest = x_min_idx+1
            y_maximas[closest] += y_maximas[x_min_idx]  # adding peak values
            x_maximas[closest] += x_maximas[x_min_idx]  # averaging the x coordinate
            x_maximas[closest] /= 2
            y_maximas.remove(y_maximas[x_min_idx])
            x_maximas.remove(x_maximas[x_min_idx])
        del closest, y_min, x_min_idx, i, y
        wasp.gc.collect()
        wasp.system.keep_awake()

        # sleep cycle period is the time average distance between those N peaks
        period = (x_maximas[-1] - x_maximas[0]) / N

        # if wake up time is in more time than last period but less than what
        # SleepTk is allowed to anticipate: add new alarm at best time
        last_peak_time = self._offset + x_maximas[-1] * _STORE_FREQ
        WU_t = self._WU_t
        allowed_time = WU_t - _ANTICIPATE_ALLOWED
        if last_peak_time + period < WU_t and last_peak_time + period > allowed_time:
            earlier = WU_t - (last_peak_time + period)
        else:
            earlier = 0  # don't anticipate
        wasp.system.keep_awake()
        return (earlier, period)

    def _smart_alarm_compute(self):
        """computes best wake up time from sleep data"""
        wasp.gc.collect()
        mute = wasp.watch.display.mute
        mute(True)
        wasp.system.wake()
        wasp.system.keep_awake()
        wasp.system.switch(self)
        t = wasp.watch.time.localtime(wasp.watch.rtc.time())
        wasp.system.notify(wasp.watch.rtc.get_uptime_ms(),
                      {"src": "SleepTk",
                       "title": "Starting smart alarm computation",
                       "body": "Starting computation for the smart alarm at {:02d}h{:02d}m".format(t[3], t[4])}
                      )
        try:
            start_time = wasp.watch.rtc.time()
            # stop tracking to save memory, keep the alarm just in case
            self._disable_tracking(keep_main_alarm=True)

            # read file one character at a time, to get only the 1st
            # value of each row, which is the arm angle
            data = array.array("f")
            buff = b""
            f = open(self.filep, "rb")
            skip = False
            while True:
                char = f.read(1)
                if char == b",":  # start ignoring after the first col
                    skip = True
                    continue
                if char == b"\n":
                    skip = False  # stop skipping because reading a new line
                    data.append(float(buff))
                    buff = b""
                    continue
                if char == b"":  # end of file
                    break
                elif not skip:  # digit of arm angle value
                    buff += char

            f.close()
            del f, char, buff
            wasp.gc.collect()
            wasp.system.keep_awake()

            earlier, period = self._signal_processing(data)
            WU_t = self._WU_t
            wasp.gc.collect()

            self._earlier = earlier
            wasp.system.set_alarm(max(WU_t - earlier, int(wasp.watch.rtc.time()) + 3),  # not before right now, to make sure it rings
                             self._listen_to_ticks)
            self._page = _TRACKING2
            wasp.system.notify(wasp.watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                      "title": "Finished smart alarm computation",
                                                      "body": "Finished computing best wake up time in {:2f}s. Best sleep cycle duration: {:.2f}h".format(wasp.watch.rtc.time() - start_time, period)
                                                      })
        except Exception as e:
            wasp.gc.collect()
            t = wasp.watch.time.localtime(wasp.watch.rtc.time())
            msg = "Exception occured at {:02d}h{:02d}m: '{}'%".format(t[3], t[4], str(e))
            wasp.system.notify(wasp.watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                      "title": "Smart alarm error",
                                                      "body": msg})
            f = open("smart_alarm_error_{}.txt".format(int(wasp.watch.rtc.time())), "wb")
            f.write(msg.encode())
            f.close()
        wasp.gc.collect()


    def _listen_to_ticks(self):
        """listen to ticks every second, telling the watch to vibrate"""
        wasp.gc.collect()
        wasp.system.notify_level = self._old_notification_level  # restore notification level
        self._page = _RINGING
        mute = wasp.watch.display.mute
        mute(True)
        wasp.system.wake()
        wasp.system.keep_awake()
        wasp.system.switch(self)
        self._draw()
        wasp.system.request_tick(period_ms=1000)

    def tick(self, ticks):
        """vibrate to wake you up"""
        if self._page == _RINGING:
            wasp.watch.vibrator.pulse(duty=50, ms=500)

    def _tiny_vibration(self):
        """vibrate just a tiny bit before waking up, to gradually return
        to consciousness"""
        wasp.gc.collect()
        mute = wasp.watch.display.mute
        mute(True)
        wasp.system.wake()
        wasp.system.keep_awake()
        wasp.system.switch(self)
        wasp.watch.vibrator.pulse(duty=60, ms=100)
