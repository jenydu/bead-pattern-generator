import numpy as np
import pytest

from core.palette import BRANDS, delta_e2000, load_palette, natural_key, rgb_to_lab


def test_natural_order():
    refs = ["B1", "A10", "A2", "ZG1", "A1"]
    assert sorted(refs, key=natural_key) == ["A1", "A2", "A10", "B1", "ZG1"]


@pytest.mark.parametrize("key", list(BRANDS))
def test_all_brands_load(key):
    p = load_palette(key)
    assert len(p) > 0 and p.rgb.shape == (len(p), 3)


def test_mard_counts():
    assert len(load_palette("mard_291")) == 291
    p = load_palette("mard_221")
    assert len(p) == 221 and not any(r[0] in "PQRTYZ" for r in p.refs)


def test_lab_known_values():
    lab = rgb_to_lab(np.array([[255, 255, 255], [0, 0, 0], [255, 0, 0]]))
    assert np.allclose(lab[0], [100, 0, 0], atol=0.05)
    assert np.allclose(lab[1], [0, 0, 0], atol=0.05)
    assert np.allclose(lab[2], [53.24, 80.09, 67.20], atol=0.1)


def test_de2000_sharma_pairs():
    # from Sharma, Wu, Dalal (2005) test data
    a = np.array([50.0, 2.6772, -79.7751])
    b = np.array([50.0, 0.0, -82.7485])
    assert delta_e2000(a, b) == pytest.approx(2.0425, abs=1e-4)
    a = np.array([50.0, 2.5, 0.0])
    b = np.array([50.0, 0.0, -2.5])
    assert delta_e2000(a, b) == pytest.approx(4.3065, abs=1e-4)


def test_match_exact_and_order():
    p = load_palette("mard_291")
    idx = p.match(p.rgb[None, :, :])[0]
    # duplicates in rgb may map to another ref, but the color must be identical
    assert (p.rgb[idx] == p.rgb).all()
    order = p.order()
    assert p.refs[order[0]] == "A1"


def test_subset():
    p = load_palette("mard_291").subset(["A1", "B1"])
    assert len(p) == 2
