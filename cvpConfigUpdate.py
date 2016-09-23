#!/usr/bin/python
# Copyright (c) 2016 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

"""
configure script populated the templates dropped by cvp rpm
"""
import cvpLib
import cvpConfigParser
import os
import time
import shutil
import tempfile

CVP_CONFIG_UPDATE_LOG = '/cvp/logs/cvpConfigUpdate.log'
CVP_HOME = cvpLib.CVP_HOME

#Dictionary of template files dropped by new rpms
templateFiles = { 'cvp.conf' : '/etc/cvp.conf',
                  'cvp.properties' : CVP_HOME + '/property/cvp.properties',
                  'boot_config.py' : CVP_HOME + '/tomcat/webapps/ROOT/ztp/'
                                                'boot_config.py',
                  'cvp' : CVP_HOME + '/scripts/cvp',
                  'loadImageToHDFS.sh' : CVP_HOME + '/scripts/loadImageToHDFS.sh',
                  'log4j.properties' : CVP_HOME + '/property/log4j/log4j.properties',
                  'export.sh' :  CVP_HOME + '/scripts/export.sh',
                  'import.sh' :  CVP_HOME + '/scripts/import.sh',
                  'setenv.sh' : CVP_HOME + '/tomcat/bin/setenv.sh',
                  # 'hadoop' and 'hbase' are symlinks to the actual version used
                  'core-site.xml' : CVP_HOME + '/hadoop/etc/hadoop/core-site.xml',
                  'hbase-site.xml' : CVP_HOME + '/hbase/conf/hbase-site.xml'
                }

def log( msg ):
   with open( CVP_CONFIG_UPDATE_LOG, "a" ) as logHandle:
      ts = time.strftime( "[%a %b %d %X %Z %Y] " )
      logHandle.write( ts + msg + "\n" )

def populateSedDict( cvpConfig, hostIp, cvpVersion, deviceIntfIp, loadBalancerIp='',
                     loadBalancerPort='' ):
   """Dictionary containing all the seding commands info"""
   sedDict = {}
   returnCode, output, _ = cvpLib.runCmd( "date +%s" )
   assert returnCode == 0, 'Error occurred while retrieving date'
   date = output.strip()
   if cvpConfig.mode() == 'multinode':
      ipDict = cvpConfig.fetchIpAddresses()
      primaryIp = ipDict[ 'primary' ]
      secondaryIp = ipDict[ 'secondary' ]
      tertiaryIp = ipDict[ 'tertiary' ]
      sedDict[ 'multinode' ] = [ {
                     # Note that the order of IPs in HAZELCAST_IPS and NODE_IPS is
                     # going to be different from what the install scripts setup,
                     # but the order is not significant.
                     'sedCmd' : 's/primary_host_ip/%s/' % primaryIp,
                     'files' : [ 'cvp.properties', 'hbase-site.xml' ]
                    },
                    {
                     'sedCmd' : 's/secondary_host_ip/%s/' % secondaryIp,
                     'files' : [ 'cvp.properties', 'hbase-site.xml' ]
                    },
                    {
                     'sedCmd' : 's/tertiary_host_ip/%s/' % tertiaryIp,
                     'files' : [ 'cvp.properties', 'hbase-site.xml' ]
                    },
                    # The order is going to be significant here
                    {
                       'sedCmd' : 's/primary_host/%s/' % cvpConfig.hostname( 1 ),
                       'files' : [ 'hbase-site.xml' ]
                    },
                    {
                       'sedCmd' : 's/secondary_host/%s/' % cvpConfig.hostname( 2 ),
                       'files' : [ 'hbase-site.xml' ]
                    },
                    {
                       'sedCmd' : 's/tertiary_host/%s/' % cvpConfig.hostname( 3 ),
                       'files' : [ 'hbase-site.xml' ]
                    },
                    {
                     'sedCmd' : 's/localhost:9001/mycluster/',
                     'files' : [ 'loadImageToHDFS.sh' ]
                    } ]
   else:
      sedDict[ 'singlenode' ] = [ {
                     'sedCmd' : 's/localhost/%s/' % hostIp,
                     'files' : [ 'cvp.properties', 'loadImageToHDFS.sh',
                                 'core-site.xml', 'hbase-site.xml' ]
                    },
                    {
                     'sedCmd' : 's/mycluster/%s/' % hostIp,
                     'files' : [ 'cvp' ]
                    } ]
   sedDict[ 'common' ] = [ {
                     'sedCmd' : 's@cvp_home@%s@' % CVP_HOME,
                     'files' : [ 'log4j.properties', 'cvp.properties', 'export.sh',
                                 'import.sh', 'core-site.xml', 'hbase-site.xml' ]
                    },
                    {
                     'sedCmd' : 's/cvpversion/%s/' % cvpVersion,
                     'files' : [ 'cvp.properties' ]
                    },
                    {
                     'sedCmd' : 's/user/cvp/',
                     'files' : [ 'cvp.properties' ]
                    },
                    {
                     'sedCmd' : 's/cvp_date/%s/' % date,
                     'files' : [ 'cvp.properties' ]
                    },
                    {
                     'sedCmd' : 's/device_vip:port/%s:80/' % deviceIntfIp,
                     'files' : [ 'cvp.properties' ]
                    } ]

   loadBalSedList = []
   if loadBalancerIp and loadBalancerPort:
      newIp, newPort = loadBalancerIp, loadBalancerPort
   else:
      newIp, newPort = hostIp, '80'
   loadBalSedList = [ {
                       'sedCmd' : 's/loadbalance:port/%s:%s/' % ( newIp, newPort ),
                       'files' : [ 'boot_config.py' ]
                      } ]
   sedDict[ 'common' ].extend( loadBalSedList )

   xml_changes = (
             ( 'ipc.client.connect.max.retries', '1', 'core-site.xml' ),
             ( 'ipc.client.connect.max.retries.on.timeouts', '1', 'core-site.xml' ),
             ( 'ipc.client.connect.timeout', '1000', 'core-site.xml' ),
             ( 'zookeeper.session.timeout', '20000', 'hbase-site.xml' )
      )
   for change in xml_changes:
      entry = {
            'sedCmd' : '/<name>%s<\/name>/{n;s/.*/<value>%s<\/value>/}'
                       % ( change[ 0 ], change[ 1 ] ),
            'files' : [ change[ 2 ] ]
      }
      sedDict[ 'common' ].append( entry )

   return sedDict

def sedFileCont( node, filePath, sedCmd ):
   '''Executes sedCmd and raises exception in case of failures'''
   cmd = 'sed -i \\"%s\\" %s' % ( sedCmd, filePath )
   log( cmd )
   output = node.sshAsCvp( cmd )
   log( output )
   assert 'Exit status 0' in output, ( 'Error occurred while running %s on file %s'
                                       % ( cmd, filePath ) )

def performSed( node, cvpConfig, nodeIp, cvpVersion ):
   """ Performs seding on the newly dropped files by rpm install"""
   nodeNum = cvpConfig.getNodeNum( nodeIp )
   deviceIntfIp = cvpConfig.deviceIp( nodeNum )
   sedDict = populateSedDict( cvpConfig, nodeIp, cvpVersion, deviceIntfIp )
   sedCommon = sedDict[ 'common' ]
   for sedAction in sedCommon:
      for fname in sedAction[ 'files' ]:
         sedFileCont( node, templateFiles[ fname ], sedAction[ 'sedCmd' ] )
   sedMode = sedDict[ cvpConfig.mode() ]
   for sedAction in sedMode:
      for fname in sedAction[ 'files' ]:
         sedFileCont( node, templateFiles[ fname ], sedAction[ 'sedCmd' ] )

def updateSetEnv( nodeList ):
   '''This can be done using sed '$ a ...' but it gets really messy with all
   the quotes. Hence this custom function.'''
   tmp = tempfile.NamedTemporaryFile( suffix='.sh', delete=False )
   tmp.write( 'export JAVA_OPTS="$JAVA_OPTS -Dhazelcast.max.operation.timeout=5"\n'
        'export JAVA_OPTS="$JAVA_OPTS -Dhazelcast.max.no.heartbeat.seconds=5"\n' )
   tmp.close()
   _, output,_ = cvpLib.runCmd(
         'chown cvp:cvp %s; chmod a+r %s' % ( tmp.name, tmp.name ),
         True )
   for node in nodeList:
      node.scpAsCvp( tmp.name, tmp.name, upload=True )
      cmd = 'cat %s >> %s' % ( tmp.name, templateFiles[ 'setenv.sh' ] )
      log( cmd )
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, 'Error occurred while updating setenv.sh'
   for node in nodeList:
      node.sshAsCvp( 'rm -f ' + tmp.name )

def modCvpConfFile( nodeList, oldCvpVersion, newCvpVersion ):
   '''Modify the cvp configuration file in the /etc/'''
   for node in nodeList:
      cmd = "cp /etc/cvp.conf /tmp/"
      log( cmd )
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, 'Error occurred while copying cvp.conf'
      sedFileCont( node, '/tmp/cvp.conf',
                   's/%s/%s/' % ( oldCvpVersion, newCvpVersion ) )
      cmd = "cp /tmp/cvp.conf /etc/cvp.conf"
      log( cmd )
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, 'Error occurred while replacing cvp.conf'

def modConfigFiles( nodeList, cvpConfig, hostIp, oldCvpVersion, newCvpVersion ):
   """Adds information in the template property files dropped by the new installed
   rpms """
   modCvpConfFile( nodeList, oldCvpVersion, newCvpVersion )
   mode = cvpConfig.mode()
   pairs = ( ( '%s/property/cvp.properties_%s' % ( CVP_HOME, mode ),
                templateFiles[ 'cvp.properties' ] ),
             ( '%s/hadoop/etc/hadoop/core-site.xml_%s' % ( CVP_HOME, mode ),
               templateFiles[ 'core-site.xml' ] ),
             ( '%s/hbase/conf/hbase-site.xml_%s' % ( CVP_HOME, mode ),
                templateFiles[ 'hbase-site.xml' ] ),
           )
   copyFilesOnAllCvp( nodeList, pairs )

   for node in nodeList:
      performSed( node, cvpConfig, node.ip, newCvpVersion )
      cmd = 'cd /cvp/tomcat/webapps/ROOT/ztp; ./build.sh'
      log( cmd )
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, ( 'Error occurred while running the '
                                          'build.sh on %s' % hostIp )
   updateSetEnv( nodeList )

   # Special case. Really hate to duplicate from cvp_{single,multi}node.
   # This is a copy into hbase/conf, so it has to be done after all
   # substitutions are done on the original.
   copyFilesOnAllCvp( nodeList, ( ( templateFiles[ 'core-site.xml' ],
                                     '%s/hbase/conf/' % CVP_HOME ), ) )

def getOldCvpVersion():
   '''Get the old cvp version from the cvp.properties file'''
   cmd = 'cat %s | grep CVP_INSTALL_VERSION | cut -d "=" -f2' % (
                                                  templateFiles[ 'cvp.properties' ] )
   returnCode, output,_ = cvpLib.runCmd( cmd, True )
   assert returnCode == 0, 'Error occurred while retrieving old cvp version'
   return output.strip()

def backupTemplateFiles( fileDict ):
   """Backups the old configuration files """
   date = time.strftime("%m:%d:%Y:%I:%M:%S")
   backupPath = '/cvp/logs/upgrade-backup-%s' % date
   try:
      os.makedirs( backupPath )
   except OSError as e:
      print 'Directory creation failed Error: %s' % e
   for fname in fileDict:
      try:
         if os.path.exists( templateFiles[ fname ] ):
            shutil.copyfile( templateFiles[ fname ], os.path.join( backupPath,
                             fname ) )
      except shutil.Error as e:
         print 'File not copied. Error: %s' % e
   print "Successfully backed up property files in %s " % backupPath

def copyFilesOnAllCvp( nodeList, pairs ):
   for node in nodeList:
      cmd = '; '.join( [ 'cp %s %s' % ( src, dst ) for src, dst in pairs ] )
      log( cmd )
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, 'Error running: %s' % cmd

def rmFilesOnAllCvp( nodeList, fname ):
   """Deletes files on all the cvp instances"""
   if not fname:
      return
   fileListStr = ''
   for fname in fname:
      fileListStr = ' '.join( [ fileListStr, fname ] )
   for node in nodeList:
      cmd = "rm -f %s" % fileListStr
      log( cmd )
      output = node.sshAsCvp( cmd )
      log( output )
      assert 'Exit status 0' in output, 'Error occurred while deleting %s on %s' % (
                                        fileListStr, node.ip )
def run( cvpConfig, nodeList ):
   if os.path.isfile( cvpLib.CVP_INSTALL_SENTINEL ):
      hostIp = cvpLib.getCurrNodeIp()
      oldCvpVersion = getOldCvpVersion()
      rmFilesOnAllCvp( nodeList, [ templateFiles[ 'cvp.properties' ] ] )
      newCvpVersion = cvpLib.getCvpVersion()
      modConfigFiles( nodeList, cvpConfig, hostIp, oldCvpVersion, newCvpVersion )
   else:
      print 'CVP install was not done on this system. Configurations of \
             properties not required'

def main():
   cvpConfig = cvpConfigParser.CvpConfigParser(
                  os.path.join( cvpLib.DEFAULT_YAML_DIR, cvpLib.DEFAULT_YAML_FILE ) )
   if not cvpConfig.sanityCheck():
      print "No valid CVP config found, populating property files after new rpm \
install failed"
   else:
      nodeList = cvpLib.getPeerList( cvpConfig,  300 )
      run( cvpConfig, nodeList )

if __name__ == '__main__':
   main()
