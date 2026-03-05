"""
Вычислимая ценовая модель общего равновесия — V3
Ключевое исправление: правильная инициализация + диагностика OLS
"""

import numpy as np
from numpy.linalg import inv, norm, eigvals, cond
from scipy.optimize import least_squares
import warnings

np.set_printoptions(precision=6, suppress=True, linewidth=130)
warnings.filterwarnings('ignore')


# ─── ЯДРО МОДЕЛИ ───

def S_matrix(A):
    return inv(np.eye(A.shape[0]) - A)


def eq_prices(A, B, theta):
    """Формула (1.13): P* = -M^{-1} θ"""
    n = A.shape[0]
    I = np.eye(n)
    IAt = I - A.T
    S = S_matrix(A)
    M = B + (I - A) @ inv(np.diag(np.diag(IAt))) @ np.diag(np.diag(S @ B)) @ IAt
    return -inv(M) @ theta


def Q_demand(B, P, theta):
    return B @ P + theta


def X_output(A, B, P, theta):
    return S_matrix(A) @ (P * Q_demand(B, P, theta))


def VA_model(A, B, P, theta):
    return (P - A.T @ P) * (S_matrix(A) @ Q_demand(B, P, theta))


# ─── ФОРМУЛА (4.2) ───

def offdiag_42(B_diag, theta, Y_base):
    n = len(B_diag)
    phi = Y_base / Y_base.sum()
    R = sum((2 * B_diag[i] + theta[i]) / (1 - phi[i]) for i in range(n))
    G = sum(phi[i] / (1 - phi[i]) for i in range(n))
    M_tot = R / (1 + G)
    m = np.array([(2 * B_diag[i] + theta[i] - phi[i] * M_tot) / (1 - phi[i])
                  for i in range(n)])
    B = np.diag(B_diag.copy())
    for i in range(n):
        for k in range(n):
            if k != i:
                B[k, i] = -m[i] * phi[k]
    return B


# ─── БАЗОВАЯ КАЛИБРОВКА ───

def calibrate_base(A, X_base, Y_base, B_offdiag=None, init_diag=None, init_theta=None):
    """
    Найти diag(B) и θ: P*=1, X=X_base.
    B_offdiag: если задана — фиксируем недиагональные элементы.
    init_diag, init_theta: начальные приближения.
    """
    n = A.shape[0]
    d0 = init_diag if init_diag is not None else -Y_base / 2.0
    t0 = init_theta if init_theta is not None else 2 * Y_base

    def residuals(params):
        B_diag = params[:n]
        theta = params[n:]
        if np.any(theta <= 0) or np.any(B_diag >= 0):
            return np.ones(2 * n) * 1e6
        if B_offdiag is not None:
            B = B_offdiag.copy()
            np.fill_diagonal(B, B_diag)
        else:
            B = offdiag_42(B_diag, theta, Y_base)
        try:
            P = eq_prices(A, B, theta)
            X = X_output(A, B, P, theta)
        except Exception:
            return np.ones(2 * n) * 1e6
        if np.any(np.isnan(P)) or np.any(np.isnan(X)):
            return np.ones(2 * n) * 1e6
        return np.concatenate([(P - 1.0) * 1000, (X - X_base) / X_base * 1000])

    x0 = np.concatenate([d0, t0])
    res = least_squares(residuals, x0, method='lm', max_nfev=200000,
                        ftol=1e-15, xtol=1e-15, gtol=1e-15)

    B_diag = res.x[:n]
    theta = res.x[n:]
    if B_offdiag is not None:
        B = B_offdiag.copy()
        np.fill_diagonal(B, B_diag)
    else:
        B = offdiag_42(B_diag, theta, Y_base)
    return theta, B, res.cost


# ─── ГЕНЕРАЦИЯ ДАННЫХ ───

def gen_periods(A, B_true, theta_true, n_per, noise=0.20, seed=42):
    rng = np.random.RandomState(seed)
    n = B_true.shape[0]
    out = []
    for _ in range(n_per * 5):
        shock = np.clip(rng.normal(1.0, noise, n), 0.5, 2.0)
        th_k = theta_true * shock
        try:
            P_k = eq_prices(A, B_true, th_k)
            Q_k = Q_demand(B_true, P_k, th_k)
            X_k = X_output(A, B_true, P_k, th_k)
            if np.all(P_k > 0) and np.all(Q_k > 0):
                out.append({'theta': th_k, 'P': P_k, 'Q': Q_k, 'X': X_k})
                if len(out) >= n_per:
                    break
        except Exception:
            pass
    return out


# ─── OLS ОЦЕНКА B ───

def estimate_B_ols(periods, n):
    """q(t) - θ(t) = B @ P(t) => OLS по строкам."""
    Y_mat = np.array([p['Q'] - p['theta'] for p in periods])
    X_mat = np.array([p['P'] for p in periods])
    Bt, residuals, rank, sv = np.linalg.lstsq(X_mat, Y_mat, rcond=None)
    return Bt.T, sv


def estimate_B_ridge(periods, n, B_prior, lam):
    K = len(periods)
    B_est = np.zeros((n, n))
    for i in range(n):
        y = np.array([p['Q'][i] - p['theta'][i] for p in periods])
        X = np.array([p['P'] for p in periods])
        bp = B_prior[i, :]
        B_est[i, :] = np.linalg.solve(X.T @ X + lam * np.eye(n),
                                        X.T @ y + lam * bp)
    return B_est


# ─── РЕКАЛИБРОВКА С ФИКСИРОВАННЫМИ НЕДИАГОНАЛЬНЫМИ ───

def recalibrate(A, X_base, Y_base, B_full):
    """Фиксируем недиагональные B_full, ищем новые diag+θ для P*=1, X=X_base.
    Используем диагональ B_full как начальное приближение!"""
    n = A.shape[0]
    B_off = B_full.copy()
    d0 = np.diag(B_full).copy()
    # θ из условия q = B@1 + θ = Y_base при P=1
    t0 = Y_base - B_full @ np.ones(n)
    t0 = np.maximum(t0, 1.0)

    return calibrate_base(A, X_base, Y_base, B_offdiag=B_off,
                          init_diag=d0, init_theta=t0)


# ─── МЕТРИКИ ───

def evaluate(A, B, theta, B_true, X_base, Y_base, periods, label):
    n = B.shape[0]
    try:
        P = eq_prices(A, B, theta)
        X = X_output(A, B, P, theta)
        Q = Q_demand(B, P, theta)
    except Exception:
        print(f"  [{label}] ОШИБКА при вычислении равновесия")
        return None

    err_B = norm(B - B_true, 'fro')
    err_P = np.max(np.abs(P - 1.0))
    err_X = np.max(np.abs((X - X_base) / X_base))

    pred = []
    for per in periods:
        Qp = Q_demand(B, per['P'], per['theta'])
        pred.append(np.mean(np.abs((Qp - per['Q']) / np.maximum(np.abs(per['Q']), 1e-6))))
    mean_pred = np.mean(pred) * 100

    offdiag_err = 0.0
    cnt = 0
    for i in range(n):
        for j in range(n):
            if i != j:
                offdiag_err += (B[i, j] - B_true[i, j]) ** 2
                cnt += 1
    offdiag_rmse = np.sqrt(offdiag_err / cnt)

    print(f"  [{label}]")
    print(f"    ||B-B_true||_F   = {err_B:.4f}")
    print(f"    offdiag RMSE     = {offdiag_rmse:.4f}")
    print(f"    max|P*-1|        = {err_P:.2e}")
    print(f"    max|(X-Xb)/Xb|  = {err_X:.2e}")
    print(f"    Q pred err       = {mean_pred:.3f}%")
    return {'err_B': err_B, 'err_P': err_P, 'err_X': err_X,
            'pred_Q': mean_pred, 'offdiag_rmse': offdiag_rmse}


# ─── ГЛАВНЫЙ ЭКСПЕРИМЕНТ ───

def main():
    print("=" * 80)
    print("КАЛИБРОВКА НЕДИАГОНАЛЬНЫХ B — ВЕРСИЯ 3 (с диагностикой)")
    print("=" * 80)

    M1 = np.array([[20, 30, 10], [40, 80, 20], [15, 25, 30]], dtype=float)
    Y0 = np.array([40, 70, 35], dtype=float)
    X0 = np.array([100, 210, 105], dtype=float)
    n = 3
    A = M1 / X0[np.newaxis, :]

    # ─── Базовая калибровка ───
    theta0, B0, _ = calibrate_base(A, X0, Y0)
    P0 = eq_prices(A, B0, theta0)
    print(f"\nБазовая (4.2): P*={P0}, θ={theta0}")
    print(f"B0=\n{B0}\n")

    # ─── Истинная B (с контролируемыми отклонениями) ───
    B_true = B0.copy()
    B_true[0, 1] += 8;  B_true[1, 0] -= 8
    B_true[1, 2] += 5;  B_true[2, 1] -= 5
    B_true[0, 2] -= 2;  B_true[2, 0] += 2

    I = np.eye(n)
    IAt = I - A.T
    S = S_matrix(A)
    M_mat = B_true + (I - A) @ inv(np.diag(np.diag(IAt))) @ np.diag(np.diag(S @ B_true)) @ IAt
    theta_true = -M_mat @ np.ones(n)
    P_true = eq_prices(A, B_true, theta_true)
    X_true = X_output(A, B_true, P_true, theta_true)
    Q_true = Q_demand(B_true, P_true, theta_true)

    print(f"B_true=\n{B_true}")
    print(f"θ_true={theta_true}")
    print(f"P*_true={P_true}, X_true={X_true}, Q_true={Q_true}")

    Y_true = Q_true.copy()
    X_true_b = X_true.copy()

    # ─── Диагностика: проверка Q = B@P + θ ───
    print("\n" + "=" * 80)
    print("ДИАГНОСТИКА: ПРОВЕРКА РЕГРЕССИОННОЙ МОДЕЛИ")
    print("=" * 80)

    periods_diag = gen_periods(A, B_true, theta_true, 20, noise=0.20, seed=42)
    print(f"Периодов: {len(periods_diag)}")

    # Проверим: Q(t) - θ(t) = B_true @ P(t) ?
    max_resid = 0
    for p in periods_diag:
        resid = p['Q'] - p['theta'] - B_true @ p['P']
        max_resid = max(max_resid, np.max(np.abs(resid)))
    print(f"Макс. невязка Q-θ-B@P: {max_resid:.2e} (должно быть ≈0)")

    # Матрица регрессоров
    X_mat = np.array([p['P'] for p in periods_diag])
    print(f"Число обусловленности матрицы P: {cond(X_mat):.2f}")
    print(f"Sing. values: {np.linalg.svd(X_mat, compute_uv=False)[:5]}")
    print(f"Среднее P: {X_mat.mean(axis=0)}")
    print(f"Стд. откл. P: {X_mat.std(axis=0)}")

    # OLS
    B_ols, sv = estimate_B_ols(periods_diag, n)
    print(f"\nOLS B =\n{B_ols}")
    print(f"B_true =\n{B_true}")
    print(f"OLS ошибка: ||B_ols - B_true||_F = {norm(B_ols - B_true, 'fro'):.6f}")

    # Проверка: если OLS точно, то ошибка должна быть ≈ 0
    ols_err = norm(B_ols - B_true, 'fro')
    print(f"\n*** OLS ТОЧНОСТЬ: {ols_err:.6e} ***")
    if ols_err < 1e-6:
        print("OLS восстанавливает B_true ТОЧНО!")
    else:
        print("OLS НЕ восстанавливает B_true точно. Разберёмся почему...")
        print(f"Разница B_ols - B_true:\n{B_ols - B_true}")

    # ─── Рекалибровка с OLS ───
    print("\n" + "=" * 80)
    print("РЕКАЛИБРОВКА: OLS B → diag+θ для P*=1, X=X_base")
    print("=" * 80)

    theta_rc, B_rc, cost_rc = recalibrate(A, X_true_b, Y_true, B_ols)
    print(f"Стоимость: {cost_rc:.2e}")
    P_rc = eq_prices(A, B_rc, theta_rc)
    X_rc = X_output(A, B_rc, P_rc, theta_rc)
    print(f"P*={P_rc}")
    print(f"X={X_rc} (target={X_true_b})")
    print(f"θ_rc={theta_rc} (θ_true={theta_true})")
    print(f"diag(B_rc)={np.diag(B_rc)} (true={np.diag(B_true)})")
    print(f"||B_rc - B_true||_F = {norm(B_rc - B_true, 'fro'):.6f}")
    print(f"B_rc=\n{B_rc}")

    # ─── ПОЛНЫЙ ЭКСПЕРИМЕНТ ───
    print("\n" + "=" * 80)
    print("ПОЛНЫЙ ЭКСПЕРИМЕНТ: РАЗНОЕ КОЛИЧЕСТВО ПЕРИОДОВ")
    print("=" * 80)

    for n_per in [5, 10, 20, 50, 100]:
        periods = gen_periods(A, B_true, theta_true, n_per, noise=0.20, seed=42)
        print(f"\n{'═'*60}")
        print(f"  {len(periods)} ПЕРИОДОВ")
        print(f"{'═'*60}")

        # Метод 0: Только формула (4.2)
        theta_42, B_42, _ = calibrate_base(A, X_true_b, Y_true)
        evaluate(A, B_42, theta_42, B_true, X_true_b, Y_true, periods, "Формула 4.2")

        # Метод 1: OLS + рекалибровка
        B_ols_k, _ = estimate_B_ols(periods, n)
        theta_ols_k, B_ols_rc_k, _ = recalibrate(A, X_true_b, Y_true, B_ols_k)
        evaluate(A, B_ols_rc_k, theta_ols_k, B_true, X_true_b, Y_true,
                 periods, "OLS+recalib")

        # Метод 2: Ridge с разными λ + рекалибровка
        best = None
        for lam in [0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0]:
            B_rdg = estimate_B_ridge(periods, n, B_42, lam)
            th_r, B_r, _ = recalibrate(A, X_true_b, Y_true, B_rdg)
            try:
                P_r = eq_prices(A, B_r, th_r)
                if np.max(np.abs(P_r - 1.0)) < 0.01:
                    e = norm(B_r - B_true, 'fro')
                    if best is None or e < best[0]:
                        best = (e, lam, B_r, th_r)
            except Exception:
                pass

        if best:
            evaluate(A, best[2], best[3], B_true, X_true_b, Y_true,
                     periods, f"Ridge(λ={best[1]})+recal")

    # ─── OOS тест на лучшем ───
    print("\n" + "=" * 80)
    print("OUT-OF-SAMPLE ТЕСТ (seed=999, noise=0.25)")
    print("=" * 80)

    periods_train = gen_periods(A, B_true, theta_true, 100, noise=0.20, seed=42)
    periods_oos = gen_periods(A, B_true, theta_true, 50, noise=0.25, seed=999)

    # 4.2
    theta_42, B_42, _ = calibrate_base(A, X_true_b, Y_true)

    # OLS + recal
    B_ols_train, _ = estimate_B_ols(periods_train, n)
    theta_ols_train, B_ols_train_rc, _ = recalibrate(A, X_true_b, Y_true, B_ols_train)

    for name, B_m, th_m in [("Формула 4.2", B_42, theta_42),
                              ("OLS+recalib (100 per)", B_ols_train_rc, theta_ols_train)]:
        q_errs = []
        for per in periods_oos:
            Qp = Q_demand(B_m, per['P'], per['theta'])
            q_errs.append(np.mean(np.abs((Qp - per['Q']) / per['Q'])))
        print(f"  {name}: Q_err={np.mean(q_errs)*100:.3f}% (max={np.max(q_errs)*100:.3f}%)")


if __name__ == "__main__":
    main()
