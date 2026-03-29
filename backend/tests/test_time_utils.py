"""Unit tests for app.cubes.utils.time_utils."""

import time

import pytest

from app.cubes.utils.time_utils import (
    TIME_MODE_PARAMS,
    epoch_cutoff,
    validate_datetime_pair,
)


# epoch_cutoff tests

def test_epoch_cutoff_lookback():
    """epoch_cutoff(604800) returns approximately int(time.time()) - 604800."""
    expected = int(time.time()) - 604800
    result = epoch_cutoff(604800)
    assert abs(result - expected) < 2


def test_epoch_cutoff_zero():
    """epoch_cutoff(0) returns approximately int(time.time())."""
    expected = int(time.time())
    result = epoch_cutoff(0)
    assert abs(result - expected) < 2


# validate_datetime_pair tests

def test_validate_datetime_pair_neither_provided():
    """validate_datetime_pair(None, None) returns None — valid (neither provided)."""
    assert validate_datetime_pair(None, None) is None


def test_validate_datetime_pair_both_provided():
    """validate_datetime_pair('123', '456') returns None — valid (both provided)."""
    assert validate_datetime_pair("123", "456") is None


def test_validate_datetime_pair_start_only():
    """validate_datetime_pair('123', None) returns error dict for partial input."""
    result = validate_datetime_pair("123", None)
    assert isinstance(result, dict)
    assert "error" in result
    assert "start_time provided but end_time is missing" in result["error"]


def test_validate_datetime_pair_end_only():
    """validate_datetime_pair(None, '456') returns error dict for partial input."""
    result = validate_datetime_pair(None, "456")
    assert isinstance(result, dict)
    assert "error" in result
    assert "end_time provided but start_time is missing" in result["error"]


# TIME_MODE_PARAMS tests

def test_time_mode_params_length():
    """TIME_MODE_PARAMS contains exactly 4 ParamDefinition objects."""
    assert len(TIME_MODE_PARAMS) == 4


def test_time_mode_params_names():
    """TIME_MODE_PARAMS param names are ['time_mode', 'lookback_days', 'start_time', 'end_time']."""
    names = [p.name for p in TIME_MODE_PARAMS]
    assert names == ["time_mode", "lookback_days", "start_time", "end_time"]


def test_time_mode_param_time_mode():
    """time_mode param has correct defaults, options, and widget_hint."""
    p = TIME_MODE_PARAMS[0]
    assert p.name == "time_mode"
    assert p.default == "lookback"
    assert p.options == ["lookback", "datetime"]
    assert p.widget_hint == "toggle"


def test_time_mode_params_lookback_days():
    """lookback_days param has default=7."""
    p = TIME_MODE_PARAMS[1]
    assert p.name == "lookback_days"
    assert p.default == 7


def test_time_mode_params_start_time():
    """start_time param has widget_hint='datetime'."""
    p = TIME_MODE_PARAMS[2]
    assert p.name == "start_time"
    assert p.widget_hint == "datetime"


def test_time_mode_params_end_time():
    """end_time param has widget_hint='datetime'."""
    p = TIME_MODE_PARAMS[3]
    assert p.name == "end_time"
    assert p.widget_hint == "datetime"
