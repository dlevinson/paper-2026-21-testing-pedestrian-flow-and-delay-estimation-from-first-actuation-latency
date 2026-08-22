# MCAV Initial Method Validation Note

This note treats the Manual Crossing-Actuation Validation (MCAV) workbook as independent method-validation data. It does not require joining to historical SCATS HST files.

Source extract:

- `mcav_comparison_summary.csv`

## What The Workbook Measures

The workbook provides 14 pedestrian direction cases across 11 intersections. For each case it records:

- observed pedestrian arrivals;
- manually observed actuator/button pushes;
- legal pedestrians with and without button push;
- illegal pedestrians with and without button push;
- pedestrians who pushed the button but did not walk;
- the workbook's own first-push timing measure.

## Aggregate Evidence

Across the 14 cases:

- observed pedestrians: 1,744;
- manually coded actuator events: 513;
- observed pedestrians per manual actuation: 3.40;
- observed pedestrians associated with button-push behaviour: 29.4%;
- observed pedestrians not associated with button-push behaviour: 70.6%;
- legal crossings: 95.6%.

This is direct empirical support for treating pedestrian actuations as a proxy requiring calibration, not as pedestrian counts.

## Simple First-Push Model Already In Workbook

The workbook's `Comparison ` sheet includes a simple predicted pedestrian count:

`predicted pedestrians = 3600 / mean seconds between FDW and first button push`

Against observed pedestrian totals, this simple model has:

- mean absolute relative error: 38.5%;
- median absolute relative error: 39.4%;
- total observed pedestrians: 1,744;
- total predicted pedestrians: 1,183.5.

Most cases are underpredicted, which is consistent with many pedestrians crossing without pushing the button and with multiple pedestrians being represented by one actuation.

## Recommended Validation Use

Use this dataset to test successively stronger models:

1. naive actuation count only;
2. pedestrians-per-actuation calibration factor;
3. first-push waiting-time model;
4. censored waiting-time model using cycles without a push;
5. models stratified by site type, direction, compliance, or pedestrian volume.

The next analysis should rebuild the validation from the raw second-by-second sheets, not only the workbook's summary formulas, so that censored cycles and cycle-level observations can be handled explicitly.
