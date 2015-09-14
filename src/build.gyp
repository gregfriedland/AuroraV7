{
  'includes': [ 'common.gypi' ],
  'targets': [
    {
      'target_name': 'aurora',
      'type': 'executable',
      'sources': [
        'WebServer.cpp', 'Controller.cpp', 'Aurora.cpp'
      ],
      'dependencies': [
        './deps/libuv/uv.gyp:libuv',
        './deps/http-parser/http_parser.gyp:http_parser'
      ],
      'conditions': [
         [ 'OS=="mac"', {
           'xcode_settings': {
#              'MACOSX_DEPLOYMENT_TARGET' : '10.7',
              'OTHER_CPLUSPLUSFLAGS' : ['-DMACOSX', '-std=c++11'],
#, '-Wno-c++11-extensions', '-stdlib=libc++', '-std=c++11'],
#              'OTHER_LDFLAGS': ['-std=c++11', '-stdlib=libc++'],
            },

        }],
        ],      
    },
  ],
}