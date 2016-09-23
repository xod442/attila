# Copyright (c) 2005-2011 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

"""A parser for a very simple configuration file format.  Each line of the file must
either be empty (except for whitespace) or else contain a binding of the form:

   NAME=VALUE

NAME must contain only letters, numbers and underscores.  VALUE may contain any
characters.  Leading whitespace is ignored, but there must be no space before the
equals sign."""

import UserDict, re, os

class ParseError( Exception ):
   pass

class SimpleConfigFileDict( object, UserDict.DictMixin ):
   def __init__( self, filename, createIfMissing=False, autoSync=False ):
      self.filename_ = filename
      self.autoSync_ = autoSync
      if createIfMissing:
         file( self.filename_, 'a' )

   def __getitem__( self, key ):
      config = self._readConfig()
      return config[ key ]
   def __setitem__( self, key, value ):
      config = self._readConfig()
      config[ key ] = value
      self._writeConfig( config )
   def __delitem__( self, key ):
      config = self._readConfig()
      del config[ key ]
      self._writeConfig( config )
   def keys( self ):
      config = self._readConfig()
      return config.keys()
   def items( self ):
      config = self._readConfig()
      return config.items()

   def _readConfig( self ):
      d = {}
      n = 0
      for line in file( self.filename_ ):
         n += 1
         line = line.lstrip()
         if not line or line.startswith( "#" ):
            continue
         m = re.match( "([A-Za-z0-9_]+)=([^\n\r]*)", line )
         if not m:
            raise ParseError( "Syntax error in %s, line %s" % ( self.filename_, n ) )
         ( var, value ) = m.groups()
         d[ var ] = value
      return d

   def _writeConfig( self, d ):
      with file( self.filename_, 'w' ) as f:
         for var in sorted( d.keys() ):
            value = d[ var ]
            f.write( "%s=%s\n" % ( var, value ) )
         if self.autoSync_:
            f.flush()
            os.fsync( f.fileno() )
