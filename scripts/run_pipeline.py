"""Executa o pipeline ETL completo"""

from .clean import clean_SPP, clean_arboreto_citations
from .staging import stage_SPP, stage_arboreto_citations

try:
    from .load import load_SPP, load_arboreto_citations
except ImportError:
    import scripts.clean.clean_SPP as clean_SPP
    import scripts.clean.clean_arboreto_citations as clean_arboreto_citations
    import scripts.staging.stage_SPP as stage_SPP
    import scripts.staging.stage_arboreto_citations as stage_arboreto_citations
    import scripts.load.load_SPP as load_SPP
    import scripts.load.load_arboreto_citations as load_arboreto_citations


def main() -> None:
    print("== STAGING (SPP) ==")
    stage_SPP.load_staging(stage_SPP.extract_spp())

    print("\n== CLEAN (SPP) ==")
    clean_SPP.load_clean(clean_SPP.transform(clean_SPP.load_staging_df()))

    print("\n== LOAD (SPP) ==")
    load_SPP.populate_normalized_tables()

    print("\n== STAGING (arboreto - citações) ==")
    stage_arboreto_citations.load_staging(stage_arboreto_citations.extract_citations())

    print("\n== CLEAN (arboreto - citações) ==")
    clean_arboreto_citations.load_clean(
        clean_arboreto_citations.transform(clean_arboreto_citations.load_staging_df())
    )

    print("\n== LOAD (arboreto - citações) ==")
    load_arboreto_citations.populate_normalized_tables()


if __name__ == "__main__":
    main()