#! /usr/bin/env python
#
# Copyright (c) 2015 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
#
# cvpConfig.py: Take a yaml file as input and apply the configuration specified
#               in it.

import os
import sys
import argparse
import tempfile
import fileinput
import shutil
import crypt
import re
import SimpleConfigFile
import cvpConfigParser
import subprocess
import shlex
import cvpLib

CVP_HOME = '/cvp'
CVP_UID = 10010
CVP_GID = 10010

CVP_CONF = '/etc/cvp.conf'
NTPFILE = '/etc/ntp.conf'
HOSTSFILE = '/etc/hosts'
FW_CONF = "/etc/firewalld/zones/public.xml"
BOOT_CONFIG = '/cvp/tomcat/webapps/ROOT/ztp/boot_config.py'
RESOLV_CONF = "/etc/resolv.conf"

PRIMARY = 1
SECONDARY = 2
TERTIARY = 3

CVP_TMPLT = """#!/bin/bash

export CVP_VERSION=%s
export CVP_INSTALL_PATH=/cvp
export CVP_BACKUP_PATH=/data/backup
export CVP_VERSION_BACKUP=/data/backup

# singlenode or multinode
export CVP_MODE=%s

# If a loadbalancer is being used, replace with the IP address and port
# number to use
export LOAD_BALANCER_IP=
export LOAD_BALANCER_PORT=

# Please specify the Server's Hostname and Host ip's to run the CVP in Multinode
export PRIMARY_HOSTNAME=%s
export PRIMARY_HOST_IP=%s

##******************************
## For Multinode configuration
##******************************

export SECONDARY_HOSTNAME=%s
export SECONDARY_HOST_IP=%s

export TERTIARY_HOSTNAME=%s
export TERTIARY_HOST_IP=%s
"""

def rewriteFile( filename, mapping ):
   """Replace file 'filename' inplace. 'mapping' is a dict {pat: target} where
   text matching regex 'pat' is replaced with 'target' in every line of the file.
   TODO: A way to add/delete a line."""
   # fileinput inplace changes owner/perms. save and restore them
   st = os.stat( filename )
   for line in fileinput.input( filename, inplace=True ):
      for pat, target in mapping.iteritems():
         m = re.search( pat, line )
         if m:
            print re.sub( pat, target, line ),
            break
      else:
         print line,
   os.chown( filename, st.st_uid, st.st_gid )
   os.chmod( filename, st.st_mode )

# popen wrapper to run a subprocess
def runCmd( cmd, shell=False ):
   """
   Run 'cmd' as a sub-process and capture stdout and stderr. If the command
   needs shell support, like pipe, launch inside a shell.
   """
   cmdArray = shlex.split( cmd )
   popenHandle = subprocess.Popen( cmd if shell else cmdArray,
                                   env=os.environ.copy(),
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   shell=shell )

   stdoutdata, stderrdata = popenHandle.communicate()
   return popenHandle.returncode, stdoutdata, stderrdata

class CvpConfig( object ):
   """Encapsulation of CVP config and methods to make changes to it."""

   def __init__( self, yamlFile, node ):

      self.props = {
         'ip_address' : self.nop,
         'netmask' : self.nop,
         'interfaces' : self.nop,
         'default_route' : self.setDefaultGw,
         'ntp' : self.setNtp,
         'mode' : self.setMode,
         'hostname' : self.nop,
         'vmname' : self.nop,
         'dns' : self.nop,
         'root' : self.nop,
         'primary_hostname' : self.nop,
         'primary_host_ip' : self.nop,
         'secondary_hostname' : self.nop,
         'secondary_host_ip' : self.nop,
         'tertiary_hostname' : self.nop,
         'tertiary_host_ip' : self.nop,
         'cluster_interface' : self.nop,
         'device_interface' : self.nop,
      }
      self.hidden = ( 'root', )

      assert node.startswith( 'node' )

      self.node = node
      self.nodeNum = int( self.node[ len( 'node' ) : ] )
      self.cvpConfig = cvpConfigParser.CvpConfigParser( yamlFile )

      version = self.cvpConfig.config[ 'version' ]
      assert version <= cvpConfigParser.YAML_VER_CURRENT, \
            'Error: Unsupported version %s, current version is %s.' % ( version,
                  cvpConfigParser.YAML_VER_CURRENT )
      self.version = version

      self.hostnames = {}
      for node in xrange( PRIMARY, TERTIARY + 1 ):
         self.hostnames[ node ] = ''
      for node in xrange( 0, self.cvpConfig.nodeCnt() ):
         nodeNum = node + 1
         # We lowercase the given name before using. See BUG132616.
         self.hostnames[ nodeNum ] = self.cvpConfig.hostname( nodeNum ).lower()

      self.readIntfConfig()

   def display_val( self, prop, val ):
      ''' Some values shouldn't be sent to the output'''
      return crypt.crypt( val, "cvp" )[ 20:30 ] if prop in self.hidden else val

   def nop( self, val ):
      print 'Nothing to do'

   def readIntfConfig( self ):
      """Read interface configuration parameters, taking versions into account."""
      self.device_interface = self.cvpConfig.get( 'device_interface', 'eth0',
                                                  self.nodeNum )
      if self.version == 1:
         self.device_ip = self.cvpConfig.get( 'ip_address', '', self.nodeNum )
         self.device_netmask = self.cvpConfig.get( 'netmask', '', self.nodeNum )
      else:
         self.device_ip = self.cvpConfig.get( 'interfaces/%s/ip_address'
                                 % self.device_interface, '', self.nodeNum )

      self.cluster_ips = {}
      self.cluster_netmasks = {}
      self.cluster_intfs = {}
      for node in xrange( PRIMARY, TERTIARY + 1 ):
         self.cluster_ips[ node ] = ''
         self.cluster_netmasks[ node ] = ''
         self.cluster_intfs[ node ] = ''
      for node in xrange( 0, self.cvpConfig.nodeCnt() ):
         nodeNum = node + 1
         # defaults to eth0
         cluster_intf = self.cvpConfig.get( 'cluster_interface', 'eth0', nodeNum )
         if self.version == 1:
            cluster_ip = self.cvpConfig.get( 'ip_address', '', nodeNum )
         else:
            cluster_ip = self.cvpConfig.get( 'interfaces/%s/ip_address'
                                             % cluster_intf, '', nodeNum )
         if cluster_ip == '':
            print ( 'Error: No IP address configured for cluster_interface %s on '
                    'node %s' % ( cluster_intf, nodeNum ) )
         cluster_netmask = self.cvpConfig.get( 'interfaces/%s/netmask'
                                               % cluster_intf, '', nodeNum )
         self.cluster_intfs[ nodeNum ] = cluster_intf
         self.cluster_ips[ nodeNum ] = cluster_ip
         self.cluster_netmasks[ nodeNum ] = cluster_netmask

   def setupHosts( self ):
      print 'Setting up hosts'
      tmp = tempfile.NamedTemporaryFile( delete=False )
      for line in fileinput.input( HOSTSFILE ):
         if not line:
            continue
         fields = line.split()
         # skip entries that we're about to regenerate
         if fields[ 0 ] in self.cluster_ips.values() or ( len( fields ) > 1 and
               fields[ 1 ].lower() in self.hostnames.values() ):
            pass
         else:
            tmp.write( line )
      for nodeNum in self.cluster_ips:
         if self.cluster_ips[ nodeNum ]:
            tmp.write( '%s %s\n' % ( self.cluster_ips[ nodeNum ],
                                     self.hostnames[ nodeNum ] ) )
      # Should we write device_ips of others also?
      # No need to add the device_ip if it's the same as the cluster_ip
      if self.device_ip and self.device_ip != self.cluster_ips[ self.nodeNum ]:
         tmp.write( '%s %s\n' % ( self.device_ip, self.hostnames[ self.nodeNum ] ) )
      tmp.close()
      shutil.copymode( HOSTSFILE, tmp.name )
      shutil.move( tmp.name, HOSTSFILE )

   def setHostname( self ):
      name = self.cvpConfig.get( 'hostname', None, self.nodeNum )
      if not name:
         return
      lname = name.lower()
      print 'Setting hostname to:', lname
      with open( '/etc/hostname', 'w' ) as f:
         f.write( lname )
         f.write( '\n' )
      runCmd( 'sudo /usr/bin/hostname %s' % lname )

   def setDefaultGw( self, gw ):
      print 'Setting default gw to:', gw
      with open( '/etc/sysconfig/network', 'w' ) as f:
         f.write( 'GATEWAY=%s\n' % gw )

   def setDns( self ):
      ns = self.cvpConfig.get( 'dns', None, self.nodeNum )
      if not ns:
         print 'No DNS servers specified.'
         return True
      _, _, domain = self.hostnames[ self.nodeNum ].partition( "." )
      print 'setting Dns to:', ns, 'domain to:', domain
      with open( RESOLV_CONF, 'w' ) as f:
         for s in ns:
            f.write( 'nameserver %s\n' % s )
         f.write( "options timeout:5\noptions attempts:2\n" )
         if domain:
            f.write( 'search %s\n' % domain )
      return True

   def setNtp( self, ntps ):
      if not ntps:
         print 'No NTP servers specified.'
         return
      print 'Setting Ntp to:', ntps
      # Rewrite only the lines we're interested in
      tmp = tempfile.NamedTemporaryFile( delete=False )
      for line in fileinput.input( NTPFILE ):
         if not line.startswith( 'server ' ):
            tmp.write( line )
      for ntp in ntps:
         tmp.write( 'server %s\n' % ntp )
      tmp.close()
      shutil.copymode( NTPFILE, tmp.name )
      shutil.move( tmp.name, NTPFILE )

   def setMode( self, mode ):
      print 'Setting mode to:', mode
      assert mode in ( 'singlenode', 'multinode' )

   def setupFirewalld( self ):
      # Rewrite filewalld configuration
      zoneConfig = """<?xml version="1.0" encoding="utf-8"?>
<zone>
<short>Public</short>
<description>For use in public areas. You do not trust the other computers on networks to not harm your computer. Only selected incoming connections are accepted.</description>
<service name="dhcpv6-client"/>
<service name="ssh"/>
<service name="http"/>
<service name="https"/>
"""

      portRuleFormatString = """
<rule family="ipv4">
   <source address="%(primary)s"/>
   <port port="%(port)d" protocol="tcp"/>
   <accept/>
</rule>
<rule family="ipv4">
   <source address="%(secondary)s"/>
   <port port="%(port)d" protocol="tcp"/>
   <accept/>
</rule>
<rule family="ipv4">
   <source address="%(tertiary)s"/>
   <port port="%(port)d" protocol="tcp"/>
   <accept/>
</rule>
"""
      # Hadoop Namenode
      for port in ( 8020, 9001, 15070,    # Hadoop Namenode
               8480, 8481, 8485,     # JournalNode
               15090,                # Hadoop Secondary Namenode
               15010, 15020, 15075,  # Hadoop Datanode
               16000,                # HBase Master (leave out debug http port 16010)
               16201,                # HBase Master (leave out debug http port 16301)
               2181, 2888, 2889,     # Zookeeper
               2890, 3888, 3889,     # Zookeeper
               3890,                 # Zookeeper
               5701,                 # Hazelcast
               8080,                 # tomcat nodes talk to each other
            ):
         zoneConfig += portRuleFormatString % (
               { "primary" : self.cluster_ips[ PRIMARY ],
                  "secondary" : self.cluster_ips[ SECONDARY ],
                  "tertiary" : self.cluster_ips[ TERTIARY ],
                  "port" : port } )
      zoneConfig += """</zone>
"""

      with open( FW_CONF, "w" ) as handle:
         handle.write( zoneConfig )
      # Restart firewalld to get the rules to take effect
      print 'Restarting firewalld'
      runCmd( 'systemctl restart firewalld' )

   def cvpConf( self ):
      """Generate cvp.conf file."""

      print 'Generating cvp.conf'
      cvpConf = CVP_TMPLT % ( cvpLib.getCvpVersion(),
                        self.cvpConfig.mode(),
                        self.hostnames[ PRIMARY ] , self.cluster_ips[ PRIMARY ] ,
                        self.hostnames[ SECONDARY ], self.cluster_ips[ SECONDARY ],
                        self.hostnames[ TERTIARY ], self.cluster_ips[ TERTIARY ] )
      with open( CVP_CONF, 'w' ) as f:
         f.write( cvpConf )
      os.chown( CVP_CONF, CVP_UID, CVP_GID )
      print "done."

   def setupInterfaces( self ):
      """Apply interface configuration."""
      print 'Setting up network interfaces.'
      intfs = []
      if self.version == 1:
         intfs.append( ( self.device_interface, self.device_ip,
                         self.device_netmask ) )
      else:
         for intfName in self.cvpConfig.get( 'interfaces', {}, self.nodeNum ):
            ip = self.cvpConfig.get( 'interfaces/%s/ip_address' % intfName, '',
                                     self.nodeNum )
            netmask = self.cvpConfig.get( 'interfaces/%s/netmask' % intfName, '',
                                          self.nodeNum )
            intfs.append( ( intfName, ip, netmask ) )

      for intfName, ip, netmask in intfs:
         print 'Setting up interface', intfName, ', ip:', ip, ', netmask:', netmask
         netdevFile = '/etc/sysconfig/network-scripts/ifcfg-%s' % intfName
         netdevConfig = SimpleConfigFile.SimpleConfigFileDict( netdevFile,
                           createIfMissing=True )
         if ip == 'dhcp':
            netdevConfig[ 'BOOTPROTO' ] = 'dhcp'
            netdevConfig[ 'IPADDR' ] = ''
            netdevConfig[ 'NETMASK' ] = ''
         else:
            netdevConfig[ 'BOOTPROTO' ] = 'static'
            netdevConfig[ 'IPADDR' ] = ip
            netdevConfig[ 'NETMASK' ] = netmask
         netdevConfig[ 'NETBOOT' ] = 'no'
         netdevConfig[ 'ONBOOT' ] = 'yes'
         netdevConfig[ 'IPV6INIT' ] = 'yes'
         netdevConfig[ 'NAME' ] = intfName
         netdevConfig[ 'TYPE' ] = 'Ethernet'

   def setupZtp( self ):
      print 'Setting up ZTP boot script.'
      rewriteFile( BOOT_CONFIG, { 'loadbalance:port' : '%s:80' % self.device_ip } )
      runCmd( 'cd %s/tomcat/webapps/ROOT/ztp; su cvp -c ./build.sh' % CVP_HOME,
              shell=True )

   def updateProperties( self ):
      """Update cvp.properties parameters with the real values."""
      propFile = '/cvp/property/cvp.properties_%s' % self.cvpConfig.mode()
      print 'Updating %s file.' % propFile
      rewriteFile( propFile, { 'device_vip:port' : '%s:80' % self.device_ip } )

   def applyProp( self, prop, arg ):
      """Apply property in 'prop'. i.e. Call the corresponding action function with
      the given arg."""
      action = self.props.get( prop )
      if not action:
         print 'Warning: Skipping unknown property:', prop
      else:
         action( arg )

   def applyNetworkConfig( self ):
      """Read and apply network config from file 'yamlFile' corresponding to the
      node named 'node'. It's the top-level key. We could possibly accept hostname
      or IP address instead, in the future."""
      nodeConfig = self.cvpConfig.config.get( self.node, {} )
      if nodeConfig:
         for prop, val in nodeConfig.iteritems():
            print 'Applying node-specific property:', prop, ', val:', \
                  self.display_val( prop, val )
            self.applyProp( prop, val )
      else:
         print 'Warning: Node %s not found in configuration file' % self.node

      common = self.cvpConfig.config[ 'common' ]
      for prop, val in common.iteritems():
         if prop in nodeConfig:
            print 'Ignoring common property because it was overridden:', prop, \
                  ', val:', self.display_val( prop, val )
         else:
            print 'Applying common property:', prop, ', val:', \
                  self.display_val( prop, val )
            self.applyProp( prop, val )

      self.setupInterfaces()

   def applyCvpConfig( self ):
      #Set the timezone to UTC
      retcode, _, _ = runCmd( 'sudo ln -sf /usr/share/zoneinfo/UTC /etc/localtime' )
      if retcode > 0:
         print 'Timezone not set to UTC'
      self.setHostname()
      self.setupHosts()
      self.cvpConf()
      if self.cvpConfig.mode() == 'multinode':
         self.setupFirewalld()
      self.setupZtp()
      self.updateProperties()
      if not self.setDns():
         return False
      return True

def parse():
   parser = argparse.ArgumentParser(
                        description= 'Apply configuration from a yaml file' )
   parser.add_argument( '-y', '--yaml', help='Config file in YAML', required=True )
   parser.add_argument( '-n', '--node', help='Name of this node', required=True )
   parser.add_argument( '--network-only', help='Configure only the network',
      action='store_true', default=False )
   parser.add_argument( '--cvp-only', help='Configure everything except network',
      action='store_true', default=False )
   return parser.parse_args()

if __name__ == '__main__':
   sys.stdout = os.fdopen( sys.stdout.fileno(), 'w', 0 )
   args = parse()

   cc = CvpConfig( args.yaml, args.node )
   status = False
   if args.network_only:
      cc.applyNetworkConfig()
      status = True
   elif args.cvp_only:
      status = cc.applyCvpConfig()
   else:
      cc.applyNetworkConfig()
      status = cc.applyCvpConfig()
   if not status:
      sys.exit( 1 )
   print "'{}' successful".format( " ".join( sys.argv ) )
