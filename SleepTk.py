# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2021 github.com/thiswillbeyourgithub/

"""Sleep tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SleepTk is an alarm clock app designed to track body movement throughout
the night to optimize sleep. Currently a WIP, more information at
https://github.com/thiswillbeyourgithub/sleep_tracker_pinetime_wasp-os
"""

import wasp
import widgets
import shell
import fonts
import math
import ppg
from array import array
from micropython import const

# HARDCODED VARIABLES:
_ON = const(1)
_OFF = const(0)
_TRACKING = const(0)
_RINGING = const(1)
_START = const(2)  # page values:
_SETTINGS1 = const(3)
_SETTINGS2 = const(4)
_FONT = fonts.sans18
_TIMESTAMP = const(946684800)  # unix time and time used by wasp os don't have the same reference date
_FREQ = const(5)  # get accelerometer data every X seconds, but process and store them only every _STORE_FREQ seconds
_HR_FREQ = const(1800)  # how many seconds between heart rate data
_STORE_FREQ = const(120)  # process data and store to file every X seconds
_BATTERY_THRESHOLD = const(15)  # under X% of battery, stop tracking and only keep the alarm, set at -200 or lower to disable

# user might want to edit this:
_ANTICIPATE_ALLOWED = const(2400)  # number of seconds SleepTk can wake you up before the alarm clock you set
_GRADUAL_WAKE = array("H", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 15])  # nb of minutes before alarm to send a tiny vibration to make a smoother wake up
_TIME_TO_FALL_ASLEEP = const(14)  # in minutes, according to https://sleepyti.me/
_CYCLE_LENGTH = const(90)  # in minutes, default of 90 or 100, according to https://sleepyti.me/  # currently used only to display best wake up time, not to compute smart alarm!


class SleepTkApp():
    NAME = 'SleepTk'

    def __init__(self):
        wasp.gc.collect()
        # default values:
        self._alarm_state = _ON
        self._grad_alarm_state = _ON
        self._smart_alarm_state = _OFF  # activate waking you up at optimal time  based on accelerometer data, at the earliest at _WU_LAT - _WU_SMART
        self._track_HR_state = _OFF
        self._last_HR = _OFF
        self._last_HR_date = _OFF
        self._track_HR_once = _OFF
        self._spinval_H = 7  # default wake up time
        self._spinval_M = 30
        self._page = _START
        self._is_tracking = _OFF
        self._conf_view = _OFF  # confirmation view
        self._earlier = 0  # number of seconds between the alarm you set manually and the smart alarm time
        self._old_notification_level = wasp.system.notify_level
        self._buff = array("f", [_OFF, _OFF, _OFF])

        try:
            shell.mkdir("logs/")
        except:  # folder already exists
            pass
        try:
            shell.mkdir("logs/sleep")
        except:  # folder already exists
            pass

    def foreground(self):
        self._conf_view = _OFF
        wasp.gc.collect()
        self._draw()
        wasp.system.request_event(wasp.EventMask.TOUCH |
                                  wasp.EventMask.SWIPE_LEFTRIGHT |
                                  wasp.EventMask.BUTTON)

    def background(self):
        wasp.watch.hrs.disable()
        self._track_HR_once = _OFF
        self._hrdata = None
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
        "navigate between start and various settings page"
        if self._page >= 2:
            if event[0] == wasp.EventType.RIGHT:
                self._page -= 1
            else:
                self._page += 1
            self._page = max(self._page, _START)
            self._page = min(self._page, _SETTINGS2)
            self._draw()

    def touch(self, event):
        """either start trackign or disable it, draw the screen in all cases"""
        wasp.gc.collect()
        if self._page == _TRACKING:
            if self._conf_view is _OFF:
                if self.btn_off.touch(event):
                    self._conf_view = widgets.ConfirmationView()
                    self._conf_view.draw("Stop tracking?")
                    return
            else:
                if self._conf_view.touch(event):
                    if self._conf_view.value:
                        self._disable_tracking()
                        self._page = _START
                    self._conf_view = _OFF
        elif self._page == _RINGING:
            if self.btn_al.touch(event):
                self._disable_tracking()
                self._page = _START
        elif self._page == _SETTINGS1:
            if self._alarm_state and (self._spin_H.touch(event) or self._spin_M.touch(event)):
                self._spinval_H = self._spin_H.value
                self._spin_H.update()
                self._spinval_M = self._spin_M.value
                self._spin_M.update()
                if self._alarm_state:
                    draw = wasp.watch.drawable
                    draw.set_font(_FONT)
                    duration =  (self._read_time(self._spinval_H, self._spinval_M) - wasp.watch.rtc.time() - _TIME_TO_FALL_ASLEEP * 60) // 60
                    duration = max(duration, 0)  # if alarm too close
                    draw.string("Total sleep {:02d}h{:02d}m".format(
                        int(duration // 60),
                        int(duration % 60),), 0, 180)
                    cycl = duration / _CYCLE_LENGTH
                    draw.string("{} cycles   ".format(str(cycl)[0:4]), 0, 200)
                    cycl_modulo = cycl - int(cycl)
                    if cycl_modulo > 0.10 and cycl_modulo < 0.90:
                        draw.string("Not rested!", 0, 220)
                    else:
                        draw.string("Well rested", 0, 220)
                    return
            elif self.check_al.touch(event):
                self._alarm_state = self.check_al.state
                self.check_al.update()
        elif self._page == _SETTINGS2:
            if self._alarm_state:
                if self.check_smart.touch(event):
                    self._smart_alarm_state = self.check_smart.state
                    self.check_smart.draw()
                    return
                elif self.check_grad.touch(event):
                    self._grad_alarm_state = self.check_grad.state
                    self.check_grad.draw()
                    return
            if self.btn_sta.touch(event):
                self._start_tracking()
            elif self.btn_HR.touch(event):
                self.btn_HR.draw()
                self._track_HR_state = self.btn_HR.state
                return
        self._draw()

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
        elif self._page == _TRACKING:
            ti = wasp.watch.time.localtime(self._offset)
            draw.string('Began at {:02d}:{:02d}'.format(ti[3], ti[4]), 0, 70)
            if self._alarm_state:
                word = "Alarm at "
                if self._smart_alarm_state:
                    word = "Alarm BEFORE "
                ti = wasp.watch.time.localtime(self._WU_t)
                draw.string("{}{:02d}:{:02d}".format(word, ti[3], ti[4]), 0, 90)
                draw.string("Gradual wake: {}".format(True if self._grad_alarm_state else False), 0, 110)
            else:
                draw.string("No alarm set", 0, 90)
            draw.string("data points: {} / {}".format(str(self._data_point_nb), str(self._data_point_nb * _FREQ // _STORE_FREQ)), 0, 130)
            self.btn_off = widgets.Button(x=0, y=200, w=240, h=40, label="Stop tracking")
            self.btn_off.draw()
        elif self._page == _START:
            draw.set_font(_FONT)
            label = 'Sleep tracker with optional wake up alarm, smart alarm up to 40min before, gradual wake up to 15m. Swipe to navigate.'
            chunks = draw.wrap(label, 240)
            for i in range(len(chunks)-1):
                sub = label[chunks[i]:chunks[i+1]].rstrip()
                draw.string(sub, 0, 60 + 20 * i)
        elif self._page == _SETTINGS1:
            self.check_al = widgets.Checkbox(x=0, y=40, label="Wake me up")
            self.check_al.state = self._alarm_state
            self.check_al.draw()
            if self._alarm_state:
                self._spin_H = widgets.Spinner(30, 70, 0, 23, 2)
                self._spin_H.value = self._spinval_H
                self._spin_H.draw()
                self._spin_M = widgets.Spinner(150, 70, 0, 59, 2, 5)
                self._spin_M.value = self._spinval_M
                self._spin_M.draw()
        elif self._page == _SETTINGS2:
            if self._alarm_state:
                self.check_grad = widgets.Checkbox(0, 80, "Gradual wake")
                self.check_grad.state = self._grad_alarm_state
                self.check_grad.draw()
                self.check_smart = widgets.Checkbox(x=0, y=120, label="Smart alarm (alpha)")
                self.check_smart.state = self._smart_alarm_state
                self.check_smart.draw()
            else:
                draw.set_font(_FONT)
                label = 'Skipping smart and gradual alarm because no regular alarm is set'
                chunks = draw.wrap(label, 240)
                for i in range(len(chunks)-1):
                    sub = label[chunks[i]:chunks[i+1]].rstrip()
                    draw.string(sub, 0, 50 + 24 * i)
            self.btn_HR = widgets.Checkbox(x=0, y=40, label="Heart rate tracking")
            self.btn_HR.state = self._track_HR_state
            self.btn_HR.draw()
            self.btn_sta = widgets.Button(x=0, y=200, w=240, h=40, label="Start tracking")
            self.btn_sta.draw()
        self.stat_bar = widgets.StatusBar()
        self.stat_bar.clock = True
        self.stat_bar.draw()

    def _start_tracking(self):
        self._is_tracking = True
        # accel data not yet written to disk:
        self._data_point_nb = 0  # total number of data points so far
        self._last_checkpoint = 0  # to know when to save to file
        self._offset = int(wasp.watch.rtc.time())  # makes output more compact
        wasp.watch.accel.reset()

        # create one file per recording session:
        self.filep = "logs/sleep/{}.csv".format(str(self._offset + _TIMESTAMP))
        f = open(self.filep, "wb")
        f.write(b"")
        f.close()

        # add alarm to log accel data in _FREQ seconds
        self.next_al = wasp.watch.rtc.time() + _FREQ
        wasp.system.set_alarm(self.next_al, self._trackOnce)

        if self._grad_alarm_state and not self._alarm_state:
            # fix incompatible settings
            self._grad_alarm_state = _OFF

        # setting up alarm
        if self._alarm_state:
            self._WU_t = self._read_time(self._spinval_H, self._spinval_M)
            wasp.system.set_alarm(self._WU_t, self._listen_to_ticks)

            # also set alarm to vibrate a tiny bit before wake up time
            # to wake up gradually
            if self._grad_alarm_state:
                for t in _GRADUAL_WAKE:
                    wasp.system.set_alarm(self._WU_t - t*60, self._tiny_vibration)

            # wake up SleepTk 2min before earliest possible wake up
            if self._smart_alarm_state:
                self._WU_a = self._WU_t - _ANTICIPATE_ALLOWED - 120
                wasp.system.set_alarm(self._WU_a, self._smart_alarm_compute)
        wasp.system.notify_level = 1  # silent notifications
        self._page = _TRACKING

    def _read_time(self, HH, MM):
        "convert time from spinners to seconds"
        now = wasp.watch.rtc.get_localtime()
        yyyy = now[0]
        mm = now[1]
        dd = now[2]
        HH = self._spinval_H
        MM = self._spinval_M
        if HH < now[3] or (HH == now[3] and MM <= now[4]):
            dd += 1
        return wasp.watch.time.mktime((yyyy, mm, dd, HH, MM, 0, 0, 0, 0))

    def _disable_tracking(self, keep_main_alarm=False):
        """called by touching "STOP TRACKING" or when computing best alarm time
        to wake up you disables tracking features and alarms"""
        self._is_tracking = False
        wasp.system.cancel_alarm(self.next_al, self._trackOnce)
        if self._alarm_state:
            if keep_main_alarm is False:  # to keep the alarm when stopping because of low battery
                wasp.system.cancel_alarm(self._WU_t, self._listen_to_ticks)
                for t in _GRADUAL_WAKE:
                    wasp.system.cancel_alarm(self._WU_t - t*60, self._tiny_vibration)
            if self._smart_alarm_state:
                wasp.system.cancel_alarm(self._WU_a, self._smart_alarm_compute)
                self._smart_alarm_state = _OFF
        self._track_HR_state = _OFF
        wasp.watch.hrs.disable()
        self._periodicSave()
        wasp.gc.collect()

    def _trackOnce(self):
        """get one data point of accelerometer every _FREQ seconds, keep
        the average of each axis then store in a file every
        _STORE_FREQ seconds"""
        if self._is_tracking:
            buff = self._buff
            xyz = wasp.watch.accel.read_xyz()
            if xyz == (0, 0, 0):
                wasp.watch.accel.reset()
                xyz = wasp.watch.accel.read_xyz()
            buff[0] += xyz[0]
            buff[1] += xyz[1]
            buff[2] += xyz[2]
            self._data_point_nb += 1

            # add alarm to log accel data in _FREQ seconds
            self.next_al = wasp.watch.rtc.time() + _FREQ
            wasp.system.set_alarm(self.next_al, self._trackOnce)

            self._periodicSave()
            if wasp.watch.battery.level() <= _BATTERY_THRESHOLD:
                # strop tracking if battery low
                self._disable_tracking(keep_main_alarm=True)
                h, m = wasp.watch.time.localtime(wasp.watch.rtc.time())[3:5]
                wasp.system.notify(wasp.watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                          "title": "Bat low",
                                                          "body": "Stopped \
tracking sleep at {}h{}m because your battery went below {}%. Alarm kept \
on.".format(h, m, _BATTERY_THRESHOLD)})
            elif self._track_HR_state:
                if wasp.watch.rtc.time() - self._last_HR_date > _HR_FREQ and not self._track_HR_once:
                    wasp.watch.hrs.enable()
                    self._hrdata = ppg.PPG(wasp.watch.hrs.read_hrs())
                    self._track_HR_once = _ON
                    wasp.system.request_tick(1000 // 8)

        wasp.gc.collect()

    def _periodicSave(self):
        """save data to csv with row order:
            1. average arm angle
            2. elapsed times
            3. heart rate if present
         arm angle formula from https://www.nature.com/articles/s41598-018-31266-z
         note: math.atan() is faster than using a taylor serie
        """
        buff = self._buff
        n = self._data_point_nb - self._last_checkpoint
        if n >= _STORE_FREQ // _FREQ:
            buff[0] /= n
            buff[1] /= n
            buff[2] /= n
            if self._last_HR != _OFF:
                bpm = ",{}".format(self._last_HR)
                self._last_HR = _OFF
            else:
                bpm = ""
            f = open(self.filep, "ab")
            f.write("{:7f},{}{}\n".format(
                math.atan(buff[2] / (buff[0]**2 + buff[1]**2))*180/3.1415926535,  # estimated arm angle
                int(wasp.watch.rtc.time() - self._offset),
                bpm
                ).encode())
            f.close()
            del f
            buff[0] = 0  # resets x/y/z to 0
            buff[1] = 0
            buff[2] = 0
            self._last_checkpoint = self._data_point_nb
            wasp.gc.collect()

    def _signal_processing(self, data):
        """signal processing over the data read from the local file"""

        # take absolute rate of change of data
        for i in range(len(data)-1):
            mem = data[i+1]
            data[i] = abs(mem-data[i])
        del i

        # remove outliers:
        for x in range(len(data)):
            data[x] = min(0.005, data[x])
        del x
        wasp.gc.collect()
        wasp.system.keep_awake()

        # smoothen several times
        for j in range(5):
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
        x_maximas = array("H", [0])
        y_maximas = array("f", [0])
        window = int(60*60/_STORE_FREQ)
        skip = 1800 // _STORE_FREQ  # skip first 60 minutes of data
        for start_w in range(skip, len(data) - window + 1):
            m = max(data[start_w:start_w + window])
            for i in range(start_w, start_w + window):
                if data[i] == m and m > 0:
                    if i not in x_maximas:
                        if i - x_maximas[-1] <= 2:
                            # too close to last maximum, keep highest
                            if y_maximas[-1] < data[i]:
                                x_maximas[-1] = i
                                y_maximas[-1] = data[i]
                        else:
                            x_maximas.append(i)
                            y_maximas.append(m)
        del window, skip, start_w, i, m, x_maximas[0], y_maximas[0], data
        wasp.gc.collect()
        wasp.system.keep_awake()

        # merge the closest peaks while there are more than N peaks
        N = 3
        while len(x_maximas) > N:
            diffs = array("f", [x_maximas[int(x)+1] - x_maximas[int(x)] for x in range(len(x_maximas)-1)])
            ex = False
            for d_min_idx, d in enumerate(diffs):
                if ex:
                    break
                if d == min(diffs):
                    y_maximas.remove(y_maximas[d_min_idx+1])
                    x_maximas.remove(x_maximas[d_min_idx+1])
                    ex = True
        del diffs, ex, d_min_idx
        wasp.gc.collect()
        wasp.system.keep_awake()

        # sleep cycle duration is the average time distance between those N peaks
        cycle = sum([x_maximas[i+1] - x_maximas[i] for i in range(len(x_maximas) -1)]) / N * _STORE_FREQ

        last_peak = self._offset + x_maximas[-1] * _STORE_FREQ
        WU_t = self._WU_t

        # check if too late, already woken up:
        if last_peak + cycle > WU_t:
            raise Exception("Took too long to compute!")

        # if smart alarm wants to wake you up too early, limit how early
        if last_peak + cycle < WU_t - _ANTICIPATE_ALLOWED:
            earlier = _ANTICIPATE_ALLOWED
        else:  # will wake you up at computed time
            earlier = last_peak - self._offset + cycle
        wasp.system.keep_awake()
        return (earlier, cycle)

    def _smart_alarm_compute(self):
        """computes best wake up time from sleep data"""
        wasp.gc.collect()
        if not self._smart_alarm_state:
            t = wasp.watch.time.localtime(wasp.watch.rtc.time())
            wasp.system.notify(wasp.watch.rtc.get_uptime_ms(),
                          {"src": "SleepTk",
                           "title": "Smart alarm computation",
                           "body": "Started computation for the smart alarm \
BY MISTAKE at {:02d}h{:02d}m".format(t[3], t[4])})
            return
        mute = wasp.watch.display.mute
        mute(True)
        wasp.system.wake()
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
            #self._disable_tracking(keep_main_alarm=True)

            # read file one character at a time, to get only the 1st
            # value of each row, which is the arm angle
            data = array("f")
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
                    data.append(float(buff))
                    break
                if not skip:  # digit of arm angle value
                    buff += char

            f.close()
            del f, char, buff
            wasp.gc.collect()
            wasp.system.keep_awake()

            earlier, cycle = self._signal_processing(data)
            WU_t = self._WU_t
            wasp.gc.collect()

            # add new alarm
            wasp.system.set_alarm(max(WU_t - earlier, int(wasp.watch.rtc.time()) + 3),  # not before right now, to make sure it rings
                                  self._listen_to_ticks)

            # replace old gentle alarm by another one
            if self._grad_alarm_state:
                for t in _GRADUAL_WAKE:
                    wasp.system.cancel_alarm(WU_t - t*60, self._tiny_vibration)
                    if earlier + t*60 < _ANTICIPATE_ALLOWED:
                        wasp.system.set_alarm(WU_t - earlier - t*60, self._tiny_vibration)

            self._earlier = earlier
            self._page = _TRACKING
            wasp.system.notify(wasp.watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                      "title": "Finished smart alarm computation",
                                                      "body": "Finished computing best wake up time in {:2f}s. Sleep cycle: {:.2f}h".format(wasp.watch.rtc.time() - start_time, cycle)
                                                      })
        except Exception as e:
            wasp.gc.collect()
            h, m = wasp.watch.time.localtime(wasp.watch.rtc.time())[3:5]
            msg = "Exception occured at {:02d}h{:02d}m: '{}'%".format(h, m, str(e))
            f = open("smart_alarm_error_{}.txt".format(int(wasp.watch.rtc.time())), "wb")
            f.write(msg.encode())
            f.close()
            wasp.system.notify(wasp.watch.rtc.get_uptime_ms(), {"src": "SleepTk",
                                                      "title": "Smart alarm error",
                                                      "body": msg})
        wasp.gc.collect()


    def _listen_to_ticks(self):
        """listen to ticks every second, telling the watch to vibrate"""
        wasp.gc.collect()
        wasp.system.notify_level = self._old_notification_level  # restore notification level
        self._page = _RINGING
        mute = wasp.watch.display.mute
        mute(True)
        wasp.system.wake()
        wasp.system.switch(self)
        self._draw()
        wasp.system.request_tick(period_ms=1000)

    def tick(self, ticks):
        """vibrate to wake you up OR track heart rate using code from heart.py"""
        if self._page == _RINGING:
            wasp.watch.vibrator.pulse(duty=50, ms=500)
        elif self._track_HR_once:
            t = wasp.machine.Timer(id=1, period=8000000)
            mute = wasp.watch.display.mute
            t.start()
            self._subtick(1)
            wasp.system.keep_awake()
            mute(True)
            while t.time() < 41666:
                pass
            self._subtick(1)
            while t.time() < 83332:
                pass
            self._subtick(1)
            t.stop()
            del t

            if len(self._hrdata.data) >= 240:  # 10 seconds passed
                self._last_HR = self._hrdata.get_heart_rate()
                self._last_HR_date = int(wasp.watch.rtc.time())
                self._track_HR_once = _OFF
                wasp.watch.hrs.disable()

    def _subtick(self, ticks):
        """track heart rate at 24Hz"""
        self._hrdata.preprocess(wasp.watch.hrs.read_hrs())

    def _tiny_vibration(self):
        """vibrate just a tiny bit before waking up, to gradually return
        to consciousness"""
        wasp.gc.collect()
        mute = wasp.watch.display.mute
        mute(True)
        wasp.system.wake()
        wasp.system.switch(self)
        wasp.watch.vibrator.pulse(duty=60, ms=100)
