from datetime import date

import pandas as pd

from alert_pipeline.pipeline import (
    HISTORICAL_OBLAST_END_DATE,
    current_raion_records,
    daily_raion_activity,
    historical_oblast_context,
    latest_completed_day,
    normalize_alerts,
    split_kyiv_city,
)


def alerts(rows):
    return normalize_alerts(pd.DataFrame(rows))


def row(region="Lvivska oblast", raion="Lvivskyi raion", start="2026-07-10T10:00:00Z", end="2026-07-10T11:00:00Z"):
    return {"region": region, "oblast": region, "raion": raion, "start": start, "end": end}


def test_latest_completed_day_excludes_june_23_partial_day():
    assert latest_completed_day(date(2026, 6, 23), date(2026, 6, 23)) == date(2026, 6, 22)


def test_latest_completed_day_excludes_july_15_partial_day():
    assert latest_completed_day(date(2026, 7, 15), date(2026, 7, 15)) == date(2026, 7, 14)


def test_july_2026_raion_record_included_when_completed_day_after_july_10():
    df = alerts([row(start="2026-07-10T10:00:00Z"), row(start="2026-07-15T10:00:00Z")])
    complete, partial, latest = current_raion_records(df, date(2026, 7, 15))
    assert latest == date(2026, 7, 14)
    assert date(2026, 7, 10) in set(complete["start_local_date"])
    assert partial["start_local_date"].tolist() == [date(2026, 7, 15)]


def test_current_partial_day_excluded_from_complete_and_written_to_partial():
    df = alerts([row(start="2026-06-22T10:00:00Z"), row(start="2026-06-23T10:00:00Z")])
    complete, partial, latest = current_raion_records(df, date(2026, 6, 23))
    assert latest == date(2026, 6, 22)
    assert complete["start_local_date"].tolist() == [date(2026, 6, 22)]
    assert partial["start_local_date"].tolist() == [date(2026, 6, 23)]


def test_primary_dataset_has_no_hard_coded_maximum_date():
    df = alerts([row(start="2026-08-05T10:00:00Z"), row(start="2026-08-06T10:00:00Z")])
    complete, _, latest = current_raion_records(df, date(2026, 8, 7))
    assert latest == date(2026, 8, 6)
    assert set(complete["start_local_date"]) == {date(2026, 8, 5), date(2026, 8, 6)}


def test_split_kyiv_city_uses_exact_canonical_region_only():
    df = alerts([
        row(region="Kyiv City", raion=None),
        row(region="Kyivska oblast", raion="Buchanskyi raion"),
        row(region="Kyivska oblast", raion=None),
    ])
    kyiv, other = split_kyiv_city(df)
    assert kyiv["region"].tolist() == ["Kyiv City"]
    assert other["region"].tolist() == ["Kyivska oblast", "Kyivska oblast"]


def test_historical_context_cutoff_includes_july_31_excludes_august_1():
    df = alerts([
        row(region="Lvivska oblast", raion=None, start="2025-07-31T10:00:00Z"),
        row(region="Lvivska oblast", raion=None, start="2025-08-01T10:00:00Z"),
    ])
    hist = historical_oblast_context(df)
    assert HISTORICAL_OBLAST_END_DATE == date(2025, 7, 31)
    assert hist["start_local_date"].tolist() == [date(2025, 7, 31)]


def test_historical_cutoff_does_not_limit_primary_july_2026_records():
    df = alerts([row(start="2026-07-10T10:00:00Z"), row(start="2026-07-11T10:00:00Z")])
    complete, _, _ = current_raion_records(df, date(2026, 7, 12))
    assert set(complete["start_local_date"]) == {date(2026, 7, 10), date(2026, 7, 11)}


def test_daily_metric_splits_cross_midnight_and_merges_overlaps_by_raion():
    df = alerts([
        row(start="2026-07-10T20:30:00Z", end="2026-07-10T22:30:00Z"),  # Kyiv 23:30-01:30
        row(start="2026-07-10T21:00:00Z", end="2026-07-10T22:00:00Z"),  # overlap same raion
        row(raion="Drohobytskyi raion", start="2026-07-10T21:00:00Z", end="2026-07-10T22:00:00Z"),
        row(start="2026-07-10T11:00:00Z", end="2026-07-10T10:00:00Z"),
    ])
    daily = daily_raion_activity(df)
    by_day = dict(zip(daily["local_date"], daily["total_raion_time_under_alert_minutes"]))
    assert by_day[date(2026, 7, 10)] == 30
    assert by_day[date(2026, 7, 11)] == 150
