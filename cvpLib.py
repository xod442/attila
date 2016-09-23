import getpass
import pexpect
import subprocess
import os
import shlex
import cvpConfigParser
import json
import socket

DEFAULT_EXPECT_TIMEOUT = 20 #seconds
REPLACE_LOG_FILE = '/tmp/cvp-replace.log'
INSTALL_LOG_FILE = '/tmp/cvp_install.log'
CVP_CONFIG_SENTINEL = '/cvp/.config.complete'
CVP_INSTALL_STARTED = '/cvp/.install.started'
CVP_INSTALL_SENTINEL = '/cvp/.install.complete'
DEFAULT_YAML_DIR = '/cvp/'
DEFAULT_YAML_FILE = 'cvp-config.yaml'
SECONDARY_HOSTFILE = '/tmp/secondary.yaml'
SECONDARY_KEYFILE = '/tmp/secondary_key'
TERTIARY_HOSTFILE = '/tmp/tertiary.yaml'
TERTIARY_KEYFILE = '/tmp/tertiary_key'
CVP_HOME = '/cvp'
#cvpLib Contains useful classes common to cvpShell and cvpReplace.
#Classes that can be imported from cvpLib

#Peer      - allows the user to ssh and scp files with another node

class Peer( object ):
   '''
   Run commands and copy files from and to the peer server via SSH
   Abstracts away password, host checking and expect details.
   '''
   def __init__( self, ipAddr, timeout=DEFAULT_EXPECT_TIMEOUT ):
      self.ip = ipAddr
      self.timeout = timeout
      self.sshOpts = '-oUserKnownHostsFile=/dev/null -v -oStrictHostKeyChecking=no'

   def timeoutIs( self, timeout ):
      self.timeout = timeout

   def sshAsRoot( self, cmd ):
      sshcmd = 'ssh %s root@%s "%s"' % ( self.sshOpts, self.ip, cmd )
      child = pexpect.spawn( sshcmd )
      child.timeout = self.timeout
      self._authAsRoot( child )
      child.expect( pexpect.EOF, timeout=self.timeout )
      return child.before

   def sshAsCvp( self, cmd ):
      opts = self.sshOpts + ' -oIdentityFile=/home/cvp/.ssh/id_rsa'
      sshcmd = 'ssh %s %s "%s"' % ( opts, self.ip, cmd )
      child = pexpect.spawn( "su - cvp -c '%s'" % sshcmd )
      child.timeout = self.timeout
      child.expect( pexpect.EOF, timeout=self.timeout )
      return child.before

   def scpAsRoot( self, src, dst, upload ):
      scpcmd = self._scpCmd( self.sshOpts, src, dst, 'root', upload )
      child = pexpect.spawn( scpcmd )
      child.timeout = self.timeout
      self._authAsRoot( child )
      child.expect( pexpect.EOF, timeout=self.timeout )
      return child.before

   def scpAsCvp( self, src, dst, upload ):
      opts = self.sshOpts + ' -oIdentityFile=/home/cvp/.ssh/id_rsa'
      scpcmd = self._scpCmd( opts, src, dst, 'cvp', upload )
      child = pexpect.spawn( "su - cvp -c '%s'" % scpcmd )
      child.timeout = self.timeout
      child.expect( pexpect.EOF, timeout=self.timeout )
      return child.before

   def _scpCmd( self, opts, src, dst, user, upload ):
      if upload:
         return 'scp -r %s %s %s@%s:%s' % ( opts, src, user, self.ip, dst )
      return 'scp -r %s %s@%s:%s %s' % ( opts, user, self.ip, src, dst )

   def _authAsRoot( self, child ):
      authenticated = False
      while not authenticated:
         i = child.expect( [ '[p|P]assword:', '(Authenticated|Transferred:)' ] )
         authenticated = False if i == 0 else True
         if not authenticated:
            child.sendline( getpass.getpass( 'Root password of %s: ' % self.ip ) )

def runCmd( cmd, shell=False ):
   cmdArray = shlex.split( cmd )
   popenHandle = subprocess.Popen( cmd if shell else cmdArray,
                                      env=os.environ.copy(),
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      shell=shell )
   stdoutdata, stderrdata = popenHandle.communicate()
   return popenHandle.returncode, stdoutdata, stderrdata

def getPeerList( cvpConfig, timeout=DEFAULT_EXPECT_TIMEOUT ):
   '''Returns a list of peer objects corresponding to ip list provided'''
   assert isinstance( cvpConfig, cvpConfigParser.CvpConfigParser )
   nodeIpsDict = cvpConfig.fetchIpAddresses()
   nodeIps = [ v for k, v in nodeIpsDict.iteritems() if k != '' and v != '' ]
   if cvpConfig.mode() == 'multinode':
      assert len( nodeIps ) == 3, 'incorrect number of ips'
   if cvpConfig.mode() == 'singlenode':
      assert len( nodeIps ) == 1, 'incorrect number of ips'
   return [ Peer( ip, timeout ) for ip in nodeIps ]

def getCvpVersion():
   """ return the version present in version.txt"""
   return json.load( open( '/cvp/property/version.txt', 'r' ) )[ 'version' ]

def getCurrNodeIp():
   """Retrieves ip address of current node"""
   returnCode, output,_ = runCmd( 'hostname -i' )
   assert returnCode == 0, 'Error occured while retrieving hostip'
   return output.strip()

def getActiveHMasterIp():
   """Retrieves current Active HMaster ip"""
   returnCode, output, _ = runCmd( 'su - cvp -c "/cvp/zookeeper/bin/zkCli.sh get \
/hbase/master quit | grep host.name | cut -d "=" -f2"' )
   assert returnCode == 0, 'Error occurred while retrieving active hmaster node \
hostname using zkCli.sh'
   return socket.gethostbyname( output.strip() )
