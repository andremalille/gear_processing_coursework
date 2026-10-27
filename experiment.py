import math
from statistics import mean, stdev

BETA = 0.95
EPS = 0.01
TARGET = 0.9
STEP = 200.0
TRANSIENT_TIME = 20000.0
RUN_TIME = 20000.0
EPS_QUEUE = 0.05
PILOT = 10
DELTA_MIN = 0.0
DELTA_MAX = 6.0
LEVELS = 7
M_GRID = 6


def share(result, low):
    totals = result["totals"]
    return sum(1 for t in totals if t >= low) / len(totals)


def chebyshev_eps(sigma, n):
    return sigma / math.sqrt(n * (1 - BETA))


def replications(sigma, eps):
    return max(4, math.ceil(sigma**2 / (eps**2 * (1 - BETA))))


def make_observer(curve):
    state = {"next": STEP}

    def observe(model):
        if model.tcurr < state["next"]:
            return
        queue = (
            model.elements[1].queue_area + model.elements[2].queue_area
        ) / model.tcurr
        curve.append((model.tcurr, queue))
        state["next"] += STEP

    return observe


def transient_time(curves, eps):
    length = min(len(c) for c in curves)
    start = None
    for k in range(length):
        values = [c[k][1] for c in curves]
        if max(values) - min(values) < eps:
            if start is None:
                start = k
        else:
            start = None
    return curves[0][start][0] if start is not None else None


def research(run, cement, harden, low):
    print("\n=============== 2: ДОСЛІДЖЕННЯ МОДЕЛІ ===============")
    base_m = (M_GRID, M_GRID)

    curves = []
    for k in range(4):
        curve = []
        run(*base_m, cement, harden, TRANSIENT_TIME, 100 + k, make_observer(curve))
        curves.append(curve)
    transient = transient_time(curves, EPS_QUEUE)
    print("\n[1] Перехідний період (4 прогони)")
    if transient is None:
        print("за час спостереження розбіжність між прогонами не стала меншою за ε")
    else:
        print(f"середня довжина черги, ε = {EPS_QUEUE}: T = {transient:.0f} хв")
        print(
            f"довжина прогону {RUN_TIME:.0f} хв у {RUN_TIME / transient:.0f} разів більша за перехідний період"
        )
    print(
        "частка першого сорту залежить лише від часів обробки самої деталі, а не від початкового стану системи"
    )

    pilot = [
        share(run(*base_m, cement, harden, RUN_TIME, 200 + k), low)
        for k in range(PILOT)
    ]
    sigma = stdev(pilot)
    n = replications(sigma, EPS)
    print("\n[2] Кількість повторних замірів")
    print(
        f"середнє квадратичне відхилення за {PILOT} пробними прогонами = {sigma:.4f}, ε = {EPS}, β = {BETA}"
    )
    print(f"необхідна кількість замірів n = {n}")

    half = (DELTA_MAX - DELTA_MIN) / 2
    mid = (DELTA_MAX + DELTA_MIN) / 2
    levels = [-1 + 2 / (LEVELS - 1) * i for i in range(LEVELS)]
    deltas = [mid + half * x for x in levels]
    table = {}
    for d1 in deltas:
        for d2 in deltas:
            values = [
                share(
                    run(
                        *base_m,
                        (cement[0] + d1, cement[1]),
                        (harden[0] + d2, harden[1]),
                        RUN_TIME,
                        1000 + k,
                    ),
                    low,
                )
                for k in range(n)
            ]
            table[(d1, d2)] = (mean(values), chebyshev_eps(stdev(values), n))
    print(
        "\n[3] Пошук заходу: середня частка першого сорту, рядки d1 (цементація), стовпці d2 (загартування)"
    )
    print("d1\\d2  " + "  ".join(f"{d:5.1f}" for d in deltas))
    for d1 in deltas:
        print(f"{d1:5.1f}  " + "  ".join(f"{table[(d1, d2)][0]:5.3f}" for d2 in deltas))
    feasible = [
        (d1 + d2, -table[(d1, d2)][0], d1, d2)
        for (d1, d2), (m, e) in table.items()
        if m - e >= TARGET
    ]
    if feasible:
        feasible.sort()
        _, _, best1, best2 = feasible[0]
    else:
        best1, best2 = max(table, key=lambda key: table[key][0])
    best_mean, best_eps = table[(best1, best2)]
    print(f"обрано: d1 = {best1:.1f} хв, d2 = {best2:.1f} хв")
    print(
        f"частка першого сорту = {best_mean:.4f}, нижня межа = {best_mean - best_eps:.4f}"
    )
    return (cement[0] + best1, cement[1]), (harden[0] + best2, harden[1])
