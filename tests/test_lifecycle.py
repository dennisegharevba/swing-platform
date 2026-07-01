"""
Test Suite — Signal Lifecycle & Countdown System
=================================================
Covers the pure, DB-free logic in src/signals/lifecycle.py:
- Session classification
- Signal age buckets
- Countdown formatting
- Status state machine (target/stop hits, near-stop, expiry, extension)
- MFE/MAE tracking
- P/L computation
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.core.config import Direction
from src.signals.lifecycle import (
    AGE_AGING,
    AGE_DEVELOPING,
    AGE_EXPIRED,
    AGE_FRESH,
    AGE_MATURE,
    SESSION_AFTER_HOURS,
    SESSION_ASIAN,
    SESSION_LONDON,
    SESSION_NEW_YORK,
    SESSION_PREMARKET,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_EXTENDED_TREND,
    STATUS_FINAL_TARGET_HIT,
    STATUS_NEAR_STOP,
    STATUS_STOP_HIT,
    STATUS_TARGET_1_HIT,
    TERMINAL_STATUSES,
    classify_session,
    compute_pnl_pct,
    evaluate_status,
    format_countdown,
    signal_age_bucket,
    update_extremes,
)


# ── Sessions ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hour,expected", [
    (0, SESSION_ASIAN),
    (6, SESSION_ASIAN),
    (7, SESSION_LONDON),
    (10, SESSION_LONDON),
    (11, SESSION_PREMARKET),
    (12, SESSION_PREMARKET),
    (13, SESSION_NEW_YORK),
    (20, SESSION_NEW_YORK),
    (21, SESSION_AFTER_HOURS),
    (23, SESSION_ASIAN),
])
def test_classify_session(hour, expected):
    dt = datetime(2026, 6, 1, hour, 0, 0)
    assert classify_session(dt) == expected


# ── Signal age ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours,expected", [
    (0, AGE_FRESH),
    (23, AGE_FRESH),
    (25, AGE_DEVELOPING),
    (71, AGE_DEVELOPING),
    (73, AGE_MATURE),
    (167, AGE_MATURE),
    (169, AGE_AGING),
    (335, AGE_AGING),
    (337, AGE_EXPIRED),
])
def test_signal_age_bucket(hours, expected):
    assert signal_age_bucket(timedelta(hours=hours)) == expected


def test_signal_age_bucket_negative_clamped_to_fresh():
    assert signal_age_bucket(timedelta(hours=-5)) == AGE_FRESH


# ── Countdown formatting ─────────────────────────────────────────────────────

def test_format_countdown_days_hours_minutes():
    assert format_countdown(timedelta(days=2, hours=4, minutes=13)) == "2d 04h 13m"


def test_format_countdown_hours_only():
    assert format_countdown(timedelta(hours=3, minutes=5, seconds=9)) == "3h 05m 09s"


def test_format_countdown_minutes_only():
    assert format_countdown(timedelta(minutes=7, seconds=2)) == "7m 02s"


def test_format_countdown_overdue_is_negative():
    result = format_countdown(timedelta(days=-1, hours=-2))
    assert result.startswith("-")


# ── Status state machine ─────────────────────────────────────────────────────

NOW = datetime(2026, 6, 15, 12, 0, 0)


def test_long_hits_stop():
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=94, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=NOW,
    )
    assert status == STATUS_STOP_HIT


def test_short_hits_stop():
    status = evaluate_status(
        Direction.SHORT, entry=100, stop_loss=105, take_profit_1=90, take_profit_2=80,
        current_price=106, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=NOW,
    )
    assert status == STATUS_STOP_HIT


def test_long_hits_target_1_then_stays_open():
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=111, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=NOW,
    )
    assert status == STATUS_TARGET_1_HIT


def test_target_1_status_persists_even_if_price_pulls_back():
    # Price already tagged TP1 last update; now it's drifted back below TP1
    # but not near the stop -- should remain target_1_hit, not revert to active.
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=108, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_TARGET_1_HIT, now=NOW,
    )
    assert status == STATUS_TARGET_1_HIT


def test_long_hits_final_target():
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=121, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_TARGET_1_HIT, now=NOW,
    )
    assert status == STATUS_FINAL_TARGET_HIT


def test_short_hits_final_target():
    status = evaluate_status(
        Direction.SHORT, entry=100, stop_loss=105, take_profit_1=90, take_profit_2=80,
        current_price=79, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=NOW,
    )
    assert status == STATUS_FINAL_TARGET_HIT


def test_near_stop_flagged_before_stop_hit():
    # Risk distance is 5 (100 -> 95). 75%+ consumed = price <= 96.25, but not <= 95.
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=96, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=NOW,
    )
    assert status == STATUS_NEAR_STOP


def test_terminal_status_never_changes():
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=200, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_STOP_HIT, now=NOW,
    )
    assert status == STATUS_STOP_HIT


def test_expiry_with_loss_becomes_expired():
    later = NOW + timedelta(days=15)
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=99, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=later,
    )
    assert status == STATUS_EXPIRED


def test_expiry_with_profit_becomes_extended_trend():
    later = NOW + timedelta(days=15)
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=105, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=later,
    )
    assert status == STATUS_EXTENDED_TREND


def test_within_hold_window_stays_active():
    soon = NOW + timedelta(days=2)
    status = evaluate_status(
        Direction.LONG, entry=100, stop_loss=95, take_profit_1=110, take_profit_2=120,
        current_price=102, opened_at=NOW, expected_hold_days=10, prior_status=STATUS_ACTIVE, now=soon,
    )
    assert status == STATUS_ACTIVE


def test_all_terminal_statuses_are_covered_in_labels():
    from src.signals.lifecycle import STATUS_LABELS
    for status in TERMINAL_STATUSES:
        assert status in STATUS_LABELS


# ── P/L and MFE/MAE ──────────────────────────────────────────────────────────

def test_compute_pnl_pct_long_profit():
    assert compute_pnl_pct(Direction.LONG, 100, 110) == 10.0


def test_compute_pnl_pct_short_profit():
    assert compute_pnl_pct(Direction.SHORT, 100, 90) == 10.0


def test_compute_pnl_pct_zero_entry_safe():
    assert compute_pnl_pct(Direction.LONG, 0, 100) == 0.0


def test_update_extremes_tracks_best_and_worst():
    mfe, mae = update_extremes(Direction.LONG, 100, 105, prior_mfe_pct=2.0, prior_mae_pct=-1.0)
    assert mfe == 5.0
    assert mae == -1.0  # unchanged -- 105 isn't a new worst

    mfe2, mae2 = update_extremes(Direction.LONG, 100, 97, prior_mfe_pct=mfe, prior_mae_pct=mae)
    assert mfe2 == 5.0  # unchanged -- 97 isn't a new best
    assert mae2 == -3.0


def test_update_extremes_short_direction():
    mfe, mae = update_extremes(Direction.SHORT, 100, 90, prior_mfe_pct=0.0, prior_mae_pct=0.0)
    assert mfe == 10.0
    assert mae == 0.0
