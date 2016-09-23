import cvpLib
from subprocess import PIPE, Popen
import time

def log( content ):
   #print 'Replacement Procedure: %s' % content
   logfile = cvpLib.INSTALL_LOG_FILE
   ts = time.strftime( "[%a %b %d %X %Z %Y] " )
   with open( logfile, 'a+' ) as logHandle:
      logHandle.write( ts + content + "\n" )

def configureReplacement( nodeId, ips ):
   '''
   Runs sequences of required scripts to configure multinode from
   configuration file. This step is required before starting cvp.
   '''
   p = Popen( [ 'su cvp' ], stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True )
   cmds = [ 'source /bin/cvpLib.sh',
            'source /etc/cvp.conf ',
            'setupReplacement %s' % nodeId ]

   # Import namenode and journal data
   if nodeId in [ 1, 2 ]:
      sourceIp = ips[ 'secondary' ] if nodeId is 1 else ips[ 'primary' ]
      cmds.append( 'importNameNodeData %s' % sourceIp )
   else:
      sourceIp = ips[ 'primary' ]
   cmds.append( 'importJournalData %s' % sourceIp )
   cmds.append( 'sudo chkconfig cvp on' )

   out, err = p.communicate( '\n'.join( cmds ) )
   log( 'Output: %s Error: %s' % ( out, err ) )
   if p.returncode != 0:
      raise RuntimeError( 'Error:' + err )

def joinCvpCluster( nodeId, ips ):
   '''
   Allow the Cvp Node to join existing cluster using the applied configuration
   '''
   open( cvpLib.CVP_INSTALL_STARTED, 'a+' ).close()
   configureReplacement( nodeId, ips )
   open( cvpLib.CVP_INSTALL_SENTINEL, 'a+' ).close()

