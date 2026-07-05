import sys
from src.scrapers.fr import discover_de, discover_mlp_families
magazines = discover_de()
for k, v in magazines.items():
    if "mickey" in str(v).lower():
        print("DE:", v)

mlp = discover_mlp_families(set(magazines.keys()), {})
for k, v in mlp.items():
    if "mickey" in str(v).lower():
        print("MLP:", v)
