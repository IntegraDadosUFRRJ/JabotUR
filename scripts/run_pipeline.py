"""Executa o pipeline ETL completo"""

from .clean import clean_SPP
from .staging import stage_SPP

try:
    from .load import load_SPP
except ImportError:  
    import scripts.clean.clean_SPP as clean_SPP
    import scripts.staging.stage_SPP as stage_SPP
    import scripts.load.load_SPP as load_SPP


def main() -> None:
    print("== STAGING ==")
    stage_SPP.load_staging(stage_SPP.extract_spp())

    print("\n== CLEAN ==")
    clean_SPP.load_clean(clean_SPP.transform(clean_SPP.load_staging_df()))

    print("\n== LOAD ==")
    load_SPP.run()


if __name__ == "__main__":
    main()