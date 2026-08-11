"""Курируемая политика изменения частоты для мировых рядов.

Наличие подходящей единицы само по себе не доказывает метод агрегации. Поэтому
каждый разрешённый dataset фиксируется явно; всё остальное остаётся fail-closed.
Официальный ряд нужной частоты всегда имеет приоритет над расчётным.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

AggregationPolicy = Literal["sum", "mean", "last"]

_CURATED_POLICIES: dict[tuple[str, str], AggregationPolicy] = {
    # Индексы и балансы обследований: квартал/год = среднее месячных уровней.
    ("prc_hicp_midx", "I15"): "mean",
    ("prc_fpmt_m", "I25"): "mean",
    ("prc_hicp_cind", "I15"): "mean",
    ("prc_hicp_ct", "I15"): "mean",
    ("prc_hicp_fp", "I15"): "mean",
    ("prc_hicp_fpd", "I15"): "mean",
    ("prc_hicp_minr", "I15"): "mean",
    ("prc_ipc_g20", "I15"): "mean",
    ("ei_isbu_m", "I2015"): "mean",
    ("ei_isrt_m", "I15"): "mean",
    ("ei_issp_m", "I21"): "mean",
    ("ei_mfef_m", "I15"): "mean",
    ("ert_eff_ic_m", "I15"): "mean",
    ("ei_bsee_m_r2", "INX"): "mean",
    ("ei_bslh_m_r2", "INX"): "mean",
    ("ei_bsbu_m_r2", ""): "mean",
    ("ei_bssi_m_r2", ""): "mean",
    ("ei_bsco_m", "BAL"): "mean",
    ("ei_bsin_m_r2", "BAL"): "mean",
    ("ei_bsrt_m_r2", "BAL"): "mean",
    ("ei_bsse_m_r2", "BAL"): "mean",
    ("sts_cobp_m", "I15"): "mean",
    ("sts_colb_m", "I15"): "mean",
    ("sts_copi_m", "I15"): "mean",
    ("sts_copr_m", "I15"): "mean",
    ("sts_inlb_m", "I15"): "mean",
    ("sts_inpi_m", "I15"): "mean",
    ("sts_inpp_m", "I15"): "mean",
    ("sts_inppd_m", "I15"): "mean",
    ("sts_inppnd_m", "I15"): "mean",
    ("sts_inpr_m", "I15"): "mean",
    ("sts_intv_m", "I15"): "mean",
    ("sts_intvd_m", "I15"): "mean",
    ("sts_intvnd_m", "I15"): "mean",
    ("sts_rb_m", "I15"): "mean",
    ("sts_selb_m", "I15"): "mean",
    ("sts_trlb_m", "I15"): "mean",
    ("sts_trtu_m", "I15"): "mean",
    # Ставки, доли и среднемесячная численность — среднее за период.
    ("ei_mfir_m", ""): "mean",
    ("irt_lt_mcby_m", ""): "mean",
    ("irt_st_m", ""): "mean",
    ("une_rt_m", "PC_ACT"): "mean",
    ("une_rt_m", "THS_PER"): "mean",
    ("ei_lmhr_m", "PC_ACT"): "mean",
    ("ei_lmhu_m", "THS_PER"): "mean",
    ("tour_occ_mnor", "PC"): "mean",
    # Месячные потоки энергии и торговли суммируются.
    ("ei_etea_m", "MIO_EUR_SA"): "sum",
    ("ei_eteu27_2020_m", "MIO_EUR_SA"): "sum",
    ("nrg_cb_cosm", ""): "sum",
    ("nrg_cb_eim", "GWH"): "sum",
    ("nrg_cb_em", "GWH"): "sum",
    ("nrg_cb_gasm", "MIO_M3"): "sum",
    ("nrg_cb_oilm", "THS_T"): "sum",
    ("nrg_cb_sffm", "THS_T"): "sum",
    ("nrg_chdd_m", "NR"): "sum",
    ("nrg_chddr2_m", "NR"): "sum",
    ("nrg_te_gasm", "MIO_M3"): "sum",
    ("nrg_te_oilm", "THS_T"): "sum",
    ("nrg_ti_gasm", "MIO_M3"): "sum",
    ("nrg_ti_oilm", "THS_T"): "sum",
    # Запасы — состояние на конец квартала/года.
    ("nrg_stk_gasm", "MIO_M3"): "last",
    ("nrg_stk_oem", "NR"): "last",
    ("nrg_stk_oilm", "THS_T"): "last",
    ("nrg_stk_oom", "THS_T"): "last",
}

# Квартальные уровни → год. Пары перечислены явно: даже внутри одного раздела
# готовые темпы (PCH_SM) и доли ВВП не усредняются без исходных числителя и
# знаменателя. Рынок труда — среднее четырёх квартальных оценок; индексы и
# балансы — среднегодовой уровень; потоки — сумма четырёх кварталов.
_QUARTERLY_MEAN_BY_UNIT: dict[str, frozenset[str]] = {
    "": frozenset({
        "ei_bsin_q_r2", "ei_lmjv_q_r2",
    }),
    "BAL": frozenset({
        "ei_bsbu_q_r2", "ei_bsco_q", "ei_bsse_q_r2",
    }),
    "I15": frozenset({
        "ei_isind_q", "ei_isrt_q", "ei_isset_q", "namq_10_lp_ulc",
        "sts_colb_q", "sts_copi_q", "sts_copr_q", "sts_inlb_q",
        "sts_rb_q", "sts_selb_q", "sts_trlb_q", "sts_trtu_q",
    }),
    "I15_Q": frozenset({
        "prc_hpi_ooq", "prc_hpi_q",
    }),
    "I21": frozenset({
        "lfsi_ahw_q",
    }),
    "I2021": frozenset({
        "ei_isppi_q",
    }),
    "I2015": frozenset({
        "ei_isbu_q",
    }),
    "I25_NSA": frozenset({
        "ei_hppi_q",
    }),
    "PC_ACT": frozenset({
        "une_ltu_q", "une_rt_q",
    }),
    "PC_POP": frozenset({
        "lfsi_educ_q", "lfsi_emp_q", "lfsi_neet_q", "lfsi_sup_q",
    }),
    "PC": frozenset({
        "lfsq_argacob", "lfsq_argaed", "lfsq_argan", "lfsq_eppga",
        "lfsq_ergacob", "lfsq_ergan", "lfsq_etpga", "lfsq_ipga",
        "lfsq_upgal", "lfsq_urgacob", "lfsq_urgaed", "lfsq_urgan",
    }),
    "HR": frozenset({
        "lfsq_ewh2n2", "lfsq_ewhais", "lfsq_ewhan2", "lfsq_ewhuis",
        "lfsq_ewhun2",
    }),
    "THS": frozenset({
        "lfsi_abt_q", "lfsi_lea_q", "lfsi_sta_q",
    }),
    "THS_PER": frozenset({
        "lfsi_long_q", "lfsi_pt_q", "lfsi_sla_q",
        "lfsq_agacob", "lfsq_agaed", "lfsq_agan",
        "lfsq_e2ged", "lfsq_e2gis", "lfsq_e2gps",
        "lfsq_eegaed", "lfsq_eegais", "lfsq_eegan2", "lfsq_eftpt",
        "lfsq_egacob", "lfsq_egaed", "lfsq_egais", "lfsq_egan",
        "lfsq_egan2", "lfsq_egan22d", "lfsq_egaps", "lfsq_egdn2",
        "lfsq_egised", "lfsq_eisn2", "lfsq_epgaed", "lfsq_epgais",
        "lfsq_epgan2", "lfsq_esgaed", "lfsq_esgais", "lfsq_esgan2",
        "lfsq_etgadc", "lfsq_etgaed", "lfsq_etgais", "lfsq_etgan2",
        "lfsq_igacob", "lfsq_igaed", "lfsq_igan", "lfsq_igaww",
        "lfsq_pgacws", "lfsq_pgaed", "lfsq_sup_edu",
        "lfsq_ugacob", "lfsq_ugad", "lfsq_ugan",
        "namq_10_a10_e", "namq_10_pe",
        "tour_lfsq1r2", "tour_lfsq2r2", "tour_lfsq3r2",
        "tour_lfsq4r2", "tour_lfsq5r2", "tour_lfsq6r2",
        "une_rt_q",
    }),
}

_QUARTERLY_SUM_BY_UNIT: dict[str, frozenset[str]] = {
    "CLV15_MEUR": frozenset({
        "namq_10_exi", "namq_10_gdp",
    }),
    "EUR": frozenset({
        "prc_hpi_hsvq",
    }),
    "NR": frozenset({
        "prc_hpi_hsnq",
    }),
    "THS_T": frozenset({
        "road_go_ctq_tt", "road_go_iq_ltt", "road_go_iq_utt",
        "road_go_tq_tott",
    }),
}

for _unit, _datasets in _QUARTERLY_MEAN_BY_UNIT.items():
    _CURATED_POLICIES.update({(_dataset, _unit): "mean" for _dataset in _datasets})
for _unit, _datasets in _QUARTERLY_SUM_BY_UNIT.items():
    _CURATED_POLICIES.update({(_dataset, _unit): "sum" for _dataset in _datasets})


def _unit_code(indicator: Any) -> str:
    return (getattr(indicator, "unit", None) or "").strip().upper().replace("-", "_")


def aggregation_policy_for(indicator: Any) -> AggregationPolicy | None:
    """Вернуть доказуемую политику либо None для неизвестной семантики."""
    dataset_id = (getattr(indicator, "dataset_id", None) or "").strip().lower()
    unit = _unit_code(indicator)
    return _CURATED_POLICIES.get((dataset_id, unit))


def aggregate_series(
    series: list[tuple[date, float]],
    *,
    source_frequency: str,
    target_frequency: str,
    policy: AggregationPolicy,
) -> list[tuple[date, float]]:
    """Агрегировать только полные календарные периоды."""
    source = source_frequency.strip().lower()
    target = target_frequency.strip().lower()
    if (source, target) not in {
        ("monthly", "quarterly"),
        ("monthly", "annual"),
        ("quarterly", "annual"),
    }:
        raise ValueError(f"unsupported aggregation: {source} -> {target}")

    buckets: dict[tuple[int, int], dict[tuple[int, int], float]] = {}
    for point_date, raw_value in sorted(series, key=lambda point: point[0]):
        if target == "quarterly":
            period = (point_date.year, (point_date.month - 1) // 3 + 1)
        else:
            period = (point_date.year, 1)
        observation = (
            (point_date.year, point_date.month)
            if source == "monthly"
            else (point_date.year, (point_date.month - 1) // 3 + 1)
        )
        buckets.setdefault(period, {})[observation] = float(raw_value)

    expected = 3 if (source, target) == ("monthly", "quarterly") else (
        12 if source == "monthly" else 4
    )
    result: list[tuple[date, float]] = []
    for (year, period_no), observations in sorted(buckets.items()):
        if len(observations) != expected:
            continue
        values = [observations[key] for key in sorted(observations)]
        if policy == "sum":
            value = sum(values)
        elif policy == "mean":
            value = sum(values) / len(values)
        elif policy == "last":
            value = values[-1]
        else:
            raise ValueError(f"unknown aggregation policy: {policy}")
        month = (period_no - 1) * 3 + 1 if target == "quarterly" else 1
        result.append((date(year, month, 1), round(value, 4)))
    return result
