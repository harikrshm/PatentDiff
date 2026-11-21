"""Heatmap cell text must contrast with the fill it sits on, in both themes."""
import pytest

from app_workbench import theme

RATES = [i / 20 for i in range(21)]


def _contrast_at(rate, dark):
    fill = theme._fill_at((theme._DARK if dark else theme._LIGHT)["fail"], rate)
    return theme._contrast(fill, theme._rgb(theme.cell_text_color(rate, dark)))


@pytest.mark.parametrize("dark", [False, True])
def test_text_never_drops_below_4_to_1_anywhere_on_the_scale(dark):
    assert min(_contrast_at(r, dark) for r in RATES) >= 4.0


def test_dark_low_end_gets_light_text():
    # Regression: a rate>=0.75 threshold put near-black text on the dark teal 0% cell.
    assert theme.cell_text_color(0.0, dark=True) == theme._DARK["cell_text_high"]
    assert _contrast_at(0.0, True) >= 7.0


def test_light_orange_band_gets_dark_text():
    # Regression: white on #DC8A52-ish orange is ~2.7:1; dark text is ~5.
    assert theme.cell_text_color(0.8, dark=False) == theme._LIGHT["cell_text_low"]
