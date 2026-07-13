"""First-run onboarding wizard tests (headless Qt)."""

from __future__ import annotations

from dictux.config import Config
from dictux.onboarding import OnboardingWindow


def test_navigation_and_button_labels(qapp):
    done = []
    w = OnboardingWindow(Config(), on_done=done.append)
    assert w.stack.currentIndex() == 0
    assert w.next_btn.text() == "Next"
    assert not w.skip_btn.isHidden()

    last = w.stack.count() - 1
    for _ in range(last):
        w._on_next()
    assert w.stack.currentIndex() == last
    assert w.next_btn.text() == "Get started"
    assert w.skip_btn.isHidden()              # no skip on the final page

    w._go_back()
    assert w.stack.currentIndex() == last - 1


def test_finish_applies_config(qapp):
    done = []
    w = OnboardingWindow(Config(model="base", language="auto"), on_done=done.append)
    w.lang_combo.setCurrentIndex(w.lang_combo.findData("fr"))
    w.model_combo.setCurrentIndex(w.model_combo.findData("turbo-large"))

    w._finish()

    assert done, "on_done should fire"
    cfg = done[0]
    assert cfg.language == "fr"
    assert cfg.model == "turbo-large"
    assert cfg.compute_type == "float16"      # Turbo V3 large preset applied
    assert cfg.onboarded is True


def test_finish_keeps_explicit_language_over_model_preset(qapp):
    done = []
    w = OnboardingWindow(Config(), on_done=done.append)
    w.lang_combo.setCurrentIndex(w.lang_combo.findData("en"))
    w.model_combo.setCurrentIndex(w.model_combo.findData("turbo-hebrew"))
    w._finish()
    # User chose English on the language step; the Hebrew model must not override it.
    assert done[0].language == "en"


def test_skip_marks_onboarded(qapp):
    done = []
    w = OnboardingWindow(Config(), on_done=done.append)
    w.skip_btn.click()
    assert done and done[0].onboarded is True
