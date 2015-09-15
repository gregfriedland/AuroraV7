{
  'includes': [ 'common.gypi' ],
  'targets': [
    {
      'target_name': 'aurora',
      'type': 'executable',
      'sources': [
        'src/WebServer.cpp', 'src/Controller.cpp', 'src/Aurora.cpp', 
        './deps/lodepng/lodepng.cpp'
      ],
      'dependencies': [
        './deps/libuv/uv.gyp:libuv',
        './deps/http-parser/http_parser.gyp:http_parser'
      ],
      'include_dirs': [ './deps/lodepng' ],

    },
  ],
}