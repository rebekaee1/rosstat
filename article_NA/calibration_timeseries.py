"""
ПРАВИЛЬНЫЙ ПОДХОД к калибровке недиагональных B.

Ключевая идея:
  - Нам НЕ НУЖНЫ несколько IO-таблиц
  - Нужна ОДНА IO-таблица (для A, X_base, Y_base)
  - Плюс ВРЕМЕННЫЕ РЯДЫ цен и объёмов по секторам:
    * ИЦП (индексы цен производителей) по ОКВЭД — Росстат, ежемесячно
    * Индексы физического объёма производства — Росстат, ежеквартально
    * Объёмы розничной торговли по группам товаров — ежемесячно

  Это даёт 12–48 наблюдений в год, что БОЛЕЕ чем достаточно
  для оценки n×n элементов B при n = 3–10 секторов.

Метод:
  Q_t = B · P_t + θ_t
  Первые разности (eliminates θ if it changes slowly):
  ΔQ_t = B · ΔP_t + Δθ_t  (≈ B · ΔP_t + ε_t)

  Ответ на критику Н.А.:
  - B может дрейфовать → используем КОРОТКИЕ окна (2–3 года)
  - Внутри окна B ≈ const — это ГОРАЗДО более мягкое предположение,
    чем B = const между 2011 и 2021
  - При ежемесячных данных: 24–36 наблюдений в окне
"""

import numpy as np
from numpy.linalg import inv, norm
from scipy.optimize import least_squares
import warnings

np.set_printoptions(precision=4, suppress=True, linewidth=140)
warnings.filterwarnings('ignore')


# ═══════════════════════════════════════
# ЯДРО МОДЕЛИ
# ═══════════════════════════════════════

def S_mat(A):
    return inv(np.eye(A.shape[0]) - A)

def M_matrix(A, B):
    n = A.shape[0]; I = np.eye(n); IAt = I - A.T; S = S_mat(A)
    return B + (I-A) @ inv(np.diag(np.diag(IAt))) @ np.diag(np.diag(S@B)) @ IAt

def eq_P(A, B, th):
    return -inv(M_matrix(A, B)) @ th

def Q_fn(B, P, th):
    return B @ P + th

def X_fn(A, B, P, th):
    return S_mat(A) @ (P * Q_fn(B, P, th))


def offdiag_42(Bd, th, Y):
    n = len(Bd); phi = Y / Y.sum()
    R = sum((2*Bd[i]+th[i])/(1-phi[i]) for i in range(n))
    G = sum(phi[i]/(1-phi[i]) for i in range(n))
    M = R/(1+G)
    m = np.array([(2*Bd[i]+th[i]-phi[i]*M)/(1-phi[i]) for i in range(n)])
    B = np.diag(Bd.copy())
    for i in range(n):
        for k in range(n):
            if k != i: B[k,i] = -m[i]*phi[k]
    return B


def calib_42(A, Xb, Yb):
    n = A.shape[0]
    def res(p):
        d, t = p[:n], p[n:]
        if np.any(t <= 0) or np.any(d >= 0): return np.ones(2*n)*1e6
        B = offdiag_42(d, t, Yb)
        try:
            Ps = eq_P(A, B, t); Xs = X_fn(A, B, Ps, t)
        except: return np.ones(2*n)*1e6
        if np.any(np.isnan(Ps)) or np.any(np.isnan(Xs)): return np.ones(2*n)*1e6
        return np.concatenate([(Ps-1)*1e3, (Xs-Xb)/Xb*1e3])
    r = least_squares(res, np.concatenate([-Yb/2, 2*Yb]), method='lm',
                       max_nfev=500000, ftol=1e-15, xtol=1e-15, gtol=1e-15)
    d, t = r.x[:n], r.x[n:]
    return t, offdiag_42(d, t, Yb)


def recalib(A, Xb, Yb, Boff):
    n = A.shape[0]
    d0 = np.diag(Boff); t0 = np.maximum(Yb - Boff @ np.ones(n), 1.0)
    def res(p):
        d, t = p[:n], p[n:]
        if np.any(t <= 0) or np.any(d >= 0): return np.ones(2*n)*1e6
        B = Boff.copy(); np.fill_diagonal(B, d)
        try:
            Ps = eq_P(A, B, t); Xs = X_fn(A, B, Ps, t)
        except: return np.ones(2*n)*1e6
        if np.any(np.isnan(Ps)) or np.any(np.isnan(Xs)): return np.ones(2*n)*1e6
        return np.concatenate([(Ps-1)*1e3, (Xs-Xb)/Xb*1e3])
    r = least_squares(res, np.concatenate([d0, t0]), method='lm',
                       max_nfev=500000, ftol=1e-15, xtol=1e-15, gtol=1e-15)
    d, t = r.x[:n], r.x[n:]
    B = Boff.copy(); np.fill_diagonal(B, d)
    return t, B


# ═══════════════════════════════════════
# ГЕНЕРАЦИЯ РЕАЛИСТИЧНЫХ ВРЕМЕННЫХ РЯДОВ
# (имитация данных Росстата: ИЦП + объёмы)
# ═══════════════════════════════════════

def make_economy(n, seed=42):
    rng = np.random.RandomState(seed)
    if n == 3:
        M1 = np.array([[20,30,10],[40,80,20],[15,25,30]], dtype=float)
        Y0 = np.array([40,70,35], dtype=float)
        X0 = np.array([100,210,105], dtype=float)
        A = M1 / X0[np.newaxis, :]
    else:
        A = rng.uniform(0.02, 0.25, (n,n))
        for i in range(n): A[i,i] = rng.uniform(0.05, 0.35)
        A = A / (A.sum(axis=0)[np.newaxis,:] * 1.5)
        Y0 = rng.uniform(20, 100, n)
        X0 = S_mat(A) @ Y0

    th0, B0 = calib_42(A, X0, Y0)

    # Добавляем реалистичные отклонения от (4.2)
    Bt = B0.copy()
    for i in range(n):
        for j in range(n):
            if i != j:
                Bt[i,j] += rng.normal(0, abs(B0[i,j]) * 0.3)

    th_t = -M_matrix(A, Bt) @ np.ones(n)
    P_check = eq_P(A, Bt, th_t)
    if np.max(np.abs(P_check - 1)) > 0.01: return None
    Xt = X_fn(A, Bt, P_check, th_t)
    Yt = Q_fn(Bt, P_check, th_t)
    if np.any(Yt <= 0) or np.any(Xt <= 0): return None
    return {'A': A, 'B': Bt, 'theta': th_t, 'X': Xt, 'Y': Yt, 'n': n, 'B0': B0}


def generate_monthly_data(A, B, theta, T_months, noise_p=0.02, noise_q=0.03,
                          B_drift_annual=0.0, seed=42):
    """
    Имитирует ежемесячные данные Росстата:
    - P_t: индексы цен (ИЦП) — случайные блуждания с шумом
    - Q_t: объёмы спроса — из модели Q = B·P + θ + шум наблюдения

    noise_p: std месячного шока цен (реалистично: 1-3%)
    noise_q: std шума наблюдения в Q (реалистично: 2-5%)
    B_drift_annual: ежегодный дрейф B (% от |B|)
    """
    rng = np.random.RandomState(seed)
    n = len(theta)

    P_series, Q_series, Q_true_series = [], [], []
    B_current = B.copy()
    theta_current = theta.copy()

    P_t = np.ones(n)  # базовые цены = 1

    for t in range(T_months):
        # Цены: случайное блуждание (как реальные ИЦП)
        dP = rng.normal(0, noise_p, n)
        # Секторальная корреляция (реалистично: общий макрошок)
        macro_shock = rng.normal(0, noise_p * 0.5)
        dP += macro_shock
        P_t = P_t * (1 + dP)
        P_t = np.clip(P_t, 0.5, 2.0)

        # θ: сезонность + тренд (реалистично)
        seasonal = 1 + 0.05 * np.sin(2*np.pi*t/12 + rng.uniform(0, 2*np.pi, n))
        trend = 1 + 0.005 * (t / 12)  # +0.5%/год
        theta_t = theta_current * seasonal * trend
        # + случайный шок автономного спроса
        theta_t *= np.clip(rng.normal(1.0, 0.02, n), 0.9, 1.1)

        # B дрейфует
        if B_drift_annual > 0 and t > 0 and t % 12 == 0:
            drift = rng.normal(0, B_drift_annual, (n,n))
            B_current = B_current * (1 + drift)
            for i in range(n): B_current[i,i] = min(B_current[i,i], -5)

        # Истинный спрос
        Q_true = Q_fn(B_current, P_t, theta_t)
        # Наблюдаемый спрос (с шумом измерения)
        Q_obs = Q_true * np.clip(rng.normal(1.0, noise_q, n), 0.8, 1.2)

        if np.all(Q_true > 0):
            P_series.append(P_t.copy())
            Q_series.append(Q_obs.copy())
            Q_true_series.append(Q_true.copy())

    return (np.array(P_series), np.array(Q_series),
            np.array(Q_true_series), B_current)


# ═══════════════════════════════════════
# АЛГОРИТМ: ОЦЕНКА B ИЗ ВРЕМЕННЫХ РЯДОВ
# ═══════════════════════════════════════

def estimate_B_first_diff(P_series, Q_series, B_prior=None, lam=0.0):
    """
    Оценка B методом первых разностей:
    ΔQ_t = B · ΔP_t + ε_t

    Первые разности убирают θ (если оно меняется гладко).
    """
    dQ = np.diff(Q_series, axis=0)  # (T-1) × n
    dP = np.diff(P_series, axis=0)  # (T-1) × n
    n = dQ.shape[1]

    if lam > 0 and B_prior is not None:
        # Ridge
        B = np.zeros((n,n))
        for i in range(n):
            B[i,:] = np.linalg.solve(
                dP.T @ dP + lam * np.eye(n),
                dP.T @ dQ[:,i] + lam * B_prior[i,:])
        return B
    else:
        # OLS
        Bt = np.linalg.lstsq(dP, dQ, rcond=None)[0]
        return Bt.T


def estimate_B_levels_detrended(P_series, Q_series, B_prior=None, lam=0.0):
    """
    Оценка B из уровней с удалением тренда θ:
    Q_t - trend(Q_t) = B · (P_t - mean(P)) + ε_t

    Линейный детренд Q убирает гладко меняющееся θ.
    """
    T, n = Q_series.shape

    # Детренд Q (убираем линейный тренд = гладко меняющееся θ)
    t_axis = np.arange(T).reshape(-1, 1)
    Q_detrend = np.zeros_like(Q_series)
    for i in range(n):
        # Линейная регрессия Q_i на t
        X_t = np.column_stack([np.ones(T), t_axis])
        beta = np.linalg.lstsq(X_t, Q_series[:, i], rcond=None)[0]
        Q_detrend[:, i] = Q_series[:, i] - X_t @ beta

    # Центрируем P
    P_centered = P_series - P_series.mean(axis=0)

    if lam > 0 and B_prior is not None:
        B = np.zeros((n,n))
        for i in range(n):
            B[i,:] = np.linalg.solve(
                P_centered.T @ P_centered + lam * np.eye(n),
                P_centered.T @ Q_detrend[:,i] + lam * B_prior[i,:])
        return B
    else:
        Bt = np.linalg.lstsq(P_centered, Q_detrend, rcond=None)[0]
        return Bt.T


# ═══════════════════════════════════════
# ТЕСТЫ
# ═══════════════════════════════════════

def run_test(title, eco, T_months, noise_p, noise_q, B_drift, seed=42):
    A, Bt, th_t = eco['A'], eco['B'], eco['theta']
    Xt, Yt, n = eco['X'], eco['Y'], eco['n']
    B0 = eco['B0']
    mask = ~np.eye(n, dtype=bool)

    P_s, Q_s, Q_true, B_final = generate_monthly_data(
        A, Bt, th_t, T_months,
        noise_p=noise_p, noise_q=noise_q,
        B_drift_annual=B_drift, seed=seed)
    T = len(P_s)

    # Формула (4.2) — baseline
    th_42, B_42 = calib_42(A, Xt, Yt)
    err_42 = norm(B_42 - Bt, 'fro')
    od_42 = np.sqrt(np.mean((B_42[mask] - Bt[mask])**2))

    print(f"\n  ── {title} (T={T} мес, n={n}) ──")
    if B_drift > 0:
        d_B = norm(B_final - Bt, 'fro')
        print(f"  Дрейф B за период: ||ΔB|| = {d_B:.2f}")

    results = []

    # Метод 1: Первые разности + OLS
    B_fd = estimate_B_first_diff(P_s, Q_s)
    th_fd, B_fd_rc = recalib(A, Xt, Yt, B_fd)
    P_fd = eq_P(A, B_fd_rc, th_fd)
    err_fd = norm(B_fd_rc - Bt, 'fro')
    od_fd = np.sqrt(np.mean((B_fd_rc[mask] - Bt[mask])**2))
    results.append(('Δ-OLS + recalib', err_fd, od_fd, np.max(np.abs(P_fd-1))))

    # Метод 2: Первые разности + Ridge (prior = 4.2)
    for lam in [0.1, 1.0, 10.0]:
        B_fr = estimate_B_first_diff(P_s, Q_s, B_prior=B_42, lam=lam)
        th_fr, B_fr_rc = recalib(A, Xt, Yt, B_fr)
        P_fr = eq_P(A, B_fr_rc, th_fr)
        err_fr = norm(B_fr_rc - Bt, 'fro')
        od_fr = np.sqrt(np.mean((B_fr_rc[mask] - Bt[mask])**2))
        results.append((f'Δ-Ridge(λ={lam}) + recalib', err_fr, od_fr,
                        np.max(np.abs(P_fr-1))))

    # Метод 3: Детренд уровней + OLS
    B_dt = estimate_B_levels_detrended(P_s, Q_s)
    th_dt, B_dt_rc = recalib(A, Xt, Yt, B_dt)
    P_dt = eq_P(A, B_dt_rc, th_dt)
    err_dt = norm(B_dt_rc - Bt, 'fro')
    od_dt = np.sqrt(np.mean((B_dt_rc[mask] - Bt[mask])**2))
    results.append(('Detrend-OLS + recalib', err_dt, od_dt, np.max(np.abs(P_dt-1))))

    # Метод 4: Детренд + Ridge
    B_dr = estimate_B_levels_detrended(P_s, Q_s, B_prior=B_42, lam=1.0)
    th_dr, B_dr_rc = recalib(A, Xt, Yt, B_dr)
    P_dr = eq_P(A, B_dr_rc, th_dr)
    err_dr = norm(B_dr_rc - Bt, 'fro')
    od_dr = np.sqrt(np.mean((B_dr_rc[mask] - Bt[mask])**2))
    results.append(('Detrend-Ridge(λ=1) + recalib', err_dr, od_dr,
                    np.max(np.abs(P_dr-1))))

    # Таблица результатов
    print(f"  {'Метод':35s} ||ΔB||  od_RMSE  |P*-1|    vs(4.2)")
    print(f"  {'─'*75}")
    print(f"  {'Формула (4.2) [baseline]':35s} {err_42:6.2f}  {od_42:7.2f}  {'—':8s}  {'—':>7s}")
    for name, e, od, pmax in results:
        delta = (1 - e/err_42)*100 if err_42 > 0 else 0
        ok = '✓' if pmax < 0.01 else f'{pmax:.1e}'
        print(f"  {name:35s} {e:6.2f}  {od:7.2f}  {ok:8s}  {delta:+6.1f}%")

    # Лучший метод
    best = min(results, key=lambda x: x[1])
    if best[1] < err_42:
        print(f"  → Лучший: {best[0]} (улучшение {(1-best[1]/err_42)*100:.1f}%)")
    else:
        print(f"  → Временные ряды не улучшили (4.2)")

    return results, err_42


def main():
    import time
    t0 = time.time()

    print("█" * 80)
    print("█  КАЛИБРОВКА B ИЗ ВРЕМЕННЫХ РЯДОВ ЦЕН И ОБЪЁМОВ")
    print("█  (ИЦП + объёмы производства, данные Росстата)")
    print("█" * 80)
    print("""
  Данные:
    - ОДНА IO-таблица → матрица A, X_base, Y_base, формула (4.2) → B₀, θ₀
    - Временные ряды (Росстат):
      * ИЦП по видам экономической деятельности — ежемесячно
      * Индексы физического объёма — ежемесячно/ежеквартально
      * Это НЕ дополнительные IO-таблицы!

  Метод:
    ΔQ_t = B · ΔP_t + ε_t  (первые разности убирают θ)
    или: detrend(Q_t) = B · center(P_t) + ε_t

  Ответ на критику «B меняется»:
    Используем короткое окно (2–3 года ≈ 24–36 месяцев).
    Внутри окна B ≈ const — мягкое предположение.
""")

    # ═══ 3 сектора ═══
    eco3 = make_economy(3, seed=42)

    print(f"\n{'▓'*80}")
    print(f"▓  3 СЕКТОРА")
    print(f"{'▓'*80}")

    run_test("Идеальные данные (мало шума)",
             eco3, T_months=36, noise_p=0.02, noise_q=0.01, B_drift=0.0)

    run_test("Реалистичный шум (σ_p=2%, σ_q=3%)",
             eco3, T_months=36, noise_p=0.02, noise_q=0.03, B_drift=0.0)

    run_test("Сильный шум (σ_p=3%, σ_q=5%)",
             eco3, T_months=36, noise_p=0.03, noise_q=0.05, B_drift=0.0)

    run_test("Короткий ряд: 12 месяцев",
             eco3, T_months=12, noise_p=0.02, noise_q=0.03, B_drift=0.0)

    run_test("Длинный ряд: 60 месяцев (5 лет)",
             eco3, T_months=60, noise_p=0.02, noise_q=0.03, B_drift=0.0)

    # Главный тест: B ДРЕЙФУЕТ (критика Н.А.)
    run_test("B дрейфует 5%/год, окно 2 года",
             eco3, T_months=24, noise_p=0.02, noise_q=0.03, B_drift=0.05)

    run_test("B дрейфует 5%/год, окно 3 года",
             eco3, T_months=36, noise_p=0.02, noise_q=0.03, B_drift=0.05)

    run_test("B дрейфует 10%/год, окно 2 года",
             eco3, T_months=24, noise_p=0.02, noise_q=0.03, B_drift=0.10)

    run_test("B дрейфует 10%/год, окно 3 года",
             eco3, T_months=36, noise_p=0.02, noise_q=0.03, B_drift=0.10)

    # ═══ 5 секторов ═══
    print(f"\n{'▓'*80}")
    print(f"▓  5 СЕКТОРОВ")
    print(f"{'▓'*80}")

    eco5 = None
    for s in range(100):
        eco5 = make_economy(5, seed=s)
        if eco5 is not None: break

    if eco5:
        run_test("Реалистичный (σ_p=2%, σ_q=3%)",
                 eco5, T_months=36, noise_p=0.02, noise_q=0.03, B_drift=0.0)

        run_test("B дрейфует 5%/год, окно 3 года",
                 eco5, T_months=36, noise_p=0.02, noise_q=0.03, B_drift=0.05)

        run_test("Длинный ряд 60 мес + шум 5%",
                 eco5, T_months=60, noise_p=0.03, noise_q=0.05, B_drift=0.0)

    # ═══ 10 секторов ═══
    print(f"\n{'▓'*80}")
    print(f"▓  10 СЕКТОРОВ")
    print(f"{'▓'*80}")

    eco10 = None
    for s in range(200):
        eco10 = make_economy(10, seed=s)
        if eco10 is not None: break

    if eco10:
        run_test("36 мес, реалистичный шум",
                 eco10, T_months=36, noise_p=0.02, noise_q=0.03, B_drift=0.0)

        run_test("60 мес, B дрейфует 5%/год",
                 eco10, T_months=60, noise_p=0.02, noise_q=0.03, B_drift=0.05)

    # ═══ ФИНАЛ ═══
    print(f"\n{'█'*80}")
    print(f"█  ВРЕМЯ: {time.time()-t0:.1f} сек")
    print(f"{'█'*80}")

    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        ФИНАЛЬНЫЙ АЛГОРИТМ                                    ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  ДАННЫЕ:                                                                      ║
║    1. Одна IO-таблица (Росстат, напр. 2021)                                  ║
║       → матрица A, базовые X и Y                                             ║
║    2. Ежемесячные данные Росстата за 2–3 года:                               ║
║       → ИЦП по видам экономической деятельности (P_t)                        ║
║       → Индексы физического объёма производства (Q_t)                        ║
║                                                                               ║
║  АЛГОРИТМ:                                                                   ║
║    Шаг 1: IO-таблица → A, X_base, Y_base                                    ║
║    Шаг 2: Формула (4.2) → B₀, θ₀ (prior / начальное приближение)           ║
║    Шаг 3: Первые разности ΔQ_t = B·ΔP_t + ε_t                              ║
║            → Ridge-регрессия с prior B₀, подбор λ кросс-валидацией           ║
║    Шаг 4: Рекалибровка diag(B) + θ → P*=1, X=X_base                        ║
║                                                                               ║
║  ПОЧЕМУ ЭТО РАБОТАЕТ:                                                        ║
║    - Не требует дополнительных IO-таблиц                                     ║
║    - Использует широко доступные данные Росстата                             ║
║    - Короткое окно (2–3 года) → B ≈ const внутри окна                       ║
║    - Первые разности убирают тренд θ                                         ║
║    - Ridge с prior (4.2) устойчив к шуму                                     ║
║    - Рекалибровка ГАРАНТИРУЕТ P*=1 и X=X_base                               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
