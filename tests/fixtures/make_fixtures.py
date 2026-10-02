"""Generate the SYNTHETIC test downloads in this folder.

The numbers are invented for testing and are NOT OECD statistics. The
column layout imitates the SDMX-CSV the OECD API returns.

Run: python tests/fixtures/make_fixtures.py
"""

import csv
from pathlib import Path

HERE = Path(__file__).parent


def months(start_year, start_month, n):
    y, m = start_year, start_month
    for _ in range(n):
        yield f"{y}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def quarters(start_year, n):
    for i in range(n):
        yield f"{start_year + i // 4}-Q{i % 4 + 1}"


def write(name, header, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


# Unemployment: monthly, 2024-01 to 2025-08.
une_header = ["DATAFLOW", "REF_AREA", "MEASURE", "UNIT_MEASURE", "TRANSFORMATION", "ADJUSTMENT",
              "SEX", "AGE", "ACTIVITY", "FREQ", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS",
              "UNIT_MULT", "DECIMALS"]
une_series = {
    "USA": [3.7, 3.9, 3.8, 3.9, 4.0, 4.1, 4.3, 4.2, 4.1, 4.1, 4.2, 4.1,
            4.0, 4.1, 4.2, 4.2, 4.2, 4.1, 4.2, 4.3],
    "FRA": [7.4, 7.4, 7.5, 7.4, 7.3, 7.4, 7.5, 7.5, 7.6, 7.6, 7.7, 7.6,
            7.5, 7.4, 7.5, 7.5, 7.6, 7.5, 7.5, 7.5],
    "ITA": [7.2, 7.0, 7.1, 6.9, 6.8, 7.0, 6.6, 6.4, 6.1, 5.9, 5.8, 6.2,
            6.3, 5.9, "", 6.0, 6.5, 6.3, 6.0, 6.7],
    "EA20": [6.5] * 20,  # not in the test config -> must be dropped
}
rows = []
for area, values in une_series.items():
    for period, v in zip(months(2024, 1, 20), values):
        rows.append(["OECD.SDD.TPS:DSD_LFS@DF_IALFS_UNE_M(1.0)", area, "UNE_LF_M", "PT_LF_SUB",
                     "_Z", "Y", "_T", "Y_GE15", "_Z", "M", period, v, "A", "0", "1"])
write("unemployment_rate_20251001T080000Z.csv", une_header, rows)

# CPI inflation: monthly, year-on-year.
cpi_header = ["DATAFLOW", "REF_AREA", "FREQ", "METHODOLOGY", "MEASURE", "UNIT_MEASURE",
              "EXPENDITURE", "ADJUSTMENT", "TRANSFORMATION", "TIME_PERIOD", "OBS_VALUE",
              "OBS_STATUS", "UNIT_MULT", "DECIMALS"]
cpi_series = {
    "USA": [3.1, 3.2, 3.5, 3.4, 3.3, 3.0, 2.9, 2.5, 2.4, 2.6, 2.7, 2.9,
            3.0, 2.8, 2.4, 2.3, 2.4, 2.7, 2.7, 2.9],
    "FRA": [3.1, 2.9, 2.3, 2.2, 2.3, 2.2, 2.3, 1.8, 1.1, 1.2, 1.3, 1.3,
            1.7, 0.8, 0.8, 0.8, 0.7, 0.9, 1.0, 0.9],
    "ITA": [0.8, 0.8, 1.2, 0.8, 0.8, 0.8, 1.3, 1.1, 0.7, 0.9, 1.3, 1.3,
            1.5, 1.6, 1.9, 1.9, 1.6, 1.7, 1.7, 1.6],
}
rows = []
for area, values in cpi_series.items():
    for period, v in zip(months(2024, 1, 20), values):
        rows.append(["OECD.SDD.TPS:DSD_PRICES@DF_PRICES_ALL(1.0)", area, "M", "N", "CPI", "PA",
                     "_T", "N", "GY", period, v, "A", "0", "2"])
write("cpi_inflation_20251001T080000Z.csv", cpi_header, rows)

# GDP growth: quarterly, 2023-Q1 to 2025-Q2. FRA has a second series for one
# quarter (duplicate check); ITA stops one quarter early (lagging flag).
gdp_header = ["DATAFLOW", "FREQ", "ADJUSTMENT", "REF_AREA", "SECTOR", "COUNTERPART_SECTOR",
              "TRANSACTION", "INSTR_ASSET", "ACTIVITY", "EXPENDITURE", "UNIT_MEASURE",
              "PRICE_BASE", "TRANSFORMATION", "TABLE_IDENTIFIER", "TIME_PERIOD", "OBS_VALUE",
              "OBS_STATUS", "UNIT_MULT", "DECIMALS"]
gdp_series = {
    "USA": [0.6, 0.5, 1.1, 0.8, 0.4, 0.7, 0.7, 0.6, -0.1, 0.8],
    "FRA": [0.1, 0.6, 0.0, 0.4, 0.2, 0.3, 0.4, -0.1, 0.1, 0.3],
    "ITA": [0.5, -0.2, 0.3, 0.1, 0.3, 0.2, 0.0, 0.2, 0.3],
}
rows = []
for area, values in gdp_series.items():
    for period, v in zip(quarters(2023, 10), values):
        rows.append(["OECD.SDD.NAD:DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD(1.1)", "Q", "Y",
                     area, "S1", "S1", "B1GQ", "_Z", "_Z", "_Z", "PC", "L", "G1", "T0102",
                     period, v, "A", "0", "2"])
rows.append(["OECD.SDD.NAD:DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD(1.1)", "Q", "Y", "FRA",
             "S1", "S1", "B1GQ", "_Z", "_Z", "_Z", "PC", "L", "G1", "T0103", "2025-Q1", 0.2, "A",
             "0", "2"])
write("gdp_growth_20251001T080000Z.csv", gdp_header, rows)

# A download with the wrong columns (e.g. an error page saved as CSV).
write("broken_download.csv", ["message"], [["NoRecordsFound"]])
print("Fixtures written to", HERE)
