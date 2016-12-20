#ifndef PALETTE_H
#define PALETTE_H

#include <math.h>
#include <assert.h>
#include <iostream>
#include <vector>
#include "Util.h"

class Palettes {
public:
    Palettes(int palSize, const std::vector<int>& baseColors, int baseColorsPerPalette, float gamma);

    int size();

    Color24 get(int paletteIndex, int gradientIndex);
    
private:
    int m_palSize;
    const std::vector<int>& m_baseColors;
    int m_baseColorsPerPalette;
    unsigned char m_gammaTable[256];
};

#endif
