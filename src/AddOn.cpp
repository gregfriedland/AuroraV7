#include <nan.h>
#include "ControllerWrap.h"

void InitAll(v8::Local<v8::Object> exports) {
  ControllerWrap::Init(exports);
}

NODE_MODULE(aurora, InitAll)
