"""月龄 / 早产矫正口径校验（domain/dates.py）。"""
from app.domain.dates import age_months, age_text


def test_term_baby_no_correction():
    # 足月 40 周：不回拨
    assert abs(age_months("2026-01-01", "2026-04-01", 40) - 3.0) < 1e-9


def test_premature_corrected_before_due_date():
    # 早产 32 周、未满预产期：矫正月龄应小于实际月龄
    corrected = age_months("2026-01-01", "2026-01-20", 32)
    actual = age_months("2026-01-01", "2026-01-20", 40)
    assert corrected < actual


def test_correction_stops_after_due_date():
    # 满预产期（birth + 8 周）后不再矫正：早产与足月月龄一致
    corrected = age_months("2026-01-01", "2026-03-02", 32)
    actual = age_months("2026-01-01", "2026-03-02", 40)
    assert abs(corrected - actual) < 1e-9


def test_age_text_actual_months_day_baseline():
    # 文字月龄按实际日历年龄：整月当天 0 天，过 9 天为 3 个月 9 天
    assert age_text("2026-01-01", "2026-04-01", 32) == "3 个月"
    assert age_text("2026-01-01", "2026-04-10", 32) == "3 个月 9 天"


def test_age_text_newborn_days():
    assert age_text("2026-01-01", "2026-01-08", 40) == "7 天"
