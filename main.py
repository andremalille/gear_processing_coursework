import random
from statistics import NormalDist, mean, stdev

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulation import Create, Process, Dispose, Model
import experiment

M1 = 2
M2 = 3
CEMENT = (10, 7)
HARDEN = (10, 6)
TIME = 100000.0
LOW = 20.0
HIGH = 25.0
BINS = 20
CHI2_CRITICAL = 27.59
SEED = 1
PLOT_FILE = "histogram_T.png"
PLOT_FILE_MEASURE = "histogram_T_measure.png"


class Router:
    def __init__(self):
        self.process1 = None
        self.process2 = None
        self.dispose = None
        self.first = 0
        self.partial = 0
        self.full = 0

    def blocked_exit(self, total, stage):
        return not (stage == 1 or total > HIGH)

    def blocked_partial(self, total, stage):
        return not (stage == 0 and LOW <= total <= HIGH)

    def blocked_full(self, total, stage):
        return not (stage == 0 and total < LOW)

    def __call__(self, gear, process, idx):
        total = process.channel_total[idx]
        stage = process.channel_stage[idx]
        if not self.blocked_exit(total, stage):
            target = self.dispose
        elif not self.blocked_partial(total, stage):
            target = self.process2
        else:
            target = self.process1
        if stage == 0:
            self.first += 1
            if target is self.process2:
                self.partial += 1
            elif target is self.process1:
                self.full += 1
        gear.stage = 1
        return target


def run(m1, m2, cement, harden, time_limit, seed, observer=None):
    random.seed(seed)
    router = Router()
    create = Create("Arrival", 10, 5)
    process1 = Process("Cementation", cement[0], cement[1], m1, "c")
    process2 = Process("Hardening", harden[0], harden[1], m2, "h")
    dispose = Dispose("Exit")
    router.process1 = process1
    router.process2 = process2
    router.dispose = dispose
    create.next_element = process1
    process1.next_element = process2
    process2.route = router
    model = Model([create, process1, process2, dispose], observer)
    model.simulate(time_limit)
    return {
        "arrived": create.quantity,
        "totals": dispose.totals,
        "first": router.first,
        "partial": router.partial,
        "full": router.full,
    }


def chi_square_normal(values):
    n = len(values)
    dist = NormalDist(mean(values), stdev(values))
    low, high = min(values), max(values)
    width = (high - low) / BINS
    counts = [0] * BINS
    for v in values:
        counts[min(BINS - 1, int((v - low) / width))] += 1
    expected = []
    for i in range(BINS):
        left = 0.0 if i == 0 else dist.cdf(low + i * width)
        right = 1.0 if i == BINS - 1 else dist.cdf(low + (i + 1) * width)
        expected.append(n * (right - left))
    chi2 = sum((o - e) ** 2 / e for o, e in zip(counts, expected))
    return low, width, counts, expected, chi2, BINS - 3


def plot_histogram(low, width, counts, expected, path):
    centers = [low + (i + 0.5) * width for i in range(BINS)]
    plt.figure(figsize=(8, 5))
    plt.bar(
        centers,
        counts,
        width=width,
        edgecolor="black",
        color="#8fb8de",
        label="Спостережена частота",
    )
    plt.plot(
        centers, expected, "o-", color="#c0392b", label="Нормальний закон (гіпотеза)"
    )
    plt.xlabel("Сумарний час обробки T, хв")
    plt.ylabel("Частота")
    plt.title("Гістограма частот сумарного часу обробки")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def yes_no(value):
    return "так" if value else "ні"


def characteristics(cement, harden, path):
    print(
        f"цементація unif({cement[0]:g}, {cement[1]:g}), загартування unif({harden[0]:g}, {harden[1]:g}), "
        f"пристроїв: {M1} і {M2}, час моделювання {TIME:.0f} хв"
    )
    result = run(M1, M2, cement, harden, TIME, SEED)
    totals = result["totals"]
    exited = len(totals)
    first_sort = sum(1 for t in totals if t >= LOW) / exited
    print(f"надійшло деталей              = {result['arrived']}")
    print(f"вийшло з системи              = {exited}")
    print(f"лишилось у системі            = {result['arrived'] - exited}")
    print(f"P(повторне загартування)      = {result['partial'] / result['first']:.4f}")
    print(f"P(повна повторна обробка)     = {result['full'] / result['first']:.4f}")
    print(f"P(перший сорт)                = {first_sort:.4f}")
    print(f"P(другий сорт)                = {1 - first_sort:.4f}")
    print(f"перший сорт не менше 90%      = {yes_no(first_sort >= 0.9)}")
    print(f"T середнє                     = {mean(totals):.4f}")
    print(f"T середнє квадратичне відхил. = {stdev(totals):.4f}")
    low, width, counts, expected, chi2, dof = chi_square_normal(totals)
    print(
        f"гіпотеза: нормальний закон з μ = {mean(totals):.2f}, σ = {stdev(totals):.2f}, {BINS} інтервалів"
    )
    print(
        f"хі-квадрат = {chi2:.2f}, ступенів свободи = {dof}, критичне (0.05) = {CHI2_CRITICAL}"
    )
    print(f"гіпотезу прийнято             = {yes_no(chi2 < CHI2_CRITICAL)}")
    plot_histogram(low, width, counts, expected, path)
    print(f"гістограму збережено у файл {path}")


if __name__ == "__main__":
    print("=============== БЛОК 1: ХАРАКТЕРИСТИКИ МОДЕЛІ ===============")
    characteristics(CEMENT, HARDEN, PLOT_FILE)
    new_cement, new_harden = experiment.research(run, CEMENT, HARDEN, LOW)
    print("\n[4] Характеристики системи із заходом")
    characteristics(new_cement, new_harden, PLOT_FILE_MEASURE)
