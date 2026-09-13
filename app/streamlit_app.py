
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src import db  # noqa: E402

st.set_page_config(page_title="Transport Emissions (Australia)", layout="wide")

DRIFT_REPORT_PATH = REPO_ROOT / "reports" / "monitoring" / "drift_report.json"
