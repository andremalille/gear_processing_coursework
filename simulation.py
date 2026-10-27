import random
from collections import deque


def unif(d, s):
    return random.uniform(d - s, d + s)


class Gear:
    def __init__(self):
        self.c = 0.0
        self.h = 0.0
        self.stage = 0


class Element:
    def __init__(self, name):
        self.name = name
        self.tcurr = 0.0
        self.tnext = float("inf")
        self.next_element = None

    def in_act(self, gear):
        pass

    def out_act(self):
        pass

    def do_statistics(self, delta):
        pass


class Create(Element):
    def __init__(self, name, mean, dev):
        super().__init__(name)
        self.mean = mean
        self.dev = dev
        self.tnext = 0.0
        self.quantity = 0

    def out_act(self):
        self.quantity += 1
        self.tnext = self.tcurr + unif(self.mean, self.dev)
        self.next_element.in_act(Gear())


class Process(Element):
    def __init__(self, name, mean, dev, channels, key):
        super().__init__(name)
        self.mean = mean
        self.dev = dev
        self.key = key
        self.channel_end = [float("inf")] * channels
        self.channel_gear = [None] * channels
        self.queue = deque()
        self.route = None
        self.busy_time = 0.0
        self.queue_area = 0.0

    def do_statistics(self, delta):
        busy = sum(1 for g in self.channel_gear if g is not None)
        self.busy_time += busy * delta
        self.queue_area += len(self.queue) * delta

    def start(self, idx, gear):
        t = unif(self.mean, self.dev)
        setattr(gear, self.key, t)
        self.channel_end[idx] = self.tcurr + t
        self.channel_gear[idx] = gear
        self.tnext = min(self.channel_end)

    def in_act(self, gear):
        for idx, gear_in_channel in enumerate(self.channel_gear):
            if gear_in_channel is None:
                self.start(idx, gear)
                return
        self.queue.append(gear)

    def out_act(self):
        for idx in range(len(self.channel_end)):
            if self.channel_end[idx] == self.tcurr:
                finished = self.channel_gear[idx]
                self.channel_end[idx] = float("inf")
                self.channel_gear[idx] = None
                if self.queue:
                    self.start(idx, self.queue.popleft())
                target = self.route(finished) if self.route else self.next_element
                target.in_act(finished)
        self.tnext = min(self.channel_end)


class Dispose(Element):
    def __init__(self, name):
        super().__init__(name)
        self.totals = []

    def in_act(self, gear):
        self.totals.append(gear.c + gear.h)


class Model:
    def __init__(self, elements, observer=None):
        self.elements = elements
        self.observer = observer
        self.tcurr = 0.0

    def simulate(self, time_limit):
        while True:
            tnext = min(e.tnext for e in self.elements)
            if tnext > time_limit:
                break
            delta = tnext - self.tcurr
            for e in self.elements:
                e.do_statistics(delta)
            self.tcurr = tnext
            for e in self.elements:
                e.tcurr = tnext
            for e in self.elements:
                if e.tnext == tnext:
                    e.out_act()
            if self.observer:
                self.observer(self)
