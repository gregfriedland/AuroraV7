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

    inline Color24 get(int paletteIndex, int gradientIndex) {
      assert(paletteIndex < size());
      
      gradientIndex = gradientIndex % m_palSize;
      int subGradientSize = ceil(m_palSize / (float)m_baseColorsPerPalette);
      
      int baseColIndex1 = floor(gradientIndex / subGradientSize);
      int baseColIndex2 = (baseColIndex1 + 1) % m_baseColorsPerPalette;
      //cout << "gradInd=" << gradientIndex << " subGradSize=" << subGradientSize << " baseColIndex1=" << baseColIndex1 << " baseColIndex2=" << baseColIndex2 << endl;
      
      Color24 col1(m_baseColors[baseColIndex1 + paletteIndex * m_baseColorsPerPalette]);
      Color24 col2(m_baseColors[baseColIndex2 + paletteIndex * m_baseColorsPerPalette]);
      
      gradientIndex = gradientIndex % subGradientSize;
      
      unsigned char r, g, b;
      r = floor(col1.r + gradientIndex * (col2.r - col1.r) / subGradientSize);
      g = floor(col1.g + gradientIndex * (col2.g - col1.g) / subGradientSize);
      b = floor(col1.b + gradientIndex * (col2.b - col1.b) / subGradientSize);
      
      return Color24(m_gammaTable[r], m_gammaTable[g], m_gammaTable[b]); 
    }
    
private:
    int m_palSize;
    const std::vector<int>& m_baseColors;
    int m_baseColorsPerPalette;
    unsigned char m_gammaTable[256];
};

#endif
