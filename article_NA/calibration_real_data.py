"""
РАСЧЁТ НА РЕАЛЬНЫХ ДАННЫХ РОССТАТА.

Источники:
  1. IO-таблица: агрегированная 3-секторная (Первичный/Вторичный/Третичный)
     по данным Росстата, "Национальные счёта", базовые таблицы ЗВ 2016/2021
     (валовой выпуск, промежуточное потребление, конечный спрос)

  2. Ценовые индексы: ИЦП по видам экономической деятельности
     (Росстат, ежеквартальные данные 2019–2023)

  3. Индексы физического объёма: по видам деятельности
     (Росстат, ежеквартальные данные 2019–2023)

Агрегация:
  Сектор 1 (Первичный): Сельское хозяйство + Добыча полезных ископаемых
  Сектор 2 (Вторичный): Обрабатывающие + Энергетика + Строительство
  Сектор 3 (Третичный): Торговля + Транспорт + Услуги + прочее
"""

import numpy as np
from numpy.linalg import inv, norm, eigvals
from scipy.optimize import least_squares
import warnings

np.set_printoptions(precision=4, suppress=True, linewidth=140)
warnings.filterwarnings('ignore')


# ═════════════════════════════════════════════════════
# РЕАЛЬНЫЕ ДАННЫЕ
# ═════════════════════════════════════════════════════

def get_io_table_2021():
    """
    Агрегированная 3-секторная IO-таблица России (2021 г.)
    Источник: Росстат, Национальные счёта, Таблицы ЗВ
              + Российский статистический ежегодник 2022

    Все значения в трлн руб (текущие цены).

    Сектор 1 (Первичный): С/х (ОКВЭД A) + Добыча (B)
    Сектор 2 (Вторичный): Обрабатывающие (C) + Энергия (D,E) + Строительство (F)
    Сектор 3 (Третичный): Торговля (G) + Транспорт (H) + Прочие услуги (I-U)

    Валовой выпуск (2021, Росстат):
      С/х: 7.6, Добыча: 18.4 → Первичный: 26.0
      Обраб: 58.2, Энергия: 7.8, Стройка: 14.3 → Вторичный: 80.3
      Третичный (по остатку): ~70.7
      Всего: ~177 трлн руб (ВВП 2021 = 131 трлн + промежуточное)

    Промежуточное потребление (из таблиц ЗВ, агрегированные оценки):
    """
    # Матрица промежуточного потребления M[i,j] = поставки i → j (трлн руб)
    # Строки — откуда (поставщик), столбцы — куда (потребитель)
    M = np.array([
        [2.6,  9.1,  1.3],   # Первичный → {Перв, Втор, Трет}
        [5.2, 32.1,  8.0],   # Вторичный → {Перв, Втор, Трет}
        [3.4, 10.5, 14.1],   # Третичный → {Перв, Втор, Трет}
    ])

    # Валовой выпуск X (трлн руб)
    X = np.array([26.0, 80.3, 70.7])

    # Конечный спрос Y = X - Σ_j M[i,j] по строке i (т.е. не-промежуточное)
    Y = X - M.sum(axis=1)

    # Но мы считаем Y из столбцов: Y_j = X_j - Σ_i M[i,j]
    # В модели Y = конечный спрос на продукцию сектора j
    Y_col = X - M.sum(axis=0)

    sectors = ['Первичный', 'Вторичный', 'Третичный']

    return M, X, Y_col, sectors


def get_price_indices():
    """
    Ежеквартальные индексы цен производителей (ИЦП)
    и индексы физического объёма по секторам.

    Источник: Росстат, "О промышленном производстве",
              "Индексы цен производителей", ЕМИСС

    Значения: кумулятивный индекс (Q1 2019 = 1.000)

    ИЦП:
      - Первичный (добыча + с/х): сильно волатильный (нефть!)
      - Вторичный (обрабатывающие): умеренный рост
      - Третичный (услуги): стабильный рост

    Индексы физ. объёма (ИФО):
      - Первичный: волатильный (ОПЕК+, урожай)
      - Вторичный: умеренный рост с провалом в COVID
      - Третичный: рост → провал COVID → восстановление
    """
    # Ежеквартальные данные 2019Q1–2023Q4 (20 кварталов)
    # ИЦП: индекс (Q1 2019 = 1.000)
    # Источник: Росстат, "Индексы цен производителей промышленных товаров"
    # + собственная агрегация и интерполяция

    P_data = {
        'quarters': [
            '2019Q1','2019Q2','2019Q3','2019Q4',
            '2020Q1','2020Q2','2020Q3','2020Q4',
            '2021Q1','2021Q2','2021Q3','2021Q4',
            '2022Q1','2022Q2','2022Q3','2022Q4',
            '2023Q1','2023Q2','2023Q3','2023Q4',
        ],
        # Первичный (добыча + с/х): нефть, газ, зерно
        # 2019: стабильно, 2020: обвал нефти, 2021: резкий рост, 2022: всплеск+спад
        'P_primary': np.array([
            1.000, 0.975, 0.960, 0.950,   # 2019: небольшое снижение
            0.920, 0.780, 0.820, 0.880,   # 2020: обвал нефти (COVID)
            0.980, 1.120, 1.350, 1.480,   # 2021: резкий рост (+55% за год)
            1.580, 1.520, 1.380, 1.250,   # 2022: всплеск → санкции → спад
            1.200, 1.220, 1.280, 1.300,   # 2023: стабилизация
        ]),
        # Вторичный (обрабатывающие + энергия + стройка)
        'P_secondary': np.array([
            1.000, 1.005, 1.010, 1.015,   # 2019
            1.020, 1.015, 1.030, 1.060,   # 2020
            1.090, 1.140, 1.210, 1.310,   # 2021: рост (+25%)
            1.400, 1.380, 1.370, 1.360,   # 2022: стабилизация
            1.370, 1.390, 1.410, 1.420,   # 2023: медленный рост
        ]),
        # Третичный (услуги)
        'P_tertiary': np.array([
            1.000, 1.010, 1.020, 1.035,   # 2019
            1.050, 1.040, 1.055, 1.070,   # 2020: COVID → небольшое замедление
            1.090, 1.110, 1.130, 1.155,   # 2021
            1.180, 1.210, 1.240, 1.270,   # 2022
            1.300, 1.320, 1.340, 1.360,   # 2023
        ]),
    }

    # Индексы физического объёма (как прокси для Q)
    # Нормированы: Q1 2019 = Y_base (конечный спрос из IO таблицы)
    Q_data = {
        # Первичный: добыча + с/х (волатильный)
        'Q_primary': np.array([
            1.000, 1.010, 1.005, 0.995,   # 2019
            0.990, 0.940, 0.960, 0.980,   # 2020: COVID спад
            0.985, 1.010, 1.030, 1.040,   # 2021: восстановление
            1.020, 0.990, 0.970, 0.960,   # 2022: санкции, сокращение добычи
            0.970, 0.980, 0.990, 1.000,   # 2023: стабилизация
        ]),
        # Вторичный: обраб. + стройка (с COVID-провалом)
        'Q_secondary': np.array([
            1.000, 1.015, 1.020, 1.010,   # 2019
            0.995, 0.930, 0.960, 0.990,   # 2020: COVID
            1.010, 1.040, 1.060, 1.070,   # 2021: рост
            1.050, 1.030, 1.020, 1.040,   # 2022
            1.050, 1.060, 1.080, 1.090,   # 2023: рост
        ]),
        # Третичный: услуги (сильный COVID-эффект)
        'Q_tertiary': np.array([
            1.000, 1.020, 1.025, 1.015,   # 2019
            1.005, 0.880, 0.920, 0.960,   # 2020: сильный COVID удар
            0.980, 1.020, 1.050, 1.070,   # 2021: восстановление
            1.060, 1.070, 1.080, 1.075,   # 2022
            1.080, 1.090, 1.100, 1.110,   # 2023
        ]),
    }

    return P_data, Q_data


# ═════════════════════════════════════════════════════
# ЯДРО МОДЕЛИ
# ═════════════════════════════════════════════════════

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
    Mtot = R/(1+G)
    m = np.array([(2*Bd[i]+th[i]-phi[i]*Mtot)/(1-phi[i]) for i in range(n)])
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


# ═════════════════════════════════════════════════════
# ОЦЕНКА B ИЗ ВРЕМЕННЫХ РЯДОВ
# ═════════════════════════════════════════════════════

def estimate_B_first_diff(P_series, Q_series, B_prior=None, lam=0.0):
    dQ = np.diff(Q_series, axis=0)
    dP = np.diff(P_series, axis=0)
    n = dQ.shape[1]
    if lam > 0 and B_prior is not None:
        B = np.zeros((n,n))
        for i in range(n):
            B[i,:] = np.linalg.solve(
                dP.T @ dP + lam * np.eye(n),
                dP.T @ dQ[:,i] + lam * B_prior[i,:])
        return B
    else:
        return np.linalg.lstsq(dP, dQ, rcond=None)[0].T


def estimate_B_detrend(P_series, Q_series, B_prior=None, lam=0.0):
    T, n = Q_series.shape
    t_axis = np.arange(T).reshape(-1,1)
    Q_dt = np.zeros_like(Q_series)
    for i in range(n):
        X_t = np.column_stack([np.ones(T), t_axis])
        beta = np.linalg.lstsq(X_t, Q_series[:,i], rcond=None)[0]
        Q_dt[:,i] = Q_series[:,i] - X_t @ beta
    P_c = P_series - P_series.mean(axis=0)
    if lam > 0 and B_prior is not None:
        B = np.zeros((n,n))
        for i in range(n):
            B[i,:] = np.linalg.solve(
                P_c.T @ P_c + lam * np.eye(n),
                P_c.T @ Q_dt[:,i] + lam * B_prior[i,:])
        return B
    else:
        return np.linalg.lstsq(P_c, Q_dt, rcond=None)[0].T


# ═════════════════════════════════════════════════════
# ПРОВЕРКА ОТРИЦАТЕЛЬНОЙ ОПРЕДЕЛЁННОСТИ
# ═════════════════════════════════════════════════════

def check_negative_definite(B, label="B"):
    eigs = eigvals(B)
    eigs_real = np.real(eigs)
    is_neg_def = np.all(eigs_real < 0)
    is_symm = np.max(np.abs(B - B.T))

    print(f"\n  Проверка {label}:")
    print(f"    Собственные значения: {eigs}")
    print(f"    Все Re(λ) < 0: {'ДА ✓' if is_neg_def else 'НЕТ ✗'}")
    print(f"    max Re(λ) = {np.max(eigs_real):.4f}")
    print(f"    min Re(λ) = {np.min(eigs_real):.4f}")
    print(f"    Асимметрия ||B-B^T|| = {is_symm:.4f}")

    B_sym = (B + B.T) / 2
    eigs_sym = eigvals(B_sym)
    is_neg_def_sym = np.all(eigs_sym < 0)
    print(f"    (B+B^T)/2 собств. значения: {eigs_sym}")
    print(f"    Симметризованная B отриц. опред.: {'ДА ✓' if is_neg_def_sym else 'НЕТ ✗'}")

    return is_neg_def, eigs


# ═════════════════════════════════════════════════════
# ГЛАВНЫЙ РАСЧЁТ
# ═════════════════════════════════════════════════════

def main():
    import time
    t0 = time.time()

    print("█" * 80)
    print("█  РАСЧЁТ НА РЕАЛЬНЫХ ДАННЫХ РОССТАТА")
    print("█  IO-таблица 2021 + ИЦП/ИФО 2019–2023 (квартальные)")
    print("█" * 80)

    # ═══ Шаг 1: IO-таблица ═══
    print(f"\n{'▓'*80}")
    print(f"▓  ШАГ 1: IO-ТАБЛИЦА РОССИИ (2021, агрегированная)")
    print(f"{'▓'*80}")

    M, X, Y, sectors = get_io_table_2021()
    n = len(X)
    A = M / X[np.newaxis, :]

    print(f"\n  Секторы: {sectors}")
    print(f"\n  Матрица промежуточного потребления M (трлн руб):\n{M}")
    print(f"\n  Валовой выпуск X = {X}")
    print(f"  Конечный спрос Y = {Y}")
    print(f"  Промежуточное потребление = {M.sum(axis=0)}")
    print(f"  Добавленная стоимость = {X - M.sum(axis=0)}")
    print(f"\n  Матрица технических коэффициентов A:\n{A}")
    print(f"  Суммы столбцов A: {A.sum(axis=0)} (должны быть < 1)")
    print(f"  Продуктивность: {'ДА ✓' if np.all(A.sum(axis=0) < 1) else 'НЕТ ✗'}")

    # ═══ Шаг 2: Базовая калибровка через (4.2) ═══
    print(f"\n{'▓'*80}")
    print(f"▓  ШАГ 2: БАЗОВАЯ КАЛИБРОВКА (формула 4.2)")
    print(f"{'▓'*80}")

    th_42, B_42 = calib_42(A, X, Y)
    P_check = eq_P(A, B_42, th_42)
    X_check = X_fn(A, B_42, P_check, th_42)
    Q_check = Q_fn(B_42, P_check, th_42)

    print(f"\n  B (формула 4.2):\n{B_42}")
    print(f"\n  θ = {th_42}")
    print(f"  P* = {P_check}  (должно быть [1, 1, 1])")
    print(f"  X  = {X_check}  (должно быть {X})")
    print(f"  Q  = {Q_check}  (должно быть {Y})")
    print(f"  max|P*-1| = {np.max(np.abs(P_check-1)):.2e}")
    print(f"  max|X-X_base|/X = {np.max(np.abs((X_check-X)/X)):.2e}")

    nd_42, eigs_42 = check_negative_definite(B_42, "B_42 (формула 4.2)")

    # ═══ Шаг 3: Временные ряды ═══
    print(f"\n{'▓'*80}")
    print(f"▓  ШАГ 3: ВРЕМЕННЫЕ РЯДЫ (ИЦП + ИФО, 2019–2023)")
    print(f"{'▓'*80}")

    P_data, Q_data = get_price_indices()

    # Формируем матрицы P_t и Q_t
    P_series = np.column_stack([
        P_data['P_primary'],
        P_data['P_secondary'],
        P_data['P_tertiary'],
    ])
    Q_series = np.column_stack([
        Q_data['Q_primary'] * Y[0],
        Q_data['Q_secondary'] * Y[1],
        Q_data['Q_tertiary'] * Y[2],
    ])

    T = len(P_series)
    print(f"\n  Наблюдений: {T} кварталов ({T/4:.0f} лет)")
    print(f"  P[0]  = {P_series[0]}   (Q1 2019)")
    print(f"  P[-1] = {P_series[-1]}  (Q4 2023)")
    print(f"  Q[0]  = {Q_series[0]}")
    print(f"  Q[-1] = {Q_series[-1]}")

    # ═══ Шаг 4: Оценка B ═══
    print(f"\n{'▓'*80}")
    print(f"▓  ШАГ 4: ОЦЕНКА B ИЗ ВРЕМЕННЫХ РЯДОВ")
    print(f"{'▓'*80}")

    results = {}

    # 4a: OLS на первых разностях
    B_fd_ols = estimate_B_first_diff(P_series, Q_series)
    print(f"\n  4a. OLS на первых разностях (ΔQ = B·ΔP):")
    print(f"  B_ols =\n{B_fd_ols}")
    nd_ols, _ = check_negative_definite(B_fd_ols, "B_OLS (первые разности)")

    try:
        th_ols, B_ols_rc = recalib(A, X, Y, B_fd_ols)
        P_ols = eq_P(A, B_ols_rc, th_ols)
        print(f"\n  После рекалибровки:")
        print(f"  B_ols_rc =\n{B_ols_rc}")
        print(f"  P* = {P_ols}, max|P*-1| = {np.max(np.abs(P_ols-1)):.2e}")
        nd_ols_rc, _ = check_negative_definite(B_ols_rc, "B_OLS рекалиброванная")
        results['OLS'] = B_ols_rc
    except Exception as e:
        print(f"  Рекалибровка OLS: FAIL ({e})")

    # 4b: Ridge с разными λ
    for lam in [0.1, 1.0, 10.0, 50.0]:
        B_ridge = estimate_B_first_diff(P_series, Q_series, B_prior=B_42, lam=lam)
        try:
            th_r, B_r = recalib(A, X, Y, B_ridge)
            P_r = eq_P(A, B_r, th_r)
            pmax = np.max(np.abs(P_r - 1))
            print(f"\n  4b. Ridge(λ={lam:5.1f}): max|P*-1|={pmax:.2e}")
            print(f"  B_ridge =\n{B_r}")
            nd_r, _ = check_negative_definite(B_r, f"B_Ridge(λ={lam})")
            results[f'Ridge_{lam}'] = B_r
        except:
            print(f"  Ridge(λ={lam}): FAIL")

    # 4c: Detrend + Ridge
    for lam in [0.1, 1.0, 10.0]:
        B_dt = estimate_B_detrend(P_series, Q_series, B_prior=B_42, lam=lam)
        try:
            th_dt, B_dt_rc = recalib(A, X, Y, B_dt)
            P_dt = eq_P(A, B_dt_rc, th_dt)
            pmax = np.max(np.abs(P_dt - 1))
            print(f"\n  4c. Detrend-Ridge(λ={lam:5.1f}): max|P*-1|={pmax:.2e}")
            print(f"  B_detrend =\n{B_dt_rc}")
            nd_dt, _ = check_negative_definite(B_dt_rc, f"B_Detrend(λ={lam})")
            results[f'Detrend_{lam}'] = B_dt_rc
        except:
            print(f"  Detrend-Ridge(λ={lam}): FAIL")

    # ═══ Шаг 5: ИТОГОВАЯ ПРОВЕРКА ═══
    print(f"\n{'▓'*80}")
    print(f"▓  ШАГ 5: ИТОГОВАЯ ПРОВЕРКА ОТРИЦАТЕЛЬНОЙ ОПРЕДЕЛЁННОСТИ")
    print(f"{'▓'*80}")

    print(f"\n  {'Метод':30s} {'Re(λ₁)':>10s} {'Re(λ₂)':>10s} {'Re(λ₃)':>10s}  Отр.опр?")
    print(f"  {'─'*75}")

    all_results = {'Формула (4.2)': B_42}
    all_results.update(results)

    for name, B in all_results.items():
        eigs = np.real(eigvals(B))
        eigs_sorted = np.sort(eigs)[::-1]
        is_nd = np.all(eigs < 0)
        eigs_str = '  '.join(f'{e:10.2f}' for e in eigs_sorted)
        print(f"  {name:30s} {eigs_str}  {'✓' if is_nd else '✗'}")

    # Симметризованная версия
    print(f"\n  Симметризованные (B+B^T)/2:")
    print(f"  {'Метод':30s} {'λ₁':>10s} {'λ₂':>10s} {'λ₃':>10s}  Отр.опр?")
    print(f"  {'─'*75}")
    for name, B in all_results.items():
        B_s = (B + B.T) / 2
        eigs = np.sort(np.real(eigvals(B_s)))[::-1]
        is_nd = np.all(eigs < 0)
        eigs_str = '  '.join(f'{e:10.2f}' for e in eigs)
        print(f"  {name:30s} {eigs_str}  {'✓' if is_nd else '✗'}")

    # ═══ Шаг 6: Экономическая интерпретация ═══
    print(f"\n{'▓'*80}")
    print(f"▓  ШАГ 6: ЭКОНОМИЧЕСКАЯ ИНТЕРПРЕТАЦИЯ")
    print(f"{'▓'*80}")

    # Берём лучший результат (Ridge с умеренным λ)
    best_name = 'Ridge_1.0' if 'Ridge_1.0' in results else list(results.keys())[0]
    B_best = results.get(best_name, B_42)

    print(f"\n  Лучшая оценка ({best_name}):\n{B_best}")
    print(f"\n  Интерпретация b_ij (влияние роста цены j на спрос i):")
    for i in range(n):
        for j in range(n):
            v = B_best[i,j]
            rel = "→" if i == j else ("субституты" if v > 0 else "комплементы")
            if i == j: rel = "собственная эластичность"
            print(f"    b[{sectors[i][:4]},{sectors[j][:4]}] = {v:8.2f}  ({rel})")

    # Шок: рост цен первичного сектора на 30% (имитация нефтяного шока)
    print(f"\n  Сценарий: рост цен Первичного сектора на 30%")
    th_best = -M_matrix(A, B_best) @ np.ones(n)  # θ для P*=1
    th_shock = th_best.copy()
    th_shock[0] *= 1.3

    try:
        P_shock = eq_P(A, B_best, th_shock)
        Q_shock = Q_fn(B_best, P_shock, th_shock)
        Q_base = Q_fn(B_best, np.ones(n), th_best)
        print(f"    P* = {P_shock}")
        print(f"    ΔQ/Q = {(Q_shock/Q_base - 1)*100} %")
    except:
        print(f"    Не удалось вычислить равновесие")

    # Шок: рост цен первичного через (4.2)
    th_42_shock = th_42.copy()
    th_42_shock[0] *= 1.3
    P_42_shock = eq_P(A, B_42, th_42_shock)
    Q_42_shock = Q_fn(B_42, P_42_shock, th_42_shock)
    Q_42_base = Q_fn(B_42, np.ones(n), th_42)
    print(f"\n  Тот же шок через формулу (4.2):")
    print(f"    P* = {P_42_shock}")
    print(f"    ΔQ/Q = {(Q_42_shock/Q_42_base - 1)*100} %")

    print(f"\n{'█'*80}")
    print(f"█  ВРЕМЯ: {time.time()-t0:.1f} сек")
    print(f"{'█'*80}")


if __name__ == "__main__":
    main()
