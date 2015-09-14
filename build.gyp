{
  'includes': [ 'common.gypi' ],
  'targets': [
    {
      'target_name': 'aurora',
      'type': 'executable',
      'sources': [
        'src/WebServer.cpp', 'src/Controller.cpp', 'src/Aurora.cpp'
      ],
      'dependencies': [
        './deps/libuv/uv.gyp:libuv',
        './deps/http-parser/http_parser.gyp:http_parser'
      ],
      'libraries': [ '../deps/pngwriter/src/libpngwriter.a' ],
    },
  ],
}