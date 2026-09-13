from __future__ import annotations


from pathlib import Path

import pandas as pd


def load_petroleum_statistics() -> pd.DataFrame:
    """
    Real: Australian Petroleum Statistics 'Sales by state and territory'
    sheet -- wide format, one column per fuel product. Only the two
    road-relevant totals are kept (automotive gasoline, diesel oil);
    aviation turbine fuel and other non-road products are excluded.
    Note: ACT is genuinely absent from this source's state breakdown --
    not a parsing gap, confirmed against the raw file's own State column.
    Fixture fallback: flat state,year,month,product,consumption_ml CSV.
    """
    path = _locate("petroleum_statistics")
    is_real = (
        path.suffix.lower() in (".xlsx", ".xls")
        and "Sales by state and territory" in pd.ExcelFile(path).sheet_names
    )

    if is_real:
        raw = pd.read_excel(path, sheet_name="Sales by state and territory")
        raw = raw.rename(columns={"State": "state", "Month": "date"})
        gasoline = raw[["state", "date", "Automotive gasoline: total (ML)"]].rename(
            columns={"Automotive gasoline: total (ML)": "consumption_ml"}
        )
        gasoline["product"] = "Gasoline"
        diesel = raw[["state", "date", "Diesel oil: total"]].rename(
            columns={"Diesel oil: total": "consumption_ml"}
        )
        diesel["product"] = "Diesel oil"
        df = pd.concat([gasoline, diesel], ignore_index=True)
        df["date"] = pd.to_datetime(df["date"])
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
        df["fy_year"] = df["date"].apply(_fy_start_from_date)
    else:
        df = _read_tabular(path)
        df["date"] = pd.to_datetime(dict(year=df["year"], month=df["month"], day=1))
        df["fy_year"] = df["date"].apply(_fy_start_from_date)

    df = _standardise_state(df)
    df["consumption_ml"] = pd.to_numeric(df["consumption_ml"], errors="coerce")
    df = df.dropna(subset=["consumption_ml"])
    return df

