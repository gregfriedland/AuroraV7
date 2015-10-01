{
  'includes': [ 'common.gypi' ],
  'targets': [
    {
      'target_name': 'aurora',
      'type': 'executable',
      'sources': [ '<!@(ls -1 src/*.cpp)', '<!@(ls -1 src/*.h)', 
                   './deps/lodepng/lodepng.cpp' ],
      'dependencies': [ './deps/libuv/uv.gyp:libuv',
                        './deps/http-parser/http_parser.gyp:http_parser' ],
      'include_dirs': [ './deps/lodepng', '/usr/local/include' ],
      'conditions': [
        ['OS=="linux"', {
          'include_dirs': [ './deps/raspicam/src' ],
          'libraries': [ '../deps/raspicam/build/src/libraspicam.a',
                         '/opt/vc/lib/libmmal.so', '/opt/vc/lib/libmmal_core.so',
                         '/opt/vc/lib/libmmal_util.so',
                         '/usr/local/lib/libopencv_objdetect.so',
                         '/usr/local/lib/libopencv_core.so' ],
         }],
        ['OS=="mac"', {
          'libraries': [ '/usr/local/lib/libopencv_objdetect.dylib',
                         '/usr/local/lib/libopencv_core.dylib',
                         '/usr/local/lib/libopencv_highgui.dylib' ],
        }],
      ]
    },
  ],
}