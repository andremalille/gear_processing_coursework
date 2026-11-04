from statistics import mean, stdev

import simulation
import main

PROTOCOL_M = (1, 1)
PROTOCOL_SEED = 10
PROTOCOL_TIME = 150.0
PROTOCOL_EVENTS = 14
TIME = 100000.0
NAMES = {"Cementation": "Цементація", "Hardening": "Загартування"}
ACTIONS = {
    "Exit": "вихід",
    "Hardening": "повторне загартування",
    "Cementation": "повна повторна обробка",
}

PAIRS = [
    ((10, 7), (10, 6)),
    ((13, 7), (13, 6)),
    ((10, 3), (10, 2)),
    ((10, 0), (10, 0)),
    ((15, 0), (15, 0)),
    ((8, 0), (8, 0)),
]
DEVICES = [1, 2, 3]


def law(parameters):
    d, s = parameters
    return f"{d:g}" if s == 0 else f"unif({d:g}, {s:g})"


def protocol(m1, m2, cement, harden, time_limit, seed):
    records = []
    ids = {}
    gears = []
    captured = {}

    def number(gear):
        if id(gear) not in ids:
            ids[id(gear)] = len(ids) + 1
            gears.append(gear)
        return ids[id(gear)]

    def tick(value):
        return "∞" if value == float("inf") else f"{value:.3f}"

    def state():
        create, p1, p2 = captured["elements"][:3]
        parts = [f"t0 = {tick(create.tnext)}"]
        for index, process in ((1, p1), (2, p2)):
            busy = ",".join("1" if g is not None else "0" for g in process.channel_gear)
            ends = ",".join(tick(e) for e in process.channel_end)
            parts.append(
                f"L{index} = {len(process.queue)}, K{index} = ({busy}), t{index} = ({ends})"
            )
        return "; ".join(parts)

    original = {
        "init": simulation.Model.__init__,
        "create": simulation.Create.out_act,
        "in_act": simulation.Process.in_act,
        "start": simulation.Process.start,
        "out_act": simulation.Process.out_act,
        "dispose": simulation.Dispose.in_act,
        "router": main.Router.__call__,
    }

    def model_init(self, elements, observer=None):
        original["init"](self, elements, observer)
        captured["elements"] = elements

    def create_out_act(self):
        record = {"t": self.tcurr, "event": "надходження ззовні", "changes": []}
        records.append(record)
        original["create"](self)
        record["state"] = state()

    def in_act(self, gear):
        original["in_act"](self, gear)
        if self.queue and self.queue[-1] is gear:
            records[-1]["changes"].append(
                f"деталь {number(gear)} стає в чергу СМО «{NAMES[self.name]}», довжина черги {len(self.queue)}"
            )

    def start(self, idx, gear):
        original["start"](self, idx, gear)
        duration = getattr(gear, self.key)
        records[-1]["changes"].append(
            f"деталь {number(gear)} займає пристрій {idx + 1} СМО «{NAMES[self.name]}», "
            f"тривалість {duration:.3f}, завершення о {self.tcurr + duration:.3f}"
        )

    def out_act(self):
        mine = []
        for idx, end in enumerate(self.channel_end):
            if end == self.tcurr:
                gear = self.channel_gear[idx]
                record = {
                    "t": self.tcurr,
                    "event": f"завершення обслуговування, СМО «{NAMES[self.name]}», пристрій {idx + 1}, деталь {number(gear)}",
                    "changes": [],
                }
                records.append(record)
                mine.append(record)
        original["out_act"](self)
        for record in mine:
            record["state"] = state()

    def router(self, gear, process, idx):
        total = process.channel_total[idx]
        stage = process.channel_stage[idx]
        target = original["router"](self, gear, process, idx)
        records[-1]["changes"].append(
            f"контроль деталі {number(gear)}: T = {total:.3f}, R = {stage} -> {ACTIONS[target.name]}"
        )
        return target

    def dispose(self, gear):
        original["dispose"](self, gear)
        total = gear.c + gear.h
        records[-1]["changes"].append(
            f"деталь {number(gear)} залишає систему, T = {total:.3f}, сорт {1 if total >= main.LOW else 2}"
        )

    simulation.Model.__init__ = model_init
    simulation.Create.out_act = create_out_act
    simulation.Process.in_act = in_act
    simulation.Process.start = start
    simulation.Process.out_act = out_act
    simulation.Dispose.in_act = dispose
    main.Router.__call__ = router
    try:
        main.run(m1, m2, cement, harden, time_limit, seed)
    finally:
        simulation.Model.__init__ = original["init"]
        simulation.Create.out_act = original["create"]
        simulation.Process.in_act = original["in_act"]
        simulation.Process.start = original["start"]
        simulation.Process.out_act = original["out_act"]
        simulation.Dispose.in_act = original["dispose"]
        main.Router.__call__ = original["router"]
    return records


def print_protocol():
    print("=============== ПРОТОКОЛ ПОДІЙ ===============")
    print(
        f"вхід: цементація {law((10, 7))}, загартування {law((10, 6))}, надходження {law((10, 5))}, "
        f"пристроїв: {PROTOCOL_M[0]} і {PROTOCOL_M[1]}, seed = {PROTOCOL_SEED}, час моделювання {PROTOCOL_TIME:.0f} хв"
    )
    records = protocol(*PROTOCOL_M, (10, 7), (10, 6), PROTOCOL_TIME, PROTOCOL_SEED)
    for number, record in enumerate(records[:PROTOCOL_EVENTS], 1):
        print(f"\n{number}. t = {record['t']:.3f}, подія: {record['event']}")
        for change in record["changes"]:
            print(f"     {change}")
        print(f"     стан: {record['state']}")


def print_table():
    print("\n=============== ТАБЛИЦЯ ВЕРИФІКАЦІЇ ===============")
    print(f"час моделювання {TIME:.0f} хв, надходження {law((10, 5))} в усіх запусках")
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
                    f"{number:>3} {law(cement):>12} {law(harden):>13} {m1:>3} {m2:>3} "
                    f"{result['partial'] / result['first']:>9.4f} {result['full'] / result['first']:>9.4f} "
                    f"{first_sort:>10.4f} {mean(totals):>8.3f} {stdev(totals):>8.3f} {result['arrived'] - len(totals):>10}"
                )


if __name__ == "__main__":
    print_protocol()
    print_table()
