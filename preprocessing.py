import os
import numpy as np
import pandas as pd


def enforce_types(financial_data: pd.DataFrame) -> pd.DataFrame:
    for col_name, col_type in COLNAMES_MAPPER.items():
        financial_data[col_name] = financial_data[col_name].astype(col_type)
    return financial_data


def extract_type_from_fund_code(fund_codes: pd.Series) -> pd.Series:
    return fund_codes.str.split("-").str[-1].map(SUFFIX_TO_RANGE)


def fund_code_to_fund_owner(fund_code: str) -> str | None:
    prefix = fund_code.split("-")[0]
    return FUND_OWNERS.get(prefix, None)


def estimate_relative_change(combined_results: pd.DataFrame) -> pd.DataFrame:
    combined_results = combined_results.sort_values(["fund_code", "report_date"])

    fund_codes = combined_results["fund_code"]
    report_dates = combined_results["report_date"]

    ytd = combined_results["unit_value_change_ytd_pct"] / 100.0
    prev_ytd = ytd.groupby(fund_codes).shift(1)
    prev_date = report_dates.groupby(fund_codes).shift(1)

    # Keep first record of the year as that is valid without calculations
    mask_new_year = prev_date.isna() | (
        combined_results["report_date"].dt.year != prev_date.dt.year
    )

    relative_change = np.where(
        mask_new_year | prev_ytd.isna(),
        ytd,
        (1 + ytd) / (1 + prev_ytd) - 1,
    )

    combined_results["relative_change"] = relative_change * 100.0
    return combined_results


SUFFIX_TO_RANGE = {
    "03/09": "2003-2009",
    "96/02": "1996-2002",
    "89/95": "1989-1995",
    "82/88": "1982-1988",
    "75/81": "1975-1981",
    "68/74": "1968-1974",
    "61/67": "1961-1967",
    "54/60": "1954-1960",
    "TIPF": "TIPF",
}

COLNAMES_MAPPER = {
    "company_name": "string",
    "fund_code": "string",
    "fund_name": "string",
    "number_of_participants": "int32",
    "unit_value_change_ytd_pct": "float32",
    "bar_pct": "float32",
}

FUND_OWNERS = {
    "LMN": "Luminor",
    "INV": "Artea",
    "SBN": "SEB",
    "SWD": "Swedbank",
    "AVI": "Allianz",
    "GOX": "Goindex",
}


combined_results = []
for root, dirs, files in os.walk("raw_data"):
    for filename in files:
        if not filename.lower().endswith((".xlsx")):
            continue

        filepath = os.path.join(root, filename)
        print(f"Processing: {filepath}")

        excel_file = pd.read_excel(filepath)
        report_date = excel_file.columns[0]

        financial_data = excel_file.iloc[2:].copy()
        financial_data = financial_data.iloc[:, [0, 1, 2, 6, 8, -3]]

        financial_data.columns = list(COLNAMES_MAPPER.keys())

        financial_data["bar_pct"] = (
            financial_data["bar_pct"]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .str.extract(r"(\d+\.?\d*)")[0]
            .astype(float)
        )

        rows_with_financials = financial_data["fund_code"].notna()
        financial_data = financial_data[rows_with_financials].reset_index(drop=True)

        financial_data = financial_data.replace(["Veikia trumpiau", "-"], None)
        financial_data["report_date"] = report_date
        financial_data = enforce_types(financial_data)

        fund_codes = financial_data["fund_code"]
        financial_data["fund_type"] = extract_type_from_fund_code(fund_codes)
        financial_data["company_short"] = fund_codes.apply(fund_code_to_fund_owner)

        financial_data = financial_data.dropna(subset=["unit_value_change_ytd_pct"])
        combined_results.append(financial_data)

if combined_results:
    combined = pd.concat(combined_results, ignore_index=True)
    combined_results = estimate_relative_change(combined)
    path = "combined_results.csv"
    combined_results.to_csv(path, index=False)
    print(f"Saved combined file: {path}")
else:
    print("No Excel files found / processed.")
