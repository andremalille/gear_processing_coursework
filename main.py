import math
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
PLOT_BINS = 20
ALPHA = 0.05
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


def chi2_critical(dof, alpha):
    def lower(a, x):
        if x <= 0:
            return 0.0
        if x < a + 1:
            term = total = 1.0 / a
            n = a
            while abs(term) > 1e-14 * abs(total):
                n += 1
                term *= x / n
                total += term
            return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
        b = x + 1 - a
        c = 1e300
        d = 1 / b
        h = d
        for i in range(1, 500):
            an = -i * (i - a)
            b += 2
            d = an * d + b
            d = 1 / (d if abs(d) > 1e-300 else 1e-300)
            c = b + an / c
            h *= d * c
        return 1 - h * math.exp(-x + a * math.log(x) - math.lgamma(a))

    low, high = 0.0, 200.0
    for _ in range(100):
        mid = (low + high) / 2
        if lower(dof / 2, mid / 2) < 1 - alpha:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def fit_truncated_normal(values, low, high):
    nd = NormalDist()

    def minus_log_likelihood(m, s):
        if s <= 0.3:
            return float("inf")
        z = nd.cdf((high - m) / s) - nd.cdf((low - m) / s)
        if z <= 1e-12:
            return float("inf")
        return len(values) * math.log(s * z) + sum((v - m) ** 2 for v in values) / (
            2 * s * s
        )

    m = mean(values)
    s = stdev(values)
    best = minus_log_likelihood(m, s)
    step = s / 2
    while step > 1e-5:
        improved = False
        for dm, ds in ((step, 0), (-step, 0), (0, step), (0, -step)):
            value = minus_log_likelihood(m + dm, s + ds)
            if value < best:
                best, m, s, improved = value, m + dm, s + ds, True
        if not improved:
            step /= 2
    return m, s


def identify_left(values):
    low = min(values)
    m, s = fit_truncated_normal(values, low, HIGH)
    nd = NormalDist(m, s)
    z = nd.cdf(HIGH) - nd.cdf(low)
    return {
        "name": "усічений нормальний",
        "text": f"μ = {m:.2f}, σ = {s:.2f}",
        "low": low,
        "high": HIGH,
        "pdf": lambda x: nd.pdf(x) / z,
        "cdf": lambda x: min(1.0, max(0.0, (nd.cdf(x) - nd.cdf(low)) / z)),
    }


def identify_right(values):
    low = HIGH
    high = low + 3 * (mean(values) - low)
    return {
        "name": "трикутний спадний",
        "text": f"b = {high:.2f}",
        "low": low,
        "high": high,
        "pdf": lambda x: 2 * (high - x) / (high - low) ** 2,
        "cdf": lambda x: (
            0.0
            if x <= low
            else 1.0 if x >= high else 1 - ((high - x) / (high - low)) ** 2
        ),
    }


def plot_bins(totals):
    width = (max(totals) - min(totals)) / PLOT_BINS
    while True:
        width = math.ceil(width * 20 - 1e-9) / 20
        left_bins = math.ceil((HIGH - min(totals)) / width)
        right_bins = math.ceil((max(totals) - HIGH) / width)
        if left_bins + right_bins <= PLOT_BINS:
            break
        width += 0.05
    start = HIGH - left_bins * width
    edges = [start + i * width for i in range(left_bins + right_bins + 1)]
    counts = [0] * (len(edges) - 1)
    for t in totals:
        counts[min(len(counts) - 1, int((t - start) / width))] += 1
    return edges, counts, width


def goodness_of_fit(part, n_part, edges, counts, side):
    if side == "left":
        picked = [i for i in range(len(counts)) if edges[i + 1] <= HIGH + 1e-9]
    else:
        picked = [i for i in range(len(counts)) if edges[i] >= HIGH - 1e-9]
    bounds = [edges[i] for i in picked] + [edges[picked[-1] + 1]]
    if side == "left":
        bounds[0] = -math.inf
    else:
        bounds[-1] = math.inf
    observed = [counts[i] for i in picked]
    expected = [
        n_part * (part["cdf"](bounds[i + 1]) - part["cdf"](bounds[i]))
        for i in range(len(picked))
    ]
    while expected[-1] < 5:
        expected[-2] += expected.pop()
        observed[-2] += observed.pop()
    while expected[0] < 5:
        expected[1] += expected.pop(0)
        observed[1] += observed.pop(0)
    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected))
    return chi2, len(observed)


def plot_identification(totals, left, right, edges, counts, width, path):
    n_left = sum(1 for t in totals if t <= HIGH)
    n_right = len(totals) - n_left
    plt.figure(figsize=(9, 5.5))
    plt.bar(
        [e + width / 2 for e in edges[:-1]],
        counts,
        width=width,
        edgecolor="black",
        color="#8fb8de",
    )
    for part, count, color in ((left, n_left, "#c0392b"), (right, n_right, "#1e8449")):
        xs = [part["low"] + (part["high"] - part["low"]) * i / 200 for i in range(201)]
        ys = [count * width * part["pdf"](x) for x in xs]
        plt.plot(xs, ys, color=color, linewidth=2, label=f"{part['name']} закон")
    plt.xticks(range(math.ceil(edges[0] / 5) * 5, int(edges[-1]) + 1, 5))
    plt.xlabel("Сумарний час обробки T, хв")
    plt.ylabel("Частота")
    plt.title("Гістограма частот сумарного часу обробки")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def yes_no(value):
    return "так" if value else "ні"


def report_part(title, part, n_part, edges, counts, side, parameters):
    chi2, intervals = goodness_of_fit(part, n_part, edges, counts, side)
    dof = intervals - 1 - parameters
    critical = chi2_critical(dof, ALPHA)
    print(f"{title}: {part['name']} закон, {part['text']}")
    print(
        f"  інтервалів = {intervals}, хі-квадрат = {chi2:.2f}, ступенів свободи = {dof}, критичне ({ALPHA}) = {critical:.2f}, прийнято = {yes_no(chi2 < critical)}"
    )


def identification(totals, path):
    left_values = [t for t in totals if t <= HIGH]
    right_values = [t for t in totals if t > HIGH]
    left = identify_left(left_values)
    right = identify_right(right_values)
    edges, counts, width = plot_bins(totals)
    report_part(f"T ≤ {HIGH:g}", left, len(left_values), edges, counts, "left", 2)
    report_part(f"T > {HIGH:g}", right, len(right_values), edges, counts, "right", 1)
    plot_identification(totals, left, right, edges, counts, width, path)
    print(f"гістограму збережено у файл {path}")


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
    identification(totals, path)


if __name__ == "__main__":
    print("=============== БЛОК 1: ХАРАКТЕРИСТИКИ МОДЕЛІ ===============")
    characteristics(CEMENT, HARDEN, PLOT_FILE)
    new_cement, new_harden = experiment.research(run, CEMENT, HARDEN, LOW)
    print("\n[4] Характеристики системи із заходом")
    characteristics(new_cement, new_harden, PLOT_FILE_MEASURE)
