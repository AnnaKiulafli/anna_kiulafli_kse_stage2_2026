# Data Quality Investigation Summary

Rows before exact deduplication: 272699
Unique rows after exact deduplication: 158854
Excess fully duplicated rows: 113845
Distinct duplicate groups: 113845

## Duplicate multiplicity summary
```
                        bucket  groups
               appearing_twice  113845
         appearing_three_times       0
          appearing_four_times       0
appearing_more_than_four_times       0
          maximum_multiplicity       2
```

## Duration anomaly counts
```
  threshold  records
gt_12_hours     5471
gt_24_hours     1117
  gt_7_days       19
 gt_30_days        4
 gt_90_days        4
```

## Administrative granularity milestones
```
            milestone first_month
oblast_share_below_75     2022-03
oblast_share_below_50     2025-08
oblast_share_below_25     2025-09
oblast_share_below_10     2025-11
 raion_share_above_50     2025-08
```

## Candidate cutoff comparison
```
cutoff_month_exclusive_for_historical_period  months_before  records_before  oblast_share_before  raion_share_before  months_after  records_after  oblast_share_after  raion_share_after
                                     2025-07             40          147840             0.816761            0.027827            12         124859            0.074508           0.826805
                                     2025-08             41          153950             0.807288            0.034466            11         118749            0.048598           0.859308
                                     2025-09             42          162320             0.779423            0.062716            10         110379            0.032044           0.880312
                                     2025-11             44          181614             0.712258            0.132743             8          91085            0.007652           0.913872
                                     2025-12             45          197854             0.655453            0.195205             7          74845            0.004930           0.918244
```