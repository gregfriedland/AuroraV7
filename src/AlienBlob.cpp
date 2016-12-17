#include <map>
#include <vector>

#include "AlienBlob.h"
#include "Drawer.h"
#include "Util.h"


#define DECAY 0.5f
#define ALIENBLOB_SPEED_MULTIPLIER 0.07f


static void init_noise(void);
static float noise(float x, float y, float z, int octaves, float decay);

static void alienblob(int width, int height, int numColors, float zoff, int perlinOctaves,
                      float perlinDecay, float zoom, int* indices, float* sineTable);



AlienBlobDrawer::AlienBlobDrawer(int width, int height, int palSize, Camera* camera)
: Drawer("AlienBlob", width, height, palSize), m_colorIndex(0), m_camera(camera) {
    m_settings.insert(std::make_pair("speed",3));
    m_settings.insert(std::make_pair("colorSpeed",0));
    m_settings.insert(std::make_pair("detail",3));
    m_settings.insert(std::make_pair("zoom",70));
    m_settingsRanges.insert(std::make_pair("speed", std::make_pair(0,100)));
    m_settingsRanges.insert(std::make_pair("colorSpeed", std::make_pair(0,50)));
    m_settingsRanges.insert(std::make_pair("detail", std::make_pair(1,4)));
    m_settingsRanges.insert(std::make_pair("zoom", std::make_pair(0,100)));

    init_noise();
    for (int i = 0; i < 360; i ++) 
        m_sineTable[i] = sin(i * M_PI / 180);

    reset();
}

void AlienBlobDrawer::reset() {
    m_pos = random2() % 1000;
}

void AlienBlobDrawer::draw(int* colIndices)
{
    alienblob(m_width, m_height, m_palSize, m_pos, m_settings["detail"], DECAY,
        m_settings["zoom"]/100.0, colIndices, m_sineTable);

    for (int x = 0; x < m_width; x++)
        for (int y = 0; y < m_height; y++)
            colIndices[x + y * m_width] += m_colorIndex;

    m_pos += ALIENBLOB_SPEED_MULTIPLIER * m_settings["speed"] / 100.0;
    m_colorIndex += m_settings["colorSpeed"];
}

AlienBlobDrawer::~AlienBlobDrawer() {}


static void alienblob(int width, int height, int numColors, float zoff, int perlinOctaves,
                      float perlinDecay, float zoom, int* indices, float* sineTable) {
    float incr = 0.3125;
    float noiseMult = 7;
    float multiplier = (1-zoom) + 0.02;

    int y, x;
    float yy = 0;
    for (y = 0; y < height; y++) {
        float xx = 0;
        for (x = 0; x < width; x++) {
            //float n = pnoise_harmonics(xx*multiplier, yy*multiplier, zoff,
            //                           perlinOctaves, perlinDecay);
            float n = noise(xx*multiplier, yy*multiplier, zoff, perlinOctaves, perlinDecay);
            // use pre-calculated sine results
            int deg = (int) ((n * noiseMult + 4 * M_PI) * 180 / M_PI);
            float h = (sineTable[deg % 360] + 1) / 2;
            
            // determine pixel color
            indices[x + y * width] = (int) (h * numColors);
            
            xx += incr;
        }
        
        yy += incr;
    }  
}




#if 0
/*
 Ken Perlins improved noise   -  http://mrl.nyu.edu/~perlin/noise/
 C-port:  http://www.fundza.com/c4serious/noise/perlin/perlin.html
 by Malcolm Kesson;   arduino port by Peter Chiochetti, Sep 2007 :
 -  make permutation constant byte, obsoletes init(), lookup % 256
 */


static const uint8_t p[] = {   151,160,137,91,90, 15,131, 13,201,95,96,
    53,194,233, 7,225,140,36,103,30,69,142, 8,99,37,240,21,10,23,190, 6,
    148,247,120,234,75, 0,26,197,62,94,252,219,203,117, 35,11,32,57,177,
    33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,
    48,27,166, 77,146,158,231,83,111,229,122, 60,211,133,230,220,105,92,
    41,55,46,245,40,244,102,143,54,65,25,63,161, 1,216,80,73,209,76,132,
    187,208, 89, 18,169,200,196,135,130,116,188,159, 86,164,100,109,198,
    173,186, 3,64,52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,
    212,207,206, 59,227, 47,16,58,17,182,189, 28,42,223,183,170,213,119,
    248,152,2,44,154,163,70,221,153,101,155,167,43,172, 9,129,22,39,253,
    19,98,108,110,79,113,224,232,178,185,112,104,218,246, 97,228,251,34,
    242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,
    49,192,214, 31,181,199,106,157,184, 84,204,176,115,121,50,45,127, 4,
    150,254,138,236,205, 93,222,114, 67,29,24, 72,243,141,128,195,78,66,
    215,61,156,180
};

static float fade(float t){ return t * t * t * (t * (t * 6 - 15) + 10); }
static float lerp(float t, float a, float b){ return a + t * (b - a); }
static float grad(int hash, float x, float y, float z)
{
    int     h = hash & 15;          /* CONVERT LO 4 BITS OF HASH CODE */
    float  u = h < 8 ? x : y,      /* INTO 12 GRADIENT DIRECTIONS.   */
    v = h < 4 ? y : h==12||h==14 ? x : z;
    return ((h&1) == 0 ? u : -u) + ((h&2) == 0 ? v : -v);
}

#define P(x) p[(x) & 255]

static float pnoise(float x, float y, float z)
{
    int   X = (int)floor(x) & 255,             /* FIND UNIT CUBE THAT */
    Y = (int)floor(y) & 255,             /* CONTAINS POINT.     */
    Z = (int)floor(z) & 255;
    x -= floor(x);                             /* FIND RELATIVE X,Y,Z */
    y -= floor(y);                             /* OF POINT IN CUBE.   */
    z -= floor(z);
    float  u = fade(x),                       /* COMPUTE FADE CURVES */
    v = fade(y),                       /* FOR EACH OF X,Y,Z.  */
    w = fade(z);
    
    //if (X==0 && Y==0 && x==0 && y==0) {
    //  Serial.print(X); Serial.print(" "); Serial.print(x); Serial.print(" "); Serial.print(Y); Serial.print(" ");
    //  Serial.print(y); Serial.print(" "); Serial.print(Z); Serial.print(" "); Serial.print(z); Serial.print(": "); Serial.println(w);
    //}
    
    int  A = P(X)+Y,
    AA = P(A)+Z,
    AB = P(A+1)+Z,                        /* HASH COORDINATES OF */
    B = P(X+1)+Y,
    BA = P(B)+Z,
    BB = P(B+1)+Z;                        /* THE 8 CUBE CORNERS, */
    
    return lerp(w,lerp(v,lerp(u, grad(P(AA  ), x, y, z),   /* AND ADD */
                                                        grad(P(BA  ), x-1, y, z)),   /* BLENDED */
                                         lerp(u, grad(P(AB  ), x, y-1, z),        /* RESULTS */
                                                    grad(P(BB  ), x-1, y-1, z))),       /* FROM  8 */
                            lerp(v, lerp(u, grad(P(AA+1), x, y, z-1),  /* CORNERS */
                                                     grad(P(BA+1), x-1, y, z-1)),          /* OF CUBE */
                                     lerp(u, grad(P(AB+1), x, y-1, z-1),
                                                grad(P(BB+1), x-1, y-1, z-1))));
}

// x, y, z, num harmonics, unused, harmonic falloff
static float pnoise_harmonics(float x, float y, float z, int octaves, float decay) {
    float scale = 0;
    float result = 0;
    float decay2 = 1;
    int i;
    for (i=0; i<octaves; i++ ) {
        scale += decay2;
        result += pnoise(x, y, z) * decay2;
        decay2 *= decay;
        //    x *= freq;
        //    y *= freq;
    }
    
    return result / scale;
}
#endif





/* -*- mode: java; c-basic-offset: 2; indent-tabs-mode: nil -*- */

/*
 Part of the Processing project - http://processing.org
 
 Copyright (c) 2012-13 The Processing Foundation
 Copyright (c) 2004-12 Ben Fry and Casey Reas
 Copyright (c) 2001-04 Massachusetts Institute of Technology
 
 This library is free software; you can redistribute it and/or
 modify it under the terms of the GNU Lesser General Public
 License as published by the Free Software Foundation, version 2.1.
 
 This library is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 Lesser General Public License for more details.
 
 You should have received a copy of the GNU Lesser General
 Public License along with this library; if not, write to the
 Free Software Foundation, Inc., 59 Temple Place, Suite 330,
 Boston, MA  02111-1307  USA
 */

static float noise_fsc(float i);

#define RANDOM() (random() / (float)RAND_MAX)

#define SINCOS_PRECISION 0.5f
#define SINCOS_LENGTH (360*2)
#define DEG_TO_RAD (3.14159 / 180)

#define PERLIN_YWRAPB 4
#define PERLIN_YWRAP (1<<PERLIN_YWRAPB)
#define PERLIN_ZWRAPB 8
#define PERLIN_ZWRAP (1<<PERLIN_ZWRAPB)
#define PERLIN_SIZE 4095

static float sinLUT[SINCOS_LENGTH];
static float cosLUT[SINCOS_LENGTH];
static int perlin_TWOPI, perlin_PI;
static float *perlin_cosTable;
static float perlin[PERLIN_SIZE+1];


static void init_noise(void) {
    srandom(clock());
    
    perlin_TWOPI = perlin_PI = SINCOS_LENGTH;
    perlin_PI >>= 1;
    
    int i;
    for (i = 0; i < SINCOS_LENGTH; i++) {
        sinLUT[i] = (float) sin(i * DEG_TO_RAD * SINCOS_PRECISION);
        cosLUT[i] = (float) cos(i * DEG_TO_RAD * SINCOS_PRECISION);
    }
    perlin_cosTable = cosLUT;
    
    for (i = 0; i < PERLIN_SIZE + 1; i++) {
        perlin[i] = RANDOM(); //perlinRandom.nextFloat(); //(float)Math.random();
    }
}

inline float noise_fsc(float i) {
    // using bagel's cosine table instead
    return 0.5f*(1.0f-perlin_cosTable[(int)(i*perlin_PI)%perlin_TWOPI]);
}

static float noise(float x, float y, float z, int perlin_octaves, float perlin_amp_falloff) {
    if (x<0) x=-x;
    if (y<0) y=-y;
    if (z<0) z=-z;
    
    int xi=(int)x, yi=(int)y, zi=(int)z;
    float xf = x - xi;
    float yf = y - yi;
    float zf = z - zi;
    float rxf, ryf;
    
    float r=0;
    float ampl=0.5f;
    
    float n1,n2,n3;
    
    int i;
    for (i=0; i<perlin_octaves; i++) {
        int of=xi+(yi<<PERLIN_YWRAPB)+(zi<<PERLIN_ZWRAPB);
        
        rxf=noise_fsc(xf);
        ryf=noise_fsc(yf);
        
        n1  = perlin[of&PERLIN_SIZE];
        n1 += rxf*(perlin[(of+1)&PERLIN_SIZE]-n1);
        n2  = perlin[(of+PERLIN_YWRAP)&PERLIN_SIZE];
        n2 += rxf*(perlin[(of+PERLIN_YWRAP+1)&PERLIN_SIZE]-n2);
        n1 += ryf*(n2-n1);

        of += PERLIN_ZWRAP;
        n2  = perlin[of&PERLIN_SIZE];
        n2 += rxf*(perlin[(of+1)&PERLIN_SIZE]-n2);
        n3  = perlin[(of+PERLIN_YWRAP)&PERLIN_SIZE];
        n3 += rxf*(perlin[(of+PERLIN_YWRAP+1)&PERLIN_SIZE]-n3);
        n2 += ryf*(n3-n2);
        
        n1 += noise_fsc(zf)*(n2-n1);
        
        r += n1*ampl;
        ampl *= perlin_amp_falloff;
        xi<<=1; xf*=2;
        yi<<=1; yf*=2;
        zi<<=1; zf*=2;
        
        if (xf>=1.0f) { xi++; xf--; }
        if (yf>=1.0f) { yi++; yf--; }
        if (zf>=1.0f) { zi++; zf--; }
    }
    return r;
}
