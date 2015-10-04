#ifndef WS2801_H
#define WS2801_H

#include <Arduino.h>

#define NOP asm("nop\n")
#define NOP10 { NOP; NOP; NOP; NOP; NOP; NOP; NOP; NOP; NOP; NOP; }
#define NOP48 { NOP10; NOP10; NOP10; NOP10; NOP; NOP; NOP; NOP; NOP; NOP; NOP; NOP; }
#define NOP96 { NOP48; NOP48; }

volatile uint8_t *dataport, *clockport;
uint32_t datapin, clockpin;

// Initialize the matrix
void WS2801Init(int dataPin, int clockPin) {
  dataport  = portOutputRegister(digitalPinToPort(dataPin));
  clockport = portOutputRegister(digitalPinToPort(clockPin));
  datapin   = digitalPinToBitMask(dataPin);
  clockpin  = digitalPinToBitMask(clockPin);
  
  pinMode(dataPin, OUTPUT);
  pinMode(clockPin, OUTPUT);
}

// Send a single RGB 24-bit triplet.
void sendRGB(uint32_t *data, int offset, uint32_t tick, uint32_t tock) {
  uint32_t color = data[offset];
  // Iterate through color bits (red MSB)
  for(int b=23; b>=0; b--) {
    *clockport = tick;
    //NOP42; // not needed
    if (color & (1<<b)) *dataport |= datapin;
    else *dataport &= ~datapin;
    
    // stall to give the WS2801 time to register the change.
    NOP48; // 42 cycles is ok; 21 is not ok
    
    *clockport = tock;
    NOP48; // 21 cycles is ok; but slight flicker?
    
  }
}

// Call to refresh the LEDs. Sends all the data to the WS2801s.
void WS2801Update(uint32_t *data, int width, int height) {
  uint32_t tick = *clockport & ~clockpin;
  uint32_t tock = *clockport | clockpin;
  for (int y=0; y<height; y++) {
    for (int x=0; x<width; x++) {
      sendRGB(data, x+y*width, tick, tock);
    }
  }
  *clockport = tick;
  delayMicroseconds(1000);
}

#endif
