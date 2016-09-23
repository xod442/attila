#!/usr/bin/env python

import os

licenses = {}

def _walk( arg, dirname, fnames ):
   for fn in fnames:
      if fn.startswith( "COPY" ) or fn.startswith( "LICEN" ) or \
         fn.startswith( "NOTICE" ):
         fp = dirname + "/" + fn
         if os.path.isfile( fp ):
            with file( fp ) as f:
               try:
                  licenses[ fp ] = f.read()
               except IOError:
                  print "Failed to display file %s" % fp

def main( ):
   topdirs = ( '/usr/share/licenses', '/usr/share/doc', '/cvp' )
   for topdir in topdirs:
      os.path.walk( topdir, _walk, None )

   for fn, text in licenses.iteritems():
      print "++++++++"
      print fn
      print "++++++++"
      print ""
      print text
      print ""

if __name__ == '__main__':
   main()
