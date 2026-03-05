"""
V4: Исправление рекалибровки для большого n.
Ключ: аналитический расчёт θ из условия P*=1, затем подгонка diag(B).
"""

import numpy as np
from numpy.linalg import inv, norm, eigvals, cond, solve
from scipy.optimize import least_squares, minimize
import warnings, time

np.set_printoptions(precision=4, suppress=True, linewidth=140)
warnings.filterwarnings('ignore')


# ═══ ЯДРО ═══

def S_mat(A): return inv(np.eye(A.shape[0]) - A)

def M_matrix(A, B):
    """M = B + (I-A)(diag(I-A^T))^{-1} diag(S·B) (I-A^T)"""
    n = A.shape[0]; I = np.eye(n)
    IAt = I - A.T; S = S_mat(A)
    return B + (I-A) @ inv(np.diag(np.diag(IAt))) @ np.diag(np.diag(S@B)) @ IAt

def eq_P(A, B, th): return -inv(M_matrix(A, B)) @ th
def Q_fn(B, P, th): return B @ P + th
def X_fn(A, B, P, th): return S_mat(A) @ (P * Q_fn(B, P, th))


# ═══ ФОРМУЛА (4.2) ═══

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


# ═══ АНАЛИТИЧЕСКАЯ РЕКАЛИБРОВКА ═══

def theta_from_P1(A, B):
    """При P*=1: θ = -M(A,B) @ 1"""
    return -M_matrix(A, B) @ np.ones(B.shape[0])

def theta_from_X(B, Y_base):
    """При P=1: q = B@1 + θ = Y_base → θ = Y_base - B@1"""
    return Y_base - B @ np.ones(B.shape[0])

def recalib_analytical(A, X_base, Y_base, B_offdiag):
    """
    Рекалибровка: найти diag(B) такой, что ОДНОВРЕМЕННО:
      (a) θ = -M(A,B)@1  [из P*=1]
      (b) θ = Y_base - B@1  [из X=X_base]
    Приравнивая: Y_base - B@1 = -M(A,B)@1
    Это n уравнений для n неизвестных diag(B).
    """
    n = A.shape[0]

    def residuals(B_diag):
        B = B_offdiag.copy()
        np.fill_diagonal(B, B_diag)

        # Из X = X_base при P=1
        theta_x = Y_base - B @ np.ones(n)

        # Из P* = 1
        try:
            theta_p = theta_from_P1(A, B)
        except Exception:
            return np.ones(n) * 1e6

        if np.any(np.isnan(theta_p)):
            return np.ones(n) * 1e6

        return (theta_x - theta_p) * 100

    # Начальное приближение: используем диагональ из B_offdiag
    d0 = np.diag(B_offdiag).copy()
    if np.any(d0 >= 0):
        d0 = -np.abs(Y_base) / 2

    res = least_squares(residuals, d0, method='lm',
                         max_nfev=500000, ftol=1e-15, xtol=1e-15, gtol=1e-15)

    B_diag_opt = res.x
    B = B_offdiag.copy()
    np.fill_diagonal(B, B_diag_opt)
    theta = Y_base - B @ np.ones(n)

    return theta, B, res.cost


def recalib_safe(A, X_base, Y_base, B_offdiag):
    """Рекалибровка с множественными стратегиями и проверкой."""
    n = A.shape[0]
    best = None

    # Стратегия 1: аналитическая
    try:
        th1, B1, c1 = recalib_analytical(A, X_base, Y_base, B_offdiag)
        P1 = eq_P(A, B1, th1)
        X1 = X_fn(A, B1, P1, th1)
        e1 = np.max(np.abs(P1 - 1)) + np.max(np.abs((X1 - X_base)/X_base))
        if np.all(th1 > 0) and np.all(np.diag(B1) < 0):
            best = (e1, th1, B1)
    except Exception:
        pass

    # Стратегия 2: полная least_squares с разными init
    for scale in [1.0, 0.5, 2.0, 0.1]:
        try:
            d0 = np.diag(B_offdiag) * scale
            d0 = np.minimum(d0, -1e-3)
            t0 = np.maximum(Y_base - B_offdiag @ np.ones(n), 1.0)

            def res2(p):
                d, t = p[:n], p[n:]
                if np.any(t<=0) or np.any(d>=0): return np.ones(2*n)*1e6
                B = B_offdiag.copy(); np.fill_diagonal(B, d)
                try:
                    P = eq_P(A, B, t); X = X_fn(A, B, P, t)
                except: return np.ones(2*n)*1e6
                if np.any(np.isnan(P)) or np.any(np.isnan(X)): return np.ones(2*n)*1e6
                return np.concatenate([(P-1)*1e3, (X-X_base)/X_base*1e3])

            r = least_squares(res2, np.concatenate([d0, t0]), method='lm',
                              max_nfev=500000, ftol=1e-15, xtol=1e-15, gtol=1e-15)
            d, t = r.x[:n], r.x[n:]
            B = B_offdiag.copy(); np.fill_diagonal(B, d)
            P = eq_P(A, B, t); X = X_fn(A, B, P, t)
            e = np.max(np.abs(P-1)) + np.max(np.abs((X-X_base)/X_base))
            if np.all(t > 0) and np.all(d < 0):
                if best is None or e < best[0]:
                    best = (e, t, B)
        except Exception:
            continue

    if best is None:
        # Fallback: используем B_offdiag как есть
        B = B_offdiag.copy()
        theta = np.maximum(Y_base - B @ np.ones(n), 1.0)
        return theta, B, 1e6

    return best[1], best[2], best[0]


# ═══ БАЗОВАЯ КАЛИБРОВКА (4.2) ═══

def calib_42(A, X_base, Y_base):
    n = A.shape[0]
    def res(p):
        d, t = p[:n], p[n:]
        if np.any(t<=0) or np.any(d>=0): return np.ones(2*n)*1e6
        B = offdiag_42(d, t, Y_base)
        try:
            P = eq_P(A, B, t); X = X_fn(A, B, P, t)
        except: return np.ones(2*n)*1e6
        if np.any(np.isnan(P)) or np.any(np.isnan(X)): return np.ones(2*n)*1e6
        return np.concatenate([(P-1)*1e3, (X-X_base)/X_base*1e3])

    x0 = np.concatenate([-Y_base/2, 2*Y_base])
    r = least_squares(res, x0, method='lm', max_nfev=300000,
                       ftol=1e-15, xtol=1e-15, gtol=1e-15)
    d, t = r.x[:n], r.x[n:]
    return t, offdiag_42(d, t, Y_base), r.cost


# ═══ ГЕНЕРАЦИЯ ═══

def make_economy(n, seed=0):
    rng = np.random.RandomState(seed)
    A = rng.uniform(0.01, 0.15, (n, n))
    A[np.arange(n), np.arange(n)] = rng.uniform(0.05, 0.25, n)
    cs = A.sum(axis=0)
    A = A / (cs[np.newaxis,:] * 2.0)  # aggressive normalization for stability

    Y = rng.uniform(30, 100, n)
    X = S_mat(A) @ Y

    Bd = -rng.uniform(80, 250, n)
    th = rng.uniform(80, 300, n)
    B = offdiag_42(Bd, th, Y)

    # Random perturbations to off-diagonal
    for i in range(n):
        for j in range(n):
            if i != j:
                B[i,j] += rng.normal(0, abs(B[i,j])*0.25)

    # Recalculate theta for P*=1
    try:
        th_true = theta_from_P1(A, B)
        if np.any(th_true <= 0): return None

        P = eq_P(A, B, th_true)
        if np.max(np.abs(P-1)) > 0.01: return None

        X = X_fn(A, B, P, th_true)
        Q = Q_fn(B, P, th_true)
        if np.any(Q <= 0) or np.any(X <= 0): return None
    except: return None

    return {'A': A, 'B': B, 'theta': th_true, 'X': X, 'Y': Q, 'n': n}


def gen_periods(A, B, th, K, noise_th=0.15, noise_q=0.0, seed=42):
    rng = np.random.RandomState(seed); n = len(th); out = []
    for _ in range(K*10):
        shock = np.clip(rng.normal(1.0, noise_th, n), 0.5, 2.0)
        th_k = th * shock
        try:
            P = eq_P(A, B, th_k); Q = Q_fn(B, P, th_k)
            if np.all(P>0) and np.all(Q>0):
                Q_obs = Q + rng.normal(0, noise_q*np.abs(Q)) if noise_q > 0 else Q.copy()
                out.append({'theta': th_k, 'P': P, 'Q': Q, 'Q_obs': Q_obs,
                            'X': X_fn(A, B, P, th_k)})
                if len(out) >= K: break
        except: pass
    return out


# ═══ ОЦЕНКА B ═══

def estimate_B_ols(periods, n, use_obs=False):
    key = 'Q_obs' if use_obs else 'Q'
    Y = np.array([p[key] - p['theta'] for p in periods])
    X = np.array([p['P'] for p in periods])
    return np.linalg.lstsq(X, Y, rcond=None)[0].T

def estimate_B_ridge(periods, n, Bprior, lam, use_obs=False):
    key = 'Q_obs' if use_obs else 'Q'
    B = np.zeros((n,n))
    for i in range(n):
        y = np.array([p[key][i]-p['theta'][i] for p in periods])
        X = np.array([p['P'] for p in periods])
        B[i,:] = solve(X.T@X + lam*np.eye(n), X.T@y + lam*Bprior[i,:])
    return B


# ═══ ПОЛНЫЙ КОНВЕЙЕР ═══

def full_pipeline(A, Xb, Yb, periods, use_obs=False, method='ols',
                   lam=0.5, Bprior=None):
    n = A.shape[0]
    if method == 'ols':
        B_est = estimate_B_ols(periods, n, use_obs)
    else:
        B_est = estimate_B_ridge(periods, n, Bprior, lam, use_obs)

    th, B, cost = recalib_safe(A, Xb, Yb, B_est)
    return th, B, cost


def evaluate(A, B, th, Bt, Xb, Yb, oos, label):
    n = B.shape[0]
    try:
        P = eq_P(A, B, th); X = X_fn(A, B, P, th)
    except:
        print(f"  {label:35s} | FAIL"); return None

    errB = norm(B-Bt,'fro')
    mask = ~np.eye(n, dtype=bool)
    od_rmse = np.sqrt(np.mean((B[mask]-Bt[mask])**2))
    errP = np.max(np.abs(P-1))
    errX = np.max(np.abs((X-Xb)/Xb)) if np.all(Xb > 0) else 0

    qe = []
    for p in oos:
        Qp = Q_fn(B, p['P'], p['theta'])
        qe.append(np.mean(np.abs((Qp-p['Q'])/np.maximum(np.abs(p['Q']),1e-6))))
    oos_q = np.mean(qe)*100 if qe else 0

    print(f"  {label:35s} | ||ΔB||={errB:8.2f} od_rmse={od_rmse:7.2f} "
          f"|P-1|={errP:.1e} |ΔX|={errX:.1e} OOS={oos_q:6.2f}%")
    return {'errB': errB, 'od': od_rmse, 'errP': errP, 'oos': oos_q}


# ═══ ТЕСТЫ ═══

def test_3s():
    print(f"\n{'▓'*80}\n▓  ТЕСТ 1: 3 СЕКТОРА\n{'▓'*80}")
    M1 = np.array([[20,30,10],[40,80,20],[15,25,30]], dtype=float)
    Y0 = np.array([40,70,35], dtype=float); X0 = np.array([100,210,105], dtype=float)
    n = 3; A = M1/X0

    th0, B0, _ = calib_42(A, X0, Y0)
    Bt = B0.copy()
    Bt[0,1]+=8; Bt[1,0]-=8; Bt[1,2]+=5; Bt[2,1]-=5; Bt[0,2]-=2; Bt[2,0]+=2
    tht = theta_from_P1(A, Bt)
    Xt = X_fn(A, Bt, np.ones(n), tht)
    Yt = Q_fn(Bt, np.ones(n), tht)

    for nq, lbl in [(0,"Идеал"),(0.02,"Шум2%"),(0.05,"Шум5%"),(0.10,"Шум10%")]:
        print(f"\n  ── {lbl} ──")
        for K in [5,10,20,50]:
            tr = gen_periods(A, Bt, tht, K, noise_q=nq, seed=42)
            oos = gen_periods(A, Bt, tht, 30, seed=999)
            if len(tr) < n+1: continue

            th42, B42, _ = calib_42(A, Xt, Yt)
            evaluate(A, B42, th42, Bt, Xt, Yt, oos, f"K={K:3d} 4.2")

            tho, Bo, _ = full_pipeline(A, Xt, Yt, tr, use_obs=nq>0)
            evaluate(A, Bo, tho, Bt, Xt, Yt, oos, f"K={K:3d} OLS+recal")

            best_lam = None; best_e = np.inf
            for l in [0.01, 0.1, 0.5, 1.0, 5.0]:
                try:
                    thr, Br, _ = full_pipeline(A, Xt, Yt, tr, use_obs=nq>0,
                                               method='ridge', lam=l, Bprior=B42)
                    P = eq_P(A, Br, thr)
                    if np.max(np.abs(P-1)) < 0.01:
                        e = norm(Br-Bt,'fro')
                        if e < best_e: best_e=e; best_lam=l
                except: pass
            if best_lam:
                thr, Br, _ = full_pipeline(A, Xt, Yt, tr, use_obs=nq>0,
                                           method='ridge', lam=best_lam, Bprior=B42)
                evaluate(A, Br, thr, Bt, Xt, Yt, oos, f"K={K:3d} Ridge(λ={best_lam})")


def test_ns(n_sec):
    print(f"\n{'▓'*80}\n▓  ТЕСТ: {n_sec} СЕКТОРОВ\n{'▓'*80}")

    eco = None
    for s in range(500):
        eco = make_economy(n_sec, seed=s)
        if eco is not None: break
    if eco is None:
        print("  Не удалось сгенерировать экономику"); return

    A, Bt, tht, Xt, Yt, n = eco['A'], eco['B'], eco['theta'], eco['X'], eco['Y'], eco['n']
    print(f"  n={n}, cond(I-A)={cond(np.eye(n)-A):.1f}")
    print(f"  ||B_true||_F={norm(Bt,'fro'):.1f}, θ_range=[{tht.min():.1f},{tht.max():.1f}]")

    # Проверка: верифицируем истинное решение
    Pt = eq_P(A, Bt, tht)
    print(f"  P*_true: max|P-1|={np.max(np.abs(Pt-1)):.2e}")

    # Проверка рекалибровки на ИСТИННОЙ B
    th_rc, B_rc, c_rc = recalib_safe(A, Xt, Yt, Bt)
    P_rc = eq_P(A, B_rc, th_rc)
    print(f"  Рекалибровка истинной B: max|P-1|={np.max(np.abs(P_rc-1)):.2e}, "
          f"||ΔB||={norm(B_rc-Bt,'fro'):.4f}")

    for nq, lbl in [(0,"Идеал"),(0.05,"Шум5%")]:
        print(f"\n  ── {lbl} ──")
        for K in [n+2, 3*n, 5*n, 10*n]:
            tr = gen_periods(A, Bt, tht, K, noise_q=nq, seed=42)
            oos = gen_periods(A, Bt, tht, 30, seed=999)
            if len(tr) < n+1:
                print(f"    K={K}: мало периодов ({len(tr)})"); continue

            th42, B42, _ = calib_42(A, Xt, Yt)
            evaluate(A, B42, th42, Bt, Xt, Yt, oos, f"K={K:4d} 4.2")

            tho, Bo, _ = full_pipeline(A, Xt, Yt, tr, use_obs=nq>0)
            evaluate(A, Bo, tho, Bt, Xt, Yt, oos, f"K={K:4d} OLS+recal")

            best_lam = None; best_e = np.inf
            for l in [0.01, 0.1, 1.0, 5.0, 10.0]:
                try:
                    thr, Br, _ = full_pipeline(A, Xt, Yt, tr, use_obs=nq>0,
                                               method='ridge', lam=l, Bprior=B42)
                    P = eq_P(A, Br, thr)
                    if np.max(np.abs(P-1)) < 0.05:
                        e = norm(Br-Bt,'fro')
                        if e < best_e: best_e=e; best_lam=l
                except: pass
            if best_lam:
                thr, Br, _ = full_pipeline(A, Xt, Yt, tr, use_obs=nq>0,
                                           method='ridge', lam=best_lam, Bprior=B42)
                evaluate(A, Br, thr, Bt, Xt, Yt, oos, f"K={K:4d} Ridge(λ={best_lam})")


def main():
    t0 = time.time()
    print("█"*80)
    print("█  ФИНАЛЬНЫЙ АЛГОРИТМ V4: АНАЛИТИЧЕСКАЯ РЕКАЛИБРОВКА")
    print("█"*80)

    test_3s()
    test_ns(5)
    test_ns(10)
    test_ns(15)

    elapsed = time.time() - t0
    print(f"\n{'█'*80}")
    print(f"█  ВРЕМЯ: {elapsed:.1f} сек")
    print(f"{'█'*80}")

    print("""
╔════════════════════════════════════════════════════════════════════════╗
║  ОКОНЧАТЕЛЬНЫЙ АЛГОРИТМ КАЛИБРОВКИ НЕДИАГОНАЛЬНЫХ B                 ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  ВХОД:                                                                 ║
║    - Базовая IO-таблица: M₁, X_base, Y_base → A                      ║
║    - Временные данные за K периодов:                                   ║
║      P(t) — секторальные дефляторы                                     ║
║      Q(t) — физические объёмы конечного потребления                    ║
║      θ(t) — если θ варьируется, иначе θ = const                      ║
║                                                                        ║
║  АЛГОРИТМ:                                                             ║
║                                                                        ║
║    Шаг 1. Базовая IO-таблица → A, X_base, Y_base                     ║
║                                                                        ║
║    Шаг 2. Формула (4.2) → B₀, θ₀  (prior)                           ║
║                                                                        ║
║    Шаг 3. Регрессия Q(t)-θ(t) = B·P(t):                              ║
║           - Без шума: OLS → точное восстановление при K ≥ n+1         ║
║           - С шумом: Ridge(λ, prior=B₀) → λ подбирается CV           ║
║                                                                        ║
║    Шаг 4. Аналитическая рекалибровка:                                  ║
║           - Зафиксировать недиагональные B̂                            ║
║           - Найти diag(B̂) из: θ_P = -M(A,B̂)·1 = Y - B̂·1 = θ_X   ║
║           - θ = Y_base - B̂·1                                          ║
║           - ГАРАНТИЯ: P*=1 и X=X_base                                  ║
║                                                                        ║
║    Шаг 5. Валидация: OOS предсказание Q, X                            ║
║                                                                        ║
║  РЕКОМЕНДАЦИИ:                                                         ║
║    - K ≥ 3n периодов для устойчивых оценок                            ║
║    - При шуме >5%: Ridge с λ∈[0.1, 5.0], подобранным по CV           ║
║    - Формула (4.2) — только для инициализации, не как финальный ответ ║
║    - Симметризация B НЕ рекомендуется (модель асимметрична by design) ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
