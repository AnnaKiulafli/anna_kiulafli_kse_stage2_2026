from datetime import date
import pandas as pd
from alert_pipeline.pipeline import normalize_alerts, daily_raion_activity
from alert_pipeline.eda import allocated_minutes_by_geo_day, regional_comparisons, valid_duration_mask, monthly_national, national_daily, validate_inputs, geo_key


def row(oblast='A', raion='Same', level='raion', start='2026-01-02T10:00:00Z', end='2026-01-02T11:00:00Z'):
    return {'oblast':oblast,'raion':raion,'hromada':None,'level':level,'source':'t','started_at':start,'finished_at':end}

def alerts(rows): return normalize_alerts(pd.DataFrame(rows))


def test_national_totals_equal_sum_of_oblast_totals():
    df=alerts([row('A','R1'), row('B','R2', end='2026-01-02T12:00:00Z')])
    oblast,raion=regional_comparisons(df)
    allocated=allocated_minutes_by_geo_day(df)
    assert allocated.allocated_minutes.sum()==oblast.total_allocated_raion_alert_minutes.sum()
    assert allocated.allocated_minutes.sum()==raion.total_allocated_alert_minutes.sum()
    assert len(df)==oblast.total_alert_records.sum()


def test_identical_raion_names_in_different_oblasts_remain_separate():
    df=alerts([row('A','Same'), row('B','Same')])
    _,ra=regional_comparisons(df)
    assert geo_key(df).nunique()==2
    assert len(ra)==2


def test_invalid_durations_do_not_enter_duration_statistics():
    df=alerts([row(end='2026-01-02T10:00:00Z'), row(start='2026-01-02T12:00:00Z', end='2026-01-02T11:00:00Z'), row(start='2026-01-02T10:00:00Z', end='2026-01-10T11:00:00Z'), row(end='2026-01-02T11:00:00Z')])
    assert valid_duration_mask(df).sum()==1
    assert df[valid_duration_mask(df)].duration_minutes.tolist()==[60]


def test_zero_activity_dates_remain_in_national_daily_series():
    df=alerts([row(start='2026-01-03T10:00:00Z', end='2026-01-03T11:00:00Z')])
    daily=daily_raion_activity(df, date(2026,1,3))
    nd=national_daily(daily)
    assert len(nd)==3
    assert nd.loc[nd.local_date.eq(date(2026,1,1)), 'total_raion_time_under_alert_minutes'].iloc[0]==0


def test_monthly_aggregation_preserves_totals():
    df=pd.DataFrame({'local_date':[date(2026,1,1),date(2026,1,2),date(2026,2,1)],'active_raions':[1,2,3],'records_started_on_date':[2,3,4],'interval_segments':[2,3,4],'total_raion_time_under_alert_minutes':[10.0,20.0,30.0]})
    m=monthly_national(df)
    assert m.total_raion_time_under_alert_minutes.sum()==60.0
    assert m.total_records_started.sum()==9


def test_partial_day_data_is_excluded_by_validation():
    df=alerts([row(start='2026-01-02T10:00:00Z'), row(start='2026-01-03T10:00:00Z')])
    daily=daily_raion_activity(df[df.local_date<=date(2026,1,2)], date(2026,1,2))
    try:
        validate_inputs(df, daily, df.iloc[0:0].copy(), date(2026,1,2))
    except AssertionError as e:
        assert 'Partial-day' in str(e)
    else:
        raise AssertionError('expected validation failure')


def test_overlap_allocation_splits_midnight_and_reconciles_regional_totals():
    df=alerts([
        row('A','R1', start='2026-01-02T20:30:00Z', end='2026-01-02T22:30:00Z'),  # Kyiv: 22:30-00:30
        row('A','R1', start='2026-01-02T21:00:00Z', end='2026-01-02T22:00:00Z'),  # overlap within R1
        row('A','R2', start='2026-01-02T21:00:00Z', end='2026-01-02T22:00:00Z'),  # simultaneous other raion
        row('B','R3', start='2026-01-02T22:30:00Z', end='2026-01-03T01:30:00Z'),  # Kyiv: 00:30-03:30 Jan 3
    ])
    daily=daily_raion_activity(df, date(2026,1,3))
    oblast,raion=regional_comparisons(df)
    by_day=dict(zip(daily.local_date, daily.total_raion_time_under_alert_minutes))
    assert by_day[date(2026,1,2)]==150  # R1 90 + simultaneous R2 60; overlapping R1 alert counted once
    assert by_day[date(2026,1,3)]==210  # R1 30 + R3 cross-midnight portion 180
    r1=raion[raion.geo_id.eq('A | R1')].iloc[0]
    r2=raion[raion.geo_id.eq('A | R2')].iloc[0]
    assert r1.total_allocated_alert_minutes==120
    assert r2.total_allocated_alert_minutes==60
    national=daily.total_raion_time_under_alert_minutes.sum()
    assert national==360
    assert national==oblast.total_allocated_raion_alert_minutes.sum()==raion.total_allocated_alert_minutes.sum()
