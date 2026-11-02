"""WHO 锚点表移植校验：与客户端 growth.js percentileOf 同结果。"""
from app.domain import growth_lms


def test_bands_at_interpolation():
    bands = growth_lms.bands_at("weight", "boy", 0.5)
    # 0 月 P50=3.3，1 月 P50=4.5 → 线性中点
    assert abs(bands[2] - 3.9) < 1e-9
    assert len(bands) == 5


def test_percentile_at_anchor():
    assert abs(growth_lms.percentile_of("weight", "boy", 0, 3.3) - 50) < 1e-9


def test_percentile_mid_segment():
    # P50=3.3 → P85=3.8，值 3.55 → 67.5
    p = growth_lms.percentile_of("weight", "boy", 0, 3.55)
    assert abs(p - 67.5) < 1e-6


def test_percentile_clamped():
    assert growth_lms.percentile_of("weight", "boy", 0, 0.5) == 0.1
    assert growth_lms.percentile_of("weight", "boy", 0, 99) == 99.9


def test_girl_table():
    assert abs(growth_lms.percentile_of("height", "girl", 0, 49.1) - 50) < 1e-9


def test_z_score():
    assert abs(growth_lms.z_from_percentile(50)) < 1e-6
    assert abs(growth_lms.z_from_percentile(97.5) - 1.96) < 0.01
    assert abs(growth_lms.z_from_percentile(2.5) + 1.96) < 0.01


def test_standard_version():
    assert growth_lms.standard_version() == "who-2006-anchor-v1"
