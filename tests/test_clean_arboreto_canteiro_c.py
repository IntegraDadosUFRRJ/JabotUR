import pandas as pd
from scripts.clean.clean_arboreto_canteiro_c import transform
from scripts import config

def test_transform_regras_negocio():
    dados_falsos = {
        "Família": ["sem id", "Fabaceae"],
        "Espécie": ["NA", "Paubrasilia echinata"],
        "Origem": ["exótico", "Nativa"],
        "Domínio fitogeográfico": ["na", "Mata Atlântica"],
        "Categoria CNCFlora": ["na", "LC"],
        "Altura (m)": ["15124", "10,5"]
    }
    df_sujo = pd.DataFrame(dados_falsos)

    df_limpo = transform(df_sujo)

    linha_com_erro = df_limpo.iloc[0]
    linha_correta = df_limpo.iloc[1]

    assert linha_com_erro[config.COL_CANTEIRO_C_ORIGEM] == "Exótica", "Erro: 'exótico' não virou 'Exótica'"
    assert linha_com_erro[config.COL_CANTEIRO_C_CATEGORIA_CNCFLORA] == "NA", "Erro: CNCFlora 'na' não virou 'NA' maiúsculo"
    assert pd.isna(linha_com_erro[config.COL_CANTEIRO_C_ALTURA]), "Erro: Altura 15124 não virou nulo (NaN)"
    assert linha_com_erro["needs_review"] == True, "Erro: needs_review não marcou a Espécie 'NA'"

    assert linha_correta[config.COL_CANTEIRO_C_ALTURA] == 10.5, "Erro: Altura '10,5' não converteu para 10.5"
    
    print("Sucesso! Todas as colunas sobreviveram e as regras de negócio funcionaram.")

if __name__ == "__main__":
    test_transform_regras_negocio()