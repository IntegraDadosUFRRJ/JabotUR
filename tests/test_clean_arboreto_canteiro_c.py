import unittest
import pandas as pd
from scripts.clean.clean_arboreto_canteiro_c import transform

class TestCleanArboretoCanteiroC(unittest.TestCase):
    
    def test_transform_validates_rules(self):
        data = {
            "_source_file": ["arboreto.xlsx"],
            "_source_sheet": ["Canteiro C"],
            "_source_row": [1],
            "Família": ["Myrtaceae"],
            "Espécie": ["Eucalyptus grandis"],
            "Origem": ["Exótica"],
            "Domínio fitogeográfico": ["Mata Atlântica"],
            "Categoria CNCFlora": ["LC"],
            "Altura (m)": [15124]  
        }
        df_input = pd.DataFrame(data)
        
        df_output = transform(df_input)
        
        self.assertTrue(pd.isna(df_output.loc[0, "height_m"]))
        self.assertTrue(df_output.loc[0, "needs_review"])

if __name__ == "__main__":
    unittest.main()