import pandas as pd

from alert_pipeline.preprocessing import (
    add_duration_quality_flags, add_timestamp_columns, build_daily_activity,
    calculate_latest_complete_day, detect_stale_source, enrich_records,
    filter_2026_raion_records, remove_exact_duplicates, separate_completed_and_partial_days,
    split_excluded_mixed_levels, split_kyiv_city,
)


def sample_df():
    return pd.DataFrame([
        {"oblast":"A","raion":"R1","hromada":"H","level":"raion","started_at":"2026-01-01T22:30:00Z","finished_at":"2026-01-01T23:00:00Z","source":"s"},
        {"oblast":"A","raion":"R1","hromada":"H","level":"raion","started_at":"2026-01-01T22:30:00Z","finished_at":"2026-01-01T23:00:00Z","source":"s"},
        {"oblast":"B","raion":None,"hromada":None,"level":"oblast","started_at":"2026-01-02T10:00:00Z","finished_at":"2026-01-02T10:00:00Z","source":"s"},
        {"oblast":"C","raion":"R2","hromada":"H2","level":"hromada","started_at":"2026-01-02T11:00:00Z","finished_at":"2026-01-01T11:00:00Z","source":"s"},
        {"oblast":"Kyiv City","raion":None,"hromada":None,"level":"oblast","started_at":"2026-01-03T00:00:00Z","finished_at":"2026-01-11T01:00:00Z","source":"s"},
        {"oblast":"A","raion":"R2","hromada":"H","level":"raion","started_at":"2026-06-23T01:00:00Z","finished_at":"2026-06-23T02:00:00Z","source":"s"},
    ])


def test_exact_duplicate_removal():
    assert len(remove_exact_duplicates(sample_df())) == 5


def test_utc_to_europe_kyiv_conversion():
    enriched = add_timestamp_columns(sample_df().head(1))
    assert str(enriched.loc[0, "started_at_kyiv"].tz) == "Europe/Kyiv"
    assert enriched.loc[0, "local_date"] == "2026-01-02"


def test_dynamic_latest_completed_day_calculation():
    latest = calculate_latest_complete_day(pd.Timestamp("2026-06-23T12:00:00", tz="Europe/Kyiv"), pd.Timestamp("2026-06-23"))
    assert latest == pd.Timestamp("2026-06-22")


def test_stale_source_detection():
    lag, stale = detect_stale_source(pd.Timestamp("2026-06-23T12:00:00", tz="Europe/Kyiv"), pd.Timestamp("2026-06-20"))
    assert lag == 3 and stale is True


def test_separation_of_complete_and_partial_days():
    df = enrich_records(remove_exact_duplicates(sample_df()), "2026-06-22")
    complete, partial = separate_completed_and_partial_days(df, "2026-06-22", pd.Timestamp("2026-06-23T12:00:00", tz="Europe/Kyiv"))
    assert complete["local_date"].max() <= "2026-06-22"
    assert set(partial["local_date"]) == {"2026-06-23"}
    assert partial["is_complete_day"].eq(False).all()


def test_filtering_to_2026_raion_records():
    df = enrich_records(remove_exact_duplicates(sample_df()), "2026-06-22")
    raion = filter_2026_raion_records(df, "2026-06-22")
    assert set(raion["level"]) == {"raion"}
    assert "2026-06-23" not in set(raion["local_date"])


def test_separation_of_oblast_and_hromada_records():
    df = enrich_records(remove_exact_duplicates(sample_df()), "2026-06-22")
    excluded = split_excluded_mixed_levels(df)
    assert {"oblast", "hromada"}.issubset(set(excluded["level"]))


def test_kyiv_city_separation():
    df = enrich_records(remove_exact_duplicates(sample_df()), "2026-06-22")
    kyiv = split_kyiv_city(df)
    assert len(kyiv) == 1
    assert kyiv.iloc[0]["oblast"] == "Kyiv City"


def test_zero_negative_and_over_seven_day_flags():
    df = enrich_records(remove_exact_duplicates(sample_df()), "2026-06-22")
    assert df["is_zero_duration"].sum() == 1
    assert df["is_negative_duration"].sum() == 1
    assert df["is_over_7_days"].sum() == 1


def test_inclusion_of_zero_activity_dates():
    df = enrich_records(remove_exact_duplicates(sample_df()), "2026-01-04")
    raion = filter_2026_raion_records(df, "2026-01-04")
    daily = build_daily_activity(raion, "2026-01-04")
    assert list(daily["date"]) == ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    assert daily.loc[daily["date"].eq("2026-01-03"), "alert_record_count"].iloc[0] == 0
