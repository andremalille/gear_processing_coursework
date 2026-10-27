from statistics import mean, stdev

import simulation
import main

PROTOCOL_M = (1, 1)
PROTOCOL_SEED = 10
PROTOCOL_TIME = 150.0
PROTOCOL_LINES = 50
TIME = 20000.0
NAMES = {"Cementation": "Цементація", "Hardening": "Загартування"}
ACTIONS = {
    "Exit": "вихід",
    "Hardening": "повторне загартування",
    "Cementation": "повна повторна обробка",
}

PAIRS = [
    ((10, 0), (10, 0)),
    ((15, 0), (15, 0)),
    ((8, 0), (8, 0)),
    ((10, 3), (10, 2)),
    ((10, 7), (10, 6)),
    ((13, 7), (13, 6)),
]
DEVICES = [1, 2, 3]


def protocol(m1, m2, cement, harden, time_limit, seed):
    log = []
    ids = {}
    gears = []

    def number(gear):
        if id(gear) not in ids:
            ids[id(gear)] = len(ids) + 1
            gears.append(gear)
        return ids[id(gear)]

    original = {
        "in_act": simulation.Process.in_act,
        "start": simulation.Process.start,
        "out_act": simulation.Process.out_act,
        "dispose": simulation.Dispose.in_act,
        "router": main.Router.__call__,
    }

    def in_act(self, gear):
        if self.name == "Cementation" and gear.stage == 0 and id(gear) not in ids:
            log.append((self.tcurr, f"деталь {number(gear)} надходить ззовні"))
        original["in_act"](self, gear)
        if self.queue and self.queue[-1] is gear:
            log.append(
                (
                    self.tcurr,
                    f"деталь {number(gear)} стає в чергу СМО «{NAMES[self.name]}» (довжина черги {len(self.queue)})",
                )
            )

    def start(self, idx, gear):
        original["start"](self, idx, gear)
        duration = getattr(gear, self.key)
        log.append(
            (
                self.tcurr,
                f"деталь {number(gear)} починає обслуговування в СМО «{NAMES[self.name]}», пристрій {idx + 1}, "
                f"тривалість {duration:.3f}, завершення о {self.tcurr + duration:.3f}",
            )
        )

    def out_act(self):
        for idx, end in enumerate(self.channel_end):
            if end == self.tcurr:
                log.append(
                    (
                        self.tcurr,
                        f"деталь {number(self.channel_gear[idx])} завершує обслуговування в СМО «{NAMES[self.name]}», пристрій {idx + 1}",
                    )
                )
        original["out_act"](self)

    def router(self, gear):
        stage = gear.stage
        target = original["router"](self, gear)
        log.append(
            (
                self.process2.tcurr,
                f"контроль деталі {number(gear)}: T = {gear.c:.3f} + {gear.h:.3f} = {gear.c + gear.h:.3f}, "
                f"етап {stage} -> {ACTIONS[target.name]}",
            )
        )
        return target

    def dispose(self, gear):
        original["dispose"](self, gear)
        total = gear.c + gear.h
        log.append(
            (
                self.tcurr,
                f"деталь {number(gear)} залишає систему, T = {total:.3f}, сорт {1 if total >= main.LOW else 2}",
            )
        )

    simulation.Process.in_act = in_act
    simulation.Process.start = start
    simulation.Process.out_act = out_act
    simulation.Dispose.in_act = dispose
    main.Router.__call__ = router
    try:
        main.run(m1, m2, cement, harden, time_limit, seed)
    finally:
        simulation.Process.in_act = original["in_act"]
        simulation.Process.start = original["start"]
        simulation.Process.out_act = original["out_act"]
        simulation.Dispose.in_act = original["dispose"]
        main.Router.__call__ = original["router"]
    return log


def print_protocol():
    print("=============== ПРОТОКОЛ ПОДІЙ ===============")
    print(
        f"вхід: цементація unif(10, 7), загартування unif(10, 6), надходження unif(10, 5), "
        f"пристроїв: {PROTOCOL_M[0]} і {PROTOCOL_M[1]}, seed = {PROTOCOL_SEED}, час моделювання {PROTOCOL_TIME:.0f} хв"
    )
    log = protocol(*PROTOCOL_M, (10, 7), (10, 6), PROTOCOL_TIME, PROTOCOL_SEED)
    for t, text in log[:PROTOCOL_LINES]:
        print(f"{t:8.3f}  {text}")


def print_table():
    print("\n=============== ТАБЛИЦЯ ВЕРИФІКАЦІЇ ===============")
    print(f"час моделювання {TIME:.0f} хв, надходження unif(10, 5) в усіх запусках")
    print(
        f"{'№':>3} {'цементація':>12} {'загартування':>13} {'m1':>3} {'m2':>3} "
        f"{'P(част.)':>9} {'P(повна)':>9} {'P(1 сорт)':>10} {'T сер.':>8} {'T σ':>8} {'у системі':>10}"
    )
    number = 0
    for cement, harden in PAIRS:
        for m1 in DEVICES:
            for m2 in DEVICES:
                number += 1
                result = main.run(m1, m2, cement, harden, TIME, number)
                totals = result["totals"]
                first_sort = sum(1 for t in totals if t >= main.LOW) / len(totals)
                print(
                    f"{number:>3} {'unif' + str(cement):>12} {'unif' + str(harden):>13} {m1:>3} {m2:>3} "
                    f"{result['partial'] / result['first']:>9.4f} {result['full'] / result['first']:>9.4f} "
                    f"{first_sort:>10.4f} {mean(totals):>8.3f} {stdev(totals):>8.3f} {result['arrived'] - len(totals):>10}"
                )


if __name__ == "__main__":
    print_protocol()
    print_table()
