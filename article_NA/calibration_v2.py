"""
Вычислимая ценовая модель общего равновесия (Моисеев, Внуков)
ВЕРСИЯ 2: Улучшенный 2-шаговый алгоритм калибровки недиагональных элементов B.

Ключевая идея:
  Шаг 1: Оценить недиагональные B из временных данных (regression)
  Шаг 2: Зафиксировав недиагональные, аналитически найти diag(B) и θ
          для ТОЧНОГО воспроизведения базового состояния (P*=1, X=X_base)
  Шаг 3: Итерировать шаги 1-2 до сходимости
"""

import numpy as np
from numpy.linalg import inv, det, eigvals, norm
from scipy.optimize import least_squares
import warnings

np.set_printoptions(precision=6, suppress=True, linewidth=130)
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════
# ЯДРО МОДЕЛИ
# ══════════════════════════════════════════════

def leontief_inv(A):
    return inv(np.eye(A.shape[0]) - A)


def eq_prices_closed(A, B, theta):
    """P* = -[B + (I-A)(diag(I-A^T))^{-1} diag(S·B) (I-A^T)]^{-1} θ"""
    n = A.shape[0]
    I = np.eye(n)
    IAt = I - A.T
    S = inv(I - A)
    M = B + (I - A) @ inv(np.diag(np.diag(IAt))) @ np.diag(np.diag(S @ B)) @ IAt
    return -inv(M) @ theta


def model_output(A, B, P, theta):
    """X = (I-A)^{-1} · (P ∘ Q(P)), где Q = BP + θ"""
    S = leontief_inv(A)
    Q = B @ P + theta
    return S @ (P * Q)


def model_Q(B, P, theta):
    return B @ P + theta


def model_VA(A, B, P, theta):
    S = leontief_inv(A)
    Q = B @ P + theta
    return (P - A.T @ P) * (S @ Q)


# ══════════════════════════════════════════════
# ФОРМУЛА (4.2): ПРОСТАЯ ВЕРСИЯ
# b_ki = -(b_ii + Y_i) * φ_k, k ≠ i
# ══════════════════════════════════════════════

def offdiag_formula42_simple(B_diag, Y_base):
    """Простая формула: b_ki = -(b_ii + Y_i) * φ_k, не решая систему."""
    n = len(B_diag)
    phi = Y_base / Y_base.sum()
    B = np.diag(B_diag.copy())
    for i in range(n):
        m_i = B_diag[i] + Y_base[i]
        for k in range(n):
            if k != i:
                B[k, i] = -m_i * phi[k]
    return B


def offdiag_formula42_consistent(B_diag, theta, Y_base):
    """
    Решение системы (4.2) аналитически.
    m_i = b_ii + q_i, где q_i = Σ_j b_ij + θ_i
    m_i = (2b_ii + θ_i - φ_i·M) / (1 - φ_i), M = Σ m_j
    """
    n = len(B_diag)
    phi = Y_base / Y_base.sum()

    R = sum((2 * B_diag[i] + theta[i]) / (1 - phi[i]) for i in range(n))
    G = sum(phi[i] / (1 - phi[i]) for i in range(n))
    M_total = R / (1 + G)

    m = np.array([(2 * B_diag[i] + theta[i] - phi[i] * M_total) / (1 - phi[i])
                  for i in range(n)])

    B = np.diag(B_diag.copy())
    for i in range(n):
        for k in range(n):
            if k != i:
                B[k, i] = -m[i] * phi[k]
    return B


# ══════════════════════════════════════════════
# БАЗОВАЯ КАЛИБРОВКА: diag(B) + θ при фиксированных недиагональных
# ══════════════════════════════════════════════

def calibrate_diag_theta(A, X_base, Y_base, B_offdiag_fixed=None):
    """
    Найти diag(B) и θ такие, что P*=1 и X=X_base.
    B_offdiag_fixed: если задана, то это матрица с недиагональными элементами
                     (диагональ будет перезаписана).
    """
    n = A.shape[0]

    def residuals(params):
        B_diag = params[:n]
        theta = params[n:]

        if np.any(theta <= 0) or np.any(B_diag >= 0):
            return np.ones(2 * n) * 1e6

        if B_offdiag_fixed is not None:
            B = B_offdiag_fixed.copy()
            np.fill_diagonal(B, B_diag)
        else:
            B = offdiag_formula42_consistent(B_diag, theta, Y_base)

        try:
            P_star = eq_prices_closed(A, B, theta)
            X_model = model_output(A, B, P_star, theta)
        except Exception:
            return np.ones(2 * n) * 1e6

        if np.any(np.isnan(P_star)) or np.any(np.isnan(X_model)):
            return np.ones(2 * n) * 1e6

        return np.concatenate([
            (P_star - 1.0) * 1000,
            (X_model - X_base) / X_base * 1000
        ])

    x0 = np.concatenate([-Y_base / 2.0, 2 * Y_base])
    result = least_squares(residuals, x0, method='lm', max_nfev=100000,
                           ftol=1e-15, xtol=1e-15, gtol=1e-15)

    B_diag_opt = result.x[:n]
    theta_opt = result.x[n:]

    if B_offdiag_fixed is not None:
        B_opt = B_offdiag_fixed.copy()
        np.fill_diagonal(B_opt, B_diag_opt)
    else:
        B_opt = offdiag_formula42_consistent(B_diag_opt, theta_opt, Y_base)

    return theta_opt, B_diag_opt, B_opt, result.cost


# ══════════════════════════════════════════════
# ГЕНЕРАЦИЯ СИНТЕТИЧЕСКИХ ПЕРИОДОВ
# ══════════════════════════════════════════════

def generate_periods(A, B_true, theta_true, n_periods, noise_std=0.15, seed=42):
    rng = np.random.RandomState(seed)
    n = B_true.shape[0]
    periods = []
    for _ in range(n_periods * 3):  # generate more, filter valid
        shock = np.clip(rng.normal(1.0, noise_std, n), 0.5, 2.0)
        theta_k = theta_true * shock
        try:
            P_k = eq_prices_closed(A, B_true, theta_k)
            Q_k = model_Q(B_true, P_k, theta_k)
            X_k = model_output(A, B_true, P_k, theta_k)
            if np.all(P_k > 0) and np.all(Q_k > 0) and np.all(X_k > 0):
                periods.append({'theta': theta_k, 'P': P_k, 'Q': Q_k, 'X': X_k})
                if len(periods) >= n_periods:
                    break
        except Exception:
            continue
    return periods


# ══════════════════════════════════════════════
# ЭТАП A: РЕГРЕССИЯ НЕДИАГОНАЛЬНЫХ (по строкам B)
# ══════════════════════════════════════════════

def estimate_B_regression(periods, n, B_prior=None, lambda_reg=0.1,
                          enforce_diag_sign=True):
    """
    Для каждой отрасли i: q_i(t) - θ_i(t) = Σ_j b_ij P_j(t)
    Ridge regression с prior от B_prior.
    """
    K = len(periods)
    B_est = np.zeros((n, n))

    for i in range(n):
        y = np.array([p['Q'][i] - p['theta'][i] for p in periods])
        X_reg = np.array([p['P'] for p in periods])

        if B_prior is not None:
            bp = B_prior[i, :]
        else:
            bp = np.zeros(n)

        XtX = X_reg.T @ X_reg
        Xty = X_reg.T @ y

        B_est[i, :] = np.linalg.solve(
            XtX + lambda_reg * np.eye(n),
            Xty + lambda_reg * bp
        )

        if enforce_diag_sign and B_est[i, i] >= 0:
            B_est[i, i] = bp[i] if bp[i] < 0 else -1.0

    return B_est


def estimate_B_ols(periods, n):
    """Простой OLS без регуляризации: q - θ = B·P."""
    K = len(periods)
    Y_mat = np.array([p['Q'] - p['theta'] for p in periods])  # K x n
    X_mat = np.array([p['P'] for p in periods])  # K x n
    # Y = X @ B^T => B^T = (X^T X)^{-1} X^T Y
    Bt = np.linalg.lstsq(X_mat, Y_mat, rcond=None)[0]
    return Bt.T


# ══════════════════════════════════════════════
# ЭТАП B: РЕКАЛИБРОВКА diag(B)+θ ПРИ ФИКСИРОВАННЫХ НЕДИАГОНАЛЬНЫХ
# ══════════════════════════════════════════════

def recalibrate_with_fixed_offdiag(A, X_base, Y_base, B_offdiag):
    """
    Зафиксировать недиагональные элементы B_offdiag,
    найти diag(B) и θ для P*=1, X=X_base.
    """
    return calibrate_diag_theta(A, X_base, Y_base, B_offdiag_fixed=B_offdiag)


# ══════════════════════════════════════════════
# ПОЛНЫЙ 2-ШАГОВЫЙ ИТЕРАТИВНЫЙ АЛГОРИТМ
# ══════════════════════════════════════════════

def calibrate_full_iterative(A, X_base, Y_base, periods,
                              n_outer=10, lambda_start=0.1,
                              lambda_decay=0.7, verbose=True):
    """
    Итеративный алгоритм:
      1) Базовая калибровка с формулой (4.2) → B_0, θ_0
      2) Повторять:
         a) Оценить B из временных данных (regression с prior=B_current)
         b) Зафиксировать недиагональные B, рекалибровать diag(B)+θ
         c) Проверить сходимость
    """
    n = A.shape[0]

    # Шаг 0: Базовая калибровка
    if verbose:
        print("── Шаг 0: Базовая калибровка (формула 4.2) ──")
    theta, B_diag, B, cost = calibrate_diag_theta(A, X_base, Y_base)
    if verbose:
        P_check = eq_prices_closed(A, B, theta)
        X_check = model_output(A, B, P_check, theta)
        print(f"   P*={P_check}, max|P*-1|={np.max(np.abs(P_check-1)):.2e}")
        print(f"   X_err={np.max(np.abs((X_check-X_base)/X_base)):.2e}")
        print(f"   θ={theta}")
        print(f"   diag(B)={np.diag(B)}")

    lam = lambda_start
    history = [{'B': B.copy(), 'theta': theta.copy(), 'iter': 0}]

    for outer in range(1, n_outer + 1):
        if verbose:
            print(f"\n── Итерация {outer} (λ={lam:.4f}) ──")

        # Шаг A: Оценить B из временных данных
        B_reg = estimate_B_regression(periods, n, B_prior=B, lambda_reg=lam)

        # Шаг B: Зафиксировать недиагональные, рекалибровать
        B_offdiag = B_reg.copy()
        theta_new, B_diag_new, B_new, cost_new = recalibrate_with_fixed_offdiag(
            A, X_base, Y_base, B_offdiag)

        P_check = eq_prices_closed(A, B_new, theta_new)
        X_check = model_output(A, B_new, P_check, theta_new)
        Q_check = model_Q(B_new, P_check, theta_new)

        err_P = np.max(np.abs(P_check - 1.0))
        err_X = np.max(np.abs((X_check - X_base) / X_base))

        # Ошибка предсказания на периодах
        pred_errs = []
        for per in periods:
            Q_pred = model_Q(B_new, per['P'], per['theta'])
            pred_errs.append(np.mean(np.abs((Q_pred - per['Q']) / per['Q'])))
        mean_pred = np.mean(pred_errs) * 100

        if verbose:
            print(f"   max|P*-1|={err_P:.2e}, max|X_err|={err_X:.2e}, "
                  f"Q_pred_err={mean_pred:.3f}%")
            print(f"   diag(B)={np.diag(B_new)}")

        if err_P > 0.05 or err_X > 0.05:
            if verbose:
                print(f"   ⚠ Базовое состояние нарушено, отбрасываем эту итерацию")
            lam *= 2  # усиливаем регуляризацию
            continue

        B = B_new.copy()
        theta = theta_new.copy()
        history.append({'B': B.copy(), 'theta': theta.copy(), 'iter': outer,
                        'err_P': err_P, 'err_X': err_X, 'pred_err': mean_pred})

        # Уменьшаем регуляризацию
        lam *= lambda_decay

        # Сходимость
        if outer >= 2 and len(history) >= 3:
            diff = norm(history[-1]['B'] - history[-2]['B'])
            if diff < 1e-10:
                if verbose:
                    print(f"   ✓ Сходимость достигнута (diff={diff:.2e})")
                break

    return B, theta, history


# ══════════════════════════════════════════════
# ПОЛНЫЙ 2-ШАГОВЫЙ: ВЕРСИЯ С OLS + РЕКАЛИБРОВКОЙ
# ══════════════════════════════════════════════

def calibrate_ols_then_recalib(A, X_base, Y_base, periods, verbose=True):
    """
    Простейший 2-шаговый:
      1) OLS: B_ols из всех периодов (q - θ = B·P)
      2) Зафиксировать недиагональные B_ols, рекалибровать diag+θ
    """
    n = A.shape[0]

    if verbose:
        print("── OLS оценка B ──")
    B_ols = estimate_B_ols(periods, n)
    if verbose:
        print(f"   B_ols:\n{B_ols}")

    if verbose:
        print("── Рекалибровка diag(B) + θ ──")
    theta, B_diag, B_final, cost = recalibrate_with_fixed_offdiag(
        A, X_base, Y_base, B_ols)

    P_check = eq_prices_closed(A, B_final, theta)
    X_check = model_output(A, B_final, P_check, theta)

    if verbose:
        print(f"   P*={P_check}")
        print(f"   max|P*-1|={np.max(np.abs(P_check-1)):.2e}")
        print(f"   max|X_err|={np.max(np.abs((X_check-X_base)/X_base)):.2e}")

    return B_final, theta


# ══════════════════════════════════════════════
# ГЛАВНЫЙ ЭКСПЕРИМЕНТ
# ══════════════════════════════════════════════

def main():
    print("=" * 80)
    print("КАЛИБРОВКА НЕДИАГОНАЛЬНЫХ ЭЛЕМЕНТОВ МАТРИЦЫ B: ВЕРСИЯ 2")
    print("=" * 80)

    # ─── Данные из статьи ───
    M1 = np.array([[20, 30, 10],
                    [40, 80, 20],
                    [15, 25, 30]], dtype=float)
    Y_base = np.array([40, 70, 35], dtype=float)
    X_base = np.array([100, 210, 105], dtype=float)
    n = 3

    A = np.zeros((n, n))
    for j in range(n):
        A[:, j] = M1[:, j] / X_base[j]
    print(f"\nA =\n{A}")

    # ─── Шаг 0: Базовая калибровка ───
    print("\n" + "=" * 80)
    print("БАЗОВАЯ КАЛИБРОВКА (формула 4.2)")
    print("=" * 80)

    theta_base, B_diag_base, B_base, _ = calibrate_diag_theta(A, X_base, Y_base)
    P_base = eq_prices_closed(A, B_base, theta_base)
    print(f"θ = {theta_base}")
    print(f"diag(B) = {np.diag(B_base)}")
    print(f"P* = {P_base}")
    print(f"B_base =\n{B_base}")

    # ─── Создаём "истинную" B ───
    print("\n" + "=" * 80)
    print("СОЗДАНИЕ ИСТИННОЙ B (с отклонениями от 4.2)")
    print("=" * 80)

    # Возьмём B_base и добавим осмысленные отклонения
    B_true = B_base.copy()
    # С↔П: усилим субституцию (увеличим перекрёстный положительный эффект)
    B_true[0, 1] += 8   # спрос на С растёт при росте цены П
    B_true[1, 0] -= 8   # спрос на П падает при росте цены С (комплементарность)
    # П↔У: усилим комплементарность
    B_true[1, 2] += 5
    B_true[2, 1] -= 5
    # С↔У: слабый эффект
    B_true[0, 2] -= 2
    B_true[2, 0] += 2

    print(f"B_true =\n{B_true}")
    print(f"B_true - B_base =\n{B_true - B_base}")

    # Пересчитаем θ_true для P*=1
    I = np.eye(n)
    IAt = I - A.T
    S = leontief_inv(A)
    M_mat = B_true + (I - A) @ inv(np.diag(np.diag(IAt))) @ np.diag(np.diag(S @ B_true)) @ IAt
    theta_true = -M_mat @ np.ones(n)

    P_true = eq_prices_closed(A, B_true, theta_true)
    X_true = model_output(A, B_true, P_true, theta_true)
    Q_true = model_Q(B_true, P_true, theta_true)

    print(f"\nθ_true = {theta_true}")
    print(f"P*_true = {P_true}")
    print(f"X_true = {X_true}")
    print(f"Q_true = {Q_true}")

    Y_true = Q_true.copy()  # при P=1
    X_true_base = X_true.copy()

    # ─── Генерация синтетических периодов ───
    print("\n" + "=" * 80)
    print("ГЕНЕРАЦИЯ СИНТЕТИЧЕСКИХ ДАННЫХ")
    print("=" * 80)

    for n_per in [10, 20, 50, 100, 200]:
        periods = generate_periods(A, B_true, theta_true, n_per,
                                    noise_std=0.20, seed=42)
        print(f"  {n_per} запрошено → {len(periods)} сгенерировано")

    # ─── ЭКСПЕРИМЕНТ: Разные количества периодов ───
    print("\n" + "=" * 80)
    print("ЭКСПЕРИМЕНТ: ВЛИЯНИЕ ЧИСЛА ПЕРИОДОВ И МЕТОДА")
    print("=" * 80)

    results_table = []

    for n_per in [5, 10, 20, 50, 100]:
        periods = generate_periods(A, B_true, theta_true, n_per,
                                    noise_std=0.20, seed=42)
        if len(periods) < 3:
            continue

        print(f"\n{'─'*60}")
        print(f"ПЕРИОДОВ: {len(periods)}")
        print(f"{'─'*60}")

        # Метод 0: Только формула (4.2)
        theta_42, _, B_42, _ = calibrate_diag_theta(A, X_true_base, Y_true)
        err_42 = norm(B_42 - B_true, 'fro')
        P_42 = eq_prices_closed(A, B_42, theta_42)
        pred_42 = np.mean([np.mean(np.abs((model_Q(B_42, p['P'], p['theta']) - p['Q']) / p['Q']))
                           for p in periods]) * 100

        print(f"  [Формула 4.2]  ||B-B_true||={err_42:.4f}  max|P*-1|={np.max(np.abs(P_42-1)):.2e}  "
              f"Q_err={pred_42:.2f}%")

        # Метод 1: OLS + рекалибровка
        B_ols = estimate_B_ols(periods, n)
        theta_ols, _, B_ols_recal, _ = recalibrate_with_fixed_offdiag(
            A, X_true_base, Y_true, B_ols)
        err_ols = norm(B_ols_recal - B_true, 'fro')
        P_ols = eq_prices_closed(A, B_ols_recal, theta_ols)
        pred_ols = np.mean([np.mean(np.abs((model_Q(B_ols_recal, p['P'], p['theta']) - p['Q']) / p['Q']))
                            for p in periods]) * 100

        print(f"  [OLS+recalib]  ||B-B_true||={err_ols:.4f}  max|P*-1|={np.max(np.abs(P_ols-1)):.2e}  "
              f"Q_err={pred_ols:.2f}%")

        # Метод 2: Ridge (разные λ) + рекалибровка
        best_ridge = None
        for lam in [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]:
            B_ridge = estimate_B_regression(periods, n, B_prior=B_42, lambda_reg=lam)
            theta_r, _, B_r, _ = recalibrate_with_fixed_offdiag(
                A, X_true_base, Y_true, B_ridge)
            try:
                P_r = eq_prices_closed(A, B_r, theta_r)
                if np.any(np.isnan(P_r)) or np.max(np.abs(P_r - 1)) > 0.01:
                    continue
                err_r = norm(B_r - B_true, 'fro')
                if best_ridge is None or err_r < best_ridge[0]:
                    best_ridge = (err_r, lam, B_r, theta_r, P_r)
            except Exception:
                continue

        if best_ridge:
            err_r, lam_r, B_r, theta_r, P_r = best_ridge
            pred_r = np.mean([np.mean(np.abs((model_Q(B_r, p['P'], p['theta']) - p['Q']) / p['Q']))
                              for p in periods]) * 100
            print(f"  [Ridge+recal]  ||B-B_true||={err_r:.4f}  λ={lam_r}  "
                  f"max|P*-1|={np.max(np.abs(P_r-1)):.2e}  Q_err={pred_r:.2f}%")

        # Метод 3: Итеративный
        B_iter, theta_iter, hist = calibrate_full_iterative(
            A, X_true_base, Y_true, periods,
            n_outer=15, lambda_start=0.05, lambda_decay=0.6,
            verbose=False)
        err_iter = norm(B_iter - B_true, 'fro')
        P_iter = eq_prices_closed(A, B_iter, theta_iter)
        pred_iter = np.mean([np.mean(np.abs((model_Q(B_iter, p['P'], p['theta']) - p['Q']) / p['Q']))
                             for p in periods]) * 100

        print(f"  [Iterative]    ||B-B_true||={err_iter:.4f}  max|P*-1|={np.max(np.abs(P_iter-1)):.2e}  "
              f"Q_err={pred_iter:.2f}%")

        results_table.append({
            'n_per': len(periods),
            'err_42': err_42,
            'err_ols': err_ols,
            'err_ridge': best_ridge[0] if best_ridge else np.nan,
            'err_iter': err_iter
        })

    # ─── Итоговая таблица ───
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ ТАБЛИЦА: ||B_est - B_true||_F")
    print("=" * 80)
    print(f"{'Периоды':>8} {'4.2':>10} {'OLS+recal':>10} {'Ridge+rec':>10} {'Iterative':>10}")
    for r in results_table:
        print(f"{r['n_per']:>8d} {r['err_42']:>10.4f} {r['err_ols']:>10.4f} "
              f"{r['err_ridge']:>10.4f} {r['err_iter']:>10.4f}")

    # ─── Детальный вывод лучшего результата ───
    print("\n" + "=" * 80)
    print("ДЕТАЛЬНЫЙ АНАЛИЗ ЛУЧШЕГО РЕЗУЛЬТАТА (100 периодов, итеративный)")
    print("=" * 80)

    periods_100 = generate_periods(A, B_true, theta_true, 100,
                                    noise_std=0.20, seed=42)
    B_best, theta_best, hist_best = calibrate_full_iterative(
        A, X_true_base, Y_true, periods_100,
        n_outer=20, lambda_start=0.05, lambda_decay=0.5,
        verbose=True)

    P_best = eq_prices_closed(A, B_best, theta_best)
    X_best = model_output(A, B_best, P_best, theta_best)
    Q_best = model_Q(B_best, P_best, theta_best)

    print(f"\nB_true =\n{B_true}")
    print(f"B_best =\n{B_best}")
    print(f"B_best - B_true =\n{B_best - B_true}")
    print(f"||B_best - B_true||_F = {norm(B_best - B_true, 'fro'):.6f}")

    print(f"\nθ_true = {theta_true}")
    print(f"θ_best = {theta_best}")
    print(f"P* = {P_best}")
    print(f"X = {X_best} (target: {X_true_base})")
    print(f"Q = {Q_best} (target: {Y_true})")

    eig_best = eigvals(B_best)
    print(f"\nСобственные значения B_best: {eig_best.real}")
    sym_err = np.max(np.abs(B_best - B_best.T))
    print(f"Асимметрия B: {sym_err:.4f}")

    # ─── Out-of-sample тест ───
    print("\n" + "=" * 80)
    print("OUT-OF-SAMPLE ТЕСТ")
    print("=" * 80)

    periods_oos = generate_periods(A, B_true, theta_true, 50,
                                    noise_std=0.25, seed=999)
    print(f"Тестовых периодов: {len(periods_oos)}")

    methods = {
        'Формула 4.2': (B_42, theta_42),
        'Лучший (итеративный)': (B_best, theta_best),
    }

    for name, (B_m, th_m) in methods.items():
        Q_errors = []
        X_errors = []
        for per in periods_oos:
            Q_pred = model_Q(B_m, per['P'], per['theta'])
            Q_errors.append(np.mean(np.abs((Q_pred - per['Q']) / per['Q'])))
            X_pred = model_output(A, B_m, per['P'], per['theta'])
            X_errors.append(np.mean(np.abs((X_pred - per['X']) / per['X'])))

        print(f"\n  {name}:")
        print(f"    Ср. ошибка Q: {np.mean(Q_errors)*100:.3f}% "
              f"(макс: {np.max(Q_errors)*100:.3f}%)")
        print(f"    Ср. ошибка X: {np.mean(X_errors)*100:.3f}% "
              f"(макс: {np.max(X_errors)*100:.3f}%)")

    # ─── Тест устойчивости: разные seed ───
    print("\n" + "=" * 80)
    print("ТЕСТ УСТОЙЧИВОСТИ: РАЗНЫЕ SEED")
    print("=" * 80)

    for seed in [1, 42, 100, 777, 2024]:
        per_s = generate_periods(A, B_true, theta_true, 50,
                                  noise_std=0.20, seed=seed)
        if len(per_s) < 10:
            continue
        B_s, th_s, _ = calibrate_full_iterative(
            A, X_true_base, Y_true, per_s,
            n_outer=15, lambda_start=0.05, lambda_decay=0.5,
            verbose=False)
        err_s = norm(B_s - B_true, 'fro')
        P_s = eq_prices_closed(A, B_s, th_s)
        print(f"  seed={seed:>4d}: ||B-B_true||={err_s:.4f}  max|P*-1|={np.max(np.abs(P_s-1)):.2e}")


if __name__ == "__main__":
    main()
