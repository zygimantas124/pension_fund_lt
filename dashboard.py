import datetime
import json

import pandas as pd
from dateutil.relativedelta import relativedelta

import dash
from dash import Dash, html, dcc, dash_table, Input, Output, State

# ----------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------
df = pd.read_csv("combined_results.csv")
df["report_date"] = pd.to_datetime(df["report_date"])

# ----------------------------------------------------------------------
# i18n: load translations
# ----------------------------------------------------------------------
with open("i18n_en.json", encoding="utf-8") as f:
    I18N_EN = json.load(f)
with open("i18n_lt.json", encoding="utf-8") as f:
    I18N_LT = json.load(f)

TRANSLATIONS = {
    "en": I18N_EN,
    "lt": I18N_LT,
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Translate a key with optional format variables."""
    template = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)
    try:
        return template.format(**kwargs)
    except Exception:
        return template


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def get_ytd_range(df_sub: pd.DataFrame) -> tuple:
    end = df_sub["report_date"].max()
    start = datetime.datetime(end.year, 1, 1)
    return start, end


def get_previous_year_range(df_sub: pd.DataFrame, months: int) -> tuple:
    end = df_sub["report_date"].max()
    base = end - relativedelta(months=months - 1)
    candidates = df_sub.loc[df_sub["report_date"] > base, "report_date"]
    start = candidates.min()
    return start, end


def get_range(df_sub: pd.DataFrame, period) -> tuple:
    """
    period: "YTD", "ALL", "1", "2", "3", "4", "5" (years)
    Window is defined for whatever df_sub is passed in.
    "ALL" is exposed as "Since Inception" in the UI.
    """
    if period == "YTD":
        return get_ytd_range(df_sub)

    if period == "ALL":  # "Since Inception" in the UI
        start, end = df_sub["report_date"].min(), df_sub["report_date"].max()
        return start, end

    if isinstance(period, str) and period.isdigit():
        years = int(period)
        return get_previous_year_range(df_sub, years * 12)

    if isinstance(period, int):
        return get_previous_year_range(df_sub, period * 12)

    raise ValueError("Range must be 'YTD', 'ALL', or an integer-like string")


def geometric_cumulative_growth(series: pd.Series) -> float:
    results = series / 100.0
    if results.empty:
        return float("nan")
    return round(((1.0 + results).prod() - 1.0) * 100.0, 2)


def annualised_yearly_return(series: pd.Series) -> float:
    series = series.dropna()
    quarters = len(series)

    if quarters == 0:
        return float("nan")

    years = quarters / 4.0
    if years <= 0:
        return float("nan")

    total_growth_pct = geometric_cumulative_growth(series)
    total_growth = total_growth_pct / 100.0

    annualised = (1.0 + total_growth) ** (1.0 / years) - 1.0
    return round(annualised * 100.0, 2)


def fmt_signed(val: float, decimals: int = 2, msg_if_nan: str = "Fund did not exist") -> str:
    """
    Format a float with explicit + / - sign.
    If val is NaN, return msg_if_nan.
    """
    if pd.isna(val):
        return msg_if_nan
    fmt = "{:+." + str(decimals) + "f}"
    return fmt.format(val)


def replace_nan_with_msg(rows, skip_keys=("company_short",), msg="Fund did not exist"):
    """Replace any None/NaN/'nan'/'' values in rows dicts with a message."""
    for row in rows:
        for k, v in list(row.items()):
            if k in skip_keys:
                continue
            if v is None:
                row[k] = msg
            elif isinstance(v, float) and pd.isna(v):
                row[k] = msg
            elif isinstance(v, str) and v.strip().lower() in {"nan", ""}:
                row[k] = msg
    return rows


# ----------------------------------------------------------------------
# Dash app
# ----------------------------------------------------------------------
app = Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

fund_type_options = sorted(df["fund_type"].dropna().unique())
company_options = sorted(df["company_short"].dropna().unique())

base_table_style = {
    "width": "100%",
    "height": "auto",
    "overflowY": "auto",
}

base_cell_style = {
    "fontFamily": "'Helvetica Neue'",
    "fontSize": "13px",
    "padding": "4px 6px",
    "textAlign": "left",
}

base_header_style = {
    "fontFamily": "'Helvetica Neue'",
    "fontWeight": "600",
    "borderBottom": "1px solid #ccc",
    "backgroundColor": "#f0f0f0",
}

card_style = {
    "backgroundColor": "#ffffff",
    "borderRadius": "8px",
    "padding": "10px 12px",
    "boxShadow": "0 1px 4px rgba(15, 23, 42, 0.16)",
    "marginBottom": "10px",
}

# initial columns (English by default)
growth_columns_en = [
    {"name": t("col.fund", "en"), "id": "company_short", "type": "text"},
    {"name": t("col.cumulative_growth", "en"), "id": "cumulative_growth", "type": "text"},
]
avg_columns_en = [
    {"name": t("col.fund", "en"), "id": "company_short", "type": "text"},
    {"name": t("col.avg_yearly_return", "en"), "id": "avg_yearly_return", "type": "text"},
]
extremes_columns_en = [
    {"name": t("col.fund", "en"), "id": "company_short", "type": "text"},
    {"name": t("col.worst_quarter", "en"), "id": "worst_quarter", "type": "text"},
    {"name": t("col.best_quarter", "en"), "id": "best_quarter", "type": "text"},
]
participants_columns_en = [
    {"name": t("col.fund", "en"), "id": "company_short", "type": "text"},
    {"name": t("col.participants_latest", "en"), "id": "participants_latest", "type": "text"},
    {"name": t("col.participants_change", "en"), "id": "participants_change", "type": "text"},
]
bar_columns_en = [
    {"name": t("col.fund", "en"), "id": "company_short", "type": "text"},
    {"name": t("col.expense_ratio", "en"), "id": "expense_ratio", "type": "text"},
]

app.layout = html.Div(
    [
        # Language selector
        html.Div(
            [
                dcc.RadioItems(
                    id="lang-selector",
                    options=[
                        {"label": "EN", "value": "en"},
                        {"label": "LT", "value": "lt"},
                    ],
                    value="en",
                    labelStyle={
                        "display": "inline-block",
                        "marginRight": "8px",
                        "cursor": "pointer",
                        "fontFamily": "'Helvetica Neue'",
                        "fontSize": "12px",
                    },
                    style={"textAlign": "right", "marginBottom": "6px"},
                )
            ]
        ),

        html.H1(
            id="title",
            style={
                "textAlign": "center",
                "marginBottom": "12px",
                "fontFamily": "'Helvetica Neue'",
            },
        ),

        # ------------------------------------------------------------------
        # Filters card: Fund type, Fund manager, period buttons
        # ------------------------------------------------------------------
        html.Div(
            [
                html.Div(
                    [
                        html.Label(
                            id="label-fund-type",
                            style={"marginBottom": "8px", "display": "block"},
                        ),
                        dcc.Dropdown(
                            id="fund-type-dropdown",
                            options=[{"label": ft, "value": ft} for ft in fund_type_options],
                            clearable=False,
                            value=fund_type_options[6],  # default fund type
                            style={"fontFamily": "'Helvetica Neue'"},
                        ),
                    ],
                    style={"marginBottom": "8px"},
                ),
                html.Div(
                    [
                        html.Label(
                            id="label-manager",
                            style={"marginBottom": "8px", "display": "block"},
                        ),
                        dcc.Dropdown(
                            id="manager-dropdown",
                            options=[{"label": c, "value": c} for c in company_options],
                            clearable=False,
                            value=company_options[3],  # default manager
                            style={"fontFamily": "'Helvetica Neue'"},
                        ),
                    ],
                    style={"marginBottom": "8px"},
                ),
                html.Div(
                    [
                        html.Label(
                            id="label-period",
                            style={"marginBottom": "8px", "display": "block"},
                        ),
                        dcc.RadioItems(
                            id="period-selector",
                            options=[
                                {"label": t("period.ytd", "en"), "value": "YTD"},
                                {"label": t("period.1y", "en"), "value": "1"},
                                {"label": t("period.2y", "en"), "value": "2"},
                                {"label": t("period.3y", "en"), "value": "3"},
                                {"label": t("period.4y", "en"), "value": "4"},
                                {"label": t("period.5y", "en"), "value": "5"},
                                {"label": t("period.since_inception", "en"), "value": "ALL"},
                            ],
                            value="YTD",
                            labelStyle={
                                "display": "inline-block",
                                "marginRight": "8px",
                                "padding": "3px 8px",
                                "border": "1px solid #ddd",
                                "borderRadius": "16px",
                                "cursor": "pointer",
                                "fontSize": "12px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                            style={"marginTop": "4px"},
                        ),
                        html.Div(
                            id="date-range-display",
                            style={
                                "marginTop": "6px",
                                "fontSize": "12px",
                                "color": "#555",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                    ],
                ),
            ],
            style={**card_style, "marginBottom": "14px"},
        ),

        # ------------------------------------------------------------------
        # Tables: each in its own card, with tight spacing
        # ------------------------------------------------------------------
        html.Div(
            [
                html.Div(
                    [
                        html.H3(
                            id="title-growth",
                            style={
                                "marginTop": 0,
                                "fontSize": "16px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        html.P(
                            id="help-growth",
                            style={
                                "fontSize": "12px",
                                "color": "#555",
                                "marginTop": "2px",
                                "marginBottom": "6px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        dash_table.DataTable(
                            id="growth-table",
                            columns=growth_columns_en,
                            data=[],
                            style_table=base_table_style,
                            style_cell=base_cell_style,
                            style_header=base_header_style,
                            page_size=50,
                            cell_selectable=False,
                        ),
                    ],
                    style=card_style,
                ),
                html.Div(
                    [
                        html.H3(
                            id="title-avg",
                            style={
                                "marginTop": 0,
                                "fontSize": "16px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        html.P(
                            id="help-avg",
                            style={
                                "fontSize": "12px",
                                "color": "#555",
                                "marginTop": "2px",
                                "marginBottom": "6px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        dash_table.DataTable(
                            id="avg-yearly-table",
                            columns=avg_columns_en,
                            data=[],
                            style_table=base_table_style,
                            style_cell=base_cell_style,
                            style_header=base_header_style,
                            page_size=50,
                            cell_selectable=False,
                        ),
                    ],
                    style=card_style,
                ),
                html.Div(
                    [
                        html.H3(
                            id="title-extremes",
                            style={
                                "marginTop": 0,
                                "fontSize": "16px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        html.P(
                            id="help-extremes",
                            style={
                                "fontSize": "12px",
                                "color": "#555",
                                "marginTop": "2px",
                                "marginBottom": "6px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        dash_table.DataTable(
                            id="extremes-table",
                            columns=extremes_columns_en,
                            data=[],
                            style_table=base_table_style,
                            style_cell=base_cell_style,
                            style_header=base_header_style,
                            page_size=50,
                            cell_selectable=False,
                        ),
                    ],
                    style=card_style,
                ),
                html.Div(
                    [
                        html.H3(
                            id="title-participants",
                            style={
                                "marginTop": 0,
                                "fontSize": "16px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        html.P(
                            id="help-participants",
                            style={
                                "fontSize": "12px",
                                "color": "#555",
                                "marginTop": "2px",
                                "marginBottom": "6px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        dash_table.DataTable(
                            id="participants-table",
                            columns=participants_columns_en,
                            data=[],
                            style_table=base_table_style,
                            style_cell=base_cell_style,
                            style_header=base_header_style,
                            page_size=50,
                            cell_selectable=False,
                        ),
                    ],
                    style=card_style,
                ),
                html.Div(
                    [
                        html.H3(
                            id="title-expenses",
                            style={
                                "marginTop": 0,
                                "fontSize": "16px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        html.P(
                            id="help-expenses",
                            style={
                                "fontSize": "12px",
                                "color": "#555",
                                "marginTop": "2px",
                                "marginBottom": "6px",
                                "fontFamily": "'Helvetica Neue'",
                            },
                        ),
                        dash_table.DataTable(
                            id="bar-table",
                            columns=bar_columns_en,
                            data=[],
                            style_table=base_table_style,
                            style_cell=base_cell_style,
                            style_header=base_header_style,
                            page_size=50,
                            cell_selectable=False,
                        ),
                    ],
                    style=card_style,
                ),
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "gap": "6px",
            },
        ),
    ],
    style={
        "maxWidth": "1100px",
        "margin": "0 auto",
        "padding": "10px",
        "backgroundColor": "#f5f5f5",
        "fontFamily": "'Helvetica Neue'",
    },
)

# ----------------------------------------------------------------------
# Callback 0: static texts & column names based on language
# ----------------------------------------------------------------------
@app.callback(
    Output("title", "children"),
    Output("label-fund-type", "children"),
    Output("label-manager", "children"),
    Output("label-period", "children"),
    Output("title-growth", "children"),
    Output("help-growth", "children"),
    Output("title-avg", "children"),
    Output("help-avg", "children"),
    Output("title-extremes", "children"),
    Output("help-extremes", "children"),
    Output("title-participants", "children"),
    Output("help-participants", "children"),
    Output("title-expenses", "children"),
    Output("help-expenses", "children"),
    Output("growth-table", "columns"),
    Output("avg-yearly-table", "columns"),
    Output("extremes-table", "columns"),
    Output("participants-table", "columns"),
    Output("bar-table", "columns"),
    Input("lang-selector", "value"),
)
def update_texts_and_columns(lang):
    growth_columns = [
        {"name": t("col.fund", lang), "id": "company_short", "type": "text"},
        {"name": t("col.cumulative_growth", lang), "id": "cumulative_growth", "type": "text"},
    ]
    avg_columns = [
        {"name": t("col.fund", lang), "id": "company_short", "type": "text"},
        {"name": t("col.avg_yearly_return", lang), "id": "avg_yearly_return", "type": "text"},
    ]
    extremes_columns = [
        {"name": t("col.fund", lang), "id": "company_short", "type": "text"},
        {"name": t("col.worst_quarter", lang), "id": "worst_quarter", "type": "text"},
        {"name": t("col.best_quarter", lang), "id": "best_quarter", "type": "text"},
    ]
    participants_columns = [
        {"name": t("col.fund", lang), "id": "company_short", "type": "text"},
        {"name": t("col.participants_latest", lang), "id": "participants_latest", "type": "text"},
        {"name": t("col.participants_change", lang), "id": "participants_change", "type": "text"},
    ]
    bar_columns = [
        {"name": t("col.fund", lang), "id": "company_short", "type": "text"},
        {"name": t("col.expense_ratio", lang), "id": "expense_ratio", "type": "text"},
    ]

    return (
        t("app.title", lang),
        t("label.fund_type", lang),
        t("label.manager", lang),
        t("label.period", lang),
        t("section.growth.title", lang),
        t("section.growth.help", lang),
        t("section.avg_return.title", lang),
        t("section.avg_return.help", lang),
        t("section.extremes.title", lang),
        t("section.extremes.help", lang),
        t("section.participants.title", lang),
        t("section.participants.help", lang),
        t("section.expenses.title", lang),
        t("section.expenses.help", lang),
        growth_columns,
        avg_columns,
        extremes_columns,
        participants_columns,
        bar_columns,
    )


# ----------------------------------------------------------------------
# Callback 1: update managers + period buttons based on fund type + manager + language
# ----------------------------------------------------------------------
@app.callback(
    Output("manager-dropdown", "options"),
    Output("manager-dropdown", "value"),
    Output("period-selector", "options"),
    Output("period-selector", "value"),
    Input("fund-type-dropdown", "value"),
    Input("manager-dropdown", "value"),
    Input("lang-selector", "value"),
    State("period-selector", "value"),
)
def update_controls(selected_fund_type, selected_manager, lang, current_period):
    # Base period options in current language
    base_period_opts = [
        {"label": t("period.ytd", lang), "value": "YTD"},
        {"label": t("period.1y", lang), "value": "1"},
        {"label": t("period.2y", lang), "value": "2"},
        {"label": t("period.3y", lang), "value": "3"},
        {"label": t("period.4y", lang), "value": "4"},
        {"label": t("period.5y", lang), "value": "5"},
        {"label": t("period.since_inception", lang), "value": "ALL"},
    ]

    # No fund type selected → all managers, all periods
    if not selected_fund_type:
        managers = sorted(df["company_short"].dropna().unique())
        manager_opts = [{"label": c, "value": c} for c in managers]
        manager_val = (
            selected_manager
            if selected_manager in managers
            else managers[0]
            if managers
            else None
        )

        valid_period_vals = [p["value"] for p in base_period_opts]
        period_val = current_period if current_period in valid_period_vals else "YTD"
        return manager_opts, manager_val, base_period_opts, period_val

    # Filter managers by fund type
    fund_df = df[df["fund_type"] == selected_fund_type]
    managers = sorted(fund_df["company_short"].dropna().unique())
    manager_opts = [{"label": c, "value": c} for c in managers]

    if selected_manager in managers:
        manager_val = selected_manager
    else:
        manager_val = managers[0] if managers else None

    # Restrict period buttons based on selected manager history
    if manager_val is not None:
        manager_df = fund_df[fund_df["company_short"] == manager_val]
    else:
        manager_df = fund_df

    min_date = manager_df["report_date"].min()
    max_date = manager_df["report_date"].max()
    if pd.isna(min_date) or pd.isna(max_date):
        span_years = 0.0
    else:
        span_years = (max_date - min_date).days / 365.25

    max_whole_years = int(span_years)
    max_button_years = min(max_whole_years, 5)

    # Always include YTD
    period_opts = [next(o for o in base_period_opts if o["value"] == "YTD")]
    # Add only the years that fit the manager's history
    for y in range(1, max_button_years + 1):
        period_opts.append(next(o for o in base_period_opts if o["value"] == str(y)))
    # Always include Since Inception
    period_opts.append(next(o for o in base_period_opts if o["value"] == "ALL"))

    valid_period_vals = [p["value"] for p in period_opts]
    period_val = current_period if current_period in valid_period_vals else "YTD"

    return manager_opts, manager_val, period_opts, period_val

# ----------------------------------------------------------------------
# Callback 2: update date range text (from - to)
# ----------------------------------------------------------------------
@app.callback(
    Output("date-range-display", "children"),
    Input("fund-type-dropdown", "value"),
    Input("period-selector", "value"),
    Input("manager-dropdown", "value"),
    Input("lang-selector", "value"),
)
def update_date_range(selected_fund_type, selected_period, selected_company, lang):
    if not selected_fund_type or not selected_period:
        return ""
    fund_df = df[df["fund_type"] == selected_fund_type]
    if fund_df.empty:
        return ""

    # Match semantics used in update_tables for Since Inception
    if selected_period == "ALL" and selected_company:
        base_df = fund_df[fund_df["company_short"] == selected_company]
        if base_df.empty:
            base_df = fund_df
    else:
        base_df = fund_df

    start, end = get_range(base_df, selected_period)
    if pd.isna(start) or pd.isna(end):
        return ""

    return t("label.date_range", lang, start=start.date(), end=end.date())


# ----------------------------------------------------------------------
# Callback 3: update tables & styles
# ----------------------------------------------------------------------
@app.callback(
    Output("growth-table", "data"),
    Output("avg-yearly-table", "data"),
    Output("extremes-table", "data"),
    Output("participants-table", "data"),
    Output("bar-table", "data"),
    Output("growth-table", "style_data_conditional"),
    Output("avg-yearly-table", "style_data_conditional"),
    Output("extremes-table", "style_data_conditional"),
    Output("participants-table", "style_data_conditional"),
    Output("bar-table", "style_data_conditional"),
    Input("fund-type-dropdown", "value"),
    Input("period-selector", "value"),
    Input("manager-dropdown", "value"),
    Input("lang-selector", "value"),
)
def update_tables(selected_fund_type, selected_period, selected_company, lang):
    if not selected_fund_type or not selected_period:
        empty = [], [], [], [], [], [], [], [], [], []
        return empty

    msg_not_exist = t("msg.fund_not_exist", lang)
    msg_no_data = t("msg.no_data_reported", lang)

    fund_df = df[df["fund_type"] == selected_fund_type].copy()

    coverage_years = {}
    for company, grp_all in fund_df.groupby("company_short"):
        span_days = (grp_all["report_date"].max() - grp_all["report_date"].min()).days
        coverage_years[company] = span_days / 365.25

    requested_years = None
    if isinstance(selected_period, str) and selected_period.isdigit():
        requested_years = int(selected_period)

    # Since Inception → base on selected manager's history
    if selected_period == "ALL" and selected_company:
        base_df = fund_df[fund_df["company_short"] == selected_company]
        if base_df.empty:
            base_df = fund_df
    else:
        base_df = fund_df

    start, end = get_range(base_df, selected_period)
    range_fund_data = fund_df[
        (fund_df["report_date"] >= start) & (fund_df["report_date"] <= end)
    ].copy()

    all_companies = sorted(fund_df["company_short"].unique())

    growth_numeric, growth_nodata = [], []
    avg_numeric, avg_nodata = [], []
    extremes_numeric, extremes_nodata = [], []
    part_numeric, part_nodata = [], []
    bar_numeric, bar_nodata = [], []

    for company in all_companies:
        grp_range = range_fund_data[range_fund_data["company_short"] == company]
        cov_years = coverage_years.get(company, 0.0)

        has_enough_history = True
        if requested_years is not None:
            has_enough_history = cov_years + 1e-6 >= requested_years

        if grp_range.empty or not has_enough_history:
            growth_nodata.append(
                {"company_short": company, "cumulative_growth": msg_not_exist}
            )
            avg_nodata.append(
                {"company_short": company, "avg_yearly_return": msg_not_exist}
            )
            extremes_nodata.append(
                {
                    "company_short": company,
                    "worst_quarter": msg_not_exist,
                    "best_quarter": msg_not_exist,
                }
            )
            part_nodata.append(
                {
                    "company_short": company,
                    "participants_latest": msg_not_exist,
                    "participants_change": msg_not_exist,
                }
            )
            bar_nodata.append(
                {"company_short": company, "expense_ratio": msg_not_exist}
            )
        else:
            grp_sorted = grp_range.sort_values("report_date")

            # performance
            growth_val = geometric_cumulative_growth(grp_sorted["relative_change"])
            avg_val = annualised_yearly_return(grp_sorted["relative_change"])

            # extremes
            worst_val = round(grp_sorted["relative_change"].min(), 2)
            best_val = round(grp_sorted["relative_change"].max(), 2)

            # participants
            first_part = grp_sorted["number_of_participants"].iloc[0]
            last_part = grp_sorted["number_of_participants"].iloc[-1]
            if pd.isna(first_part) or pd.isna(last_part):
                part_latest_str = msg_not_exist
                part_change_str = msg_not_exist
                sort_part = float("-inf")
            else:
                part_latest = int(last_part)
                part_change = int(last_part - first_part)
                part_latest_str = str(part_latest)
                part_change_str = f"{part_change:+d}"
                sort_part = part_latest

            # BAR
            bar_last = grp_sorted["bar_pct"].iloc[-1]
            if pd.isna(bar_last):
                bar_str = msg_no_data
                sort_bar = float("inf")
            else:
                bar_str = f"{bar_last:.3f}"
                sort_bar = bar_last

            growth_numeric.append(
                {
                    "company_short": company,
                    "cumulative_growth": fmt_signed(growth_val, 2, msg_if_nan=msg_not_exist),
                    "_sort": growth_val,
                }
            )
            avg_numeric.append(
                {
                    "company_short": company,
                    "avg_yearly_return": fmt_signed(avg_val, 2, msg_if_nan=msg_not_exist),
                    "_sort": avg_val,
                }
            )
            extremes_numeric.append(
                {
                    "company_short": company,
                    "worst_quarter": fmt_signed(worst_val, 2, msg_if_nan=msg_not_exist),
                    "best_quarter": fmt_signed(best_val, 2, msg_if_nan=msg_not_exist),
                    "_sort": worst_val,
                }
            )
            part_numeric.append(
                {
                    "company_short": company,
                    "participants_latest": part_latest_str,
                    "participants_change": part_change_str,
                    "_sort": sort_part,
                }
            )
            bar_numeric.append(
                {
                    "company_short": company,
                    "expense_ratio": bar_str,
                    "_sort": sort_bar,
                }
            )

    # sort numeric rows, then append "not exist / no data" rows at bottom
    growth_numeric.sort(key=lambda r: r["_sort"], reverse=True)
    avg_numeric.sort(key=lambda r: r["_sort"], reverse=True)
    extremes_numeric.sort(key=lambda r: r["_sort"])  # more negative worst first
    part_numeric.sort(key=lambda r: r["_sort"], reverse=True)
    bar_numeric.sort(key=lambda r: r["_sort"])  # cheaper first

    for lst in (growth_numeric, avg_numeric, extremes_numeric, part_numeric, bar_numeric):
        for r in lst:
            r.pop("_sort", None)

    growth_rows = growth_numeric + growth_nodata
    avg_rows = avg_numeric + avg_nodata
    extremes_rows = extremes_numeric + extremes_nodata
    participants_rows = part_numeric + part_nodata
    bar_rows = bar_numeric + bar_nodata

    # Replace any remaining NaNs / 'nan' / empty strings
    growth_rows = replace_nan_with_msg(growth_rows, msg=msg_not_exist)
    avg_rows = replace_nan_with_msg(avg_rows, msg=msg_not_exist)
    extremes_rows = replace_nan_with_msg(extremes_rows, msg=msg_not_exist)
    participants_rows = replace_nan_with_msg(participants_rows, msg=msg_not_exist)
    bar_rows = replace_nan_with_msg(bar_rows, msg=msg_no_data)

    # styles
    highlight_rule = []
    if selected_company:
        highlight_rule = [
            {
                "if": {"filter_query": f'{{company_short}} = "{selected_company}"'},
                "backgroundColor": "#fff3cd",
                "fontWeight": "700",
            }
        ]

    growth_style = [
        {
            "if": {
                "filter_query": '{cumulative_growth} contains "+"',
                "column_id": "cumulative_growth",
            },
            "color": "#2e7d32",
            "fontWeight": "600",
        },
        {
            "if": {
                "filter_query": '{cumulative_growth} contains "-"',
                "column_id": "cumulative_growth",
            },
            "color": "#c62828",
            "fontWeight": "600",
        },
    ] + highlight_rule

    avg_style = [
        {
            "if": {
                "filter_query": '{avg_yearly_return} contains "+"',
                "column_id": "avg_yearly_return",
            },
            "color": "#2e7d32",
            "fontWeight": "600",
        },
        {
            "if": {
                "filter_query": '{avg_yearly_return} contains "-"',
                "column_id": "avg_yearly_return",
            },
            "color": "#c62828",
            "fontWeight": "600",
        },
    ] + highlight_rule

    extremes_style = [
        {
            "if": {
                "filter_query": '{worst_quarter} contains "-"',
                "column_id": "worst_quarter",
            },
            "color": "#c62828",
            "fontWeight": "600",
        },
        {
            "if": {
                "filter_query": '{worst_quarter} contains "+"',
                "column_id": "worst_quarter",
            },
            "color": "#2e7d32",
            "fontWeight": "600",
        },
        {
            "if": {
                "filter_query": '{best_quarter} contains "+"',
                "column_id": "best_quarter",
            },
            "color": "#2e7d32",
            "fontWeight": "600",
        },
        {
            "if": {
                "filter_query": '{best_quarter} contains "-"',
                "column_id": "best_quarter",
            },
            "color": "#c62828",
            "fontWeight": "600",
        },
    ] + highlight_rule

    participants_style = [
        {
            "if": {
                "filter_query": '{participants_change} contains "+"',
                "column_id": "participants_change",
            },
            "color": "#2e7d32",
            "fontWeight": "600",
        },
        {
            "if": {
                "filter_query": '{participants_change} contains "-"',
                "column_id": "participants_change",
            },
            "color": "#c62828",
            "fontWeight": "600",
        },
    ] + highlight_rule

    bar_style = [] + highlight_rule

    return (
        growth_rows,
        avg_rows,
        extremes_rows,
        participants_rows,
        bar_rows,
        growth_style,
        avg_style,
        extremes_style,
        participants_style,
        bar_style,
    )


if __name__ == "__main__":
    app.run(debug=True)