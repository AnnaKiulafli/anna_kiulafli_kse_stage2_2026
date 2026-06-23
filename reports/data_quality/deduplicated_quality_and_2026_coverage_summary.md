# Deduplicated Data Quality and 2026 Coverage Summary

Raw rows before exact deduplication: 272699
Rows after exact full-row deduplication: 158854
Excess fully duplicated rows removed analytically: 113845
Distinct duplicate groups in raw data: 113845

## Deduplicated duration anomaly counts
```
  threshold  deduplicated_records
gt_12_hours                  3310
gt_24_hours                   696
  gt_7_days                    12
 gt_30_days                     2
 gt_90_days                     2
```

## Deduplicated administrative granularity milestones
```
            milestone first_month
oblast_share_below_75     2022-03
oblast_share_below_50     2025-08
oblast_share_below_25     2025-09
oblast_share_below_10     2025-11
 raion_share_above_50     2025-08
 raion_share_above_75     2025-11
 raion_share_above_90     2025-12
```

## 2026 administrative-level coverage by month
```
year_month_kyiv  total_records  oblast  raion  hromada  oblast_share  raion_share  hromada_share
        2026-01           8426      58   7663      705      0.006883     0.909447       0.083670
        2026-02           7930      41   7351      538      0.005170     0.926986       0.067844
        2026-03           9746      39   8908      799      0.004002     0.914016       0.081982
        2026-04           8613      35   7889      689      0.004064     0.915941       0.079995
        2026-05          10085      58   9378      649      0.005751     0.929896       0.064353
        2026-06           7101      35   6603      463      0.004929     0.929869       0.065202
```

## 2026 raion coverage by month
```
year_month_kyiv  raion_records  unique_oblasts  unique_raions          first_start_kyiv           last_start_kyiv
        2026-01           7663              23            118 2026-01-01 00:03:24+02:00 2026-01-31 23:54:04+02:00
        2026-02           7351              23            118 2026-02-01 00:16:36+02:00 2026-02-28 23:12:02+02:00
        2026-03           8908              23            118 2026-03-01 00:18:39+02:00 2026-03-31 23:52:02+03:00
        2026-04           7889              23            118 2026-04-01 00:06:27+03:00 2026-04-30 23:55:49+03:00
        2026-05           9378              23            118 2026-05-01 00:38:39+03:00 2026-05-31 23:52:32+03:00
        2026-06           6603              23            118 2026-06-01 00:32:35+03:00 2026-06-23 02:49:37+03:00
```

## Candidate historical cutoff comparison after deduplication
```
cutoff_month_exclusive_for_historical_period  months_before  records_before  oblast_share_before  raion_share_before  months_after  records_after  oblast_share_after  raion_share_after
                                     2025-07             40           73908             0.816732            0.027845            12          84946            0.056142           0.851635
                                     2025-08             41           76968             0.807336            0.034378            11          81886            0.036551           0.876279
                                     2025-09             42           81146             0.779546            0.062542            10          77708            0.024129           0.892135
                                     2025-11             44           90806             0.712255            0.132700             8          68048            0.006686           0.916280
                                     2025-12             45           98895             0.655665            0.194843             7          59959            0.004837           0.919495
```