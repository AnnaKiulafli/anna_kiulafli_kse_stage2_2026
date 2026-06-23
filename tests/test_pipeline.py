from datetime import date

import pandas as pd

from alert_pipeline.pipeline import (
    CURRENT_START_DATE,
    DAILY_COLUMNS,
    HISTORICAL_OBLAST_END_DATE,
    anomaly_frames,
    current_raion_records,
    daily_raion_activity,
    historical_oblast_context,
    latest_completed_day,
    latest_dataset_local_date,
    normalize_alerts,
    split_current_records,
    split_kyiv_city,
)


def alerts(rows):
    return normalize_alerts(pd.DataFrame(rows))


def row(oblast="Lvivska oblast", raion="Lvivskyi raion", hromada=None, level="raion", start="2026-07-10T10:00:00Z", end="2026-07-10T11:00:00Z", source="test"):
    return {"oblast": oblast, "raion": raion, "hromada": hromada, "level": level, "source": source, "started_at": start, "finished_at": end}


def test_latest_completed_day_excludes_june_23_partial_day():
    assert latest_completed_day(date(2026, 6, 23), date(2026, 6, 23)) == date(2026, 6, 22)


def test_latest_completed_day_excludes_july_15_partial_day():
    assert latest_completed_day(date(2026, 7, 15), date(2026, 7, 15)) == date(2026, 7, 14)


def test_latest_date_comes_from_full_dataset_not_raion_subset():
    df = alerts([
        row(start="2026-07-13T10:00:00Z"),
        row(oblast="Kyiv City", raion=None, level="city", start="2026-07-14T10:00:00Z"),
    ])
    full_latest = latest_dataset_local_date(df)
    complete, partial, latest = current_raion_records(df, date(2026, 7, 15), full_latest)
    assert full_latest == date(2026, 7, 14)
    assert latest == date(2026, 7, 14)
    assert complete["local_date"].tolist() == [date(2026, 7, 13)]
    assert partial.empty


def test_july_2026_raion_record_included_when_completed_day_after_july_10():
    df = alerts([row(start="2026-07-10T10:00:00Z"), row(start="2026-07-15T10:00:00Z")])
    complete, partial, latest = current_raion_records(df, date(2026, 7, 15), latest_dataset_local_date(df))
    assert latest == date(2026, 7, 14)
    assert date(2026, 7, 10) in set(complete["local_date"])
    assert partial["local_date"].tolist() == [date(2026, 7, 15)]


def test_current_partial_day_excluded_from_complete_and_written_to_partial():
    df = alerts([row(start="2026-06-22T10:00:00Z"), row(start="2026-06-23T10:00:00Z")])
    complete, partial, latest = current_raion_records(df, date(2026, 6, 23), latest_dataset_local_date(df))
    assert latest == date(2026, 6, 22)
    assert complete["local_date"].tolist() == [date(2026, 6, 22)]
    assert partial["local_date"].tolist() == [date(2026, 6, 23)]


def test_primary_dataset_has_no_hard_coded_maximum_date():
    df = alerts([row(start="2026-08-05T10:00:00Z"), row(start="2026-08-06T10:00:00Z")])
    complete, _, latest = current_raion_records(df, date(2026, 8, 7), latest_dataset_local_date(df))
    assert latest == date(2026, 8, 6)
    assert set(complete["local_date"]) == {date(2026, 8, 5), date(2026, 8, 6)}


def test_split_kyiv_city_uses_exact_canonical_region_only():
    df = alerts([
        row(oblast="Kyiv City", raion=None, level="city"),
        row(oblast="Kyivska oblast", raion="Buchanskyi raion"),
        row(oblast="Kyivska oblast", raion=None, level="oblast"),
    ])
    kyiv, other = split_kyiv_city(df)
    assert kyiv["oblast"].tolist() == ["Kyiv City"]
    assert other["oblast"].tolist() == ["Kyivska oblast", "Kyivska oblast"]


def test_historical_context_cutoff_includes_july_31_excludes_august_1():
    df = alerts([
        row(oblast="Lvivska oblast", raion=None, level="oblast", start="2025-07-31T10:00:00Z"),
        row(oblast="Lvivska oblast", raion=None, level="oblast", start="2025-08-01T10:00:00Z"),
    ])
    hist = historical_oblast_context(df)
    assert HISTORICAL_OBLAST_END_DATE == date(2025, 7, 31)
    assert hist["local_date"].tolist() == [date(2025, 7, 31)]


def test_historical_cutoff_does_not_limit_primary_july_2026_records():
    df = alerts([row(start="2026-07-10T10:00:00Z"), row(start="2026-07-11T10:00:00Z")])
    complete, _, _ = current_raion_records(df, date(2026, 7, 12), latest_dataset_local_date(df))
    assert set(complete["local_date"]) == {date(2026, 7, 10), date(2026, 7, 11)}


def test_non_raion_and_raion_outputs_cover_2026_records_without_overlap_or_loss():
    df = alerts([
        row(level="raion", start="2026-07-10T10:00:00Z"),
        row(oblast="Kyiv City", raion=None, level="city", start="2026-07-10T10:00:00Z"),
        row(raion=None, level="oblast", start="2026-07-11T10:00:00Z"),
        row(level="raion", start="2026-07-12T10:00:00Z"),
        row(raion=None, level="oblast", start="2026-07-12T10:00:00Z"),
    ])
    complete, partial, non_complete, non_partial, latest = split_current_records(df, date(2026, 7, 12), latest_dataset_local_date(df))
    assert latest == date(2026, 7, 11)
    assert set(complete.index).isdisjoint(set(non_complete.index))
    expected_complete = set(df[(df["local_date"] >= CURRENT_START_DATE) & (df["local_date"] <= latest)].index)
    assert set(complete.index) | set(non_complete.index) == expected_complete
    assert set(partial.index).isdisjoint(set(non_partial.index))
    expected_partial = set(df[df["local_date"] == date(2026, 7, 12)].index)
    assert set(partial.index) | set(non_partial.index) == expected_partial


def test_daily_calendar_includes_zero_activity_dates_with_zero_values():
    df = alerts([row(start="2026-01-03T10:00:00Z", end="2026-01-03T11:00:00Z")])
    daily = daily_raion_activity(df, date(2026, 1, 3))
    jan1 = daily[daily["local_date"].eq(date(2026, 1, 1))].iloc[0]
    assert len(daily) == 3
    assert jan1["active_raions"] == 0
    assert jan1["total_raion_time_under_alert_minutes"] == 0


def test_daily_metric_splits_cross_midnight_merges_by_oblast_raion_and_counts_segments():
    df = alerts([
        row(oblast="Lvivska oblast", raion="Same raion", start="2026-07-10T20:30:00Z", end="2026-07-10T22:30:00Z"),
        row(oblast="Lvivska oblast", raion="Same raion", start="2026-07-10T21:00:00Z", end="2026-07-10T22:00:00Z"),
        row(oblast="Odeska oblast", raion="Same raion", start="2026-07-10T21:00:00Z", end="2026-07-10T22:00:00Z"),
        row(start="2026-07-10T11:00:00Z", end="2026-07-10T10:00:00Z"),
    ])
    daily = daily_raion_activity(df, date(2026, 7, 11))
    assert list(daily.columns) == DAILY_COLUMNS
    by_day = dict(zip(daily["local_date"], daily["total_raion_time_under_alert_minutes"]))
    assert by_day[date(2026, 7, 10)] == 30
    assert by_day[date(2026, 7, 11)] == 150
    july_11 = daily[daily["local_date"].eq(date(2026, 7, 11))].iloc[0]
    assert july_11["active_raions"] == 2
    assert july_11["interval_segments"] == 3
    assert july_11["records_started_on_date"] == 2


def test_anomaly_records_are_preserved_separately():
    df = alerts([
        row(start="2026-07-10T10:00:00Z", end="2026-07-10T10:00:00Z"),
        row(start="2026-07-10T11:00:00Z", end="2026-07-10T10:00:00Z"),
        row(start="2026-07-10T10:00:00Z", end="2026-07-18T10:01:00Z"),
        row(start="2026-07-10T10:00:00Z", end=None),
    ])
    anomalies = anomaly_frames(df)
    assert len(anomalies["zero_duration_intervals"]) == 1
    assert len(anomalies["negative_duration_intervals"]) == 1
    assert len(anomalies["longer_than_seven_day_intervals"]) == 1
    assert len(anomalies["missing_finished_at_intervals"]) == 1
