"""Executa o pipeline ETL completo"""

try:
    from . import clean_SPP, stage_SPP, load_SPP
except ImportError:  
    import clean_SPP
    import stage_SPP
    import load_SPP


def main() -> None:
    print("== STAGING ==")
    stage_SPP.load_staging(stage_SPP.extract_spp())

    print("\n== CLEAN ==")
    clean_SPP.load_clean(clean_SPP.transform(clean_SPP.load_staging_df()))

    print("\n== LOAD ==")
    load_SPP.populate_normalized_tables()


if __name__ == "__main__":
    main()