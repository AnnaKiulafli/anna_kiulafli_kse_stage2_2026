from datetime import date

import pandas as pd

from alert_pipeline.pipeline import (
    DEDUP_FIELDS,
    HISTORICAL_OBLAST_END_DATE,
    current_raion_records,
    daily_raion_activity,
    exact_deduplicate_source,
    historical_oblast_context,
    kyiv_city_records,
    latest_completed_day,
    normalize_alerts,
    split_kyiv_city,
)


def alerts(rows, deduplicate=True):
    return normalize_alerts(pd.DataFrame(rows), deduplicate=deduplicate)


def row(oblast="Lvivska oblast", raion="Lvivskyi raion", level="raion", start="2026-07-10T10:00:00Z", end="2026-07-10T11:00:00Z", hromada=None, source="api"):
    return {"oblast": oblast, "raion": raion, "hromada": hromada, "level": level, "started_at": start, "finished_at": end, "source": source}


def test_exact_deduplication_uses_original_source_fields_before_region_normalization():
    raw = pd.DataFrame([row(), row(), {**row(), "source": "other"}])
    dedup = exact_deduplicate_source(raw)
    norm = normalize_alerts(raw)
    assert len(dedup) == 2
    assert len(norm) == 2
    assert norm.duplicated(subset=DEDUP_FIELDS).sum() == 0
    assert "region" in norm.columns


def test_latest_completed_day_excludes_june_23_partial_day():
    assert latest_completed_day(date(2026, 6, 23), date(2026, 6, 23)) == date(2026, 6, 22)


def test_latest_completed_day_excludes_july_15_partial_day():
    assert latest_completed_day(date(2026, 7, 15), date(2026, 7, 15)) == date(2026, 7, 14)


def test_utc_to_europe_kyiv_conversion_sets_local_date():
    df = alerts([row(start="2026-07-10T21:30:00Z", end="2026-07-10T22:00:00Z")])
    assert df["local_date"].tolist() == [date(2026, 7, 11)]


def test_july_2026_raion_record_included_when_completed_day_after_july_10():
    df = alerts([row(start="2026-07-10T10:00:00Z"), row(start="2026-07-15T10:00:00Z")])
    complete, partial, latest = current_raion_records(df, date(2026, 7, 15))
    assert latest == date(2026, 7, 14)
    assert date(2026, 7, 10) in set(complete["local_date"])
    assert partial["local_date"].tolist() == [date(2026, 7, 15)]


def test_current_partial_day_excluded_from_complete_and_written_to_partial():
    df = alerts([row(start="2026-06-22T10:00:00Z"), row(start="2026-06-23T10:00:00Z")])
    complete, partial, latest = current_raion_records(df, date(2026, 6, 23))
    assert latest == date(2026, 6, 22)
    assert complete["local_date"].tolist() == [date(2026, 6, 22)]
    assert partial["local_date"].tolist() == [date(2026, 6, 23)]


def test_primary_dataset_has_no_hard_coded_maximum_date_and_includes_august_2026():
    df = alerts([row(start="2026-08-05T10:00:00Z"), row(start="2026-08-06T10:00:00Z")])
    complete, _, latest = current_raion_records(df, date(2026, 8, 7))
    assert latest == date(2026, 8, 6)
    assert set(complete["local_date"]) == {date(2026, 8, 5), date(2026, 8, 6)}


def test_raion_only_filtering_excludes_mixed_non_raion_levels():
    df = alerts([row(level="raion"), row(level="oblast", raion=None), row(level="hromada", raion="Lvivskyi raion")])
    complete, _, _ = current_raion_records(df, date(2026, 7, 11))
    assert complete["level"].tolist() == ["raion"]


def test_split_kyiv_city_uses_exact_canonical_oblast_only():
    df = alerts([
        row(oblast="Kyiv City", raion=None, level="oblast"),
        row(oblast="Kyivska oblast", raion="Buchanskyi raion"),
        row(oblast="Kyivska oblast", raion=None, level="oblast"),
    ])
    kyiv, other = split_kyiv_city(df)
    assert kyiv["oblast"].tolist() == ["Kyiv City"]
    assert other["oblast"].tolist() == ["Kyivska oblast", "Kyivska oblast"]


def test_kyiv_city_current_outputs_exclude_kyivska_missing_raion_pre_2026_and_split_partial():
    df = alerts([
        row(oblast="Kyiv City", raion=None, level="oblast", start="2025-12-31T10:00:00Z"),
        row(oblast="Kyiv City", raion=None, level="oblast", start="2026-06-22T10:00:00Z"),
        row(oblast="Kyiv City", raion=None, level="oblast", start="2026-06-23T10:00:00Z"),
        row(oblast="Kyivska oblast", raion=None, level="oblast", start="2026-06-22T10:00:00Z"),
    ])
    complete, partial = kyiv_city_records(df, date(2026, 6, 22), date(2026, 6, 23))
    assert complete["oblast"].tolist() == ["Kyiv City"]
    assert complete["local_date"].tolist() == [date(2026, 6, 22)]
    assert partial["local_date"].tolist() == [date(2026, 6, 23)]


def test_historical_context_cutoff_includes_july_31_excludes_august_1_and_deduplicates():
    df = alerts([
        row(oblast="Lvivska oblast", raion=None, level="oblast", start="2025-07-31T10:00:00Z"),
        row(oblast="Lvivska oblast", raion=None, level="oblast", start="2025-07-31T10:00:00Z"),
        row(oblast="Lvivska oblast", raion=None, level="oblast", start="2025-08-01T10:00:00Z"),
    ])
    hist = historical_oblast_context(df)
    assert HISTORICAL_OBLAST_END_DATE == date(2025, 7, 31)
    assert hist["local_date"].tolist() == [date(2025, 7, 31)]
    assert hist.duplicated(subset=DEDUP_FIELDS).sum() == 0


def test_historical_cutoff_does_not_limit_primary_july_2026_records():
    df = alerts([row(start="2026-07-10T10:00:00Z"), row(start="2026-07-11T10:00:00Z")])
    complete, _, _ = current_raion_records(df, date(2026, 7, 12))
    assert set(complete["local_date"]) == {date(2026, 7, 10), date(2026, 7, 11)}


def test_daily_metric_one_alert_inside_one_local_day():
    daily = daily_raion_activity(alerts([row(start="2026-07-10T10:00:00Z", end="2026-07-10T11:30:00Z")]))
    assert daily["total_raion_time_under_alert_minutes"].tolist() == [90]


def test_daily_metric_splits_cross_midnight_and_merges_same_raion_overlap():
    df = alerts([
        row(start="2026-07-10T20:30:00Z", end="2026-07-10T22:30:00Z"),
        row(start="2026-07-10T21:00:00Z", end="2026-07-10T22:00:00Z", source="api2"),
    ])
    by_day = dict(zip(daily_raion_activity(df)["local_date"], daily_raion_activity(df)["total_raion_time_under_alert_minutes"]))
    assert by_day[date(2026, 7, 10)] == 30
    assert by_day[date(2026, 7, 11)] == 90


def test_daily_metric_simultaneous_different_raions_are_summed():
    df = alerts([
        row(raion="A", start="2026-07-10T10:00:00Z", end="2026-07-10T11:00:00Z"),
        row(raion="B", start="2026-07-10T10:00:00Z", end="2026-07-10T11:00:00Z"),
    ])
    assert daily_raion_activity(df)["total_raion_time_under_alert_minutes"].tolist() == [120]


def test_daily_metric_excludes_zero_negative_and_more_than_seven_day_flags():
    df = alerts([
        row(start="2026-07-10T10:00:00Z", end="2026-07-10T10:00:00Z"),
        row(start="2026-07-10T11:00:00Z", end="2026-07-10T10:00:00Z"),
        row(start="2026-07-10T10:00:00Z", end="2026-07-18T10:01:00Z"),
    ])
    assert daily_raion_activity(df).empty


def test_daily_metric_includes_july_and_august_2026_intervals():
    df = alerts([
        row(start="2026-07-10T10:00:00Z", end="2026-07-10T11:00:00Z"),
        row(start="2026-08-10T10:00:00Z", end="2026-08-10T11:00:00Z"),
    ])
    assert set(daily_raion_activity(df)["local_date"]) == {date(2026, 7, 10), date(2026, 8, 10)}


def test_zero_activity_dates_are_absent_from_daily_activity():
    assert daily_raion_activity(alerts([row(start="2026-07-10T10:00:00Z", end=None)])).empty


def test_stale_source_detection_via_latest_completed_day_uses_dataset_latest_when_older():
    assert latest_completed_day(date(2026, 7, 15), date(2026, 7, 10)) == date(2026, 7, 10)
