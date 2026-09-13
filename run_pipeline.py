

from src.analysis import clean, eda, model, validate
from src import db


def main() -> None:
    print("=" * 60)
    print("STEP 1/5 -- Clean & merge source data")
    print("=" * 60)
    clean.run()

    print("\n" + "=" * 60)
    print("STEP 2/5 -- Exploratory data analysis")
    print("=" * 60)
    eda.run()

    print("\n" + "=" * 60)
    print("STEP 3/5 -- Model training & evaluation")
    print("=" * 60)
    model.run()

    print("\n" + "=" * 60)
    print("STEP 4/5 -- Data quality validation")
    print("=" * 60)
    validate.run()

    print("\n" + "=" * 60)
    print("STEP 5/5 -- Load analysis-ready tables into the DBMS")
    print("=" * 60)
    db.run()

    print("\nDone. See data/processed/, reports/figures/, "
          "reports/model_results/, reports/validation/, and the "
          "database at DATABASE_URL (see .env).")


if __name__ == "__main__":
    main()
