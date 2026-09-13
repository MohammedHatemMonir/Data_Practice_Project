from __future__ import annotations

import logging
import re
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


def load_state_territory_ghg() -> pd.DataFrame:
    """
    Real: 'State & Territory Inventories 2024 - Emission Data Tables' --
    one sheet per state, IPCC sector rows, financial-year columns. Uses
    the '3.  Transport' row -- the WHOLE transport sector (road + rail +
    domestic aviation + shipping combined). This dataset does not break
    transport down further by mode at the state level, so this is the
    finest granularity genuinely available -- treat results as "state
    transport sector emissions", not "road transport emissions"
    specifically. Units: Gg CO2-e, numerically identical to kt CO2-e
    (1 Gg = 1 kt), so no conversion needed.
    Fixture fallback: flat state,year,sector,ghg_kt_co2e CSV.
    """
    path = _locate("state_territory_ghg")
    is_real = path.suffix.lower() in (".xlsx", ".xls") and "NSW" in pd.ExcelFile(path).sheet_names

    if is_real:
        sheet_to_state = {"NSW": "NSW", "Vic": "VIC", "Qld": "QLD", "SA": "SA",
                           "WA": "WA", "Tas": "TAS", "NT": "NT", "ACT": "ACT"}
        fy_pattern = re.compile(r"^\d{4}-\d{2}$")
        records = []
        for sheet, state in sheet_to_state.items():
            raw = pd.read_excel(path, sheet_name=sheet, header=None)
            row0 = raw[0].astype(str).str.strip()
            transport_row = raw[row0 == "3.  Transport"]
            if transport_row.empty:
                log.warning("'%s' sheet: '3.  Transport' row not found, skipping", sheet)
                continue
            year_header = raw.iloc[6]
            vals = transport_row.iloc[0]
            for col in raw.columns[1:]:
                fy = year_header[col]
                if not isinstance(fy, str) or not fy_pattern.match(fy.strip()):
                    continue
                emissions = pd.to_numeric(vals[col], errors="coerce")
                if pd.notna(emissions):
                    records.append({
                        "state": state,
                        "year": _parse_financial_year(fy),
                        "sector": "Transport",
                        "ghg_kt_co2e": emissions,
                    })
        df = pd.DataFrame(records)
    else:
        df = _read_tabular(path)

    df = _standardise_state(df)
    df["ghg_kt_co2e"] = pd.to_numeric(df["ghg_kt_co2e"], errors="coerce")
    df = df.dropna(subset=["ghg_kt_co2e"])
    return df


def load_nga_factors() -> pd.DataFrame:
    """
    Real: NGA Factors 2025 workbook, 'Table 9' (transport fuels by
    equipment type) -- multi-row header, 'Transport type' forward-filled
    down merged cells. Only 'Cars and light commercial vehicles' x
    Gasoline/Diesel oil are extracted -- the two fuels petroleum_statistics
    actually reports at state level. Factor = energy content (GJ/kL) x
    combined Scope 1 factor (kg CO2-e/GJ) / 1000 -- the two-step real
    calculation, not a single looked-up number.
    (Table 8, stationary energy factors, exists in the same workbook but
    isn't used -- not relevant to a transport emissions model.)
    Fixture fallback: flat fuel_type,factor_kg_co2e_per_l CSV.
    """
    path = _locate("nga_factors_2025")
    is_real = path.suffix.lower() in (".xlsx", ".xls") and "Table 9" in pd.ExcelFile(path).sheet_names

    if is_real:
        raw = pd.read_excel(path, sheet_name="Table 9", header=None, skiprows=3)
        raw.columns = ["transport_type", "fuel_type", "energy_content", "sc1_co2",
                       "sc1_ch4", "sc1_n2o", "sc1_combined", "sc3"]
        raw["transport_type"] = raw["transport_type"].ffill()
        target = raw[
            (raw["transport_type"] == "Cars and light commercial vehicles")
            & (raw["fuel_type"].isin(["Gasoline", "Diesel oil"]))
        ].copy()
        target["energy_content"] = pd.to_numeric(target["energy_content"], errors="coerce")
        target["sc1_combined"] = pd.to_numeric(target["sc1_combined"], errors="coerce")
        target["factor_kg_co2e_per_l"] = target["energy_content"] * target["sc1_combined"] / 1000
        df = target[["fuel_type", "factor_kg_co2e_per_l"]]
    else:
        df = _read_tabular(path)

    df["factor_kg_co2e_per_l"] = pd.to_numeric(df["factor_kg_co2e_per_l"], errors="coerce")
    return df.dropna(subset=["factor_kg_co2e_per_l"])


def load_bitre_yearbook() -> pd.DataFrame:
    """
    Real: BITRE Yearbook 'Table 4.3' -- total VKT by state/territory,
    wide format (states as columns, financial years as rows), in BILLION
    vehicle-km (converted to million here to match this project's unit).
    Fixture fallback: flat state,year,mode,vkt_million_km CSV.
    """
    path = _locate("bitre_yearbook")
    is_real = path.suffix.lower() in (".xlsx", ".xls") and "Table 4.3" in pd.ExcelFile(path).sheet_names

    if is_real:
        raw = pd.read_excel(path, sheet_name="Table 4.3", header=None)
        state_cols = raw.iloc[3]
        col_map = {c: state_cols[c] for c in raw.columns if state_cols[c] in VALID_STATES}
        records = []
        for col, state in col_map.items():
            block = raw.iloc[5:, [0, col]].copy()
            block.columns = ["fy", "vkt_billion_km"]
            block["state"] = state
            records.append(block)
        df = pd.concat(records, ignore_index=True)
        df = df.dropna(subset=["fy", "vkt_billion_km"])
        df["year"] = df["fy"].astype(str).str.split("-").str[0].astype(int)
        df["vkt_million_km"] = pd.to_numeric(df["vkt_billion_km"], errors="coerce") * 1000
        df = df[["state", "year", "vkt_million_km"]]
    else:
        df = _read_tabular(path)

    df = _standardise_state(df)
    df["vkt_million_km"] = pd.to_numeric(df["vkt_million_km"], errors="coerce")
    df = df.dropna(subset=["vkt_million_km"])
    return df