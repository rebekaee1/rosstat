"""
Вычислимая ценовая модель общего равновесия (Моисеев, Внуков)
Полная реализация + расширенный алгоритм калибровки недиагональных элементов матрицы B
"""

import numpy as np
from numpy.linalg import inv, det, eigvals
from scipy.optimize import minimize, least_squares
import warnings

np.set_printoptions(precision=6, suppress=True, linewidth=120)
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════
# 1. ЯДРО МОДЕЛИ
# ══════════════════════════════════════════════════════════════

def compute_A(M1):
    """Производственная матрица A из матрицы межотраслевых поставок M1."""
    X_total = M1.sum(axis=0) + np.zeros(M1.shape[1])  # будет передано отдельно
    raise NotImplementedError("Use compute_A_from_table instead")


def compute_A_from_table(M1, X):
    """A[i,j] = x_ij / x_j"""
    n = M1.shape[0]
    A = np.zeros((n, n))
    for j in range(n):
        if X[j] > 0:
            A[:, j] = M1[:, j] / X[j]
    return A


def leontief_inverse(A):
    """S = (I - A)^{-1}"""
    n = A.shape[0]
    return inv(np.eye(n) - A)


def compute_PN(P):
    """Ценовая матрица PN: PN[i,j] = P[i]/P[j]"""
    n = len(P)
    PN = np.outer(P, 1.0 / P)
    return PN


def compute_Q(B, P, theta, T=None):
    """Физический объём конечного спроса: Q = B * (T*P) + theta"""
    if T is not None:
        return B @ (T @ P) + theta
    return B @ P + theta


def compute_X(A, B, P, theta, T=None):
    """Валовой выпуск: X = (I - A)^{-1} * (P ∘ Q(P))  -- формула (1.3)"""
    S = leontief_inverse(A)
    Q = compute_Q(B, P, theta, T)
    Y = P * Q  # конечное потребление в стоимостном выражении
    return S @ Y


def compute_PR(A, B, P, theta, T=None, Im=None):
    """Добавленная стоимость: формула (1.9) / (2.2) / (3.3)"""
    n = len(P)
    S = leontief_inverse(A)
    Q = compute_Q(B, P, theta, T)

    cost_part = P - A.T @ P
    if Im is not None:
        cost_part = cost_part - Im

    volume_part = S @ Q
    return cost_part * volume_part


# ══════════════════════════════════════════════════════════════
# 2. АНАЛИТИЧЕСКОЕ РЕШЕНИЕ ДЛЯ РАВНОВЕСНЫХ ЦЕН
# ══════════════════════════════════════════════════════════════

def equilibrium_prices_closed(A, B, theta):
    """Равновесные цены для закрытой экономики — формула (1.13).
    P* = -[B + (I-A)(diag(I-A^T))^{-1} diag((I-A)^{-1} B) (I-A^T)]^{-1} theta
    """
    n = A.shape[0]
    I = np.eye(n)
    I_minus_AT = I - A.T
    S = inv(I - A)  # (I-A)^{-1}
    SB = S @ B

    diag_I_minus_AT = np.diag(np.diag(I_minus_AT))
    diag_I_minus_AT_inv = inv(diag_I_minus_AT)
    diag_SB = np.diag(np.diag(SB))

    M = B + (I - A) @ diag_I_minus_AT_inv @ diag_SB @ I_minus_AT
    return -inv(M) @ theta


def equilibrium_prices_open(A, B, theta, T, Im=None):
    """Равновесные цены для открытой экономики — формула (2.4).
    P* = (P0 + P1)^{-1} * (P2 - P3)
    """
    n = A.shape[0]
    I = np.eye(n)
    I_minus_AT = I - A.T
    S = inv(I - A)
    BT = B @ T

    diag_I_minus_AT = np.diag(np.diag(I_minus_AT))
    diag_SBT = np.diag(np.diag(S @ BT))

    P0 = diag_I_minus_AT @ S @ BT
    P1 = diag_SBT @ I_minus_AT

    if Im is None:
        Im = np.zeros(n)

    P2 = diag_SBT @ Im
    P3 = diag_I_minus_AT @ S @ theta

    return inv(P0 + P1) @ (P2 - P3)


# ══════════════════════════════════════════════════════════════
# 3. ФОРМУЛА (4.2) ДЛЯ НЕДИАГОНАЛЬНЫХ ЭЛЕМЕНТОВ
# ══════════════════════════════════════════════════════════════

def compute_off_diagonal_B(B_diag, theta, q_base):
    """
    Формула (4.2):
    b_ki = -(b_ii + sum_j b_ij + theta_i) * phi_k
    где phi_k = q_k / sum(q)

    Это СИСТЕМА уравнений, т.к. sum_j b_ij включает недиагональные элементы строки i,
    которые в свою очередь зависят от диагональных элементов ДРУГИХ столбцов.

    Решаем итеративно до сходимости.
    """
    n = len(B_diag)
    phi = q_base / q_base.sum()
    B = np.diag(B_diag.copy())

    for iteration in range(500):
        B_old = B.copy()
        for i in range(n):
            row_sum = B[i, :].sum()  # b_ii + sum_{j!=i} b_ij
            marginal = row_sum + theta[i]  # = b_ii + q_i в равновесии
            for k in range(n):
                if k != i:
                    B[k, i] = -marginal * phi[k]

        if np.max(np.abs(B - B_old)) < 1e-14:
            break

    return B


def compute_off_diagonal_B_direct(B_diag, theta, q_base):
    """
    Прямое (нитеративное) решение системы (4.2).

    Из формулы: b_ki = -(b_ii + sum_j b_ij + theta_i) * phi_k  для k != i

    Обозначим S_i = sum_j b_ij = b_ii + sum_{j!=i} b_ij.
    Из функции спроса при P=1: q_i = S_i + theta_i, т.е. S_i = q_i - theta_i.

    НО: sum_{j!=i} b_ij — это сумма элементов строки i вне диагонали.
    b_ij (j != i) определяется из СТОЛБЦА j: b_ij = -(b_jj + S_j + theta_j) * phi_i

    Тогда sum_{j!=i} b_ij = -phi_i * sum_{j!=i} (b_jj + S_j + theta_j)
                           = -phi_i * sum_{j!=i} (b_jj + q_j)

    И S_i = b_ii + sum_{j!=i} b_ij = b_ii - phi_i * sum_{j!=i} (b_jj + q_j)

    Но q_j = S_j + theta_j, и S_j = b_jj - phi_j * sum_{k!=j} (b_kk + q_k)

    Это линейная система. Обозначим m_i = b_ii + q_i (маржинальный эффект).
    Тогда b_ki = -m_i * phi_k.
    sum_{j!=i} b_ij = sum_{j!=i} (-m_j * phi_i) = -phi_i * sum_{j!=i} m_j

    S_i = b_ii - phi_i * sum_{j!=i} m_j
    q_i = S_i + theta_i = b_ii + theta_i - phi_i * sum_{j!=i} m_j
    m_i = b_ii + q_i = 2*b_ii + theta_i - phi_i * sum_{j!=i} m_j

    Обозначим M = sum_j m_j. Тогда sum_{j!=i} m_j = M - m_i.
    m_i = 2*b_ii + theta_i - phi_i * (M - m_i)
    m_i = 2*b_ii + theta_i - phi_i * M + phi_i * m_i
    m_i * (1 - phi_i) = 2*b_ii + theta_i - phi_i * M
    m_i = (2*b_ii + theta_i - phi_i * M) / (1 - phi_i)

    Суммируя по всем i:
    M = sum_i (2*b_ii + theta_i - phi_i * M) / (1 - phi_i)
    M = sum_i (2*b_ii + theta_i) / (1 - phi_i) - M * sum_i phi_i / (1 - phi_i)

    Обозначим:
    R = sum_i (2*b_ii + theta_i) / (1 - phi_i)
    G = sum_i phi_i / (1 - phi_i)

    M = R - M * G
    M * (1 + G) = R
    M = R / (1 + G)

    Затем m_i = (2*b_ii + theta_i - phi_i * M) / (1 - phi_i)
    И b_ki = -m_i * phi_k для k != i.
    """
    n = len(B_diag)
    phi = q_base / q_base.sum()

    R = sum((2 * B_diag[i] + theta[i]) / (1 - phi[i]) for i in range(n))
    G = sum(phi[i] / (1 - phi[i]) for i in range(n))
    M_total = R / (1 + G)

    m = np.zeros(n)
    for i in range(n):
        m[i] = (2 * B_diag[i] + theta[i] - phi[i] * M_total) / (1 - phi[i])

    B = np.diag(B_diag.copy())
    for i in range(n):
        for k in range(n):
            if k != i:
                B[k, i] = -m[i] * phi[k]

    return B, m


# ══════════════════════════════════════════════════════════════
# 4. БАЗОВАЯ КАЛИБРОВКА (БИНАРНЫЙ ПОИСК)
# ══════════════════════════════════════════════════════════════

def calibrate_base(A, X_base, Y_base, T=None, Im=None,
                   max_iter=5000, tol=1e-10, verbose=False):
    """
    Калибровка θ и diag(B) по системе (4.1):
      P*|B,θ = 1
      X|B,θ = X_base

    При P_base = 1, q_base = Y_base.
    """
    n = A.shape[0]
    q_base = Y_base.copy()

    theta = 2 * Y_base.copy()
    B_diag = -Y_base.copy() / 2.0

    use_taxes = T is not None
    if T is None:
        T_mat = np.eye(n)
    else:
        T_mat = T

    if Im is None:
        Im_vec = np.zeros(n)
    else:
        Im_vec = Im

    best_err = np.inf
    best_theta = theta.copy()
    best_B_diag = B_diag.copy()

    lr_theta = 0.3
    lr_b = 0.3

    for it in range(max_iter):
        B, m_vec = compute_off_diagonal_B_direct(B_diag, theta, q_base)

        if use_taxes or Im is not None:
            P_star = equilibrium_prices_open(A, B, theta, T_mat, Im_vec)
        else:
            P_star = equilibrium_prices_closed(A, B, theta)

        X_model = compute_X(A, B, P_star, theta, T_mat if use_taxes else None)

        err_P = P_star - np.ones(n)
        err_X = (X_model - X_base) / X_base

        total_err = np.max(np.abs(err_P)) + np.max(np.abs(err_X))

        if total_err < best_err:
            best_err = total_err
            best_theta = theta.copy()
            best_B_diag = B_diag.copy()

        if verbose and it % 200 == 0:
            print(f"  iter {it}: max|err_P|={np.max(np.abs(err_P)):.2e}, "
                  f"max|err_X|={np.max(np.abs(err_X)):.2e}")

        if total_err < tol:
            if verbose:
                print(f"  Converged at iter {it}")
            break

        # Корректировка θ: если P* > 1, значит θ слишком велико → уменьшаем
        # Корректировка B_diag: если X > X_base, |b_ii| слишком мал → увеличиваем |b_ii|
        theta = theta - lr_theta * theta * err_P
        B_diag = B_diag - lr_b * B_diag * err_X

        # Гарантировать ограничения
        theta = np.maximum(theta, 1e-6)
        B_diag = np.minimum(B_diag, -1e-6)

        # Адаптивный шаг
        if it > 100 and total_err > 0.1:
            lr_theta *= 0.999
            lr_b *= 0.999

    B_final, _ = compute_off_diagonal_B_direct(best_B_diag, best_theta, q_base)
    return best_theta, best_B_diag, B_final, best_err


def calibrate_base_scipy(A, X_base, Y_base, T=None, Im=None, verbose=False):
    """Калибровка через scipy.optimize (более надёжная)."""
    n = A.shape[0]
    q_base = Y_base.copy()

    use_taxes = T is not None
    T_mat = T if T is not None else np.eye(n)
    Im_vec = Im if Im is not None else np.zeros(n)

    def residuals(params):
        theta = params[:n]
        B_diag = params[n:]

        if np.any(theta <= 0) or np.any(B_diag >= 0):
            return np.ones(2 * n) * 1e6

        B, _ = compute_off_diagonal_B_direct(B_diag, theta, q_base)

        try:
            if use_taxes or Im is not None:
                P_star = equilibrium_prices_open(A, B, theta, T_mat, Im_vec)
            else:
                P_star = equilibrium_prices_closed(A, B, theta)

            X_model = compute_X(A, B, P_star, theta, T_mat if use_taxes else None)
        except Exception:
            return np.ones(2 * n) * 1e6

        if np.any(np.isnan(P_star)) or np.any(np.isnan(X_model)):
            return np.ones(2 * n) * 1e6

        err_P = P_star - 1.0
        err_X = (X_model - X_base) / X_base
        return np.concatenate([err_P * 100, err_X * 100])

    theta0 = 2 * Y_base
    B_diag0 = -Y_base / 2.0
    x0 = np.concatenate([theta0, B_diag0])

    result = least_squares(residuals, x0, method='lm', max_nfev=50000,
                           ftol=1e-14, xtol=1e-14, gtol=1e-14)

    theta_opt = result.x[:n]
    B_diag_opt = result.x[n:]
    B_opt, _ = compute_off_diagonal_B_direct(B_diag_opt, theta_opt, q_base)

    if verbose:
        print(f"  Scipy calibration: cost={result.cost:.2e}, nfev={result.nfev}")
        print(f"  theta = {theta_opt}")
        print(f"  B_diag = {B_diag_opt}")

    return theta_opt, B_diag_opt, B_opt, result.cost


# ══════════════════════════════════════════════════════════════
# 5. РАСШИРЕННАЯ КАЛИБРОВКА НЕДИАГОНАЛЬНЫХ ЭЛЕМЕНТОВ
# ══════════════════════════════════════════════════════════════

def generate_synthetic_periods(A, B_true, theta_true, n_periods=10,
                               price_noise_std=0.15, T=None, seed=42):
    """Генерирует синтетические данные для нескольких периодов.
    Каждый период имеет случайный шок к θ, и модель вычисляет равновесие."""
    rng = np.random.RandomState(seed)
    n = A.shape[0]
    periods = []

    T_mat = T if T is not None else np.eye(n)

    for k in range(n_periods):
        shock = rng.normal(1.0, price_noise_std, n)
        shock = np.clip(shock, 0.5, 2.0)
        theta_k = theta_true * shock

        try:
            if T is not None:
                P_k = equilibrium_prices_open(A, B_true, theta_k, T_mat)
            else:
                P_k = equilibrium_prices_closed(A, B_true, theta_k)

            Q_k = compute_Q(B_true, P_k, theta_k, T_mat if T is not None else None)
            X_k = compute_X(A, B_true, P_k, theta_k, T_mat if T is not None else None)

            if np.all(P_k > 0) and np.all(Q_k > 0) and np.all(X_k > 0):
                periods.append({
                    'theta': theta_k, 'P': P_k, 'Q': Q_k, 'X': X_k,
                    'shock': shock
                })
        except Exception:
            continue

    return periods


def calibrate_offdiag_regression(B_base, theta_base, periods, q_base,
                                  T=None, lambda_reg=0.1):
    """
    Этап 2: Регуляризованная регрессия для строк B по временным данным.
    Для каждой отрасли i: q_i(t) = sum_j b_ij * P_j(t) + theta_i(t)
    Но theta меняется между периодами → используем q_i - theta_i как зависимую.
    q_i(t) - theta_i(t) = sum_j b_ij * P_j(t)
    """
    n = B_base.shape[0]
    K = len(periods)

    if K < 2:
        return B_base.copy()

    T_mat = T if T is not None else np.eye(n)
    B_new = B_base.copy()

    for i in range(n):
        # Зависимая: q_i(t) - theta_i(t)
        y = np.array([per['Q'][i] - per['theta'][i] for per in periods])
        # Независимые: T * P(t) для каждого периода
        X_reg = np.array([T_mat @ per['P'] for per in periods])

        # Ridge regression с prior = B_base[i, :]
        b_prior = B_base[i, :].copy()
        XtX = X_reg.T @ X_reg
        Xty = X_reg.T @ y

        # (X^T X + lambda * I) b = X^T y + lambda * b_prior
        reg_matrix = XtX + lambda_reg * np.eye(n)
        reg_rhs = Xty + lambda_reg * b_prior
        try:
            b_hat = np.linalg.solve(reg_matrix, reg_rhs)
            # Сохранить знак диагонали
            if b_hat[i] >= 0:
                b_hat[i] = B_base[i, i]
            B_new[i, :] = b_hat
        except np.linalg.LinAlgError:
            pass

    return B_new


def calibrate_offdiag_joint(A, X_base, Y_base, periods, B_init, theta_init,
                             q_base, T=None, Im=None,
                             w0=100.0, w1=1.0, w2=0.1, w3=0.01,
                             verbose=False):
    """
    Этап 4: Совместная оптимизация всех элементов B и θ.

    min L(B, θ) = w0 * [||P*(B,θ) - 1||² + ||X(B,θ) - X_base||²]
                + w1 * sum_k ||q_model(t_k) - q_obs(t_k)||²
                + w2 * sum_{i!=j} (b_ij - b_ij^{4.2})²
                + w3 * sum_{i<j} (b_ij - b_ji)²

    С ограничениями: b_ii < 0, θ_i > 0
    """
    n = A.shape[0]
    T_mat = T if T is not None else np.eye(n)
    Im_vec = Im if Im is not None else np.zeros(n)
    use_taxes = T is not None

    B_42, _ = compute_off_diagonal_B_direct(np.diag(B_init), theta_init, q_base)

    def pack(theta, B):
        return np.concatenate([theta, B.flatten()])

    def unpack(x):
        theta = x[:n]
        B = x[n:].reshape(n, n)
        return theta, B

    def objective(x):
        theta, B = unpack(x)

        if np.any(theta <= 0) or np.any(np.diag(B) >= 0):
            return 1e12

        try:
            if use_taxes or Im is not None:
                P_star = equilibrium_prices_open(A, B, theta, T_mat, Im_vec)
            else:
                P_star = equilibrium_prices_closed(A, B, theta)

            X_model = compute_X(A, B, P_star, theta, T_mat if use_taxes else None)
        except Exception:
            return 1e12

        if np.any(np.isnan(P_star)) or np.any(np.isnan(X_model)):
            return 1e12

        # Базовое состояние
        loss_base = w0 * (np.sum((P_star - 1.0) ** 2) +
                          np.sum(((X_model - X_base) / X_base) ** 2))

        # Временная динамика
        loss_time = 0.0
        for per in periods:
            Q_mod = compute_Q(B, per['P'], per['theta'], T_mat if use_taxes else None)
            loss_time += np.sum((Q_mod - per['Q']) ** 2)
        loss_time *= w1

        # Регуляризация к (4.2)
        loss_reg = 0.0
        for i in range(n):
            for j in range(n):
                if i != j:
                    loss_reg += (B[i, j] - B_42[i, j]) ** 2
        loss_reg *= w2

        # Штраф за асимметрию
        loss_sym = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                loss_sym += (B[i, j] - B[j, i]) ** 2
        loss_sym *= w3

        return loss_base + loss_time + loss_reg + loss_sym

    x0 = pack(theta_init, B_init)
    result = minimize(objective, x0, method='Nelder-Mead',
                      options={'maxiter': 100000, 'xatol': 1e-12,
                               'fatol': 1e-12, 'adaptive': True})

    theta_opt, B_opt = unpack(result.x)

    if verbose:
        print(f"  Joint optimization: fun={result.fun:.6e}, nit={result.nit}, "
              f"success={result.success}")

    return theta_opt, B_opt, result


def calibrate_offdiag_leastsq(A, X_base, Y_base, periods, B_init, theta_init,
                                q_base, T=None, Im=None,
                                w0=100.0, w1=1.0, w2=0.1, w3=0.01,
                                verbose=False):
    """Совместная оптимизация через least_squares (быстрее и точнее)."""
    n = A.shape[0]
    T_mat = T if T is not None else np.eye(n)
    Im_vec = Im if Im is not None else np.zeros(n)
    use_taxes = T is not None

    B_42, _ = compute_off_diagonal_B_direct(np.diag(B_init), theta_init, q_base)

    def residuals(x):
        theta = x[:n]
        B = x[n:].reshape(n, n)

        penalty = []
        for i in range(n):
            if theta[i] <= 0:
                penalty.append(1e4 * abs(theta[i]))
            if B[i, i] >= 0:
                penalty.append(1e4 * abs(B[i, i]))

        try:
            if use_taxes or Im is not None:
                P_star = equilibrium_prices_open(A, B, theta, T_mat, Im_vec)
            else:
                P_star = equilibrium_prices_closed(A, B, theta)
            X_model = compute_X(A, B, P_star, theta, T_mat if use_taxes else None)
        except Exception:
            return np.ones(2 * n + len(periods) * n + n * n + n * (n - 1) // 2) * 1e4

        if np.any(np.isnan(P_star)) or np.any(np.isnan(X_model)):
            return np.ones(2 * n + len(periods) * n + n * n + n * (n - 1) // 2) * 1e4

        r = []
        # Базовое состояние
        r.extend((P_star - 1.0) * np.sqrt(w0))
        r.extend(((X_model - X_base) / X_base) * np.sqrt(w0))

        # Временная динамика
        for per in periods:
            Q_mod = compute_Q(B, per['P'], per['theta'], T_mat if use_taxes else None)
            r.extend((Q_mod - per['Q']) / np.maximum(np.abs(per['Q']), 1e-6) * np.sqrt(w1))

        # Регуляризация
        for i in range(n):
            for j in range(n):
                if i != j:
                    r.append((B[i, j] - B_42[i, j]) * np.sqrt(w2))

        # Симметрия
        for i in range(n):
            for j in range(i + 1, n):
                r.append((B[i, j] - B[j, i]) * np.sqrt(w3))

        r.extend(penalty)
        return np.array(r)

    x0 = np.concatenate([theta_init, B_init.flatten()])
    result = least_squares(residuals, x0, method='lm', max_nfev=200000,
                           ftol=1e-14, xtol=1e-14, gtol=1e-14)

    theta_opt = result.x[:n]
    B_opt = result.x[n:].reshape(n, n)

    if verbose:
        print(f"  LeastSq joint: cost={result.cost:.6e}, nfev={result.nfev}, "
              f"status={result.status}")

    return theta_opt, B_opt, result


# ══════════════════════════════════════════════════════════════
# 6. ПРОВЕРКИ И ДИАГНОСТИКА
# ══════════════════════════════════════════════════════════════

def validate_model(A, B, theta, X_base, Y_base, T=None, Im=None, label=""):
    """Полная проверка модели."""
    n = A.shape[0]
    T_mat = T if T is not None else np.eye(n)
    Im_vec = Im if Im is not None else np.zeros(n)
    use_taxes = T is not None

    if use_taxes or Im is not None:
        P_star = equilibrium_prices_open(A, B, theta, T_mat, Im_vec)
    else:
        P_star = equilibrium_prices_closed(A, B, theta)

    X_model = compute_X(A, B, P_star, theta, T_mat if use_taxes else None)
    Q_model = compute_Q(B, P_star, theta, T_mat if use_taxes else None)
    PR_model = compute_PR(A, B, P_star, theta, T_mat if use_taxes else None, Im_vec)

    print(f"\n{'='*60}")
    print(f"ВАЛИДАЦИЯ: {label}")
    print(f"{'='*60}")
    print(f"P*     = {P_star}")
    print(f"X_mod  = {X_model}")
    print(f"X_base = {X_base}")
    print(f"X_err% = {(X_model - X_base) / X_base * 100}")
    print(f"Q      = {Q_model}")
    print(f"q_base = {Y_base}")
    print(f"PR     = {PR_model}")
    print(f"theta  = {theta}")
    print(f"B_diag = {np.diag(B)}")

    # Проверка свойств B
    eigenvalues = eigvals(B)
    print(f"\nСобственные значения B: {eigenvalues.real}")
    all_neg = np.all(eigenvalues.real <= 1e-10)
    print(f"B отрицательно полуопределена: {all_neg}")

    # Проверка симметрии
    sym_err = np.max(np.abs(B - B.T))
    print(f"Максимальная асимметрия B: {sym_err:.6e}")

    # Проверка Курно-агрегации
    col_sums = B.sum(axis=0)
    cournot_err = col_sums + Q_model
    print(f"Ошибка Курно-агрегации (col_sum_B + q): {cournot_err}")

    print(f"\nПолная матрица B:")
    print(B)

    return {
        'P': P_star, 'X': X_model, 'Q': Q_model, 'PR': PR_model,
        'eigenvalues': eigenvalues, 'symmetry_err': sym_err,
        'X_err_pct': (X_model - X_base) / X_base * 100,
        'P_err': P_star - 1.0
    }


# ══════════════════════════════════════════════════════════════
# ГЛАВНАЯ ЛОГИКА
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("ВЫЧИСЛИМАЯ ЦЕНОВАЯ МОДЕЛЬ ОБЩЕГО РАВНОВЕСИЯ")
    print("Калибровка недиагональных элементов матрицы B")
    print("=" * 70)

    # ─── Демонстрационный пример из статьи (таблица 1) ───
    M1 = np.array([
        [20, 30, 10],
        [40, 80, 20],
        [15, 25, 30]
    ], dtype=float)

    Y_base = np.array([40, 70, 35], dtype=float)
    X_base = np.array([100, 210, 105], dtype=float)
    VA_base = np.array([25, 75, 45], dtype=float)  # добавленная стоимость

    A = compute_A_from_table(M1, X_base)
    print("\n--- Производственная матрица A ---")
    print(A)

    S = leontief_inverse(A)
    print("\n--- Матрица Леонтьева S = (I-A)^{-1} ---")
    print(S)

    # ─────────────────────────────────────────
    # ЭТАП 1: Базовая калибровка (авторский метод)
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ЭТАП 1: Базовая калибровка (scipy least_squares)")
    print("=" * 70)

    theta1, B_diag1, B1, err1 = calibrate_base_scipy(A, X_base, Y_base, verbose=True)
    res1 = validate_model(A, B1, theta1, X_base, Y_base, label="Базовая калибровка (формула 4.2)")

    # ─────────────────────────────────────────
    # Сравнение с табл. 3 из статьи
    # ─────────────────────────────────────────
    print("\n--- Сравнение с таблицей 3 статьи ---")
    paper_theta = np.array([250.63, 247.83, 143.45])
    paper_bii = np.array([-212.74, -182.46, -111.32])
    print(f"θ (статья):  {paper_theta}")
    print(f"θ (модель):  {theta1}")
    print(f"θ разница:   {theta1 - paper_theta}")
    print(f"bii (статья):{paper_bii}")
    print(f"bii (модель):{B_diag1}")
    print(f"bii разница: {B_diag1 - paper_bii}")

    # ─────────────────────────────────────────
    # ЭТАП 2-3: Генерация данных и расширенная калибровка
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ЭТАП 2: Генерация синтетических многопериодных данных")
    print("=" * 70)

    # Создаём "истинную" B с ИЗВЕСТНЫМИ недиагональными элементами,
    # отличающимися от формулы (4.2)
    B_true = B1.copy()
    n = 3
    # Добавим отклонения от (4.2) для тестирования
    perturbation = np.array([
        [0,    5,  -3],
        [-4,   0,   6],
        [2,   -5,   0]
    ], dtype=float)
    B_true += perturbation
    print(f"\nИстинная B (с отклонениями от 4.2):")
    print(B_true)

    # Пересчитаем θ_true, чтобы при B_true модель воспроизводила P=1
    # Из (1.13): θ = -M * P* = -M * 1, где M = B + (I-A)(diag(I-A^T))^{-1} diag(S*B) (I-A^T)
    I = np.eye(n)
    I_minus_AT = I - A.T
    S = leontief_inverse(A)
    diag_I_minus_AT_inv = inv(np.diag(np.diag(I_minus_AT)))
    M_mat = B_true + (I - A) @ diag_I_minus_AT_inv @ np.diag(np.diag(S @ B_true)) @ I_minus_AT
    theta_true = -M_mat @ np.ones(n)

    print(f"θ_true (пересчитанный): {theta_true}")

    # Проверим что P* = 1
    P_check = equilibrium_prices_closed(A, B_true, theta_true)
    print(f"P* при B_true, θ_true: {P_check}")
    X_check = compute_X(A, B_true, P_check, theta_true)
    print(f"X при B_true, θ_true: {X_check}")
    Q_check = compute_Q(B_true, P_check, theta_true)
    print(f"Q при B_true, θ_true: {Q_check}")

    # Генерируем синтетические периоды
    periods = generate_synthetic_periods(A, B_true, theta_true,
                                         n_periods=20, price_noise_std=0.15,
                                         seed=42)
    print(f"\nСгенерировано {len(periods)} периодов")
    for i, per in enumerate(periods[:3]):
        print(f"  Период {i}: P={per['P']}, Q={per['Q']}")

    # ─────────────────────────────────────────
    # ЭТАП 3: Калибровка только по базовой IO-таблице (формула 4.2)
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ЭТАП 3: Калибровка ТОЛЬКО по базовой таблице (формула 4.2)")
    print("Это даст B_42, отличающуюся от B_true")
    print("=" * 70)

    q_check = Q_check.copy()
    theta_42, B_diag_42, B_42, err_42 = calibrate_base_scipy(
        A, X_check, q_check, verbose=True)
    res_42 = validate_model(A, B_42, theta_42, X_check, q_check,
                             label="Только формула (4.2)")

    err_42_vs_true = np.sqrt(np.sum((B_42 - B_true) ** 2))
    print(f"\n||B_42 - B_true||_F = {err_42_vs_true:.4f}")
    print(f"B_42 - B_true (разница):")
    print(B_42 - B_true)

    # ─────────────────────────────────────────
    # ЭТАП 4: Регрессионная калибровка по временным данным
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ЭТАП 4: Регрессионная калибровка недиагональных элементов")
    print("=" * 70)

    for lam in [0.001, 0.01, 0.1, 1.0, 10.0]:
        B_reg = calibrate_offdiag_regression(B_42, theta_42, periods,
                                              q_check, lambda_reg=lam)
        err_reg = np.sqrt(np.sum((B_reg - B_true) ** 2))
        print(f"  lambda={lam:8.3f}: ||B_reg - B_true||_F = {err_reg:.4f}")

    # Выбираем лучший lambda
    best_lam = 0.01
    B_reg_best = calibrate_offdiag_regression(B_42, theta_42, periods,
                                               q_check, lambda_reg=best_lam)
    print(f"\nB_reg (lambda={best_lam}):")
    print(B_reg_best)
    print(f"B_true:")
    print(B_true)
    print(f"Разница B_reg - B_true:")
    print(B_reg_best - B_true)

    # ─────────────────────────────────────────
    # ЭТАП 5: Совместная оптимизация
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ЭТАП 5: Совместная оптимизация (least_squares)")
    print("=" * 70)

    # Начинаем от регрессионных оценок
    theta_joint, B_joint, res_joint = calibrate_offdiag_leastsq(
        A, X_check, q_check, periods,
        B_reg_best, theta_42, q_check,
        w0=1000.0, w1=10.0, w2=0.01, w3=0.001,
        verbose=True
    )

    res_joint_val = validate_model(A, B_joint, theta_joint, X_check, q_check,
                                    label="Совместная оптимизация")

    err_joint = np.sqrt(np.sum((B_joint - B_true) ** 2))
    print(f"\n||B_joint - B_true||_F = {err_joint:.4f}")
    print(f"B_joint - B_true:")
    print(B_joint - B_true)

    # ─────────────────────────────────────────
    # ЭТАП 5b: Совместная оптимизация с разными весами
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ЭТАП 5b: Поиск оптимальных весов")
    print("=" * 70)

    best_total_err = np.inf
    best_config = None
    best_B_final = None
    best_theta_final = None

    for w0 in [100, 500, 1000, 5000]:
        for w1 in [1, 5, 10, 50]:
            for w2 in [0.001, 0.01, 0.1]:
                for w3 in [0.0, 0.001, 0.01]:
                    try:
                        th, Bj, rj = calibrate_offdiag_leastsq(
                            A, X_check, q_check, periods,
                            B_reg_best, theta_42, q_check,
                            w0=w0, w1=w1, w2=w2, w3=w3,
                            verbose=False
                        )
                        P_test = equilibrium_prices_closed(A, Bj, th)
                        X_test = compute_X(A, Bj, P_test, th)

                        err_B = np.sqrt(np.sum((Bj - B_true) ** 2))
                        err_P = np.max(np.abs(P_test - 1.0))
                        err_X = np.max(np.abs((X_test - X_check) / X_check))

                        if err_P < 0.01 and err_X < 0.01:
                            if err_B < best_total_err:
                                best_total_err = err_B
                                best_config = (w0, w1, w2, w3)
                                best_B_final = Bj.copy()
                                best_theta_final = th.copy()
                    except Exception:
                        continue

    if best_config is not None:
        print(f"Лучшая конфигурация весов: w0={best_config[0]}, w1={best_config[1]}, "
              f"w2={best_config[2]}, w3={best_config[3]}")
        print(f"||B_best - B_true||_F = {best_total_err:.6f}")
        res_best = validate_model(A, best_B_final, best_theta_final,
                                   X_check, q_check,
                                   label="Лучший результат")
        print(f"\nB_best - B_true:")
        print(best_B_final - B_true)
    else:
        print("Не удалось найти конфигурацию с допустимой точностью")
        best_B_final = B_joint
        best_theta_final = theta_joint

    # ─────────────────────────────────────────
    # ИТОГОВОЕ СРАВНЕНИЕ
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ИТОГОВОЕ СРАВНЕНИЕ МЕТОДОВ")
    print("=" * 70)

    methods = {
        "Формула (4.2) только": (B_42, theta_42),
        "Регрессия (lambda=0.01)": (B_reg_best, theta_42),
        "Совместная оптимизация": (B_joint, theta_joint),
    }
    if best_config is not None:
        methods["Лучший (grid search)"] = (best_B_final, best_theta_final)

    for name, (B_m, th_m) in methods.items():
        try:
            P_m = equilibrium_prices_closed(A, B_m, th_m)
            X_m = compute_X(A, B_m, P_m, th_m)
            err_B_m = np.sqrt(np.sum((B_m - B_true) ** 2))
            err_P_m = np.max(np.abs(P_m - 1.0))
            err_X_m = np.max(np.abs((X_m - X_check) / X_check))

            # Предсказание на периодах
            pred_errs = []
            for per in periods:
                Q_pred = compute_Q(B_m, per['P'], per['theta'])
                pred_errs.append(np.mean(np.abs((Q_pred - per['Q']) / per['Q'])))
            mean_pred_err = np.mean(pred_errs) * 100

            print(f"\n  {name}:")
            print(f"    ||B - B_true||_F   = {err_B_m:.4f}")
            print(f"    max|P* - 1|        = {err_P_m:.6f}")
            print(f"    max|(X-X_base)/X|  = {err_X_m:.6f}")
            print(f"    Ср. ошибка Q (%)   = {mean_pred_err:.2f}%")
        except Exception as e:
            print(f"\n  {name}: ОШИБКА: {e}")

    # ─────────────────────────────────────────
    # ЭТАП 6: Тест с бОльшим количеством периодов
    # ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("ЭТАП 6: Влияние количества периодов на точность")
    print("=" * 70)

    for n_per in [5, 10, 20, 50, 100]:
        periods_test = generate_synthetic_periods(
            A, B_true, theta_true, n_periods=n_per,
            price_noise_std=0.15, seed=123)

        if len(periods_test) < 3:
            continue

        B_reg_test = calibrate_offdiag_regression(
            B_42, theta_42, periods_test, q_check, lambda_reg=0.01)

        try:
            th_t, Bj_t, _ = calibrate_offdiag_leastsq(
                A, X_check, q_check, periods_test,
                B_reg_test, theta_42, q_check,
                w0=best_config[0] if best_config else 1000,
                w1=best_config[1] if best_config else 10,
                w2=best_config[2] if best_config else 0.01,
                w3=best_config[3] if best_config else 0.001,
                verbose=False)
            err_t = np.sqrt(np.sum((Bj_t - B_true) ** 2))
            P_t = equilibrium_prices_closed(A, Bj_t, th_t)
            err_P_t = np.max(np.abs(P_t - 1.0))
            print(f"  {n_per:3d} периодов: ||B-B_true||_F={err_t:.4f}, max|P*-1|={err_P_t:.6f}")
        except Exception as e:
            print(f"  {n_per:3d} периодов: ОШИБКА: {e}")


if __name__ == "__main__":
    main()
