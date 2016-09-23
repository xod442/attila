#!/usr/bin/python
# Copyright (c) 2015 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
'''This script performs sanity testing for the cvp library. It checks
on the individual methods for confgilets, image bundles and containers.
Further this script takes a tar.gz file as an input. It restores the cvp
using this tar file and again perform backup of that cvp instance. It checks
the equality for the backup data and data used for restore in order to
check the integrity of cvptool.
'''
import errorCodes
import argparse
import cvp
import cvpServices
import cvptool
import json
#
# Configlet API tests:
#  getConfiglets: nominal, empty, more than one page (>100) of config
#  getConfig: nominal, non-existant
#  addConfig: nominal, already exists
#  delConfig: nominal, does not exist
#  add/del/add/del of same
#  multi line config
#
def testConfiglet( server ):
   ''' Tests all the functionalities pertaining to configlets in Cvp application'''

   # generate more than a page worth of configlets
   reference = [ ('configlet%d' % c, 'configlet%d' % c ) for c in range( 25 ) ]

   # insert them into cvp
   print 'inserting %d configs into cvp' % len( reference )
   for name, config in reference:
      configlet = cvp.Configlet( name, config )
      server.addConfiglet( configlet )

   # try inserting again
   print 'Retry inserting %d configs into cvp' % len( reference )
   for name, config in reference:
      configlet = cvp.Configlet( name, config )
      try:
         server.addConfiglet( configlet )
      except cvpServices.CvpError as err:
         if err.errorCode == errorCodes.CONFIGLET_ALREADY_EXIST:
            pass
         else:
            raise

   # read them all back and verify
   print 'verifying %d configs from cvp' % len( reference )
   configs = server.getConfiglets()
   for name, config in reference:
      for configInfo in configs:
         if configInfo.name == name:
            assert configInfo.config == config

   # change a configet and update
   print 'Inserting a modified configlet'
   configlet = cvp.Configlet( 'configlet20', 'configlet25' )
   server.updateConfiglet( configlet )

   # check whether config is modified
   print 'checking for updated config'
   configlet = server.getConfiglet( 'configlet20' )
   assert configlet.config == 'configlet25'

   # remove them all
   print 'removing %d configs from cvp' % len( reference )
   for config in configs:
      server.deleteConfiglet( config )
   assert len( server.getConfiglets() ) == 0

def testContainer( server ):
   ''' Tests all the functionalities pertaining to containers in Cvp application'''

   #generate sample configlets
   reference = [ ('configlet%d' % c, 'configlet%d' % c ) for c in range( 25 ) ]
   for name, config in reference:
      configlet = cvp.Configlet( name, config )
      server.addConfiglet( configlet )
   #generate random container hierarchy
   containerList = {}
   parentConfig = []
   parentConfig.append( reference[ 0 ][ 0 ] )
   parentConfig.append( reference[ 2 ][ 0 ] )
   parentConfig.append( reference[ 4 ][ 0 ] )
   childConfig = []
   childConfig.append( reference[ 3 ][ 0 ] )
   childConfig.append( reference[ 5 ][ 0 ] )
   childConfig.append( reference[ 6 ][ 0 ] )
   print 'inserting containers'
   currRootContainerInfo = server.getRootContainerInfo()
   for i in range( 0, 5 ):
      container = cvp.Container( 'parentContainer-%d' % i,
                                 currRootContainerInfo.name, parentConfig )
      server.addContainer( container )
      server.mapConfigletToContainer( container, parentConfig )
      containerList[ container.name ] = container
      for j in range( 0, 3 ):
         childContainer = cvp.Container( 'parentContainer%dchildContainer-%d'
                                  % ( i, j ), 'parentContainer-%d' % i, childConfig )
         server.addContainer( childContainer )
         server.mapConfigletToContainer( childContainer, childConfig )
         containerList[ childContainer.name ] = childContainer

   print 're-inserting same containers'
   for i in range( 0, 5 ):
      container = cvp.Container( 'parentContainer-%d' % i,
                                 currRootContainerInfo.name )
      try:
         server.addContainer( container )
      except cvpServices.CvpError as err:
         if err.errorCode == errorCodes.DATA_ALREADY_EXISTS:
            pass
         else:
            raise

      for j in range( 0, 3 ):
         childContainer = cvp.Container( 'parentContainer%dchildContainer-%d' %
               ( i, j ), 'parentContainer-%d' % i )
         try:
            server.addContainer( childContainer )
         except cvpServices.CvpError as err:
            if err.errorCode == errorCodes.DATA_ALREADY_EXISTS:
               pass
            else:
               raise

   # read them all back and verify
   print 'verifying all the containers'
   containers = server.getContainers()
   for container in containers:
      if container.name == currRootContainerInfo.name :
         continue
      if container.name in containerList:
         assert container.parentName == containerList[ container.name ].parentName
         assert container.configlets == containerList[ container.name ].configlets
      else:
         raise KeyError

   # remove all the containers
   print 'removing all the containers'
   for container in containers:
      if container.name != currRootContainerInfo.name :
         server.deleteContainer( container )

   configs = server.getConfiglets()
   for config in configs:
      server.deleteConfiglet( config )

def testImage( args, server ):
   ''' Tests all the functionalities pertaining to image and
   image bundles in Cvp application'''

   currRootContainerInfo = server.getRootContainerInfo()
   appImageBundleRootContainer = False
   #insert image bundle into inventory
   name = 'testImageBundle'
   certified = False
   imageNameList = []
   imageNameList.append( args.swi )
   print 'loading %s to %s' % ( imageNameList[ 0 ], server.cvpService.hostname )
   imageBundle = cvp.ImageBundle( name, imageNameList, certified )
   try:
      server.addImageBundle( imageBundle )
   except cvpServices.CvpError as err:
      if err.errorCode == errorCodes.IMAGE_BUNDLE_ALREADY_EXIST:
         pass
      else:
         raise

   #Reinserting the same image bundle
   print' Reloading %s to %s' % ( imageNameList[ 0 ], server.cvpService.hostname )
   try:
      server.addImageBundle( imageBundle )
   except cvpServices.CvpError as err:
      if err.errorCode == errorCodes.IMAGE_BUNDLE_ALREADY_EXIST:
         pass
      else:
         raise

   # read image bundle and verify
   bundle = server.getImageBundle( name )
   assert bundle.name == name

   # modify imageBundle
   print 'modifying the image bundle'
   certified = 'True'
   imageBundle = cvp.ImageBundle( name, imageNameList, certified )
   server.updateImageBundle( imageBundle )

   # verify the modification
   print 'verifying the modification'
   bundleModified = server.getImageBundle( name )
   assert str( bundleModified.certified ) == certified.lower()

   # remove all the imageBundles
   bundles = server.getImageBundles( )
   assert name in [ bundle.name for bundle in bundles ]
   print 'deleting image bundle'
   for bundle in bundles:
      try:
         server.deleteImageBundle( bundle )
      except cvpServices.CvpError as err:
         if err.errorCode == errorCodes.CANNOT_DELETE_IMAGE_BUNDLE:
            containers = server.cvpService.imageBundleAppliedContainers(
                  bundle.name )
            for container in containers:
               if container[ 'containerName' ] != currRootContainerInfo.name:
                  raise
               else:
                  appImageBundleRootContainer = True
         else:
            raise
   bundles = server.getImageBundles( )
   if appImageBundleRootContainer == True :
      assert len( bundles ) == 1
   else:
      assert len( bundles ) == 0

def clearCVPInstance( server ):
   ''' Deletes all the configlets imagebundles, devices and
   containers associated with the cvp instance. Note: But doesn't
   delete the root container and image bundle applied to it'''

   objects = [ 'devices', 'containers', 'imagebundles', 'configlets' ]
   cvptool.reset( server, objects )
   containers = server.getContainers()
   assert len( containers ) == 1
   devices = server.getDevices()
   assert len( devices ) == 0
   configlets = server.getConfiglets()
   assert len( configlets ) == 0
   imageBundles = server.getImageBundles()
   assert len( imageBundles ) == 0

def testDevice( args, server ):
   '''This method checks addition of device, correctness of the configlets
   to the device ( compliance check ).'''

   print "Device addition test"
   fObject = open( args.file, 'r' )
   db = json.load( fObject )
   fObject.close()
   inventoryList = []
   cvptool.addInventory( server, db, objects=[ 'configlets', 'imagebundles',
      'devices', 'images','containers', 'roles', 'tasks' ] )
   for device in db[ 'inventory' ]:
      inventoryList.append( cvp.Device( device[ 'ipAddress' ], device[ 'fqdn' ],
         device[ 'macAddress' ], device[ 'containerName' ],
         device[ 'imageBundle' ], device[ 'configlets' ] ) )
      complianceCheck = server.deviceComplianceCheck( device[ 'macAddress' ] )
      if complianceCheck == False :
         raise Exception( "Device compliance check failed. IP : " +
               device[ 'ipAddress' ]  )
   newdb = {}
   newdb[ 'inventory' ] = server.getDevices()
   for newDevice in newdb[ 'inventory' ]:
      for device in inventoryList:
         if newDevice == device:
            inventoryList.remove( device )
            break
   assert len( inventoryList ) == 0

def main( ):
   '''Parses all the parameters provided by the user and calls methods to test
   the functionalities of cvp tools'''

   parser = argparse.ArgumentParser( description='CVP API test' )
   parser.add_argument( '--host', required=True )
   parser.add_argument( '--port', default=80 )
   parser.add_argument( '--ssl', choices=[ True, False ], default=False )
   parser.add_argument( '--user', default='cvpuser', required=True )
   parser.add_argument( '--password', default='cvpuser', required=True )
   parser.add_argument( '--swi', required=True )
   # We'll eventually make --file required, but we need to work out
   # how this works in our automated test environment / with multiple
   # folks running tests in parallel
   parser.add_argument( '--file' )
   args = parser.parse_args()
   print 'testing http://%s:%d as %s' % ( args.host, args.port, args.user )
   server = cvp.Cvp(  args.host, args.ssl, args.port  )
   server.authenticate( args.user, args.password )
   clearCVPInstance( server )
   testConfiglet( server )
   #testImage( args, server )
   #testContainer( server )
   if args.file:
      testDevice( args, server )
   clearCVPInstance( server )

if __name__ == '__main__':
   main()

