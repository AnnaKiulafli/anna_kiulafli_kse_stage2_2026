from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import matplotlib.pyplot as plt
import pandas as pd
from alert_pipeline.eda import *

P = ROOT / 'data' / 'processed'
R = ROOT / 'reports' / 'eda'
T = R / 'tables'
F = R / 'figures'

def save(df,name):
    T.mkdir(parents=True, exist_ok=True); df.to_csv(T/f'{name}.csv', index=False); return T/f'{name}.csv'

def bar(df, x, y, title, name, xlabel='', ylabel=''):
    fig, ax = plt.subplots(figsize=(11,6)); df.plot.barh(x=x,y=y,ax=ax,legend=False); ax.invert_yaxis(); ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); fig.tight_layout(); F.mkdir(parents=True, exist_ok=True); fig.savefig(F/name, dpi=160); plt.close(fig)

def main():
    raion=read_processed(P/'current_2026_raion_alerts_complete_days.csv')
    daily=read_processed(P/'daily_2026_raion_activity.csv')
    non=read_processed(P/'current_2026_non_raion_records_complete_days.csv')
    hist=read_processed(P/'historical_oblast_context.csv')
    latest=max(daily['local_date'])
    nd=national_daily(daily); mn=monthly_national(daily); wd=weekday_patterns(daily)
    cov=coverage_tables(raion); obl, rai=regional_comparisons(raion, latest); validate_inputs(raion,daily,non,latest,obl,rai); dur=duration_summary(raion); nonc=non_raion_counts(non, raion); hc=historical_context(hist)
    # reconciliation
    if abs(nd['records_started_on_date'].sum()-obl['total_alert_records'].sum())>1e-6: raise AssertionError('National records do not reconcile with oblast records')
    if abs(rai['total_allocated_alert_minutes'].sum()-obl['total_allocated_raion_alert_minutes'].sum())>1e-6: raise AssertionError('Raion allocated minutes do not reconcile with oblast allocated minutes')
    outputs=[]
    for name, df in [('national_daily',nd),('monthly_national',mn),('weekday_patterns',wd),('daily_activity_distribution',nd[['active_raions','records_started_on_date','interval_segments','total_raion_time_under_alert_minutes']].describe(percentiles=[.25,.5,.75,.9,.95]).reset_index()),('unusually_high_activity_days',nd[nd.unusually_high_activity]),('oblast_comparison',obl),('raion_comparison',rai)]: outputs.append(save(df,name))
    for k,v in cov.items(): outputs.append(save(v, k))
    for k,v in dur.items(): outputs.append(save(v.reset_index() if k=='overall' else v, 'duration_'+k))
    for k,v in nonc.items(): outputs.append(save(v,'non_raion_'+k))
    outputs.append(save(hc['monthly_totals'],'historical_monthly_totals')); outputs.append(save(hc['granularity'],'historical_granularity'))
    F.mkdir(parents=True, exist_ok=True)
    fig, ax=plt.subplots(figsize=(12,6)); ax.plot(pd.to_datetime(nd.local_date), nd.total_raion_time_under_alert_minutes,label='Daily minutes'); ax.plot(pd.to_datetime(nd.local_date), nd.rolling_7d_total_minutes,label='7-day mean'); ax.plot(pd.to_datetime(nd.local_date), nd.rolling_14d_total_minutes,label='14-day mean'); ax.set_title('Nationwide raion alert activity by completed day'); ax.set_ylabel('Allocated raion-minutes under alert'); ax.set_xlabel('Date'); ax.legend(); fig.tight_layout(); fig.savefig(F/'national_daily_activity.png',dpi=160); plt.close(fig)
    fig, ax=plt.subplots(figsize=(10,5)); ax.bar(mn.month, mn.total_raion_time_under_alert_minutes); ax.set_title('Monthly nationwide raion alert activity'); ax.set_ylabel('Allocated raion-minutes'); ax.set_xlabel('Month'); fig.tight_layout(); fig.savefig(F/'monthly_national_activity.png',dpi=160); plt.close(fig)
    fig, ax=plt.subplots(figsize=(10,5)); ax.bar(cov['monthly_recorded_activity_presence'].month, cov['monthly_recorded_activity_presence'].active_raions); ax.set_title('Monthly recorded raion activity presence'); ax.set_ylabel('Unique oblast + raion units'); ax.set_xlabel('Month'); fig.tight_layout(); fig.savefig(F/'monthly_recorded_raion_activity_presence.png',dpi=160); plt.close(fig)
    bar(obl.head(15).sort_values('total_allocated_raion_alert_minutes'), 'oblast','total_allocated_raion_alert_minutes','Top oblasts by allocated raion alert minutes','top_oblasts_by_minutes.png','Allocated raion-minutes','Oblast')
    bar(rai.sort_values('total_allocated_alert_minutes',ascending=False).head(20).sort_values('total_allocated_alert_minutes'), 'geo_id','total_allocated_alert_minutes','Top oblast + raion units by allocated alert minutes','top_raions_by_minutes.png','Allocated minutes','Oblast + raion')
    fig, ax=plt.subplots(figsize=(10,5)); raion[valid_duration_mask(raion)]['duration_minutes'].plot.hist(bins=60, ax=ax); ax.set_title('Distribution of valid alert durations'); ax.set_xlabel('Minutes'); fig.tight_layout(); fig.savefig(F/'valid_duration_distribution.png',dpi=160); plt.close(fig)
    fig, ax=plt.subplots(figsize=(7,5)); ax.pie(nonc['raion_vs_non_raion'].records, labels=nonc['raion_vs_non_raion'].category, autopct='%1.1f%%'); ax.set_title('2026 complete-day record share: raion vs non-raion'); fig.savefig(F/'raion_vs_non_raion_share.png',dpi=160); plt.close(fig)
    anomalies = {
      'zero_duration_records': int((raion['duration_minutes']==0).sum()),
      'negative_duration_records': int((raion['duration_minutes']<0).sum()),
      'longer_than_7_day_records': int((raion['duration_minutes']>VALID_MAX_MINUTES).sum()),
      'missing_finished_at_records': int(raion['finished_at'].isna().sum()),
    }
    unusually=nd[nd.unusually_high_activity]
    md=R/'eda_summary.md'
    md.write_text(f"""# Nationwide Ukrainian raion air-raid alert EDA\n\n## Dataset scope\nThis report summarizes completed-day processed 2026 Ukrainian raion-level alert records from 2026-01-01 through **{latest}**. It uses `oblast + raion` as the administrative identifier and excludes current partial-day records from time-series summaries. Results describe historical recorded alert activity only and are not real-time safety or operational guidance.\n\n## Main nationwide findings\n- Latest completed date: **{latest}**.\n- Completed daily rows: **{len(daily)}**.\n- Represented oblast values: **{raion['oblast'].nunique(dropna=True)}**.\n- Unique oblast + raion units: **{geo_key(raion).nunique()}**.\n- Total completed raion records: **{len(raion)}**; non-raion records: **{len(non)}**.\n- Total allocated valid raion alert minutes: **{nd['total_raion_time_under_alert_minutes'].sum():,.1f}**.\n- Unusually high-activity days use the transparent IQR rule: {nd.attrs['high_activity_rule']}; flagged days: **{len(unusually)}**.\n\n## Coverage limitations\nCoverage is based on records present in the processed source data, not an external authoritative administrative register. A concise oblast coverage table is in `reports/eda/tables/coverage_by_oblast.csv`; per-raion first/last dates and months-with-no-recorded-alerts audits are in sibling CSV files.\n\n## Raion vs non-raion distinction\nPrimary analysis covers the whole country at oblast + raion level. Non-raion records are audited separately by level, oblast, raion, and hromada. These are all available non-raion administrative records in the dataset, not a complete list of Ukrainian cities; Kyiv City is only one administrative exception in this audit.\n\n## Duration anomaly handling\nDuration statistics exclude missing `finished_at`, zero-duration, negative-duration, and intervals longer than seven days. Reported anomaly counts in the completed raion data are: {anomalies}.\n\n## Historical context\nHistorical oblast context date range: **{hc['date_range']}**. It is summarized separately in `historical_monthly_totals.csv` and `historical_granularity.csv` because historical oblast-level counts are a different administrative granularity and are not directly comparable with the current 2026 raion-level series.\n\n## Generated tables and figures\nTables are under `reports/eda/tables/`; figures are under `reports/eda/figures/`. Core figures: national daily activity, monthly activity, monthly recorded raion activity presence, top oblasts, top raions, valid duration distribution, and raion versus non-raion share.\n""")
    print(f'latest_complete_day={latest}')
    print(f'represented_oblasts={raion["oblast"].nunique(dropna=True)}')
    print(f'unique_oblast_raion_units={geo_key(raion).nunique()}')
    print(f'completed_daily_rows={len(daily)}')
    print(f'generated_tables={len(outputs)}')
    print(f'generated_figures={len(list(F.glob("*.png")))}')

if __name__=='__main__': main()
