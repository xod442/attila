#! /usr/bin/env python

import cvpLib
import os
import re
import readline
from commands import getstatusoutput
import shutil
import stat
import sys
import time
import tempfile
import pexpect
import getpass
import yaml
import cvpReplace
import SimpleConfigFile
import subprocess
import tarfile
import glob

sys.path.append( "/cvp/tools" )
import cvpConfigParser as configParser
CVP_SHELL_LOG = '/cvp/logs/cvpShell.log'
CVP_USER = "cvp"
PRIMARY_NODE_ID = 1
SECONDARY_NODE_ID = 2
TERTIARY_NODE_ID = 3
DEFAULT_INTERFACE = 'eth0'
CVP_UPGRADE_TMP_DIR = '/tmp/upgrade'

intfs = []
verbose = False

authfile = os.path.expanduser( "~%s/.ssh/authorized_keys" % CVP_USER )

class meta( object ):
   # types
   STRING = 'STRING'
   LIST = 'LIST'
   INTF = 'INTERFACE'

   def __init__( self, section, prompt, key, ttype, validValues=None,
                 defaultValue=None ):
      self.section = section
      self.prompt = prompt
      self.key = key
      self.ttype = ttype
      self.validValues = validValues
      self.defaultValue = defaultValue

# common Meta
cMeta = [
          # cvpShell runs as cvpadmin and setting the root password
          # from another user is bad form. Hence I'm removing this
          # option from the shell
          #meta( 'common', 'root password', 'root', 'str', meta.REQUIRED ),
          meta( 'common', 'default route', 'default_route', meta.STRING ),
          meta( 'common', 'dns', 'dns', meta.LIST ),
          meta( 'common', 'ntp', 'ntp', meta.LIST ),
        ]

# node Meta
nMeta = [
    # Don't query for vmname since it's specific to our env
    # meta( 'node', 'vmname', 'vmname', str, False ),
          meta( 'node', 'hostname (fqdn)', 'hostname', meta.STRING ),
          meta( 'node', 'default route', 'default_route', meta.STRING ),
          meta( 'node', 'dns', 'dns', meta.LIST ),
          meta( 'node', 'ntp', 'ntp', meta.LIST ),
        ]

# optional params
optionalParams = {
   'multinode' : {
      'primary' : [],
      'secondary' : [],
      'tertiary' : []
   },
   'singlenode' : {
      'primary' : [ 'dns', 'ntp' ]
   }
}

def log( msg ):
   with open( CVP_SHELL_LOG, "a" ) as logHandle:
      ts = time.strftime( "[%a %b %d %X %Z %Y] " )
      logHandle.write( ts + msg + "\n" )

def runCmd( cmd, printCmd=True, ignoreErrors=False ):
   if printCmd:
      print "Running: ", cmd
   # TODO convert getstatusoutput to os.system() so that
   # the cmd executes with root previleges.
   status, output = getstatusoutput( cmd )
   if status != 0:
      if not ignoreErrors:
         print "Cmd: '%s' failed(%d)\nstdout: %s" % ( cmd, status, output )
      log( output )
   elif verbose:
      print "Output: ", output
   return ( status, output )

def discoverIntfs( defaultIntfs=None ):
   """Discover available interfaces and add input fields for them."""
   global intfs
   def _getInterfaceNameMetas( section ):
      return [
         meta( section, 'Cluster Interface name',
               'cluster_interface', meta.STRING,
               validValues=[ '' ] + intfs, defaultValue=DEFAULT_INTERFACE ),
         meta( section, 'Device Interface name',
               'device_interface', meta.STRING,
               validValues=[ '' ] + intfs, defaultValue=DEFAULT_INTERFACE ) ]

   def _getInterfaceConfigMetas():
      metas = []
      for intf in intfs:
         metas.extend( [
             meta( 'node', 'IP address of %s' % intf,
                   'interfaces/%s/ip_address' % intf, meta.INTF ),
             meta( 'node', 'Netmask of %s' % intf,
                   'interfaces/%s/netmask' % intf, meta.INTF ) ] )
      return metas

   if defaultIntfs: # i.e. ( forcibly use eth0, eth1 )
      intfs = defaultIntfs
   else:
      intfs = sorted( os.listdir( '/sys/class/net' ) )
      intfs.remove( 'lo' )
   cMeta.extend( _getInterfaceNameMetas( 'common' ) )
   nMeta.extend( _getInterfaceNameMetas( 'node' ) )
   nMeta.extend( _getInterfaceConfigMetas() )

def printConfig( config ):
   print config

def rlinput(prompt, prefill=''):
   readline.set_startup_hook(lambda: readline.insert_text(prefill))
   try:
      val = raw_input(prompt)
      return val
   finally:
      readline.set_startup_hook()

def importConfig( config ):
   '''
   replacement only: import configuration from the other node,
   unlike other <action>Config() the user cannot call this directly
   from the menu prompt, unless mode ir set to 'replace'
   '''
   # TODO convert this method to a class with methods, instead of using
   # nested scope methods

   def verifyInterface( interface ):
      if interface in [ 'eth0', 'eth1' ]:
         return True
      print 'Please enter correct interface ( eth0 or eth1 ) '
      return False

   def verifyIp( ipAddress ):
      ipBytes = ipAddress.split( '.' )
      try:
         assert len( ipBytes ) == 4
         assert all( byte.isdigit() for byte in ipBytes )
         assert all( 0 <= int( byte ) <= 255 for byte in ipBytes )
         return True
      except AssertionError:
         print 'Please enter correct IP ( a.b.c.d )'
         return False

   def setMinimumNetworkConfig( ip, netmask, interface ):
      netdevFile = '/etc/sysconfig/network-scripts/ifcfg-%s' % interface
      netdevConfig = SimpleConfigFile.SimpleConfigFileDict( netdevFile,
                        createIfMissing=True )
      netdevConfig[ 'BOOTPROTO' ] = 'static'
      netdevConfig[ 'IPADDR' ] = ip
      netdevConfig[ 'NETMASK' ] = netmask
      netdevConfig[ 'NETBOOT' ] = 'no'
      netdevConfig[ 'ONBOOT' ] = 'yes'
      netdevConfig[ 'IPV6INIT' ] = 'yes'
      netdevConfig[ 'NAME' ] = interface
      netdevConfig[ 'TYPE' ] = 'Ethernet'

   role = 'replacement'
   ipAddress = ''            # ip address
   interface = None          # ethernet interface (either eth0 or eth1)
   ips = {}                  # node mapped to string
   peerIp = None             # peer ip chosen by the user
   otherPeerIp = None        # the other peer ip not chosen by the user
   verifiedIp = False        # ip addresses entered are verified
   verifiedInterface = False # interface entered is valid

   authKeysPath = '/home/cvp/.ssh/authorized_keys'
   publicKeyPath = '/home/cvp/.ssh/id_rsa.pub'
   cvpConfigPath = '%s%s' % ( cvpLib.DEFAULT_YAML_DIR, cvpLib.DEFAULT_YAML_FILE )

   with open( publicKeyPath, 'r' ) as f:
      publicKey = f.read().strip()

   print 'Please enter minimum configuration to connect to the other peers'
   while not verifiedInterface:
      interface = raw_input( '*Ethernet interface (eth0 or eth1): ' )
      verifiedInterface = verifyInterface( interface )

   verifiedIp = False
   while not verifiedIp:
      ipAddress = raw_input( '*IP address of %s: ' % interface )
      verifiedIp = verifyIp( ipAddress )

   verifiedIp = False
   while not verifiedIp:
      netmask = raw_input( '*Netmask of %s: ' % interface )
      verifiedIp = verifyIp( netmask )

   verifiedIp = False
   while not verifiedIp:
      peerIp = raw_input( '*IP address of one of the two active cluster nodes: ' )
      verifiedIp = verifyIp( netmask )

   setMinimumNetworkConfig( ipAddress, netmask, interface )
   status = runCmd( '/bin/sudo /sbin/service network restart' )[0]
   if status != 0:
      print "Network restart failed. Please check your network configurations"
      return status

   log( "Step 1. Append this key to peer's authorized keys" )
   peerServer = cvpLib.Peer( peerIp )
   peerServer.sshAsRoot( 'echo \"%s\" >> /home/cvp/.ssh/authorized_keys' %
                         publicKey )

   log( "Step 2. Copy the SSH key from the peer" )
   peerServer.scpAsCvp( src=authKeysPath, dst=authKeysPath, upload=False )

   log( "Step 3. Import configuration file and fetch ip addresses" )
   peerServer.scpAsCvp( cvpConfigPath, cvpConfigPath, upload=False )
   config.config = yaml.safe_load( open( cvpConfigPath ) )
   role = config.fetchRole( ipAddress )
   ips = config.fetchIpAddresses()

   log( "Step 4. Replicate the auth key to the other peer" )
   for ip in ips.values():
      otherPeerIp = ip if ip not in [ ipAddress, peerIp ] else otherPeerIp
   peerServer.sshAsCvp( 'scp ~/.ssh/authorized_keys %s:~/.ssh' % otherPeerIp )

   log( "Step 5. Remove SSH known hosts on all peers" )
   otherPeerServer = cvpLib.Peer( otherPeerIp )
   otherPeerServer.sshAsCvp( 'rm /home/cvp/.ssh/known_hosts' )
   peerServer.sshAsCvp( 'rm /home/cvp/.ssh/known_hosts' )
   return role

def isRequired( key, config, mode, role ):
   if key in optionalParams[ mode ][ role ]:
      return False
   return True

def editConfig( config, role='primary', mode='singlenode' ):
   if mode != 'singlenode' and cvpInitialized() != "no":
      print "CVP service is configured and may be running,\n" \
"reconfigure is not supported in multinode setup"
      return

   config.config[ 'version' ] = configParser.YAML_VER_CURRENT

   print 'common configuration:'
   if 'common' not in config.config:
      config.config[ 'common' ] = {}

   # TODO: factor this out
   i = 0
   while i < len( cMeta ):
      m = cMeta[ i ]
      prefill = ''
      if m.key in config.config[ 'common' ].keys():
         prefill = config.config[ 'common' ][ m.key ]

      # present lists as strings
      if m.ttype == meta.LIST:
         prefill = ', '.join( prefill )

      req = '' # all fields are optional in common config
      prefill = prefill if prefill else m.defaultValue
      value = rlinput( " %s%s: " % ( req, m.prompt ), prefill )

      # strip out special chars
      for c in ( ',', ':', ';', '_' ):
         value = value.replace( c, '' )

      if m.validValues and value not in m.validValues:
         print '%s: Invalid input. Valid inputs are: %s' % ( value,
               ', '.join( m.validValues ) )
         continue

      # convert lists back to strings
      if m.ttype == meta.LIST:
         value = value.split( )
      config.config[ 'common' ][ m.key ] = value
      i += 1

   #for nn in (1, 2, 3): # only node1 for now
   for nn in ( 1, ):
      node = 'node%d' % nn
      print 'node configuration:'

      if node not in config.config.keys():
         config.config[ node ] = {}

      i = 0
      while i < len( nMeta ):
         n = nMeta[ i ]
         # now unset the parameter if value is set
         if config.config[ 'common' ].get( n.key ) and \
            config.config[ node ].get( n.key ):
            del config.config[ node ][ n.key ]
         prefill = ''
         if n.key in config.config[ node ].keys():
            prefill = config.config[ node ][ n.key ]

         if n.defaultValue:
            prefill = n.defaultValue

         # present lists as strings
         if n.ttype == meta.LIST:
            prefill = ', '.join( prefill )

         if n.ttype == meta.INTF:
            prefill = config.get( n.key, None, nn )

            # Only ask for config from the cluster_interface or the device_interface
            interfaces = [ config.config[ 'common' ][ intfType ] for intfType in
                         [ 'device_interface', 'cluster_interface' ] ]
            intf = n.key.split( '/' )[ 1 ]
            for intfType in ( 'device_interface', 'cluster_interface' ):
               if intfType in config.config[ node ]:
                  interfaces.append( config.config[ node ][ intfType ] )
            if intf not in interfaces:
               i += 1
               continue

         # read the new config
         if isRequired( n.key, config, mode, role ) and not config.config[
               'common' ].get( n.key ):
            disposition = True
         elif config.config[ 'common' ].get( n.key ):
            i += 1
            continue # already set in common config
         else:
            disposition = False #e.g. dns entry for singlenode
         req = '*' if disposition else ' '
         value = rlinput( " %s%s: " % ( req, n.prompt ), prefill )

         # strip out special chars
         for c in ( ',', ':', ';', '_' ):
            value = value.replace( c, '' )

         if n.validValues and value not in n.validValues:
            print '%s: Invalid input. Valid inputs are: %s' % ( value,
                  ', '.join( n.validValues ) )
            continue

         # convert lists back to strings
         if n.ttype == meta.LIST:
            value = value.split( )
         config.config[ node ][ n.key ] = value
         i += 1

   def scrubConfig( config ):
      '''Post-process to fix necessary keys and remove empty items.'''

      # Convert the keys <intf>_{ip_address, netmask} into nested keys
      for nn in ( 1, ):
         node = 'node%d' % nn
         config.config[ node ][ 'interfaces' ] = {}
         for intf in intfs:
            config.config[ node ][ 'interfaces' ][ intf ] = {}
            intfVal = config.config[ node ][ 'interfaces' ][ intf ]
            if 'interfaces/%s/ip_address' % intf in config.config[ node ]:
               intfVal[ 'ip_address' ] = config.config[ node ][
                                          'interfaces/%s/ip_address' % intf ]
               del config.config[ node ][ 'interfaces/%s/ip_address' % intf ]
            if 'interfaces/%s/netmask' % intf in config.config[ node ]:
               intfVal[ 'netmask' ] = config.config[ node ][
                                          'interfaces/%s/netmask' % intf ]
               del config.config[ node ][ 'interfaces/%s/netmask' % intf ]
            if config.config[ node ][ 'interfaces' ][ intf ] == {}:
               del config.config[ node ][ 'interfaces' ][ intf ]

      for section in config.config.keys():
         if section  == 'version':
            continue
         for key in config.config[ section ].keys():
            if len( config.config[ section ][ key ] ) == 0:
               del config.config[ section ][ key ]
         # we keep both node and common secion since verifyConfig()
         # looks for common and node configuration

   scrubConfig( config )

def cvpRunning():
   """
   Run "cvp status" and check if all cvp components are running.
   Return values:
   no: cvp is not running
   yes: all cvp components are running
   some: come cvp components are running
   """
   output = runCmd( "sudo /sbin/service cvp status" )[ 1 ]
   runCount = output.count( "RUNNING" )
   noRunCount = output.count( "NOT RUNNING" )

   status = "some"
   if runCount and not noRunCount:
      status = "yes"
   elif noRunCount and runCount == noRunCount:
      status = "no"
   return status

def cvpInitialized():
   """
   Check if cvp is installed and initialized. Return values:
   no: cvp is not installed
   yes: cvp is installed and initialized
   partial: aborted or partial install
   """
   hasData = os.path.exists( "/data/hdfs/dfs/name/current" )
   installStarted = os.path.exists( "/cvp/.install.started" )
   installComplete = os.path.exists( "/cvp/.install.complete" )
   status = "no"
   if installStarted and installComplete and hasData:
      status = "yes"
   elif installStarted or installComplete or hasData:
      status = "partial"
   return status

def defaultYaml( ):
   return os.path.join( cvpLib.DEFAULT_YAML_DIR, cvpLib.DEFAULT_YAML_FILE )

def verifyConfig( config, mode, role ):
   '''Scan through and ensure that the required settings are present '''

   if 'common' not in config.config.keys():
      print 'Invalid config - missing common config'
      return False

   missing = []
   # look for the right number of nodes
   nodes = []
   if config.nodeCnt( ) == 1:
      nodes = [ 'node1' ]
   elif config.nodeCnt( ) == 3:
      nodes = [ 'node1', 'node2', 'node3' ]
   else:
      print 'Invalid config - bad node count:%s ' % config.nodeCnt()
      return False

   # scan the nodes...
   for n in nodes:
      # make sure we have config for each node
      if n not in config.config.keys():
         print 'Invalid config - missing %s config' % n
         return False

      nodeNum = int( n[ len( 'node' ) : ] )

      for m in nMeta:
         # look for missing required config

         if not config.get( m.key, None, nodeNum ) and m.key not in missing:
            if 'interfaces' in m.key:
               intf = re.search ( r'(eth\d)', m.key ).group()
               interfaces = [ config.get( intf ) for intf in
                     ( 'device_interface', 'cluster_interface' ) ]
               if intf not in interfaces:
                  continue
            if isRequired( m.key, config, mode, role ):
               missing.append( m.key )

         # we distinguish intfType  and  intf as follows:
         #    intfType is either 'cluster_interface' or 'device_interface'
         #    intf actually refers to real interface names such as eth0
         # check that the device/cluster interface are fully defined
         for intfType in ( 'cluster_interface', 'device_interface' ):
            intf = config.config[ 'common' ].get( intfType )
            if intf is None:
               intf = config.config[ 'node%d' % nodeNum ].get( intfType )
            if intf is None:
               if intfType not in missing:
                  missing.append( intfType )
               continue
            key = 'interfaces/%s/ip_address' % intf
            if not config.get( key, None, node=nodeNum ):
               if key not in missing:
                  missing.append( key )
            key = 'interfaces/%s/netmask' % intf
            if not config.get( key, None, node=nodeNum ):
               if key not in missing:
                  missing.append( key )

   if len( missing ) > 0 :
      print 'Invalid config - missing: %s' % ', '.join( missing )
      return False
   else:
      print 'Valid config.'
      return True

def saveConfig( config ):
   config.save( )
   print 'saved config to %s' % config.fname

def checkAndConfirm( mode='singlenode' ):
   """
   Make sure the user confirms he wants to blow away existing working config.
   """
   initialized = cvpInitialized()
   running = cvpRunning() if initialized == "yes" else "no"

   if mode != 'singlenode' and ( running != "no" or initialized != "no" ):
      print "CVP service is configured and may be running,\n" \
"reconfigure is not supported in multinode setup"
      return False, initialized, running
   if running == "yes":
      print "CVP service is currently running, are you sure want apply this\n" \
"config and restart CVP?",
   elif initialized == "yes":
      print "CVP service is installed and the configuration appears valid\n" \
"are you sure you want to replace it and restart CVP?",
   elif running != "no" or initialized != "no":
      print "There is existing configuration and some CVP components maybe " \
"running\nAre you sure you want to replace it and restart CVP?",
   else:
      return True, initialized, running

   choice = rlinput( "yes/no: ", "yes" )
   return choice in [ "y", "yes" ], initialized, running

def runCmdAsCvpUser( cmd ):
   return runCmd( 'su - cvp -c "%s"' % cmd, printCmd=False )

def waitForFiles( filenames, max_iter=30 ):
   for fname in filenames:
      while not os.path.isfile( fname ) and max_iter > 0:
         sys.stdout.write( '.' )
         sys.stdout.flush()
         time.sleep( 5 )
         max_iter -= 1
   return max_iter

def waitForHostAndKeyFiles():
   sys.stdout.write( "Waiting for other nodes to send their hostname and ip" )
   filenames = [ cvpLib.SECONDARY_HOSTFILE, cvpLib.SECONDARY_KEYFILE,
                 cvpLib.TERTIARY_HOSTFILE, cvpLib.TERTIARY_KEYFILE ]
   return waitForFiles( filenames, max_iter=720 )

def updateAuthorizedKeys():
   skey = open( cvpLib.SECONDARY_KEYFILE, "r" )
   tkey = open( cvpLib.TERTIARY_KEYFILE, "r" )
   with open( authfile, 'a' ) as keyFile:
      keyFile.write( skey.read() )
      keyFile.write( tkey.read() )
   skey.close()
   tkey.close()

def updateYaml( config ):
   def _combineCommonConfigs( commonConfigs ):
      '''
      We have three copies of common configs, we combine them.
      We first use common config of the primary node as a starting point,
      and then we populate missing parts from secondary/tertiary nodes
      '''
      combinedCommonConfig = config.config[ 'common' ]
      for commonConfig in commonConfigs:
         for key, value in commonConfig.iteritems():
            if key not in combinedCommonConfig:
               combinedCommonConfig[ key ] = value

   hostfiles = { '2' : cvpLib.SECONDARY_HOSTFILE, '3' : cvpLib.TERTIARY_HOSTFILE }
   commonConfigs = []
   for n in hostfiles.keys():
      infile = open( hostfiles[ n ], "r" )
      node = 'node' + n
      # We populate the yaml file with the interface, hostname, ip address
      # and netmask. The interface will be cluster interface sent from
      # the secondary and tertiary nodes
      content = infile.read()
      transferredConfig = yaml.load( content )
      config.config[ node ] = transferredConfig[ 'node1' ]
      commonConfigs.append( transferredConfig[ 'common' ] )
      log( 'content is %s' % content )
   _combineCommonConfigs( commonConfigs )
   config.save()

def waitForConsolidatedYaml():
   sys.stdout.write( "Waiting for primary to send consolidated yaml" )
   filenames = [ '/tmp/authorized_keys', '/tmp/cvp-config.yaml' ]
   received = waitForFiles( filenames, max_iter=720 )

   if received:
      cmd = 'mv /tmp/cvp-config.yaml /cvp/'
      runCmdAsCvpUser( cmd )
      cmd = 'mv /tmp/authorized_keys /home/cvp/.ssh/'
      runCmdAsCvpUser( cmd )
   else:
      print "Did not receive authorized keys and consolidated yaml files"
      return

def deleteHostAndKeyFiles():
   files = [ cvpLib.SECONDARY_HOSTFILE, cvpLib.SECONDARY_KEYFILE,
             cvpLib.TERTIARY_HOSTFILE, cvpLib.TERTIARY_KEYFILE ]
   for f in files:
      os.remove( f )

def getClusterIntfIp( config, nodeNum ):
   cluster_intf = config.get( 'cluster_interface', DEFAULT_INTERFACE, nodeNum )
   ip = config.get( 'interfaces/%s/ip_address' % cluster_intf,
                    '', nodeNum )
   netmask = config.get( 'interfaces/%s/netmask' % cluster_intf,
                         '', nodeNum )
   return ( ip, netmask )

def generateHostAndKeyFiles( config, tempDir, role ):
   '''Create <role>.yaml '''
   filename = role + '.yaml'
   with open( os.path.join( tempDir, filename ), 'w' ) as hostFile:
      hostFile.write( yaml.dump( config.config ) )
      # hostFile.write( yaml.dump( config.config[ 'node1' ] ) )
   hostFilePath = os.path.join( tempDir, filename )
   keysFilePath = os.path.join( tempDir, role + '_key' )
   shutil.copyfile( os.path.expanduser( '~%s/.ssh/id_rsa.pub' % CVP_USER ),
                    keysFilePath )
   return ( hostFilePath, keysFilePath )

def configComplete():
   cmd = 'touch %s' % cvpLib.CVP_CONFIG_SENTINEL
   runCmdAsCvpUser( cmd )

def deleteConfigComplete():
   sys.stdout.write( "Waiting for primary to complete cvp installation. "
		     "This may take several minutes" )
   filenames = [ cvpLib.CVP_INSTALL_SENTINEL ]
   waitForFiles( filenames, max_iter=720 )

   cmd = 'rm %s' % cvpLib.CVP_CONFIG_SENTINEL
   runCmdAsCvpUser( cmd )

def waitForConfigComplete( ip ):
   i = 1
   max_iter = 60
   p = pexpect.spawn( 'su cvp' )
   p.sendline( 'ssh %s' % ip )
   p.expect( r'\$' )
   while i != 0 and max_iter > 0:
      cmd = 'test -f %s && echo "Y" || echo "N"' % cvpLib.CVP_CONFIG_SENTINEL
      p.sendline( cmd )
      i = p.expect( [ 'Y', 'N' ] )
      time.sleep( 5 )
   return max_iter

def scpFilesAsRoot( src, dst ):
   new_key = 'Are you sure you want to continue connecting (yes/no)?'
   passwd = 'password:'
   scpHandle = pexpect.spawn( 'scp %s %s' % ( src, dst ) )
   pswdPrompt = scpHandle.expect( [ new_key, passwd ] )
   numOfAttempts = 1
   if not pswdPrompt:
      scpHandle.sendline( 'yes' )
      pswdPrompt = scpHandle.expect( [ 'dummy', passwd ] )
   while pswdPrompt and numOfAttempts <= 3:
      scpHandle.sendline( getpass.getpass( prompt="Primary's root password: " ) )
      pswdPrompt = scpHandle.expect( [ pexpect.EOF, passwd ], timeout=10 )
      numOfAttempts += 1

def restartNtpd( config ):
   print "Running ntpdate to force sync system time"
   if isServiceActive( "ntpd.service" ) == "active":
      print "ntp service is still active, cannot sync date"
      ntpstat = 1
   else:
      ntpstat = 0
      for ntp in config.get( 'ntp' ):
         ntpstat = runCmd( '/bin/sudo /usr/sbin/ntpdate %s' % ntp )[ 0 ]
         if not ntpstat:
            break
      if not ntpstat:
         print 'Starting ntp service'
         ntpstat = runCmd( '/bin/sudo /bin/systemctl start ntpd.service' )[ 0 ]
         if ntpstat:
            print "Failed to start ntp service"
      else:
         print "Failed to sync system date with ntp server"
   return ntpstat

def startServices( config, services ):
   status = 0
   for s in services:
      # before bringing up ntp sync the clock
      if s == 'ntpd' and config.get( 'ntp' ):
         status |= restartNtpd( config )
      elif s == 'cvp':
         # 'systemctl start' and 'service start' result in different behavior.
         # Until we root cause what causes the difference or we make cvp a
         # systemd service, we must use "service" wrapper to start cvp.
         print '"service cvp start" may take approximately fifteen minutes to \
complete.'
         status |= runCmd( '/bin/sudo /sbin/service cvp start' )[ 0 ]
      else:
         print 'Starting service: %s' % s
         status |= runCmd( '/bin/sudo /bin/systemctl start %s.service' % s )[ 0 ]
   return status

def isServiceActive( serviceName ):
   cmd = "/bin/sudo /bin/systemctl is-active {}".format( serviceName )
   _, stdout = runCmd( cmd, ignoreErrors=True )
   result = stdout.strip()

   if result == "unknown":
      print "Internal error, unkown service '{}'".format( serviceName )
      result = "failed"
   elif not result in [ "active", "inactive" ]:
      print "Could not determine state of '{}'".format( serviceName )
      result = "failed"
   return result

def configureCvp( config, node, options ):
   cmd = 'sudo /cvp/tools/cvpConfig.py -y %s -n %s ' % ( config.fname, node )
   cmd +=u' '.join( options )

   # Do not print command that shows "node1", as "node1" is misleading '''
   print 'Running cvpConfig.py tool...'
   res = runCmd( cmd, printCmd=False )
   return res

def restartServices( config, services, node, role='primary', mode='singlenode' ):
   applyconfig, initialized, _running = checkAndConfirm( mode )
   if not applyconfig:
      return 1

   status = 0
   serviceStop = services
   serviceStart = serviceStop[ ::-1 ]
   options = []
   for s in serviceStop:
      print 'Stopping service: %s' % s
      runCmd( '/bin/sudo /sbin/service %s stop' % s )
      if isServiceActive( s ) == "active":
         print "Could not stop '{}', aborting [re]install".format( s )
   if mode != 'singlenode':
      if [ 'network' ] == services:
         options = [ '--network-only' ]
      else:
         options = [ '--cvp-only' ]
   res = configureCvp( config, node, options )
   status |= res[ 0 ]

   # rebuild the cvp config files
   if initialized in [ "yes", "partial" ]:
      print "Do you want to discard existing data?",
      choice = rlinput( "yes/no: ", "no" )
      if choice in [ "n", "no" ]:
         res = runCmd( 'sudo /bin/cvpConfigure' )[ 0 ]
         if res != 0:
            print """
Could not apply current configuration. Please check settings and re-apply.
I will not try to start cvp service.\n"""
            serviceStart.remove( "cvp" )
      else:
         res = runCmd( 'sudo /bin/cvpReInstall -m' )[ 0 ]

   # restart services
   status |= startServices( config, serviceStart )
   return status

def ipApplied( ip ):
   if 0 == runCmd( "ping -c1 {} -W 3".format( ip ), printCmd=False )[ 0 ]:
      return True
   return False

def waitForPrimaryIp( ip ):
   max_iter = 120
   while not ipApplied( ip ) and max_iter > 0:
      sys.stdout.write( '.' )
      sys.stdout.flush()
      time.sleep( 5 )
      max_iter -= 1
   return max_iter

def applyConfig( config, role='primary', mode='singlenode' ):
   ''' Before applying the config we redirect stdout/err to a logfile
   and then restore it when we're done. '''
   assert mode in [ 'singlenode', 'multinode', 'replace' ]
   assert role in [ 'primary', 'secondary', 'tertiary' ]

   if mode == 'singlenode':
      services = [ 'cvp', 'ntpd', 'network' ]
      node = 'node1'
   elif mode == 'multinode':
      services = [ 'network' ]
      node = 'node1'
      # node is 'node1' since the config has only one node currently
   else:
      services = [ 'network' ]
      node = { 'primary' : 'node1',
               'secondary' : 'node2',
               'tertiary' : 'node3' }[ role ]

   if restartServices( config, services, node, role, mode ):
      return

   if mode == 'singlenode':
      return

   elif mode == 'replace': # replacement
      services = [ 'ntpd' ]
      res = restartServices( config, services, node, role, mode )
      if res != 0:
         print "Failed to (re)start one of the services"
         return
      ips = config.fetchIpAddresses()
      log( 'Configuring the node...' )
      peerIp = ips[ 'secondary' ] if role is 'primary' else ips[ 'primary' ]
      cvpReplace.log( 'Run "service cvp multistop" on the cluster' )
      peer = cvpLib.Peer( peerIp )
      peer.timeoutIs( None ) #we must wait until cvp multistop finishes
      log( 'Stop all cvp/java processes' )
      mode = os.stat( cvpLib.INSTALL_LOG_FILE )
      os.chmod( cvpLib.INSTALL_LOG_FILE, mode.st_mode |
                stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH |
                stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH )
      peer.sshAsCvp( '/bin/sudo /sbin/service cvp multistop' )
      cvpReplace.log( 'Configuring this node to join the cluster' )
      cvpReplace.joinCvpCluster( int( node[-1] ), ips )
      runCmd( '/bin/sudo /sbin/service cvp multistart' )
      res = runCmd( '/bin/sudo /sbin/service cvp status' )
      status = res[ 0 ]

   elif role == 'primary':
      if not waitForHostAndKeyFiles():
         print "Failed to receive hostname and ip address from other nodes"
         return
      updateAuthorizedKeys()
      updateYaml( config )
      services = [ 'ntpd' ]
      res = restartServices( config, services, 'node1', role, mode )
      if res != 0:
         print "Failed to (re)start one of the services"
         return
      ( secondary_ip, _ ) = getClusterIntfIp( config, SECONDARY_NODE_ID )
      ( tertiary_ip, _ ) = getClusterIntfIp( config, TERTIARY_NODE_ID )
      status = 0
      cmd = "scp %s %s %s:/tmp/" % ( defaultYaml(), authfile, secondary_ip )
      status |= runCmdAsCvpUser( cmd )[ 0 ]
      cmd = "scp %s %s %s:/tmp/" % ( defaultYaml(), authfile, tertiary_ip )
      status |= runCmdAsCvpUser( cmd )[ 0 ]
      if status != 0:
         return
      deleteHostAndKeyFiles()
      waitForConfigComplete( secondary_ip )
      waitForConfigComplete( tertiary_ip )
      startServices( config, [ 'cvp' ] )
      res = runCmd( '/bin/sudo /sbin/service cvp status' )
      status = res[ 0 ]
      if status == 0:
         print "CVP installation successful"
      else:
         print """
CVP installation failed. Please run "service cvp status" for details\n
"""

   elif role in [ 'secondary', 'tertiary' ]:
      tempDir = tempfile.mkdtemp()
      (hostFile, keyFile) = generateHostAndKeyFiles( config, tempDir, role )
      res = configureCvp( config, 'node1', [ '--cvp-only' ] )
      primIp = rlinput( "Primary IP: " )

      if not ipApplied( primIp ):
         sys.stdout.write( "Waiting for primary IP to come up" )
         if 0 == waitForPrimaryIp( primIp ):
            print "Timed out waiting for primary IP to be up"
            return
         print "\n"

      print "Receiving public keys of primary node"
      pubKey = os.path.expanduser( '~%s/.ssh/id_rsa.pub' % CVP_USER )
      src = 'root@%s:%s' % ( primIp, pubKey )
      scpFilesAsRoot( src, '/tmp/' )
      primPubKey = open( os.path.join( '/tmp', 'id_rsa.pub' ), 'r' )
      authKeys = open(
         os.path.expanduser( '~%s/.ssh/authorized_keys' % CVP_USER ), 'a' )
      authKeys.write( primPubKey.read() )
      authKeys.close()
      primPubKey.close()

      print "Pushing hostname,ip address and public key to primary node"
      src = '%s %s' % ( hostFile, keyFile )
      dst = 'root@%s:/tmp/' % primIp
      scpFilesAsRoot( src, dst )
      print "Transferred files"
      waitForConsolidatedYaml()
      config.config = yaml.safe_load( open( defaultYaml() ) )
      services = [ 'ntpd' ]
      node = "node2" if role == "secondary" else "node3"
      res = restartServices( config, services, node, role, mode )
      if res != 0:
         print "Failed to (re)start one of the services"
         return
      configComplete()
      # cleanup
      shutil.rmtree( tempDir )
      os.remove( '/tmp/id_rsa.pub' )
      deleteConfigComplete()
      print "Done"


def printHelp():
   print "[q]uit [p]rint [e]dit [v]erify [s]ave [a]pply [h]elp ve[r]bose"

def getRole():
   print "Choose a role for the node, roles should be mutually exclusive"
   while True:
      print "[p]rimary [s]econdary [t]ertiary"
      role = raw_input( '>' )
      if role in [ 'p', 'primary' ]:
         role = 'primary'
      elif role in [ 's', 'secondary' ]:
         role = 'secondary'
      elif role in [ 't', 'tertiary' ]:
         role = 'tertiary'
      else:
         print "Incorrect role"
         continue
      return role

def getCvpMode():
   print "Choose CVP installation mode"
   while True:
      print "[s]inglenode [m]ultinode [r]eplace [u]pgrade"
      mode = raw_input( '>' )
      if mode in ( 's', 'singlenode' ):
         mode = 'singlenode'
      elif mode in ( 'm', 'multinode' ):
         mode = 'multinode'
      elif mode in ( 'r', 'replace' ):
         mode = 'replace'
      elif mode in ( 'u', 'upgrade'):
         mode = 'upgrade'
      else:
         print 'Incorrect mode'
         continue
      return mode

def setRootPassword():
   '''
   setRootPassword returns True if root password is already set or successfully
   created otherwise returns False
   '''
   child = pexpect.spawn( 'su - root -c true' )
   i = child.expect( [ '[pP]assword:', pexpect.EOF ] )
   if i == 0:
      return True # Password is already set
   if 0 == subprocess.call( 'su - root -c "passwd"', shell=True ):
      return True
   else:
      return False

def cvpUpgrade():
   '''Performs CVP upgrade by running cvpUpgrade script from the tools'''
   if not os.path.exists( CVP_UPGRADE_TMP_DIR ):
      print ( '%s does not exist. Please ensure cvp RPMs and cvp-tools.tgz are '
              'copied to this directory and then select "upgrade".' %
              CVP_UPGRADE_TMP_DIR )
      return
   toolsTgz = glob.glob( '%s/cvp-tools*.tgz' % CVP_UPGRADE_TMP_DIR )
   if len( toolsTgz ) == 0:
      print 'Couldnt find the tools tgz at %s, exiting upgrade' % CVP_UPGRADE_TMP_DIR
      return
   elif len( toolsTgz ) > 1:
      print ( 'Multiple tools tgz found in %s, add only the latest tools tgz'
              ', exiting upgrade' % CVP_UPGRADE_TMP_DIR )
      return
   else:
      tar = tarfile.open( toolsTgz[ 0 ] )
      print 'Extracting cvp-tools.tgz to %s' % CVP_UPGRADE_TMP_DIR
      tar.extractall( CVP_UPGRADE_TMP_DIR )
      tar.close()
      returnCode = subprocess.call( 'cd %s && sudo ./cvpUpgrade.py' %
                                    CVP_UPGRADE_TMP_DIR, shell=True )
      if returnCode != 0:
         print 'cvpUpgrade.py failed with error code %d' % returnCode

def main():
   global verbose

   # look for default yaml file
   yamlFile = defaultYaml( )
   config = configParser.CvpConfigParser( yamlFile, ignoreErrors=True )

   role = 'primary'
   mode = None
   if not setRootPassword():
      return

   while mode not in [ 'singlenode', 'multinode', 'replace', 'upgrade' ]:
      mode = getCvpMode()
   if mode == 'upgrade':
      cvpUpgrade()
      return

   if not config.sanityCheck():
      if mode == 'multinode':
         role = getRole()
      print '''
Enter the configuration for CloudVision Portal and apply it when done.
Entries marked with '*' are required.
'''
      if mode == 'replace':
         # Import configuration and apply right away
         try:
            role = importConfig( config )
         except ( AssertionError, pexpect.TIMEOUT ):
            # TODO for now we just gracefully say that configuration failed,
            # rather than printing the whole stack trace back to the user
            print 'Configuration Setup Failed - Could not import configuration'
            return
         applyConfig( config, role, mode )
      else:
         editConfig( config, role, mode )
   else:
      print 'Found configuration at %s:\n' % yamlFile
      printConfig( config )
      if mode == 'multinode':
         role = getRole()
      elif mode == 'replace':
         role = importConfig( config )
         try:
            role = importConfig( config )
         except ( AssertionError, pexpect.TIMEOUT ):
            print 'Configuration Setup Failed - Could not import configuration'
            return

   printHelp()
   while True:
      try:
         cmd = raw_input( '>' )
      except EOFError:
         cmd = 'q'

      if len( cmd ) == 0:
         continue

      cmd = cmd.lower()

      if cmd in [ 'q', 'quit', 'exit' ]:
         break
      elif cmd in [ 'p', 'print' ]:
         printConfig( config )
      elif cmd in [ 'e', 'edit' ]:
         editConfig( config, role, mode )
      elif cmd in [ 'v', 'verify' ]:
         verifyConfig( config, mode, role )
      elif cmd in [ 'r', 've[r]bose' ]:
         # verbose is global
         verbose = not verbose
         print
      elif cmd in [ 's', 'save' ]:
         saveConfig( config )
      elif cmd in [ 'a', 'apply' ]:
         if not verifyConfig( config, mode, role ):
            continue
         saveConfig( config )
         res = 0
         if cvpInitialized() != "no" and cvpRunning() != "yes":
            # cvpReInstall may fail in multinode case if it can't kill all processes.
            # Run the command atleast twice to ensure it succeeds.
            for _ in range( 2 ):
               cmd = 'sudo /bin/cvpReInstall -m'
               res = runCmd( cmd, printCmd=False, ignoreErrors=True )[ 0 ]
               if res == 0:
                  break
         if res != 0:
            print "Could not apply configuration, cvpReInstall failed"
            printHelp()
            continue
         applyConfig( config, role, mode )
         printHelp()
      elif cmd in [ 'h', '?', 'help' ]:
         printHelp()
      else:
         print 'Invalid command:', cmd
         printHelp()

if __name__ == '__main__':
   discoverIntfs()
   main()
