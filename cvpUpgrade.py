#!/usr/bin/python
# Copyright (c) 2016 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

"""
cvpUpgrade script performs light weight rpm upgrade. This tool needs the new rpms
to be droped in the /RPMS directory of the cvp node. For mulinode this needs to be
done on all nodes. This tool uses yum for creating new repos, checking for updates
and to perform upgrades if required.
"""
import argparse
import cvpLib
import cvpConfigParser
import cvpConfigUpdate
import os
import re
import rpm
import sys
import time
import glob

CVP_UPGRADE_LOG = '/cvp/logs/cvpUpgrade.log'
CVP_HOME = '/cvp'
MOD_SUDO_CVP = 'grep "/bin/yum" /etc/sudoers.d/cvp || sed -i "s:$:,/bin/yum:g" \
/etc/sudoers.d/cvp'
MOD_SUDO_CVPADMIN = 'grep "/tmp/upgrade/cvpUpgrade.py" /etc/sudoers.d/cvpadmin \
|| sed -i "s:$:,/tmp/upgrade/cvpUpgrade.py:g" /etc/sudoers.d/cvpadmin'
# Minimum release year of cvp version which supports the cvp upgrade functionality
MIN_CVP_RELEASE_YEAR = 2016

def runCmdWithLog( cmd ):
   """
   This methods call the runCmd from cvpLib but additionaly logs the stdout and
   stderr returned by it.
   """
   returnCode, stdout, stderr = cvpLib.runCmd( cmd )
   log( cmd )
   log( stdout )
   log( stderr )
   return returnCode, stdout

def log( msg ):
   """ logs information """
   with open( CVP_UPGRADE_LOG, "a" ) as logHandle:
      ts = time.strftime( "[%a %b %d %X %Z %Y] " )
      logHandle.write( ts + msg + "\n" )

def createRepo( nodeList ):
   """ Rebuild CVP rpm repository after adding new rpms on all nodes"""
   for node in nodeList:
      log( "Adding new rpms to cvp repo on node '%s'" % node.ip )
      output = node.sshAsCvp( "createrepo -o /RPMS /RPMS && yum clean all" )
      log( output )
      assert 'Exit status 0' in output, 'Adding new rpm to cvp repo failed on \
node %s' % node.ip
      log( "created new rpm repo on %s node" % node.ip )

def rpmUpdateCheck( nodeList ):
   """performing yum update check on all the nodes"""
   upgradeRequired  = []
   for node in nodeList:
      log( 'performing yum update check on %s node' % node.ip )
      cmd = "yum check-update --disablerepo=* --enablerepo=cvp-local | grep cvp"
      output = node.sshAsCvp( cmd )
      log( output )
      if 'Exit status 0' not in output:
         log( "yum found no new rpms on %s node" % node.ip )
      else:
         upgradeRequired.append( node )
         log( "yum upgrade necessary on %s node" % node.ip )
   if not upgradeRequired:
      log( "Cvp upgrade not necessary, new rpms are installed on all node" )
      raise RuntimeError( 'Cvp instances are up to to date and no upgrade required' )
   elif upgradeRequired == nodeList:
      log( "Detected new rpms on all the nodes" )
   else:
      nodeIps = [ node.ip for node in nodeList if node not in upgradeRequired ]
      log( "Yum update check didn't detect new rpms on %s " % ' '.join( nodeIps ) )
      raise RuntimeError( 'yum update didnt detect new rpms on %s' % ' '.join(
                          nodeIps ) )
   print 'Successfully detected new rpms on all nodes'

def rpmsUpgrade( cvpConfig, nodeList ):
   """ Install new rpms on all the nodes"""
   chkCvpServicesStatus( cvpConfig, { 'all' : False }, 'rpm upgrade' )
   if not chkCvpServiceStatus( cvpConfig, 'tomcat', False ):
      log( "Failed to stop tomcat, exiting upgrade process" )
      raise RuntimeError(  "Failed to stop tomcat, exiting upgrade process" )
   for node in nodeList:
      log( 'upgrading rpms on %s node' % node.ip )
      cmd = "sudo yum upgrade --disablerepo=* --enablerepo=cvp-local -y"
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, 'yum rpm upgrade failed on %s node' % node.ip
      log( 'successfully upgraded rpms on %s' % node.ip )

def chkCvpServicesStatus( cvpConfig, serviceStatDict, action ):
   """Checks if the CVP services are in the state mentioned in the serviceStatDict.
   This Dict has services as keys and boolean value for describing the expected
   state"""
   for key,val in serviceStatDict.iteritems():
      status = 'running' if val else 'not running'
      if not chkCvpServiceStatus( cvpConfig, key, val ):
         errMsg = ( '%s action expects %s it to be %s for successful execution' % (
                    action, key, status ) )
         log( errMsg )
         raise RuntimeError( errMsg )

def dataUpgrade( cvpConfig, oldCvpVersion, newCvpVersion, currNodeIp,
                 skipVersionCheck=False ):
   """ Performs the inplace data upgrade """
   log( "performing data upgrade from %s to %s" % ( oldCvpVersion, newCvpVersion ) )
   chkCvpServicesStatus( cvpConfig, { 'tomcat' : False, 'hbase' : True, 'hadoop' :
                                      True, 'zookeeper' : True }, 'data upgrade' )
   if oldCvpVersion == newCvpVersion:
      print 'Data upgrade not required'
   else:
      if cvpConfig.mode() == 'multinode':
         activeHMasterIp = cvpLib.getActiveHMasterIp()
      else:
         activeHMasterIp = currNodeIp
      returnCode, output = runCmdWithLog( 'su - cvp -c "%s/jdk/bin/java -jar %s/'
                               'tools/upgrade-%s.jar %s %s %s"' % ( CVP_HOME,
                               CVP_HOME, newCvpVersion, oldCvpVersion,
                               newCvpVersion, activeHMasterIp ) )
      log( output )
      if returnCode != 0:
         msg = 'Data upgrade failed while performing upgrade from %s to %s' % (
                                                       oldCvpVersion, newCvpVersion )
         log( msg )
         if skipVersionCheck:
            print msg
            print 'Continuing because skipVersionCheck is true'
            log( 'Continuing because skipVersionCheck is true' )
         else:
            assert False, msg
      else:
         msg = "Successfully performed data upgrade"
         log( msg )
         print msg

def defaultImageUpgrade( cvpConfig ):
   """update the default image in the hdfs and properties file"""
   log( "Uploading the default swi images to the hdfs" )
   chkCvpServicesStatus( cvpConfig, { 'tomcat' : False, 'hbase' : True, 'hadoop' :
                         True, 'zookeeper' : True }, 'loading default swi image' )
   returnCode, _ = runCmdWithLog( 'su - cvp -c "/cvp/scripts/loadImageToHDFS.sh"' )
   assert returnCode == 0, 'Failed to add the default images to HDFS'

def cvpServicesStartStop( cvpConfig, service, action ):
   """ starts and stops cvp services"""
   if cvpConfig.mode() == "singlenode":
      # Hbase in singlenode uses internal zookeeper hence just checking hbase should
      # be enough for checking zookeeper service status.
      # For uniformaity of service status check function between singlenode and
      # multinode if zookeeper status is enquired we just return for singlenode
      if service == 'zookeeper':
         return
      log( "%s %s" % ( action, service ) )
      returnCode, _ = runCmdWithLog( 'su - cvp -c "/cvp/scripts/cvp --%s %s"' %
                                     ( action, service ) )
      assert returnCode == 0, '%s %s action failed' % ( action, service )
   elif cvpConfig.mode() == "multinode":
      log( "%s %s on all the nodes" % ( action, service ) )
      returnCode, _ = runCmdWithLog( 'su - cvp -c "/cvp/scripts/cvp_multinode'
                                     ' --multi%s %s"' % ( action, service ) )
      assert returnCode == 0, '%s %s action failed' % ( action, service )
   else:
      log( "invalid cvp mode %s" % cvpConfig.mode() )
      raise RuntimeError( 'invalid cvp mode %s' % cvpConfig.mode() )

def setupEnvironment( cvpConfig, nodeList ):
   """ Sets the environment for performing upgrade"""
   print 'Setting up the environment for the upgrade'
   pwd = os.getcwd()
   for node in nodeList:
      log( 'modifying /etc/sudoers.d/cvp file on %s' % node.ip )
      output = node.sshAsRoot( MOD_SUDO_CVP + ';' + MOD_SUDO_CVPADMIN )
      assert 'Exit status 0' in output, 'Failed to modify sudoers file on %s' % (
                                        node.ip )
      log( output )
      log( 'removing repodata directory on %s node' % node.ip )
      output = node.sshAsCvp( 'sudo rm -rf /RPMS/repodata' )
      assert 'Exit status 0' in output, 'Failed to remove repodata. on %s' % node.ip
      log( output )
      log( 'Copying the rpms to /RPMS on %s ' % node.ip )
      output = node.scpAsCvp( pwd + '/cvp-*.rpm', '/RPMS', upload=True )
      log( output )
      assert 'Exit status 0' in output, 'Failed to copy rpms to /RPMS on %s' % (
                                                                            node.ip )
      log( 'Intial setup complete on %s' % node.ip )
   print 'Successfully completed the intial setup for upgrade'

def upgradeNginx( nodeList ):
   """Upgrade nginx on all the nodes"""
   cmd = 'sudo service nginx upgrade'
   log( cmd )
   for node in nodeList:
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, ( 'Error occured while upgrading nginx on %s'
                                          % node.ip )

def chkCvpServiceStatus( cvpConfig, service, state ):
   """checks if the service on the cvp instance has the desired state"""
   if cvpConfig.mode() == "singlenode":
      if service == 'zookeeper':
         return True
      cmd = 'su - cvp -c "/cvp/scripts/cvp --status %s | grep "NOT RUNNING""' % (
                                                                            service )
   else:
      cmd = ( 'su - cvp -c "/cvp/scripts/cvp_multinode --multistatus %s | grep \
"NOT RUNNING""' % service )
   returnCode, _ = runCmdWithLog( cmd )
   #doesn't handle the cases of actual cvp service status script failure
   if ( state and returnCode == 1 ) or ( returnCode == 0 and not state ):
      return True
   else:
      return False

def run( cvpConfig, nodeList, skipVersionCheck=False ):
   try:
      currNodeIp = cvpLib.getCurrNodeIp()
      setupEnvironment( cvpConfig, nodeList )
      chkCvpServicesStatus( cvpConfig, { 'hbase' : True, 'hadoop' : True,
                                         'zookeeper' : True }, 'CVP upgrade' )
      print "Creating new RPM repository on CVP nodes"
      createRepo( nodeList )
      rpmUpdateCheck( nodeList )
      print "Stopping services on all nodes"
      cvpServicesStartStop( cvpConfig, 'all', 'stop' )
      oldCvpVersion = cvpLib.getCvpVersion()
      cvpConfigUpdate.backupTemplateFiles( cvpConfigUpdate.templateFiles )
      print "Installing new rpms on all nodes"
      rpmsUpgrade( cvpConfig, nodeList )
      cvpConfigUpdate.run( cvpConfig, nodeList )
      newCvpVersion = cvpLib.getCvpVersion()
      log( "upgrading from %s to %s" % ( oldCvpVersion, newCvpVersion ) )
      log( "Upgrading nginx on all the nodes" )
      upgradeNginx( nodeList )
      # We need all services running except tomcat, so we start all and stop tomcat.
      # Since those are the tested operations.
      print "Starting services on all nodes"
      cvpServicesStartStop( cvpConfig, 'all', 'start' )
      print "Checking if all the services are up and running"
      chkCvpServicesStatus( cvpConfig, { 'tomcat' : True, 'hbase' : True, 'hadoop' :
                                         True, 'zookeeper' : True }, 'data upgrade' )
      print "Stopping tomcat on all the nodes"
      cvpServicesStartStop( cvpConfig, 'tomcat', 'stop' )
      print "Performing data upgrade"
      dataUpgrade( cvpConfig, oldCvpVersion, newCvpVersion, currNodeIp,
                   skipVersionCheck )
      print "Updating default SWI images"
      defaultImageUpgrade( cvpConfig )
      print "Starting tomcat on all nodes"
      cvpServicesStartStop( cvpConfig, 'tomcat', 'start' )
      print 'CVP upgrade successfully completed'
      retval = 0
   except ( AssertionError, RuntimeError ) as err:
      print err
      log( str(err) )
      print "Scan through the logs file at %s for more information" % CVP_UPGRADE_LOG
      retval = 3
   return retval

def getCvpConfig():
   '''retrieves the cvp configuration from yaml file'''
   iso_based_install = False
   if not os.path.exists( os.path.join(
                             cvpLib.DEFAULT_YAML_DIR, cvpLib.DEFAULT_YAML_FILE ) ):
      print '/cvp/cvp-config.yaml not found, retrieving yaml from cdrom'
      print 'Mounting cdrom'
      returnCode, output = runCmdWithLog( 'mount /dev/cdrom /media/cdrom' )
      log( output )
      if returnCode != 0:
         raise RuntimeError( 'Failure to mount cdrom' )
      print 'Copying over the yaml file'
      returnCode, output = runCmdWithLog( 'cp /media/cdrom/cvp-config.yaml /cvp/' )
      if returnCode != 0:
         raise RuntimeError( 'Failure to retrieve the yaml file from cdrom' )
      # Absence of cvp-config.yaml in CVP_HOME indicates that previous install was
      # iso based install
      iso_based_install = True
      print 'Unmounting cdrom'
      returnCode, output = runCmdWithLog( 'umount /media/cdrom' )
      if returnCode != 0:
         raise RuntimeError( 'Failure to unmount cdrom' )
   cvpConfig = cvpConfigParser.CvpConfigParser(
                  os.path.join( cvpLib.DEFAULT_YAML_DIR, cvpLib.DEFAULT_YAML_FILE ) )
   if not cvpConfig.sanityCheck():
      log ( "No valid CVP config  provided, exiting CVP upgrade process" )
      raise RuntimeError( "No valid CVP config  provided, exiting CVP upgrade "
                          "process" )
   print 'Successfully retrieved CVP configuration'
   currNodeIp = cvpLib.getCurrNodeIp()
   nodeList = cvpLib.getPeerList( cvpConfig,  300 )
   # For iso base installs prior to 2016.1.1 the cvp-config.yaml file wasn't
   # placed in the CVP_HOME at the end of successful install.
   # Hence copying the cvp-config.yaml over to other nodes CVP_HOME for consistency
   if iso_based_install:
      for node in nodeList:
         if node.ip == currNodeIp:
            continue
         node.scpAsCvp( os.path.join( cvpLib.DEFAULT_YAML_DIR,
                        cvpLib.DEFAULT_YAML_FILE ), CVP_HOME, upload=True )
   return cvpConfig, nodeList

def parseArgs():
   parser = argparse.ArgumentParser( description='CVP upgrade tool' )
   parser.add_argument( '--skipVersionCheck', default=False, action='store_true',
                        help='skip to and from version compatibility check for'
                        ' CVP upgrade' )
   args = parser.parse_args()
   return args

def supportVerChk( version ):
   """Checks if the version supports cvp upgrade functionality"""
   verIntParse = re.match( '(\d+)\.(\d+)\.(\d+)$', version )
   return verIntParse and int( verIntParse.group( 1 ) ) >= MIN_CVP_RELEASE_YEAR

def cvpUpgradeVerChk():
   """Checks if the current version and version to which system is going to be
   upgraded is supported by the cvp upgrade tool"""

   oldCvpVersion = cvpLib.getCvpVersion()
   if not supportVerChk( oldCvpVersion ):
      raise RuntimeError( "Cannot upgrade from %s. Has to be an official release and"
                          "minimum version required is %s" % ( oldCvpVersion,
                                                            MIN_CVP_RELEASE_YEAR ) )
   ts = rpm.TransactionSet()
   rpmNames = glob.glob( 'cvp-*.rpm' )
   for rpmName in rpmNames:
      rpmFdno = os.open( rpmName, os.O_RDONLY )
      rpmHdr = ts.hdrFromFdno( rpmFdno )
      os.close( rpmFdno )
      if not supportVerChk( rpmHdr[ rpm.RPMTAG_VERSION ] ):
         raise RuntimeError( "Cannot upgrade to %s. Has to be an official release"
                             " and minimum version required is %s" % (
                             rpmHdr[ rpm.RPMTAG_VERSION ], MIN_CVP_RELEASE_YEAR ) )

def main():
   try:
      args = parseArgs()
      if not args.skipVersionCheck:
         cvpUpgradeVerChk()
      print 'Starting CVP upgrade process'
      rpmNames = glob.glob( '*.rpm' )
      if not rpmNames:
         print 'No rpms found to install at %s, exiting upgrade' % os.getcwd()
         return 2
      cvpConfig, nodeList = getCvpConfig()
   except ( AssertionError, IOError, RuntimeError ) as e:
      print "ERROR: %s" % e
      return 1
   retval = run( cvpConfig, nodeList, args.skipVersionCheck )
   return retval

if __name__ == '__main__':
   ret = main()
   sys.exit( ret )
