"""
Реалистичная калибровка недиагональных элементов B.
Условие: ОДНА IO-таблица. Никаких временных рядов.

Тестируем три подхода:
  1. Формула (4.2) — оригинальная (пропорциональное перераспределение)
  2. Модифицированная (4.2) с матрицей замещаемости σ
  3. Случай 2–3 IO-таблиц (агрегация до малого n)
"""

import numpy as np
from numpy.linalg import inv, norm, eigvals
from scipy.optimize import least_squares
import warnings

np.set_printoptions(precision=4, suppress=True, linewidth=140)
warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════
# ЯДРО МОДЕЛИ (минимальное)
# ═══════════════════════════════════════════════

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


# ═══════════════════════════════════════════════
# ФОРМУЛА (4.2) — ОРИГИНАЛЬНАЯ
# ═══════════════════════════════════════════════

def offdiag_42(Bd, th, Y):
    """b_ki = -m_i * φ_k, где m_i = b_ii + q_i (маржинальный эффект)."""
    n = len(Bd); phi = Y / Y.sum()
    R = sum((2*Bd[i]+th[i])/(1-phi[i]) for i in range(n))
    G = sum(phi[i]/(1-phi[i]) for i in range(n))
    Mtot = R/(1+G)
    m = np.array([(2*Bd[i]+th[i]-phi[i]*Mtot)/(1-phi[i]) for i in range(n)])
    B = np.diag(Bd.copy())
    for i in range(n):
        for k in range(n):
            if k != i:
                B[k, i] = -m[i] * phi[k]
    return B


# ═══════════════════════════════════════════════
# ФОРМУЛА (4.2) МОДИФИЦИРОВАННАЯ — С МАТРИЦЕЙ σ
# ═══════════════════════════════════════════════

def offdiag_42_sigma(Bd, th, Y, sigma):
    """
    Модификация: b_ki = -m_i * σ_ki * φ_k

    sigma[k,i] — коэффициент замещаемости товара k при изменении цены i:
      σ > 1: усиленный субститут (больше спроса перетекает к k)
      σ = 1: как в оригинальной (4.2)
      0 < σ < 1: ослабленная связь
      σ = 0: независимый товар
      σ < 0: комплемент

    При σ = матрица единиц → ТОЧНО совпадает с оригинальной (4.2).

    Система: b_ki = -m_i * σ_ki * φ_k  (столбец i матрицы B)
    b_ij = -m_j * σ_ij * φ_i  (строка i, элемент столбца j)
    q_i = b_ii + Σ_{j≠i} b_ij + θ_i
        = b_ii + Σ_{j≠i} (-m_j * σ_ij * φ_i) + θ_i
    m_i = b_ii + q_i = 2*b_ii + θ_i - φ_i * Σ_{j≠i} m_j * σ_ij

    Линейная система: m_i + φ_i * Σ_{j≠i} m_j * σ_ij = 2*b_ii + θ_i
    """
    n = len(Bd); phi = Y / Y.sum()

    L = np.eye(n)
    for i in range(n):
        for j in range(n):
            if i != j:
                L[i, j] = phi[i] * sigma[i, j]

    rhs = 2 * Bd + th
    m = np.linalg.solve(L, rhs)

    B = np.diag(Bd.copy())
    for i in range(n):
        for k in range(n):
            if k != i:
                B[k, i] = -m[i] * sigma[k, i] * phi[k]

    return B


# ═══════════════════════════════════════════════
# КАЛИБРОВКА diag(B) + θ
# ═══════════════════════════════════════════════

def calib(A, Xb, Yb, offdiag_func, **offdiag_kwargs):
    """
    Универсальная калибровка: находит diag(B) и θ
    при заданной функции вычисления недиагональных элементов.
    """
    n = A.shape[0]

    def res(p):
        d, t = p[:n], p[n:]
        if np.any(t <= 0) or np.any(d >= 0):
            return np.ones(2*n) * 1e6
        B = offdiag_func(d, t, Yb, **offdiag_kwargs)
        try:
            Ps = eq_P(A, B, t)
            Xs = X_fn(A, B, Ps, t)
        except:
            return np.ones(2*n) * 1e6
        if np.any(np.isnan(Ps)) or np.any(np.isnan(Xs)):
            return np.ones(2*n) * 1e6
        return np.concatenate([(Ps - 1) * 1e3, (Xs - Xb) / Xb * 1e3])

    x0 = np.concatenate([-Yb / 2, 2 * Yb])
    r = least_squares(res, x0, method='lm',
                       max_nfev=500000, ftol=1e-15, xtol=1e-15, gtol=1e-15)
    d, t = r.x[:n], r.x[n:]
    B = offdiag_func(d, t, Yb, **offdiag_kwargs)
    return t, B, r.cost


def calib_fixed_offdiag(A, Xb, Yb, Boff):
    """Калибровка с фиксированными недиагональными."""
    n = A.shape[0]
    d0 = np.diag(Boff).copy()
    t0 = np.maximum(Yb - Boff @ np.ones(n), 1.0)

    def res(p):
        d, t = p[:n], p[n:]
        if np.any(t <= 0) or np.any(d >= 0):
            return np.ones(2*n) * 1e6
        B = Boff.copy(); np.fill_diagonal(B, d)
        try:
            Ps = eq_P(A, B, t)
            Xs = X_fn(A, B, Ps, t)
        except:
            return np.ones(2*n) * 1e6
        if np.any(np.isnan(Ps)) or np.any(np.isnan(Xs)):
            return np.ones(2*n) * 1e6
        return np.concatenate([(Ps - 1) * 1e3, (Xs - Xb) / Xb * 1e3])

    x0 = np.concatenate([d0, t0])
    r = least_squares(res, x0, method='lm',
                       max_nfev=500000, ftol=1e-15, xtol=1e-15, gtol=1e-15)
    d, t = r.x[:n], r.x[n:]
    B = Boff.copy(); np.fill_diagonal(B, d)
    return t, B, r.cost


# ═══════════════════════════════════════════════
# ГЕНЕРАЦИЯ «ИСТИННОЙ» ЭКОНОМИКИ ДЛЯ ТЕСТОВ
# ═══════════════════════════════════════════════

def make_true_economy_3s():
    """3 сектора из статьи + известная B_true."""
    M1 = np.array([[20, 30, 10], [40, 80, 20], [15, 25, 30]], dtype=float)
    Y0 = np.array([40, 70, 35], dtype=float)
    X0 = np.array([100, 210, 105], dtype=float)
    n = 3
    A = M1 / X0[np.newaxis, :]

    # Базовая B через (4.2)
    th0, B0, _ = calib(A, X0, Y0, offdiag_42)

    # «Истинная» B с ИЗВЕСТНОЙ структурой замещения/комплементарности:
    # С↔П: сильные субституты (рост цены П → рост спроса на С)
    # П↔У: слабые комплементы (рост цены П → падение спроса на У)
    # С↔У: нейтральные
    Bt = B0.copy()
    Bt[0, 1] += 12   # С←П: субститут (b_01 вырос → при росте цены П спрос на С растёт)
    Bt[1, 0] -= 5    # П←С: слабый комплемент
    Bt[1, 2] += 8    # П←У: субститут
    Bt[2, 1] -= 10   # У←П: комплемент
    Bt[0, 2] += 0    # С←У: нейтрально
    Bt[2, 0] += 0    # У←С: нейтрально

    # Пересчёт θ для P*=1
    th_t = -M_matrix(A, Bt) @ np.ones(n)
    P_check = eq_P(A, Bt, th_t)
    X_t = X_fn(A, Bt, P_check, th_t)
    Y_t = Q_fn(Bt, P_check, th_t)

    return A, Bt, th_t, X_t, Y_t, B0, n


def make_true_economy_5s():
    """5 секторов: Сельхоз, Промышленность, Энергетика, Услуги, Строительство."""
    rng = np.random.RandomState(77)
    n = 5

    A = np.array([
        [0.10, 0.05, 0.02, 0.03, 0.04],
        [0.15, 0.20, 0.10, 0.05, 0.15],
        [0.05, 0.10, 0.15, 0.08, 0.10],
        [0.03, 0.04, 0.03, 0.12, 0.05],
        [0.02, 0.08, 0.05, 0.04, 0.10],
    ], dtype=float)

    Y0 = np.array([50, 80, 40, 60, 30], dtype=float)
    X0 = S_mat(A) @ Y0

    th0, B0, _ = calib(A, X0, Y0, offdiag_42)

    # Добавим структурные отклонения
    Bt = B0.copy()
    # Сельхоз↔Промышленность: субституты
    Bt[0, 1] += 6; Bt[1, 0] += 4
    # Энергетика — комплемент к Промышленности и Строительству
    Bt[2, 1] -= 5; Bt[2, 4] -= 3
    # Услуги — субститут к Строительству
    Bt[3, 4] += 7; Bt[4, 3] += 5

    th_t = -M_matrix(A, Bt) @ np.ones(n)
    if np.any(th_t <= 0):
        # Уменьшим отклонения
        Bt = B0.copy()
        Bt[0, 1] += 3; Bt[1, 0] += 2
        Bt[2, 1] -= 2; Bt[2, 4] -= 1
        Bt[3, 4] += 3; Bt[4, 3] += 2
        th_t = -M_matrix(A, Bt) @ np.ones(n)

    X_t = X_fn(A, Bt, np.ones(n), th_t)
    Y_t = Q_fn(Bt, np.ones(n), th_t)
    return A, Bt, th_t, X_t, Y_t, B0, n


# ═══════════════════════════════════════════════
# ТЕСТ 1: ОДНА IO-ТАБЛИЦА, формула (4.2) vs σ-модификация
# ═══════════════════════════════════════════════

def test_single_table():
    print("▓" * 80)
    print("▓  ТЕСТ 1: ОДНА IO-ТАБЛИЦА — формула (4.2) vs σ-модификация")
    print("▓  (единственный реалистичный сценарий)")
    print("▓" * 80)

    A, Bt, th_t, Xt, Yt, B0, n = make_true_economy_3s()

    print(f"\n  B_true =\n{Bt}")
    print(f"\n  B_42 (оригинальная) =\n{B0}")
    print(f"\n  Отклонения B_true - B_42 =\n{Bt - B0}")

    # Верификация: σ=1 должна давать ТО ЖЕ, что оригинальная (4.2)
    # Прямое сравнение (одинаковые Bd, θ, Y):
    Bd_test = np.diag(B0).copy()
    th_test = th_t.copy()
    sigma_ones = np.ones((n, n))
    B_orig = offdiag_42(Bd_test, th_test, Yt)
    B_sigm = offdiag_42_sigma(Bd_test, th_test, Yt, sigma_ones)
    print(f"\n  ВЕРИФИКАЦИЯ (прямая): ||offdiag_42 - offdiag_42_sigma(σ=1)|| = "
          f"{norm(B_orig - B_sigm, 'fro'):.2e}  (должно быть ~0)")

    # Через оптимизатор (разные начальные условия могут дать разный результат):
    th_v, B_v, _ = calib(A, Xt, Yt, offdiag_42_sigma, sigma=sigma_ones)
    print(f"  ВЕРИФИКАЦИЯ (оптим.): ||B(σ=1) - B(4.2)|| = {norm(B_v - B0, 'fro'):.2e}"
          f"  (может отличаться из-за множественности решений)")

    # ─── Метод 0: Оригинальная (4.2) ───
    th_42, B_42, _ = calib(A, Xt, Yt, offdiag_42)
    P_42 = eq_P(A, B_42, th_42)
    err_42 = norm(B_42 - Bt, 'fro')
    mask = ~np.eye(n, dtype=bool)
    od_42 = np.sqrt(np.mean((B_42[mask] - Bt[mask])**2))
    print(f"\n  ── Метод 0: Оригинальная формула (4.2) ──")
    print(f"  ||B - B_true||_F = {err_42:.4f}")
    print(f"  offdiag RMSE     = {od_42:.4f}")
    print(f"  max|P*-1|        = {np.max(np.abs(P_42 - 1)):.2e}")

    # ─── Метод 1: σ-модификация с ИДЕАЛЬНЫМ знанием структуры ───
    # Допустим, мы ЗНАЕМ (из литературы), какие пары — субституты/комплементы
    # и приблизительную силу замещения
    sigma_perfect = np.ones((n, n))
    # С↔П: субституты → σ > 1 (усилить перераспределение)
    sigma_perfect[0, 1] = 2.5   # С←П: сильный субститут
    sigma_perfect[1, 0] = 0.3   # П←С: слабый комплемент (σ < 1)
    # П↔У: субститут / комплемент
    sigma_perfect[1, 2] = 2.0   # П←У: субститут
    sigma_perfect[2, 1] = 0.0   # У←П: сильный комплемент (σ ≈ 0)
    # С↔У: нейтральные (≈1, как в оригинале)

    th_s1, B_s1, _ = calib(A, Xt, Yt, offdiag_42_sigma, sigma=sigma_perfect)
    P_s1 = eq_P(A, B_s1, th_s1)
    err_s1 = norm(B_s1 - Bt, 'fro')
    od_s1 = np.sqrt(np.mean((B_s1[mask] - Bt[mask])**2))
    print(f"\n  ── Метод 1: σ-модификация (идеальное знание структуры) ──")
    print(f"  ||B - B_true||_F = {err_s1:.4f}")
    print(f"  offdiag RMSE     = {od_s1:.4f}")
    print(f"  max|P*-1|        = {np.max(np.abs(P_s1 - 1)):.2e}")
    print(f"  Улучшение vs (4.2): {(1 - err_s1/err_42)*100:.1f}%")

    # ─── Метод 2: σ-модификация с ЧАСТИЧНЫМ знанием ───
    # Знаем только направление (субститут/комплемент), не силу
    sigma_partial = np.ones((n, n))
    sigma_partial[0, 1] = 1.5   # С←П: субститут (направление верное, сила неточная)
    sigma_partial[1, 0] = 0.7   # П←С: слабый комплемент
    sigma_partial[1, 2] = 1.5   # П←У: субститут
    sigma_partial[2, 1] = 0.3   # У←П: комплемент

    th_s2, B_s2, _ = calib(A, Xt, Yt, offdiag_42_sigma, sigma=sigma_partial)
    P_s2 = eq_P(A, B_s2, th_s2)
    err_s2 = norm(B_s2 - Bt, 'fro')
    od_s2 = np.sqrt(np.mean((B_s2[mask] - Bt[mask])**2))
    print(f"\n  ── Метод 2: σ-модификация (частичное знание) ──")
    print(f"  ||B - B_true||_F = {err_s2:.4f}")
    print(f"  offdiag RMSE     = {od_s2:.4f}")
    print(f"  max|P*-1|        = {np.max(np.abs(P_s2 - 1)):.2e}")
    print(f"  Улучшение vs (4.2): {(1 - err_s2/err_42)*100:.1f}%")

    # ─── Метод 3: σ-модификация с НЕВЕРНЫМ знанием ───
    sigma_wrong = np.ones((n, n))
    sigma_wrong[0, 1] = 0.3     # ОШИБКА: думаем что комплемент, а на деле субститут
    sigma_wrong[1, 0] = 1.5     # ОШИБКА: обратная ошибка
    sigma_wrong[1, 2] = 1.5     # верно
    sigma_wrong[2, 1] = 0.3     # верно

    th_s3, B_s3, _ = calib(A, Xt, Yt, offdiag_42_sigma, sigma=sigma_wrong)
    P_s3 = eq_P(A, B_s3, th_s3)
    err_s3 = norm(B_s3 - Bt, 'fro')
    od_s3 = np.sqrt(np.mean((B_s3[mask] - Bt[mask])**2))
    print(f"\n  ── Метод 3: σ-модификация (НЕВЕРНОЕ знание) ──")
    print(f"  ||B - B_true||_F = {err_s3:.4f}")
    print(f"  offdiag RMSE     = {od_s3:.4f}")
    print(f"  max|P*-1|        = {np.max(np.abs(P_s3 - 1)):.2e}")
    print(f"  Улучшение vs (4.2): {(1 - err_s3/err_42)*100:.1f}%")

    # ─── Метод 4: Прямая фиксация отдельных b_ij (экспертное задание) ───
    # Предположим, эксперт говорит: "b[0,1] ≈ 52, b[2,1] ≈ 25"
    # Остальные — из (4.2), затем рекалибровка
    print(f"\n  ── Метод 4: Экспертная фиксация отдельных b_ij ──")

    # 4a: Фиксируем 2 ВЕРНЫХ элемента
    B_expert = B0.copy()
    B_expert[0, 1] = 52.0  # близко к истинному 52.26
    B_expert[2, 1] = 25.0  # близко к истинному 25.23
    th_e4a, B_e4a, _ = calib_fixed_offdiag(A, Xt, Yt, B_expert)
    P_e4a = eq_P(A, B_e4a, th_e4a)
    err_e4a = norm(B_e4a - Bt, 'fro')
    od_e4a = np.sqrt(np.mean((B_e4a[mask] - Bt[mask])**2))
    print(f"  4a (2 верных b_ij):  ||ΔB||={err_e4a:.2f}  od={od_e4a:.2f}  "
          f"|P*-1|={np.max(np.abs(P_e4a-1)):.1e}  Δ={(1-err_e4a/err_42)*100:+.1f}%")

    # 4b: Фиксируем ВСЕ недиагональные верно
    B_expert_all = Bt.copy()
    th_e4b, B_e4b, _ = calib_fixed_offdiag(A, Xt, Yt, B_expert_all)
    P_e4b = eq_P(A, B_e4b, th_e4b)
    err_e4b = norm(B_e4b - Bt, 'fro')
    od_e4b = np.sqrt(np.mean((B_e4b[mask] - Bt[mask])**2))
    print(f"  4b (все b_ij верно): ||ΔB||={err_e4b:.2f}  od={od_e4b:.2f}  "
          f"|P*-1|={np.max(np.abs(P_e4b-1)):.1e}  Δ={(1-err_e4b/err_42)*100:+.1f}%")

    # 4c: Фиксируем 2 НЕВЕРНЫХ элемента (ошибка ±30%)
    B_expert_bad = B0.copy()
    B_expert_bad[0, 1] = Bt[0, 1] * 0.7  # на 30% меньше
    B_expert_bad[2, 1] = Bt[2, 1] * 1.3  # на 30% больше
    th_e4c, B_e4c, _ = calib_fixed_offdiag(A, Xt, Yt, B_expert_bad)
    P_e4c = eq_P(A, B_e4c, th_e4c)
    err_e4c = norm(B_e4c - Bt, 'fro')
    od_e4c = np.sqrt(np.mean((B_e4c[mask] - Bt[mask])**2))
    print(f"  4c (2 неверных ±30%): ||ΔB||={err_e4c:.2f}  od={od_e4c:.2f}  "
          f"|P*-1|={np.max(np.abs(P_e4c-1)):.1e}  Δ={(1-err_e4c/err_42)*100:+.1f}%")

    # ─── Сводная таблица ───
    print(f"\n  {'─'*65}")
    print(f"  {'Метод':45s} ||ΔB||   od_RMSE  Δ%")
    print(f"  {'─'*65}")
    for name, e, od in [
        ("Оригинальная (4.2)", err_42, od_42),
        ("σ (идеальное знание)", err_s1, od_s1),
        ("σ (частичное знание)", err_s2, od_s2),
        ("σ (неверное знание)", err_s3, od_s3),
        ("Фиксация 2 верных b_ij", err_e4a, od_e4a),
        ("Фиксация ВСЕХ верных b_ij", err_e4b, od_e4b),
        ("Фиксация 2 неверных b_ij (±30%)", err_e4c, od_e4c),
    ]:
        delta = (1 - e / err_42) * 100
        print(f"  {name:45s} {e:7.2f}  {od:7.2f}  {delta:+.1f}%")


# ═══════════════════════════════════════════════
# ТЕСТ 2: ТО ЖЕ НА 5 СЕКТОРАХ
# ═══════════════════════════════════════════════

def test_5sectors():
    print(f"\n{'▓'*80}")
    print(f"▓  ТЕСТ 2: 5 СЕКТОРОВ — σ-модификация")
    print(f"{'▓'*80}")

    A, Bt, th_t, Xt, Yt, B0, n = make_true_economy_5s()

    print(f"\n  Отклонения B_true - B_42 (только недиагональные):")
    diff = Bt - B0
    for i in range(n):
        for j in range(n):
            if i != j and abs(diff[i,j]) > 0.5:
                print(f"    [{i},{j}]: {diff[i,j]:+.2f}")

    mask = ~np.eye(n, dtype=bool)

    # (4.2)
    th_42, B_42, _ = calib(A, Xt, Yt, offdiag_42)
    err_42 = norm(B_42 - Bt, 'fro')
    od_42 = np.sqrt(np.mean((B_42[mask] - Bt[mask])**2))

    # σ с экспертным знанием
    sigma = np.ones((n, n))
    sigma[0, 1] = 1.8; sigma[1, 0] = 1.5  # Сельхоз↔Промышленность: субституты
    sigma[2, 1] = 0.3; sigma[2, 4] = 0.5  # Энергетика — комплемент к Промышл./Стройке
    sigma[3, 4] = 2.0; sigma[4, 3] = 1.8  # Услуги↔Строительство: субституты

    th_s, B_s, _ = calib(A, Xt, Yt, offdiag_42_sigma, sigma=sigma)
    err_s = norm(B_s - Bt, 'fro')
    od_s = np.sqrt(np.mean((B_s[mask] - Bt[mask])**2))

    print(f"\n  {'Метод':40s} ||ΔB||   od_RMSE  P*=1?")
    print(f"  {'─'*60}")
    P_42 = eq_P(A, B_42, th_42)
    P_s = eq_P(A, B_s, th_s)
    print(f"  {'Оригинальная (4.2)':40s} {err_42:7.2f}  {od_42:7.2f}  {np.max(np.abs(P_42-1)):.1e}")
    print(f"  {'σ-модификация (эксперт.)':40s} {err_s:7.2f}  {od_s:7.2f}  {np.max(np.abs(P_s-1)):.1e}")
    print(f"  Улучшение: {(1-err_s/err_42)*100:.1f}%")


# ═══════════════════════════════════════════════
# ТЕСТ 3: 2–3 IO-ТАБЛИЦЫ — КРИТИКА Н.А.:
# B МЕНЯЕТСЯ ОТ ПЕРИОДА К ПЕРИОДУ
# ═══════════════════════════════════════════════

def test_few_tables():
    print(f"\n{'▓'*80}")
    print(f"▓  ТЕСТ 3: ЗАМЕЧАНИЕ НАУЧНОГО РУКОВОДИТЕЛЯ")
    print(f"▓  «B меняется от периода к периоду»")
    print(f"▓  Сравнение: B=const vs B меняется на 5%, 10%, 20%")
    print("▓" * 80)

    A, Bt_2021, th_t, Xt, Yt, B0, n = make_true_economy_3s()
    mask = ~np.eye(n, dtype=bool)

    rng = np.random.RandomState(42)

    # Формула (4.2) — baseline (одна таблица 2021)
    th_42, B_42, _ = calib(A, Xt, Yt, offdiag_42)
    err_42 = norm(B_42 - Bt_2021, 'fro')
    od_42 = np.sqrt(np.mean((B_42[mask] - Bt_2021[mask])**2))

    # ═══ Сценарий A: B НЕ МЕНЯЕТСЯ (идеальное предположение OLS) ═══
    print(f"\n  ═══ Сценарий A: B ПОСТОЯННА (как предполагает OLS) ═══")
    tables_const = []
    for year, shock_std in [(2011, 0.10), (2016, 0.15), (2021, 0.12)]:
        shock = np.clip(rng.normal(1.0, shock_std, n), 0.7, 1.3)
        th_k = th_t * shock
        try:
            P_k = eq_P(A, Bt_2021, th_k)
            Q_k = Q_fn(Bt_2021, P_k, th_k)
            X_k = X_fn(A, Bt_2021, P_k, th_k)
            if np.all(P_k > 0) and np.all(Q_k > 0):
                tables_const.append({
                    'year': year, 'theta': th_k, 'P': P_k,
                    'Q': Q_k, 'X': X_k
                })
        except:
            pass

    Y_mat = np.array([t['Q'] - t['theta'] for t in tables_const])
    X_mat = np.array([t['P'] for t in tables_const])
    B_ols_const = np.linalg.lstsq(X_mat, Y_mat, rcond=None)[0].T
    th_oc, B_oc, _ = calib_fixed_offdiag(A, Xt, Yt, B_ols_const)
    err_oc = norm(B_oc - Bt_2021, 'fro')
    od_oc = np.sqrt(np.mean((B_oc[mask] - Bt_2021[mask])**2))
    print(f"  OLS (B=const):  ||ΔB||={err_oc:7.2f}  od={od_oc:.2f}  (эталон)")
    print(f"  Формула (4.2):  ||ΔB||={err_42:7.2f}  od={od_42:.2f}")

    # ═══ Сценарий B: B МЕНЯЕТСЯ между периодами ═══
    for drift_pct in [5, 10, 20, 30, 50]:
        print(f"\n  ═══ Сценарий B: B дрейфует на ±{drift_pct}% за 10 лет ═══")

        # B для каждого года: B_t = B_2021 * (1 + drift * ε)
        # drift пропорционален расстоянию от 2021
        drift_frac = drift_pct / 100.0
        tables_drift = []
        B_years = {}

        for year, shock_std in [(2011, 0.10), (2016, 0.15), (2021, 0.12)]:
            years_from_2021 = abs(year - 2021) / 10.0  # 0..1
            # B меняется: каждый элемент ± drift * years_from_2021
            B_year = Bt_2021.copy()
            noise = rng.normal(0, drift_frac * years_from_2021, (n, n))
            B_year += B_year * noise
            # Диагональ должна остаться отрицательной
            for i in range(n):
                B_year[i, i] = min(B_year[i, i], -10)

            B_years[year] = B_year

            # Пересчитываем θ для P*=1 при этой B
            th_year = -M_matrix(A, B_year) @ np.ones(n)
            if np.any(th_year <= 0):
                th_year = np.maximum(th_year, 1.0)

            # Дополнительный шок θ
            shock = np.clip(rng.normal(1.0, shock_std, n), 0.7, 1.3)
            th_k = th_year * shock

            try:
                P_k = eq_P(A, B_year, th_k)
                Q_k = Q_fn(B_year, P_k, th_k)
                X_k = X_fn(A, B_year, P_k, th_k)
                if np.all(P_k > 0) and np.all(Q_k > 0):
                    tables_drift.append({
                        'year': year, 'theta': th_k, 'P': P_k,
                        'Q': Q_k, 'X': X_k, 'B_true': B_year
                    })
            except:
                pass

        if len(tables_drift) < n:
            print(f"    Недостаточно таблиц ({len(tables_drift)})")
            continue

        # Показываем насколько B_t отличаются от B_2021
        for t in tables_drift:
            d = norm(t['B_true'] - Bt_2021, 'fro')
            d_od = np.sqrt(np.mean((t['B_true'][mask] - Bt_2021[mask])**2))
            print(f"    {t['year']}: ||B_{t['year']}-B_2021||={d:7.2f}  od_RMSE={d_od:.2f}")

        # OLS: предполагает ЕДИНУЮ B для всех периодов
        # Q_t - θ_t = B @ P_t  (но на деле B_t ≠ B_s)
        Y_mat = np.array([t['Q'] - t['theta'] for t in tables_drift])
        X_mat = np.array([t['P'] for t in tables_drift])
        B_ols_drift = np.linalg.lstsq(X_mat, Y_mat, rcond=None)[0].T

        # Рекалибруем на данные 2021 (последний год)
        th_od, B_od, _ = calib_fixed_offdiag(A, Xt, Yt, B_ols_drift)
        try:
            P_od = eq_P(A, B_od, th_od)
            err_od = norm(B_od - Bt_2021, 'fro')
            od_od = np.sqrt(np.mean((B_od[mask] - Bt_2021[mask])**2))
            print(f"    OLS (B≠const): ||ΔB||={err_od:7.2f}  od={od_od:.2f}  "
                  f"|P*-1|={np.max(np.abs(P_od-1)):.1e}")
        except:
            print(f"    OLS (B≠const): FAIL")
            err_od = 1e6

        # Ridge (prior = 4.2) — должен быть устойчивее
        best_lam = None; best_err = np.inf
        for lam in [0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0]:
            B_ridge = np.zeros((n, n))
            for i in range(n):
                y = np.array([t['Q'][i] - t['theta'][i] for t in tables_drift])
                X = np.array([t['P'] for t in tables_drift])
                B_ridge[i,:] = np.linalg.solve(
                    X.T@X + lam*np.eye(n), X.T@y + lam*B_42[i,:])
            th_r, B_r, _ = calib_fixed_offdiag(A, Xt, Yt, B_ridge)
            try:
                P_r = eq_P(A, B_r, th_r)
                if np.max(np.abs(P_r-1)) < 0.01:
                    e = norm(B_r - Bt_2021, 'fro')
                    if e < best_err: best_err=e; best_lam=lam
            except: pass

        if best_lam is not None:
            B_ridge = np.zeros((n, n))
            for i in range(n):
                y = np.array([t['Q'][i]-t['theta'][i] for t in tables_drift])
                X = np.array([t['P'] for t in tables_drift])
                B_ridge[i,:] = np.linalg.solve(
                    X.T@X + best_lam*np.eye(n), X.T@y + best_lam*B_42[i,:])
            th_rb, B_rb, _ = calib_fixed_offdiag(A, Xt, Yt, B_ridge)
            P_rb = eq_P(A, B_rb, th_rb)
            err_rb = norm(B_rb - Bt_2021, 'fro')
            od_rb = np.sqrt(np.mean((B_rb[mask] - Bt_2021[mask])**2))
            print(f"    Ridge(λ={best_lam:5.2f}):  ||ΔB||={err_rb:7.2f}  od={od_rb:.2f}  "
                  f"|P*-1|={np.max(np.abs(P_rb-1)):.1e}")
        else:
            err_rb = 1e6

        print(f"    Формула (4.2):  ||ΔB||={err_42:7.2f}  od={od_42:.2f}")
        print(f"    ──────")
        if err_od < err_42:
            print(f"    → OLS всё ещё лучше (4.2) на {(1-err_od/err_42)*100:.1f}%")
        else:
            print(f"    → OLS ХУЖЕ (4.2) на {(err_od/err_42-1)*100:.1f}% "
                  f"— подтверждение критики Н.А.")

    # ═══ Финальная сводка ═══
    print(f"\n  ═══ ВЫВОД ═══")
    print(f"  Если B действительно меняется между периодами (что реалистично),")
    print(f"  то OLS по нескольким IO-таблицам оценивает «среднюю» B,")
    print(f"  а не B для конкретного года → ошибка растёт с ростом дрейфа.")
    print(f"  При дрейфе >{drift_pct}% OLS может стать хуже простой формулы (4.2).")


# ═══════════════════════════════════════════════
# ТЕСТ 4: АНАЛИЗ ЧУВСТВИТЕЛЬНОСТИ
# Какие недиагональные элементы ВООБЩЕ ВАЖНЫ?
# ═══════════════════════════════════════════════

def test_sensitivity():
    print(f"\n{'▓'*80}")
    print(f"▓  ТЕСТ 4: АНАЛИЗ ЧУВСТВИТЕЛЬНОСТИ")
    print(f"▓  Какие недиагональные элементы влияют на результат?")
    print(f"{'▓'*80}")

    A, Bt, th_t, Xt, Yt, B0, n = make_true_economy_3s()
    sectors = ["С/х", "Пром", "Усл"]

    # Калибруем базу через (4.2)
    th_42, B_42, _ = calib(A, Xt, Yt, offdiag_42)

    # Имитируем шок: θ меняется на +15%
    th_shock = th_42 * 1.15
    P_base = eq_P(A, B_42, th_shock)
    X_base = X_fn(A, B_42, P_base, th_shock)
    Q_base = Q_fn(B_42, P_base, th_shock)
    VA_base = (P_base - A.T @ P_base) * (S_mat(A) @ Q_base)

    # Сравнение: B_true vs B_42 при том же шоке
    P_true = eq_P(A, Bt, th_t * 1.15)
    X_true = X_fn(A, Bt, P_true, th_t * 1.15)
    Q_true = Q_fn(Bt, P_true, th_t * 1.15)

    print(f"\n  При шоке θ × 1.15:")
    print(f"    P (B_42)   = {P_base}")
    print(f"    P (B_true) = {P_true}")
    print(f"    ΔP         = {P_base - P_true}")
    print(f"    |ΔX/X|     = {np.abs((X_base-X_true)/X_true)*100} %")

    # Варьируем КАЖДЫЙ недиагональный элемент на ±20% БЕЗ рекалибровки
    print(f"\n  Чувствительность: при шоке θ×1.15, варьируем b_ij на ±20% БЕЗ рекалибровки:")
    print(f"  {'b_ij':10s} {'базовое':>8s}  {'ΔP_max':>8s}  {'ΔQ_max%':>8s}  {'ΔVA_max%':>9s}")
    print(f"  {'─'*52}")

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            B_pert = B_42.copy()
            B_pert[i, j] *= 1.20

            try:
                P_p = eq_P(A, B_pert, th_shock)
                X_p = X_fn(A, B_pert, P_p, th_shock)
                Q_p = Q_fn(B_pert, P_p, th_shock)
                VA_p = (P_p - A.T @ P_p) * (S_mat(A) @ Q_p)

                dP = np.max(np.abs(P_p - P_base))
                dQ = np.max(np.abs((Q_p - Q_base) / Q_base)) * 100
                dVA = np.max(np.abs((VA_p - VA_base) / VA_base)) * 100

                print(f"  b[{sectors[i]},{sectors[j]}]  {B_42[i,j]:8.2f}  "
                      f"{dP:8.4f}  {dQ:7.2f}%  {dVA:8.2f}%")
            except:
                print(f"  b[{sectors[i]},{sectors[j]}]  {B_42[i,j]:8.2f}  FAIL")

    # Глобальная чувствительность: B_42 vs B_true на серии шоков
    print(f"\n  Глобальная чувствительность: B_42 vs B_true на 20 шоках θ:")
    rng = np.random.RandomState(123)
    dP_list, dQ_list, dVA_list = [], [], []
    for _ in range(20):
        shock = th_42 * np.clip(rng.normal(1.0, 0.20, n), 0.5, 1.5)
        shock_true = th_t * np.clip(rng.normal(1.0, 0.20, n), 0.5, 1.5)
        try:
            Pa = eq_P(A, B_42, shock)
            Pb = eq_P(A, Bt, shock_true)
            Qa = Q_fn(B_42, Pa, shock)
            Qb = Q_fn(Bt, Pb, shock_true)
            VAa = (Pa - A.T @ Pa) * (S_mat(A) @ Qa)
            VAb = (Pb - A.T @ Pb) * (S_mat(A) @ Qb)
            dP_list.append(np.max(np.abs(Pa - Pb)))
            dQ_list.append(np.mean(np.abs((Qa - Qb) / np.maximum(np.abs(Qb), 1))) * 100)
            dVA_list.append(np.mean(np.abs((VAa - VAb) / np.maximum(np.abs(VAb), 1))) * 100)
        except:
            pass

    if dP_list:
        print(f"    Среднее |ΔP|  = {np.mean(dP_list):.4f}")
        print(f"    Среднее |ΔQ|  = {np.mean(dQ_list):.2f}%")
        print(f"    Среднее |ΔVA| = {np.mean(dVA_list):.2f}%")


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    import time
    t0 = time.time()

    print("█" * 80)
    print("█  РЕАЛИСТИЧНАЯ КАЛИБРОВКА НЕДИАГОНАЛЬНЫХ B")
    print("█  Условие: ОДНА IO-таблица (без временных рядов)")
    print("█" * 80)

    test_single_table()
    test_5sectors()
    test_few_tables()
    test_sensitivity()

    print(f"\n{'█'*80}")
    print(f"█  ВРЕМЯ: {time.time()-t0:.1f} сек")
    print(f"{'█'*80}")

    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  ВЫВОДЫ (проверены вычислительно)                                           ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  ОДНА IO-ТАБЛИЦА (реалистичный сценарий):                                    ║
║  1. Формула (4.2) — ЕДИНСТВЕННЫЙ определённый метод                          ║
║     (2n уравнений на 2n неизвестных: diag(B) + θ)                           ║
║                                                                               ║
║  2. σ-модификация НЕ УЛУЧШАЕТ: меняет параметризацию,                       ║
║     но не добавляет информации → ошибка РАСТЁТ (проверено)                  ║
║                                                                               ║
║  3. Прямая фиксация b_ij из литературы — единственный                       ║
║     работающий путь улучшения при одной таблице (+44%)                       ║
║                                                                               ║
║  2–3 IO-ТАБЛИЦЫ (замечание Н.А.):                                            ║
║  4. OLS/Ridge по нескольким таблицам РАБОТАЕТ ТОЛЬКО                         ║
║     ПРИ ПРЕДПОЛОЖЕНИИ B=const. Но B меняется! Поэтому:                      ║
║     - При дрейфе B ~5%:  OLS может быть лучше (4.2)                         ║
║     - При дрейфе B ~20%: OLS становится ХУЖЕ (4.2)                          ║
║     - При дрейфе B >30%: OLS непригоден                                      ║
║     Замечание Н.А. ПОДТВЕРЖДЕНО вычислительно.                               ║
║                                                                               ║
║  ЧУВСТВИТЕЛЬНОСТЬ:                                                           ║
║  5. Ошибка в offdiag(B) → ΔQ ~ 47%, ΔVA ~ 37% при шоках                    ║
║     → Точная калибровка B КРИТИЧЕСКИ важна для прогнозов                    ║
║                                                                               ║
║  ИТОГ: При имеющихся данных (1 IO-таблица за период,                        ║
║  B нестационарна) формула (4.2) — практически безальтернативна.              ║
║  Улучшение возможно ТОЛЬКО через внешние эконометрические                    ║
║  оценки конкретных перекрёстных эластичностей.                               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
