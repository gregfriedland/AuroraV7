#include "Palette.h"


Palettes::Palettes(int palSize, const std::vector<int>& baseColors, int baseColorsPerPalette, float gamma)
: m_palSize(palSize), m_baseColors(baseColors),
  m_baseColorsPerPalette(baseColorsPerPalette) {
    for (int i = 0; i < 256; ++i) {
        m_gammaTable[i] = (unsigned char)(pow((float)i / (float)255, gamma) * 255 + 0.5);
    }
}

int Palettes::size() {
    return m_baseColors.size() / m_baseColorsPerPalette;
}

Color24 Palettes::get(int paletteIndex, int gradientIndex) {
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
