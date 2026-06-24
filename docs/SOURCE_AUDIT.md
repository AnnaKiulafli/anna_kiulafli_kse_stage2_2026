# Source Provenance Audit: Ukraine Air-Raid Alert Time Series

Audit date: 2026-06-24  
Repository under audit: `anna_kiulafli_kse_stage2_2026`

## Executive recommendation

**Go/no-go: NO-GO for migrating the production pipeline before the submission deadline.**

Because this is a time-limited mini-project, replacing the working source without confirmed historical equivalence would introduce more methodological risk than retaining the current source with transparent limitations.

The most authoritative source identified is the operational alert chain behind the official **“Повітряна тривога” / “Air Alert”** app, supported by Ukraine's Ministry of Digital Transformation and fed by regional military/civil-protection operators. Public evidence confirms that the app receives alarm information directly from regional administrations and can notify by oblast, raion, and territorial community. However, I did **not** find a publicly documented, unauthenticated historical export/API that can reproduce the project's complete 2026 raion-level historical analysis from `2026-01-01`.

The official Telegram channel (`https://t.me/air_alert_ua`) is a more direct duplicate of app notifications than the current aggregated GitHub CSV, but it is a message stream rather than a structured historical data API. The separate UkraineAlertBot Telegram bot is also associated with the official alert ecosystem, but it must not be conflated with the public channel. Either Telegram interface would require validation of historical completeness, message formats, edits/deletions, administrative granularity, access rules, and automated retrieval constraints.

`alerts.in.ua` has a documented token-gated API, supports oblast, raion, city, and hromada location types, and documents a limited historical endpoint for the previous month. It remains an **unofficial secondary comparison source**, not the primary authoritative source, because that public history window cannot reproduce the full project period beginning on `2026-01-01`.

## Current repository source

The production downloader currently fetches `official_data_en.csv` from `Vadimkin/ukrainian-air-raid-sirens-dataset`:

```text
https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv
```

The upstream dataset README describes two sources: “official” and volunteer-collected Telegram data. It says both datasets are updated daily, all times are UTC, the official dataset starts on 2022-03-15, and raion-level alerts became prevalent in December 2025. It also documents permanent sirens omitted from the dataset. See:

- `Vadimkin/ukrainian-air-raid-sirens-dataset` README: <https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset>
- Dataset README: <https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md>

Classification: **secondary aggregated dataset**. It is public, convenient, and historical, but it is not the original operational system.

## 1. Source hierarchy

| Rank | Source | Classification | Why |
| --- | --- | --- | --- |
| 1 | Regional military/civil-protection administrations operating the alert signal chain | Primary operational source | Regional operators declare and cancel alerts, then transmit signals through the alerting system. |
| 2 | Official “Повітряна тривога” app/feed (`com.ukrainealarm`) | Official near-primary distribution channel | Public official/regional sources state the app receives alarm data directly from regional administrations and is supported by the Ministry of Digital Transformation. |
| 3 | Official Telegram channel `@air_alert_ua` | Official secondary duplicate of app notifications | Ajax Systems announced it as a unified Telegram channel that duplicates app notifications. It receives app signals and publishes start/end messages, but it is not a structured historical API. |
| 4 | UkraineAlertBot Telegram bot | Official-ecosystem Telegram bot interface | Associated with the official alert ecosystem, but distinct from the public channel and not automatically a structured historical API. |
| 5 | `api.ukrainealarm.com` / app-associated API | Official app-associated API with controlled access | It is associated with the official “Повітряна тривога” ecosystem; API access requires an application and key, and public information does not confirm complete raion-level historical coverage from `2026-01-01`. |
| 6 | `alerts.in.ua` | Unofficial secondary comparison source | Documented token-gated API with current and previous-month regional history endpoints; explicitly not an official government/app primary source. |
| 7 | `Vadimkin/ukrainian-air-raid-sirens-dataset` | Secondary aggregated dataset | Public GitHub aggregation derived from official and volunteer sources. Current project input. |

## 2. Evidence for each classification

### Official “Повітряна тривога” application/feed

Evidence:

- Lviv Regional Military Administration states the app receives alarm information directly from regional administrations; an operator receives the signal, transmits it to a control center, and users receive start/end notifications. <https://loda.gov.ua/en/useful-info/129927?authorId=17061>
- The same page states the app was developed/launched with support from the Ministry of Digital Transformation and supports all regions plus selected districts or territorial communities. <https://loda.gov.ua/en/useful-info/129927?authorId=17061>
- Google Play describes the app as receiving alerts from the civil defense system and requiring no registration or geolocation collection. <https://play.google.com/store/apps/details?id=com.ukrainealarm&hl=en_US>
- Ajax Systems describes the app as developed by Ajax Systems with stfalcon.com and support from the Ministry of Digital Transformation. <https://ajax.systems/press-page/air-alert-third-anniversary/>

Classification: **official near-primary distribution channel**. It is not itself the administrative authority declaring alerts, but it is the official public distribution channel closest to that chain.

### Official Telegram channel and UkraineAlertBot Telegram bot

Evidence:

- Ajax Systems announced a unified Telegram channel “Повітряна тривога” that duplicates all app notifications. <https://ajax.systems/ua/blog/air-alert-telegram-channel/>
- Ukrainian technology/media coverage reported that Ajax declined to share app software/API access for security reasons and instead launched `https://t.me/air_alert_ua`, which receives signals from the app and publishes start/end messages. <https://itc.ua/ua/novini/v-zastosunku-povitryana-trivoga-zyavilosya-nalashtuvannya-guchnosti-nulovij-trafik-ta-okremij-telegram-kanal/>
- Public Telegram web previews exist for the channel family; example channel URL: <https://t.me/air_alert_ua>.
- UkraineAlertBot is a separate Telegram bot interface associated with the official alert ecosystem. It should not be treated as the same interface as the public `@air_alert_ua` channel.

Classification: **official secondary duplicate/channel interface and official-ecosystem bot interface**. The channel republishes official app notifications but is not the originating administrative system. The bot may provide alert access through Telegram, but neither the channel nor the bot should automatically be treated as a structured historical API. For either option, historical completeness, message formats, edits/deletions, administrative granularity, access rules, and automated retrieval constraints require validation.

### Official app-associated API with controlled access

Evidence:

- A public Python client/wrapper for `api.ukrainealarm.com` states that the API returns Ukraine air raid alarm information and requires an API key requested through the API site. <https://github.com/PaulAnnekov/ukrainealarm>
- The API landing page/access-request flow is available at <https://api.ukrainealarm.com/> and links an offer agreement. Publicly available information is sufficient to classify this as an app-associated controlled-access API, but not sufficient to confirm complete historical coverage, schema, correction behavior, limits, or research-publication terms for this project.

Classification: **official app-associated API with controlled access**. It is associated with the official “Повітряна тривога” ecosystem. API access requires an application and key. Publicly available information does not confirm a complete historical endpoint covering all raion-level records from `2026-01-01`; public access without credentials is insufficient to test full historical coverage. The applicability of the linked offer agreement to bulk historical research and publication of derived datasets still requires review.

### `alerts.in.ua`

Evidence:

- The official `alerts.in.ua` Python client says it provides real-time air-raid and threat information and requires an API token obtained by request form. It includes filters for `oblast`, `raion`, `hromada`, and `city` location types, and reports the last-updated time in Kyiv timezone. <https://github.com/alerts-ua/alerts-in-ua-py>
- The documented historical endpoint is `/v1/regions/{uid}/alerts/{period}.json`; the documented historical period is `month_ago`; and the relevant alert fields include `started_at`, `finished_at`, `updated_at`, and `calculated`. The documented historical endpoint limit is **2 requests per minute**; the general soft API limit is approximately **8-10 requests per minute**; and the hard limit is **12 requests per minute**. <https://alerts.in.ua/api-request>
- Its Google Play listing describes the app as volunteer-built and includes an explicit disclaimer that it is unofficial and not affiliated with or endorsed by a Ukrainian government entity. <https://play.google.com/store/apps/details?id=org.ukrzen.alertsinua&hl=en_US>
- Public descriptions of the service say it visualizes real-time alerts and has history/statistics. <https://alerts.in.ua/en>

Classification: **unofficial secondary comparison source**. It is useful for validation and discrepancy detection. Automated API use is available with an approved personal token and is subject to the published API rules and rate limits. However, the publicly documented historical endpoint covers only the previous month, so it cannot reproduce the full project period beginning on `2026-01-01` and must not be presented as the primary authoritative source.

### Current CSV aggregation

Evidence:

- The upstream README states the repository contains datasets with information about air raid sirens and has two sources: official and volunteer. <https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset>
- The dataset README states the official CSV starts 2022-03-15, is updated daily, uses UTC, and mostly contains raion-level alerts since December 2025. <https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md>

Classification: **secondary aggregated dataset**. It is the current source and best public historical source found during this audit, but it is not the origin.

## 3. Availability and coverage matrix

| Candidate | Owner/operator | Official/primary/secondary | Public documentation | Access method | Auth | Historical coverage | `2026-01-01` available? | Granularity | Start/finish timestamps | Timezone | Corrections/updates | Rate limits | License/terms | Automated downloading permitted? | Risks/limitations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Official app/feed | Ajax Systems / stfalcon.com; supported by Ministry of Digital Transformation; operational inputs from regional administrations | Official near-primary distribution | App-store pages, regional government pages, Ajax pages; no public data-export schema found | Mobile app push/feed | No user registration for app; backend/API access not public | App UI reportedly includes alert map/history, but no public bulk historical export found | Not confirmed via public export | Oblast, raion, hromada; app pages also mention city/region selection | Yes in notifications; bulk export not documented | App-facing local time; exact API timezone not documented | Operator-issued start/end; correction semantics not documented | Not documented | App-store/platform terms; no dataset license found | Not confirmed for automated data extraction | Most authoritative, but no documented public historical API/export for reproducible research |
| Official Telegram channel `@air_alert_ua` | Ajax Systems channel duplicating app notifications | Official duplicate / secondary to app | Public channel announcement; Telegram message format informal | Telegram channel history via Telegram clients/API | Telegram API account/app credentials required for robust scraping | Channel history likely from March 2022 onward, but completeness must be tested | Likely yes if channel history retained and accessible | Message text historically region-based; raion/hromada availability after local-alert rollout must be parsed/tested | Start and finish messages exist | Telegram message timestamps are UTC internally; message text may use local time | Telegram edits/deletions possible; correction rules not documented | Telegram flood limits; retrieval constraints need validation | Telegram ToS; channel content license not explicit | Not explicitly granted; must respect Telegram ToS and channel limits | Parsing fragility, message edits/deletions, language/text changes, no schema, no guaranteed completeness |
| UkraineAlertBot Telegram bot | Official alert ecosystem bot operator | Official-ecosystem Telegram bot interface; distinct from channel | Bot interface documentation/public behavior, not a historical API specification | Telegram bot interaction | Telegram account; bot-specific access behavior must be tested | Not documented as a complete historical export | Not confirmed | Operational granularity may depend on bot features; raion/hromada history must be tested | Alert notifications may include start/finish behavior; historical interval export not documented | Telegram timestamps are UTC internally; bot text may use local time | Edits/deletions/corrections not documented | Telegram/bot limits; retrieval constraints need validation | Telegram ToS; bot terms not established for bulk research | Not confirmed for automated historical retrieval | Must not be conflated with `@air_alert_ua`; not a structured historical API without validation |
| `api.ukrainealarm.com` | Official “Повітряна тривога” app/API ecosystem | Official app-associated API with controlled access | API access-request page, linked offer agreement, public wrapper README | HTTP API | Application and API key required | Publicly available information does not confirm a complete historical endpoint | Not confirmed for all raion-level records from `2026-01-01` | Not confirmable without credentials/docs; official ecosystem likely supports operational locations | Unknown for historical records without credentials/docs | Unknown from public information | Unknown from public information | Requires review under controlled-access documentation/agreement | Offer agreement linked on request page; applicability to bulk historical research and derived publication requires review | Automated use only if approved under API access terms | Cannot accept until historical coverage, schema, limits, correction behavior, and research-use terms are confirmed |
| `alerts.in.ua` | `alerts-ua` / alerts.in.ua service operators | Unofficial secondary comparison source | Website, API request documentation, official Python client | HTTP API via approved personal token | Personal API token by request form | Documented regional historical endpoint `/v1/regions/{uid}/alerts/{period}.json` with `period=month_ago` only | No; previous-month public endpoint cannot reproduce full project period from `2026-01-01` | Supported location types include oblast, raion, city, and hromada | Relevant fields include `started_at`, `finished_at`, `updated_at`, and `calculated` | API/client documentation includes Kyiv-time update context; timestamp field timezone must be preserved/tested | `updated_at` and `calculated` support update/correction diagnostics, but source correction semantics remain secondary | Historical endpoint: 2 requests/minute; general soft limit about 8-10 requests/minute; hard limit 12 requests/minute | Client MIT license; API rules/terms apply to token use | Automated API use available with approved personal token subject to published API rules and rate limits; unrestricted bulk historical downloading is not documented | Unofficial, limited previous-month history, not primary; useful for validation/discrepancy detection |
| Vadimkin CSV | GitHub repository maintainer | Secondary aggregated dataset | GitHub README/datasets README | Raw CSV download | None | Official CSV from 2022-03-15; daily updates | Yes, by upstream statement and current project use | Mostly raion since Dec 2025; includes oblast/raion/hromada | Yes: started/finished fields in CSV | UTC per upstream README | Upstream updates daily; correction policy not formalized | GitHub raw limits | MIT repository license | Public raw CSV download currently used | Secondary source, provenance not direct, transformation assumptions external |

## 4. Migration feasibility

### Can any candidate reproduce the complete 2026 raion-level historical analysis?

**Not proven.** No investigated authoritative/direct candidate has a publicly documented, complete, machine-readable historical export that is confirmed to contain all raion-level start and finish intervals from `2026-01-01` onward.

- The official app/feed is authoritative but not publicly exportable in documented bulk form.
- The official Telegram channel may contain the needed notifications, and UkraineAlertBot may provide a separate alert interface, but neither is a structured historical API by default. This audit did not run a full Telegram history extraction and parse, so neither interface can be claimed to match or reproduce the current CSV.
- `api.ukrainealarm.com` is an official app-associated API with controlled access, but public information available without credentials does not confirm a complete historical endpoint, schema, limits, correction behavior, or research-use terms for all raion-level records from `2026-01-01`.
- `alerts.in.ua` is useful for cross-checking and has a documented previous-month historical endpoint, token process, fields, and rate limits. However, it is unofficial and that public historical endpoint is limited to `month_ago`, so it cannot reproduce the project period beginning on `2026-01-01`.

### Feasibility verdict by source

| Candidate | Migration feasibility | Verdict |
| --- | --- | --- |
| Official app/feed | Low until a documented historical export/API is obtained | Reject for immediate migration; pursue official access |
| Official Telegram channel `@air_alert_ua` | Medium for validation, low-to-medium for production source | Reject as sole production source until parser/backfill validation succeeds |
| UkraineAlertBot Telegram bot | Unknown for historical analysis | Reject as production source until interface behavior, access rules, and historical completeness are validated separately from the channel |
| `api.ukrainealarm.com` | Unknown; potentially high if official historical endpoints exist under controlled access | Hold pending API key, schema, coverage, limits, correction behavior, agreement review, and test extraction |
| `alerts.in.ua` | Medium for recent validation; low as primary/full-history source | Accept only as secondary validation source; previous-month history cannot reproduce the full 2026 project period |
| Vadimkin CSV | High continuity for current project | Keep as current source pending validation against more authoritative sources |

## 5. Validation methodology

This is a proposed procedure. **No match claims should be made until it is actually run.**

### Sample design

Select at least seven calendar dates in `Europe/Kyiv` time, including weekdays/weekends and dates likely to include alerts. Recommended initial sample:

1. 2026-01-01
2. 2026-01-15
3. 2026-02-01
4. 2026-03-15
5. 2026-04-01
6. 2026-05-09
7. 2026-06-01

Select at least five oblasts plus Kyiv City vs Kyivska oblast:

- Kyiv City (`м. Київ`) separately from Kyivska oblast
- Kyivska oblast
- Kharkivska oblast
- Dnipropetrovska oblast
- Odeska oblast
- Lvivska oblast
- Donetska oblast, if source coverage permits

### Data extraction inputs

1. Current CSV: download the existing `official_data_en.csv` exactly as the production pipeline does.
2. Most authoritative available comparison source:
   - preferred: official app/API historical endpoint, if access is granted and terms allow research validation;
   - fallback: official Telegram channel history parsed from `@air_alert_ua`, with UkraineAlertBot assessed separately if needed;
   - secondary check only: `alerts.in.ua` API/history with an approved token, recognizing that the documented `month_ago` endpoint cannot cover the full project period.

### Normalization rules

- Normalize all timestamps to timezone-aware UTC for equality tests.
- Preserve original source timestamps and timezone labels in audit output.
- Convert local-date windows using `Europe/Kyiv`, not fixed UTC offsets.
- Normalize administrative names to stable IDs where available; otherwise use a controlled mapping table for Ukrainian/English names.
- Keep Kyiv City distinct from Kyivska oblast.
- Keep source administrative level as an explicit field: `oblast`, `raion`, `hromada`, `city`, or `unknown`.

### Record-level comparison checks

For each selected date/oblast/admin unit:

1. Count start events by source.
2. Count finish events by source.
3. Compare start timestamp deltas:
   - exact UTC match;
   - within ±60 seconds;
   - within ±5 minutes;
   - no match.
4. Compare finish timestamp deltas using the same thresholds.
5. Compare interval duration deltas.
6. Detect records in CSV missing from authoritative source.
7. Detect records in authoritative source missing from CSV.
8. Detect duplicates within each source after normalization.
9. Detect overlapping intervals for the same administrative unit and alert type.
10. Identify apparent corrections:
    - Telegram edited messages;
    - source records with changed finish times across repeated pulls;
    - replacement/cancellation messages;
    - CSV rows whose intervals change between upstream commits.

### Outputs to generate in a future validation PR

- `data/diagnostics/source_validation_sample.csv` (ignored or committed only if policy allows small diagnostic fixtures)
- `reports/source_validation/summary.md`
- `reports/source_validation/mismatches.csv`
- `reports/source_validation/duplicates.csv`
- `reports/source_validation/admin_level_crosswalk.csv`

### Acceptance thresholds

A migration candidate should not be accepted unless:

- it provides documented permission for automated retrieval;
- it covers every selected test date from `2026-01-01` onward;
- it preserves Kyiv City separately from Kyivska oblast;
- it exposes start and finish timestamps;
- it includes raion-level records for the current analysis period;
- validation shows no unexplained systematic missingness or level mismatch;
- rate limits allow daily reproducible updates;
- correction/update behavior is either documented or empirically monitorable.

## 6. Recommended source

**Recommended current production source for this mini-project: keep `Vadimkin/ukrainian-air-raid-sirens-dataset` and describe its secondary provenance transparently.**

**Recommended provenance target for future work: official app/API access, if UkraineAlarm/API maintainers can provide documented historical endpoints, schema, limits, correction behavior, and research-use terms.**

**Recommended validation sources for future work: official Telegram `@air_alert_ua`, UkraineAlertBot evaluated separately, and `alerts.in.ua` as a secondary cross-check for the documented previous-month window.**

Rationale:

- The official app/feed is closest to the operational chain, but is not currently accessible as a reproducible historical dataset.
- The current CSV is already historical, UTC-normalized, and daily updated, but remains secondary and must not be described as a primary or authoritative operational source.
- The official Telegram channel is more direct than the current CSV, and UkraineAlertBot is a separate official-ecosystem Telegram interface, but both require validation before use as historical data sources.
- `alerts.in.ua` can help identify discrepancies through its documented token-gated API and previous-month historical endpoint, but its unofficial status and limited history window prevent it from becoming the primary source or reproducing the full 2026 project period.

## 7. Exact reasons for accepting or rejecting each candidate

### Official app/feed

Accept as: **provenance target and authority reference**.

Reject for immediate pipeline migration because:

- no public bulk historical export was found;
- no public schema was found for start/finish interval records;
- no public correction/update policy was found;
- no public rate limits or automated-use terms were found;
- no evidence from this audit confirms full `2026-01-01` raion-level historical availability via automated download.

### Official Telegram channel `@air_alert_ua` and UkraineAlertBot

Accept the channel as: **official duplicate stream for future validation and possible backfill experiment**.

Accept UkraineAlertBot as: **separate official-ecosystem Telegram interface for future evaluation**, not as the same interface as `@air_alert_ua`.

Reject both for immediate production migration because:

- neither interface is automatically a structured historical API;
- robust channel access requires Telegram API credentials and flood-limit handling, while bot access rules and retrievable history require separate testing;
- message formats may change;
- edited/deleted messages and correction semantics are not documented;
- raion/hromada message history from `2026-01-01` has not yet been parsed and compared;
- automated downloading permission is governed by Telegram ToS, channel/bot behavior, and access constraints, not a dataset license.

### `api.ukrainealarm.com`

Accept as: **highest-priority official app-associated controlled-access API request target**.

Reject for immediate production migration because:

- API access requires an application and key;
- an offer agreement is linked on the access-request page, but its applicability to bulk historical research and publication of derived datasets still requires review;
- publicly available information does not confirm a complete historical endpoint covering all raion-level records from `2026-01-01`;
- public access without credentials is insufficient to test full historical coverage;
- historical coverage, schema, limits, correction behavior, and research-use terms are not yet confirmed for this project.

### `alerts.in.ua`

Accept as: **secondary comparison and discrepancy detection source**.

Reject as primary source because:

- its app listing says it is unofficial and not affiliated with or endorsed by a Ukrainian government entity;
- the documented historical endpoint `/v1/regions/{uid}/alerts/{period}.json` supports the documented `month_ago` period only, so it cannot reproduce the full project period beginning on `2026-01-01`;
- API access requires an approved personal token;
- automated API use is available with that token only subject to published API rules and rate limits, including 2 requests per minute for the historical endpoint, a general soft limit of about 8-10 requests per minute, and a hard limit of 12 requests per minute;
- supported location types and fields are useful for validation (`oblast`, `raion`, `city`, `hromada`; `started_at`, `finished_at`, `updated_at`, `calculated`), but data lineage and correction behavior remain secondary to official channels.

### Current Vadimkin CSV

Accept for now because:

- it is public, downloadable, historical, UTC-normalized, and already integrated;
- upstream says the official dataset starts 2022-03-15 and is updated daily;
- upstream says raion-level alerts are mostly present since December 2025, matching the project's 2026 raion focus.

Reject as long-term authoritative source because:

- it is an aggregated GitHub dataset, not the operational origin;
- its correction/update policy is informal;
- omitted permanent sirens and possible transformation assumptions require downstream awareness;
- provenance depends on upstream processing outside this repository.

## 8. Estimated code changes required for a future migration

No production files were changed in this audit. If a future migration is approved, estimated changes are:

1. **Downloader abstraction**
   - Refactor `scripts/download_data.py` into source-specific fetchers.
   - Add config for source type, credentials, and cache directory.
   - Preserve existing CSV downloader as fallback.

2. **Credential handling**
   - Add `.env`/environment-variable support for API tokens or Telegram credentials.
   - Update documentation to avoid committing secrets.

3. **Source adapters**
   - API adapter for official endpoint, if access is granted.
   - Telegram adapter if channel backfill is selected.
   - Optional `alerts.in.ua` adapter for diagnostics only.

4. **Schema normalization**
   - Add source-to-canonical schema mapping.
   - Preserve original fields and raw payload hashes for auditability.
   - Add administrative-level and administrative-ID crosswalks.

5. **Correction tracking**
   - Store immutable raw pulls by date/source.
   - Add diffing between repeated pulls to detect changed start/finish times.
   - Add explicit correction logs.

6. **Validation suite**
   - Add record-level comparison checks described above.
   - Add fixture-free tests for timestamp normalization, Kyiv City/Kyivska separation, duplicate detection, and admin-level mapping.

7. **Documentation**
   - Update README only after validation is complete and the production source changes.
   - Add source terms and citation requirements.

Estimated implementation size after source access is approved: **medium** (approximately 2-5 focused PRs), with the largest unknown being Telegram/API historical extraction and administrative crosswalk quality.

## 9. Go/no-go recommendation

**NO-GO for production migration before the submission deadline.**

Proceed with the following next steps instead:

1. Request documented access to `api.ukrainealarm.com` or another official historical endpoint from the Air Alert/Ajax/Ministry-supported ecosystem.
2. Ask explicitly for:
   - historical records from at least `2026-01-01`;
   - raion-level coverage;
   - start and finish timestamps;
   - timezone specification;
   - correction/update semantics;
   - rate limits;
   - terms permitting automated research downloads and derived public analysis.
3. In a separate diagnostic PR, implement a non-production validation harness for the seven-date/five-oblast comparison.
4. Use `@air_alert_ua`, UkraineAlertBot, and `alerts.in.ua` only as validation/comparison sources unless and until they pass the acceptance thresholds.
5. Keep the current secondary CSV pipeline unchanged for this mini-project; document provenance and limitations transparently, and do not claim it is a primary or authoritative operational source.
6. Treat official API access and cross-source record-level validation as future work until validation proves a replacement can reproduce the current complete 2026 raion-level analysis.
