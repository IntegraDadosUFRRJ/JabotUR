"""Executa o pipeline ETL completo"""

from scripts.clean import clean_SPP, clean_arboreto_citations, clean_arboreto_specimens
from scripts.staging import stage_SPP, stage_arboreto_citations, stage_arboreto_specimens
from scripts.load import load_SPP, load_arboreto_citations, load_arboreto_specimens


def main() -> None:
    print("== STAGING (SPP) ==")
    stage_SPP.load_staging(stage_SPP.extract_spp())

    print("\n== CLEAN (SPP) ==")
    clean_SPP.load_clean(
        clean_SPP.transform(clean_SPP.load_staging_df())
    )

    print("\n== LOAD (SPP) ==")
    load_SPP.populate_normalized_tables()

    print("\n== STAGING (arboreto - citações) ==")
    stage_arboreto_citations.load_staging(
        stage_arboreto_citations.extract_citations()
    )

    print("\n== CLEAN (arboreto - citações) ==")
    clean_arboreto_citations.load_clean(
        clean_arboreto_citations.transform(
            clean_arboreto_citations.load_staging_df()
        )
    )

    print("\n== LOAD (arboreto - citações) ==")
    load_arboreto_citations.populate_normalized_tables()

    print("\n== STAGING (arboreto - espécimes) ==")
    stage_arboreto_specimens.load_staging(stage_arboreto_specimens.extract_specimens())

    print("\n== CLEAN (arboreto - espécimes) ==")
    clean_arboreto_specimens.load_clean(
        clean_arboreto_specimens.transform(clean_arboreto_specimens.load_staging_df())
    )

    print("\n== LOAD (arboreto - espécimes) ==")
    load_arboreto_specimens.populate_normalized_tables()

if __name__ == "__main__":
    main()