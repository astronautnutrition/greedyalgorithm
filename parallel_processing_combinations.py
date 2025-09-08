import itertools
import multiprocessing
from collections import Counter
import pandas as pd
from tqdm import tqdm
from operator import attrgetter
import numpy as np
import os
from math import ceil

class Crop:
    def __init__(self, nutrients, indicator, max_val):
        """
        nutrients: [carbs, protein, fat, fiber, energy] per 100g
        indicator: short label (e.g. 'M', 'R', 'D')
        max_val: maximum usage for this crop
        """
        self._nutrients = nutrients
        self._contributions = []
        self._indicator = indicator
        self._max = max_val
        self._used = 0
        self.score = 0

    def getIndicator(self):
        return self._indicator

    def getNutrients(self):
        return self._nutrients

    def getMax(self):
        return self._max

    def getUsed(self):
        return self._used

    def getVariance(self):
        return np.std(self._nutrients)
    
    def isUsedAboveMax(self):
        return (self._used > self._max)
    
    def PopAsRecord(self):
        """
        Each pop increments usage by 1 g (0.01 of 100g).
        If self._nutrients[i] is X per 100 g, 1 g usage => X * 0.01.
        """
        self._used += 0.01
        return [self._indicator, [n * 0.01 for n in self._nutrients]]
    
    def setUsed(self, increment):
        self._used += increment

    def setContributions(self, maxContributions):
        """
        For each dimension, ratio = (this crop's value / max in that dimension).
        Avoid /0.
        """
        self._contributions = [
            (self._nutrients[i] / maxContributions[i]) if maxContributions[i] != 0 else 0.0
            for i in range(len(maxContributions))
        ]
        self.score = np.sum(self._contributions)

# --------------------------------------------------------------------------
class Bucket:
    def __init__(self, maxSkew, maxLevels, percentageMaxTolerance, percentageMinTolerance):
        """
        5 dimensions: [carbs, protein, fat, fiber, kcal]
        """
        self._maxSkew = maxSkew
        self._currSkew = 0
        self._maxLevels = maxLevels  
        self._currLevels = [0]*len(self._maxLevels)

        self._maxTolerance = [
            self._maxLevels[i] + self._maxLevels[i]*percentageMaxTolerance[i]
            for i in range(len(percentageMaxTolerance))
        ]
        self._minTolerance = [
            self._maxLevels[i] - self._maxLevels[i]*percentageMinTolerance[i]
            for i in range(len(percentageMinTolerance))
        ]

        self._maxContributions = [0]*len(self._maxLevels)
        self._records = []
        self._crops = []
        self._cropsExhausted = []

    def addCrop(self, crop):
        self._crops.append(crop)

        # Recompute max in each dimension
        for i in range(len(self._maxContributions)):
            self._maxContributions[i] = max(
                self._crops, key=lambda x: x.getNutrients()[i]
            ).getNutrients()[i]
        
        # Update each crop's ratio-based score
        for c in self._crops:
            c.setContributions(self._maxContributions)

        # Sort descending by that ratio sum
        self._crops.sort(key=lambda x: x.score, reverse=True)
    
    def removeCrop(self, crop):
        self._crops.remove(crop)
        self._crops.sort(key=lambda x: x.score, reverse=True)

    def getCrops(self):
        return self._crops
    
    def getCropsByIndicator(self, indicator):
        for c in self._crops:
            if c.getIndicator() == indicator:
                return c

    def flagCropAsExhausted(self, cropIndicator):
        self._cropsExhausted.append(cropIndicator)

    def addToRecords(self, record):
        """
        record: [crop_indicator, [carbs, protein, fat, fiber, energy]_portion]
        """
        self._records.append(record)
        for i in range(len(self._currLevels)):
            self._currLevels[i] += record[1][i]

        fills = [self._currLevels[i]/self._maxLevels[i] for i in range(len(self._maxLevels))]
        self._currSkew = np.std(fills)
    
    def isCurrSkewUnderMax(self):
        return (self._currSkew < self._maxSkew)
    
    def isAnyLevelCrossedMax(self):
        for i in range(len(self._maxLevels)):
            if self._currLevels[i] > self._maxTolerance[i]:
                return True
        return False

    def isAllLevelsReachedMin(self):
        for i in range(len(self._maxLevels)):
            if self._currLevels[i] < self._minTolerance[i]:
                return False
        return True

    def getRecords(self):
        return self._records
    
    def getCurrLevels(self):
        return self._currLevels
    
    def getCurrSkew(self):
        return self._currSkew

    def getBestCropByScore(self):
        if not self._crops:
            return None
        return max(self._crops, key=attrgetter('score'))
    
    def getBestCropByStd(self, curr_crop):
        if not self._crops:
            return None
            
        if curr_crop.getIndicator() not in self._cropsExhausted:
            nextBestCrop = curr_crop
        else:
            nextBestCrop = self._crops[0]

        bestDev = self._currSkew

        for c in self._crops:
            if c.getIndicator() not in self._cropsExhausted:
                # Each increment is 1 g => multiply by 0.01
                newLevels = [
                    self._currLevels[i] + 0.01 * c.getNutrients()[i]
                    for i in range(len(self._currLevels))
                ]
                newFills = [newLevels[i]/self._maxLevels[i] for i in range(len(self._maxLevels))]
                newDev = np.std(newFills)
                if newDev < bestDev:
                    nextBestCrop = c
                    bestDev = newDev
                    break
        return nextBestCrop

# --------------------------------------------------------------------------
# Updated crops: 5th element = Energy (kcal / 100g)
all_crops = [
    ('Mushroom',     Crop([6.94, 2.9, 0.19,	2.8, 41 ], 'M',  999)),
    ('Peanut',       Crop([26.5, 23.2, 43.3, 8.0,  588], 'P', 999)),
    ('Rice',         Crop([80.3, 7.04, 1.03, 0.1,  359], 'R', 999)),
    ('DryBean',      Crop([39.7, 21.3, 1.16, 4.0,  52.2], 'D', 999)),
    ('Soybean',      Crop([11.0, 13.0, 6.8,  4.2,  147],  'S', 999)),
    ('Wheat',        Crop([42.5, 7.49, 1.27, 1.1,  198],  'W', 999)),
    ('Pea',          Crop([14.4, 5.42, 0.4,  5.7,  339],  'Pe',999)),
    ('SweetPotato',  Crop([17.3, 1.58, 0.38, 4.44, 79 ], 'Sw', 999)),
    ('Strawberry',   Crop([7.96, 0.64, 0.22, 0.0,  36 ],  'St',999)),
    ('SnapBean',     Crop([7.41,1.97, 0.28, 3.0,   40],   'Sn',999)),
    ('RedBeet',      Crop([9.56,1.61, 0.17, 2.8,   43],   'Re',999)),
    ('WhitePotato',  Crop([15.7,1.68, 0.1,  2.4,   69],   'Wh',999)),
    ('Pepper',       Crop([6.65,0.9,  0.13, 1.2,   31],   'Pp',999)),
    ('Carrot',       Crop([10.3,0.94,0.35, 3.1,   48],    'C', 999)),
    ('Tomato',       Crop([3.84,0.7,  0.42, 1.0,   22],   'T', 999)),
    ('Radish',       Crop([3.4, 0.68, 0.1,  1.6,   16],   'Ra',999)),
    ('Chard',        Crop([3.74,1.8,  0.2,  1.6,   19],   'Ch',999)),
    ('Onion',        Crop([9.34,1.1,  0.1,  1.7,   40],   'O', 999)),
    ('GreenOnion',   Crop([5.74,0.97,1.8,  1.8,   27],    'G', 999)),
    ('Celery',       Crop([2.97,0.69,0.17,1.6,   14],     'Ce',999)),
    ('Spinach',      Crop([3.63,2.86,0.39,2.2,   23],     'Sp',999)),
    ('Cabbage',      Crop([5.8, 1.28,0.1,  2.5,   25],     'Ca',999)),
    ('Lettuce',      Crop([4.06,0.98,0.07,0.0,   21],     'L', 999))
]

def run_algorithm(crops):
  
    bucket = Bucket(
        maxSkew=0.001,
        maxLevels=[300, 50, 65, 25, 2000],
        percentageMaxTolerance=[0.99, 0.99, 0.99, 0.99, 0.99],
        percentageMinTolerance=[0.01, 0.01, 0.01, 0.01, 0.01]
    )
    
    for c in crops:
        bucket.addCrop(c[1])
    
    selected_crop = bucket.getBestCropByScore()
    while (
        selected_crop is not None
        and not bucket.isAnyLevelCrossedMax()
        and not bucket.isAllLevelsReachedMin()
    ):
        cropRecord = selected_crop.PopAsRecord()
        bucket.addToRecords(cropRecord)
        
        if selected_crop.isUsedAboveMax():
            bucket.flagCropAsExhausted(selected_crop.getIndicator())
            bucket.removeCrop(selected_crop)
        
        if bucket.isCurrSkewUnderMax():
            selected_crop = bucket.getBestCropByScore()
        else:
            selected_crop = bucket.getBestCropByStd(selected_crop)
    
    used_crops = [r[0] for r in bucket.getRecords()]
    usage_count = Counter(used_crops)
    levels = bucket.getCurrLevels()
    
    return {
        'crop_combination': ", ".join([c[0] for c in crops]),
        'crop_counter': str(usage_count),
        'levels': str(levels)
    }

def process_combo(combo):
    return run_algorithm(combo)

if __name__ == "__main__":
    #Filepath for saving outputs
    temp_files_dir = "/Users/jithranekanayake/Documents/Anaerobic_Digestion/AD Paper 1/02. Code/01. Menus/all_menus/permutations/Temp_Files/Seven Crop Free"
    os.makedirs(temp_files_dir, exist_ok=True)

    #Generate all 245,157 crop combinations
    all_combos = list(itertools.combinations(all_crops, 7))
    n_combos = len(all_combos)  
    print(f"Total 7-crop combinations: {n_combos}")

    #Multiprocessing
    chunk_size = 2000
    n_cores = multiprocessing.cpu_count()
    print(f"Detected {n_cores} cores. Using 8 processes.")
    pool = multiprocessing.Pool(processes=8)

    #Run in chunks of 2000 (can be varies)
    n_chunks = ceil(n_combos / chunk_size)

    for chunk_index in tqdm(range(n_chunks), desc="Chunks processed"):
        chunk_start = chunk_index * chunk_size
        chunk_end = min(chunk_start + chunk_size, n_combos)
        combo_chunk = all_combos[chunk_start:chunk_end]

        out_file = os.path.join(
            temp_files_dir,
            f"crop_combination_results_part_{chunk_index:03d}.parquet"
        )

        if os.path.exists(out_file):
            print(f"Skipping chunk {chunk_index}, already exists: {out_file}")
            continue

        chunk_results = pool.map(process_combo, combo_chunk)
        df = pd.DataFrame(chunk_results)
        df.to_parquet(out_file)

        del chunk_results, df

    pool.close()
    pool.join()

    print("All chunks processed. Parquet files saved in:\n", temp_files_dir)
