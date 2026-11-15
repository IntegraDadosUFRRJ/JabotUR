"""Executa o pipeline ETL completo"""

from scripts.clean import clean_spp_bryophytes, clean_arboretum_citations, clean_arboretum_specimens
from scripts.staging import stage_spp_bryophytes, stage_arboretum_citations, stage_arboretum_specimens
from scripts.load import load_spp_bryophytes, load_arboretum_citations, load_arboretum_specimens
from scripts.db import db_utils
from scripts.db.init_postgres import init_postgres


def main() -> None:
    try:
        print("== INIT (banco + esquema) ==")
        init_postgres()

        print("\n== STAGING (SPP) ==")
        stage_spp_bryophytes.stage_spp()

        print("\n== CLEAN (SPP) ==")
        clean_spp_bryophytes.clean_spp()

        print("\n== LOAD (SPP) ==")
        load_spp_bryophytes.populate_normalized_tables()

        print("\n== STAGING (arboreto - citações) ==")
        stage_arboretum_citations.stage_citations()

        print("\n== CLEAN (arboreto - citações) ==")
        clean_arboretum_citations.clean_citations()

        print("\n== LOAD (arboreto - citações) ==")
        load_arboretum_citations.populate_normalized_tables()

        print("\n== STAGING (arboreto - espécimes) ==")
        stage_arboretum_specimens.stage_specimens()

        print("\n== CLEAN (arboreto - espécimes) ==")
        clean_arboretum_specimens.clean_specimens()

        print("\n== LOAD (arboreto - espécimes) ==")
        load_arboretum_specimens.populate_normalized_tables()
    finally:
        # Os engines ficam em cache em db_utils; o pipeline fecha as conexões ao terminar
        db_utils.dispose_connections()

if __name__ == "__main__":
    main()
