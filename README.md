**Scripts**

We used `Greedy_Algorithm.ipynb` to generate our fully bioregenerative astronaut menus. No AI assistance was used to develop this method. 
We used `parallel_processing_combinations.py` to parallelize runs of our greedy algorithm over every 7-crop combination of all BVAD crops, using Python’s multiprocessing module (8 worker processes on an Apple M2 Pro with a 12-core CPU). This yielded 245,157 menus, of which 45,116 achieved a mean percentage difference between 1-25% across all five target NASA DRIs. The parallel processing component of this script was developed with assistance from o1-pro.

**Data Tables**

`Table_S3_New_Menus_Crops_Nutrients.xlsx` contains the crop composition and nutrient content of each of our 45,116 new fully bioregenerative astronaut menus.
`Table_S7_New_Menus_ESM_Loop_Closure.xlsx` contains the predicted methane yield, PHB yield, ESM, loop closure, and ESM per loop closure values for each of our 45,116 new fully bioregenerative astronaut menus, including breakdowns by waste stream.
`Table_S8_NASA_Menus_ESM_Loop_Closure.xlsx` contains the predicted methane yield, PHB yield, ESM, loop closure, and ESM per loop closure values, for three existing NASA astronaut menus.
