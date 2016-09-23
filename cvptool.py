#!/usr/bin/python
# Copyright (c) 2015-2016 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
'''Cvptool provides ability to take snapshots of state of the Cvp instance. The state
information is stored in a tar file. It also provides the ability to restore
the state of the Cvp instance using the backup tar file. Cvp instance can also be
reset to its initial state using this tool.p
'''

import errorCodes
import cvpServices
import Queue
import json
import argparse
import cvp
import tarfile
import os
import re
import getpass
import sys
import tempfile
import shutil

objList = [ 'configlets', 'containers', 'devices', 'images', 'imagebundles',
            'roles'  ]
currentVer = None
suppBackupVer = [ '2015.1.2', '2016.1.0' ]

def backup( server, fname, host, objects, objNames=None, skipVersionCheck=False ):
   ''' Backup the complete CVP instance
   This method calls methods from the cvp library for acquiring the neccessary
   information for storing the snapshot of the Cvp instance. All this information
   is stored in dictionary ( db ) which then is converted to json and dumped
   in a file.
   Also all images, extensions and patches  are downloaded in temporary directory
   and finally a tar ball is created of all these files in current directory
   '''
   if not _performVersionCheck( server, skipVersionCheck ):
      return
   db = {}
   db = getInventory(  server, db, objects, objNames )
   db[ 'CVP-Version' ] = server.getCvpVersionInfo()
   inventoryfileName = 'inventory_' + str( host )
   fObject = open( os.path.join( server.cvpService.tmpDir, inventoryfileName ),
                   'w+' )
   json.dump( db, fObject, default=cvp.encoder, sort_keys=True, indent=3 )
   fObject.close()
   fileList = []
   if 'images' in db:
      fileList = [ image.name for image in db[ 'images' ] ]
   fileList.append( inventoryfileName )
   makeTarFile( server, fname, fileList )
   print 'Done.'

def getInventory( server, db, objects, objNames=None ):
   ''' Downloads complete inventory information from cvp instance'''
   if 'configlets' in objects:
      print 'Retrieving configlets'
      db[ 'configlets' ] = server.getConfiglets( objNames )
   if 'imagebundles' in objects:
      print 'Retrieving image bundles'
      db[ 'imageBundle' ] = server.getImageBundles()
   if 'devices' in objects:
      print 'Retrieving device information'
      db[ 'inventory' ] = [ device for device in server.getDevices() if
                            device.containerName != 'Undefined' ]
   if 'images' in objects:
      print 'Retrieving images'
      db[ 'images' ] = server.getImages( server.cvpService.tmpDir )
   if 'containers' in objects:
      print 'Retrieving container hierarchy'
      db[ 'Tree' ] = server.getContainers()
   if 'roles' in objects:
      print 'Retrieving role information'
      db[ 'Roles' ] = server.getRoles()
   #Check if correct names are provided in objNames list
   if objNames:
      objType = objects[ 0 ]
      objRetList = [ str( obj.name ).lower() for obj in db[ objType ] ]
      objAbsList = [ objName for objName in objNames if objName not in objRetList ]
      if objAbsList:
         print 'Objects not found', ', '.join( objAbsList )
   return db

def makeTarFile( server, outputFileName, fileNameList ):
   '''Create a tar ball of all the files in listed in fileNameList.
   '''
   print 'Creating tar file of backup data'
   tar = tarfile.open( outputFileName, "w:" )
   try:
      for fileName in fileNameList:
         tar.add( os.path.join( server.cvpService.tmpDir, fileName ),
                  arcname=os.path.basename( os.path.join( server.cvpService.tmpDir,
                  fileName ) ) )
   finally:
      tar.close()

def restore( server, fname, objects, objNames=None, skipVersionCheck=False ):
   ''' Restore the inventory from backup information
   This method extract the backup contents from  the tar file and stores them in
   temporary directory. Then information about the Cvp state is loaded into a
   dictionary. It undergoes backward compatibility checks and is then utilised
   in restoring the Cvp state.
   '''
   try:
      tar = tarfile.open( fname,'r:' )
   except tarfile.ReadError:
      #Exception catching for backward compatibility with versions prior to 2016.1
      tar = tarfile.open( fname, 'r:gz' )
   fileName = None
   for member in tar.getmembers():
      name = str( member.name )
      if name.startswith( 'inventory_' ):
         fileName = name
         break
   if not fileName:
      print 'No inventory file found in the backup'
      return
   tar.extractall( server.cvpService.tmpDir )
   db = {}
   fObject = open( os.path.join( server.cvpService.tmpDir, fileName ), 'r' )
   db = json.load( fObject )
   fObject.close()
   db = genCompatibleInventory( db )
   if not _performVersionCheck( server, skipVersionCheck, db ):
      return
   addInventory( server, db, objects, objNames )
   print 'Done.'

def _performVersionCheck( server, skipVersionCheck=False, db='' ):
   '''checks if cvp and tools verion is same and also checks if restore supports
   backup version'''

   if skipVersionCheck:
      return True

   VERSION_FILE_PATH = os.path.join( os.path.dirname( sys.argv[ 0 ] ),
                                     'version.txt' )
   if not skipVersionCheck and not os.path.isfile( VERSION_FILE_PATH ):
      print 'version.txt not present with tools'
      return
   global currentVer
   currentVer = json.load( open( VERSION_FILE_PATH, 'r' ) )[ 'version' ]
   suppBackupVer.append( currentVer )

   if currentVer != server.getCvpVersionInfo():
      print 'incompatible tools version is being used'
      print 'cvp version %s and tools version %s ' % (
            server.getCvpVersionInfo(), currentVer )
      return False

   if db and db[ 'CVP-Version' ] not in suppBackupVer:
      print 'Restore doesnt support %s Backup version' % db[ 'CVP-Version' ]
      print 'Restore supports versions',', '.join( suppBackupVer )
      return False
   return True

def genCompatibleInventory( db ):
   '''Resolves the backward compatibility issues and creates the new inventory
   dict( db ) from the previous inventory dict( db )'''
   if 'CVP-Version' not in db:
      db[ 'CVP-Version' ] = '2015.1.2'
   if 'configlets' in db:
      for configletInfo in db[ 'configlets' ]:
         if 'configletType' not in configletInfo:
            configletInfo[ 'configletType' ] = 'Static'
         # Convert generated configlet to static if the mapping is not present
         if configletInfo[ 'configletType' ] == 'Generated':
            if not configletInfo.get( 'builderName' ):
               configletInfo[ 'configletType' ] = 'Static'
         elif configletInfo[ 'configletType' ] == 'Builder':
            if isinstance( configletInfo[ 'mainScript' ], dict ):
               configletInfo[ 'mainScript' ] = \
                                  configletInfo[ 'mainScript' ][ 'data' ]
         if 'reconciled' not in configletInfo:
            configletInfo[ 'reconciled' ] = False

   if 'imageBundle' in db:
      imageInfoList = {}
      for imageBundleInfo in db[ 'imageBundle' ]:
         imageNameList = []
         if isinstance( imageBundleInfo[ 'certified' ], bool ):
            continue
         elif imageBundleInfo[ 'certified' ] == 'true':
            imageBundleInfo[ 'certified' ] = True
         else:
            imageBundleInfo[ 'certified' ] = False
         if 'imageKeys' in imageBundleInfo:
            for image in db[ 'images' ]:
               imageInfoList[ image[ 'key' ] ] = image[ 'name' ]
            for imageId in imageBundleInfo[ 'imageKeys' ]:
               imageNameList.append( imageInfoList[ imageId ] )
            del imageBundleInfo[ 'imageKeys' ]
            imageBundleInfo[ 'imageNames' ] = imageNameList
   if 'images' in db:
      for imageInfo in db[ 'images' ]:
         if 'rebootRequired' not in imageInfo:
            imageInfo[ 'rebootRequired' ] = False
   if 'inventory' in db:
      for deviceInfo in db[ 'inventory' ]:
         if 'key' in deviceInfo:
            deviceInfo[ 'macAddress' ] = deviceInfo[ 'key' ]
            del deviceInfo[ 'key' ]
   return db

def addInventory( server, db, objects, objNames=None ):
   ''' Add inventory call the methods which restore cvp objects mentioned in the
   objects list like containers, configlets, image bundles, devices etc. into the
   Cvp instance
   '''
   #Check if correct names are provided in objNames list
   if objNames:
      objType = objects[ 0 ]
      if objType not in db:
         raise TypeError(  'cvp object type not present in backup' )
      dbObjNameList = [ str( obj[ 'name' ] ).lower() for obj in db[ objType ] ]
      objNotFound = [ objName for objName in objNames if objName not in
                      dbObjNameList ]
      if objNotFound:
         print 'Objects not found in backup', ', '.join( objNotFound )

   if 'roles' in objects:
      print 'Adding roles'
      addRoles( server, db )
   if 'configlets' in objects:
      print 'Adding configlets'
      addConfiglets( server, db, objNames )
   if 'imagebundles' in objects:
      print 'Adding image bundles'
      addImageBundles( server, db )
   if 'containers' in objects:
      print 'Adding containers'
      addContainers( server, db )
   if 'devices' in objects:
      print 'Adding devices to containers'
      addDevicesParallel( server, db )
   if 'tasks' in objects:
      print 'Executing tasks'
      executeAllTasks( server )
   else:
      print 'Not executing tasks.'

def addConfiglets( server, db, configletNames='' ):
   '''Adds all the configlets from the database ( db ) to the cvp instance
   This method catches allowable exceptions for smooth execution of the Cvp restore.
   But it raises all other exception denoting error situations. CvpError class object
   contains information about the occured exception
   Raises:
      CvpError -- If unknown error occur while configlet addition
   '''
   if 'configlets' in db:
      for configletInfo in db[ 'configlets' ]:
         if configletNames and ( str( configletInfo[ 'name'] ).lower()
                                 not in configletNames ):
            continue
         if configletInfo[ 'configletType' ] == 'Static':
            configlet = cvp.Configlet( configletInfo[ 'name'] ,
                                       configletInfo[ 'config' ],
                                       configletInfo[ 'configletType' ] )
         elif configletInfo[ 'configletType' ] == 'Builder':
            configlet = cvp.ConfigletBuilder( configletInfo[ 'name'],
                     configletInfo[ 'formList' ], configletInfo[ 'mainScript' ] )
         elif configletInfo[ 'configletType' ] == 'Reconciled':
            continue
         elif configletInfo[ 'configletType' ] == 'Generated':
            continue
         else:
            raise cvpServices.CvpError( errorCodes.INVALID_CONFIGLET_TYPE )
         try:
            server.addConfiglet( configlet )
         except cvpServices.CvpError as err:
            if ( err.errorCode  == errorCodes.CONFIGLET_ALREADY_EXIST or
                 err.errorCode  == errorCodes.CONFIG_BUILDER_ALREADY_EXSIST ):
               print 'Configlet already exists:', configlet.name
               currConfig = server.getConfiglet( configlet.name )
               if configlet.jsonable() != currConfig.jsonable():
                  server.updateConfiglet( configlet )
                  print configlet.name, 'configlet updated'
            else:
               raise

def addImageBundles( server, db ):
   '''Adds all the image bundles from the database ( db ) to the cvp instance.
   This method catches allowable exceptions for smooth execution of the Cvp restore.
   But it raises all other exception denoting error situations. CvpError class object
   contains information about the occured exception
   Raises:
      CvpError -- If unknown error occur while image bundle addition
   '''
   imageRebootInfo = {}
   if 'images' in db:
      for imageInfo in db[ 'images' ]:
         imageRebootInfo[ imageInfo[ 'name' ] ] = imageInfo[ 'rebootRequired' ]
   if 'imageBundle' in db:
      for imageBundleInfo in db[ 'imageBundle' ]:
         imageNameList = []
         imageNameList = imageBundleInfo[ 'imageNames' ]
         imageBundle = cvp.ImageBundle( imageBundleInfo[ 'name' ],
                                      imageNameList, imageBundleInfo[ 'certified' ] )
         imageList = []
         for imageName in imageNameList:
            imageList.append( cvp.Image( imageName, imageRebootInfo[ imageName ] ) )
         try:
            server.addImageBundle( imageBundle, imageList )
         except cvpServices.CvpError as err:
            if err.errorCode == errorCodes.IMAGE_BUNDLE_ALREADY_EXIST:
               print 'Image bundle already exists:', imageBundle.name
               currImageBundle = server.getImageBundle( imageBundle.name )
               if ( currImageBundle.imageNames != imageNameList or
                    currImageBundle.certified != imageBundle.certified ):
                  server.updateImageBundle( imageBundle, imageList )
                  print imageBundle.name, 'image bundle updated'
            else:
               print 'Failed to add Image bundle %s: %s' % ( imageBundle.name, err )

def addContainers( server, db ):
   '''Adds all the containers from the database ( db ) to the cvp instance.
   Ccontainers are addeds in hierarchal manner. After adding  containers, configlets
   and image bundles are also applied to these containers using the backup data.
   This method catches allowable exceptions for smooth execution of the Cvp restore.
   But it raises all other exception denoting error situations. CvpError class object
   contains information about the occured exception.
   Raises:
      CvpError -- If unknown error occur while container addition
   '''
   currRootContainerInfo = server.getRootContainerInfo()
   containerList = []
   if 'Tree' in db:
      for containerInfo in db[ 'Tree' ]:
         container = cvp.Container( containerInfo[ 'name' ],
                        containerInfo[ 'parentName' ], containerInfo[ 'configlets' ],
                        containerInfo[ 'imageBundle' ] )
         containerList.append( container )
         if not containerInfo[ 'parentName' ]:
            if currRootContainerInfo.name != containerInfo[ 'name' ] :
               server.renameContainer( currRootContainerInfo,
                                       containerInfo[ 'name' ] )
            rootContainerName = containerInfo[ 'name' ]
      containerCount = len( containerList )
      parentQueue = Queue.Queue()
      parentName = rootContainerName
      while containerCount > 1 :
         for container in containerList:
            if container.parentName == parentName:
               try:
                  server.addContainer( container )
               except cvpServices.CvpError as err:
                  if err.errorCode  == errorCodes.DATA_ALREADY_EXISTS:
                     print 'Container already exists:', container.name
                  else:
                     raise
               parentQueue.put( container.name )
               containerCount = containerCount - 1
         parentName = parentQueue.get()
      print 'Mapping configlets and image bundles to containers'
      for container in containerList:
         if container.imageBundle:
            imageBundle = server.getImageBundle( container.imageBundle )
            server.mapImageBundleToContainer( container, imageBundle )
         configletList = []
         for configletName in container.configlets:
            configlet = server.getConfiglet( configletName )
            configletList.append( configlet )
         server.mapConfigletToContainer( container, configletList )

def addDevicesParallel( server, db ):
   '''Adds the devices to the inventory in pipeline manner. First attempt is made
   to add all the devices. After this attempt 3 lists mentioned below are generated.
   connectedDeviceList -- list of devices successfully connected
   connFailureDeviceList -- list of devices with connection attempt failure
   unauthorisedDeviceList -- List of devices, user unauthorised to add.
   After addition of devices configlets and image bundles are mapped to the devices
   listed in the connectedDeviceList..
   Raises:
      CvpError -- If unknown error occur while device addtion
   '''
   if 'inventory' not in db:
      return
   genConfigletDict = {}
   reconcileConfigletDict = {}
   if 'configlets' in db:
      for configletInfo in db[ 'configlets' ]:
         if configletInfo[ 'configletType' ] == 'Generated':
            genConfigletDict[ configletInfo[ 'name'] ] = cvp.GeneratedConfiglet(
                     configletInfo[ 'name'], configletInfo[ 'config' ],
                     configletInfo[ 'builderName' ],
                     configletInfo[ 'containerName' ], configletInfo[ 'deviceMac' ] )
         if ( configletInfo[ 'configletType' ] == 'Reconciled' and
               configletInfo[ 'reconciled' ] == True ):
            reconcileConfigletDict[ configletInfo[ 'name'] ] = (
                     cvp.ReconciledConfiglet( configletInfo[ 'name'],
                     configletInfo[ 'config' ], configletInfo[ 'deviceMac' ] ) )

   deviceList = []
   unauthorizedDeviceList = []
   connFailureDeviceList = []
   connectedDeviceList = []
   for deviceInfo in db[ 'inventory' ]:
      device = cvp.Device( deviceInfo[ 'ipAddress' ], deviceInfo[ 'fqdn' ],
                           deviceInfo[ 'macAddress' ], deviceInfo[ 'containerName' ],
                           deviceInfo[ 'imageBundle' ], deviceInfo[ 'configlets' ] )
      deviceList.append( device )
   connectedDeviceList, unauthorizedDeviceList, connFailureDeviceList = (
                                                    server.addDevices( deviceList ) )
   if connectedDeviceList:
      print 'CVP successfully registered the following devices:'
      for device in connectedDeviceList:
         print '%s (%s)' % ( device.fqdn, device.ipAddress )
   if connFailureDeviceList:
      print 'CVP could not connect to the following devices:'
      for device in connFailureDeviceList:
         print '%s (%s)' % ( device.fqdn, device.ipAddress )
   if unauthorizedDeviceList:
      print 'CVP could not authenticate with the following devices:'
      for device in unauthorizedDeviceList:
         print '%s (%s)' % ( device.fqdn, device.ipAddress )
   for device in connectedDeviceList:
      for configletName in device.configlets:
         try:
            # this can fail, e.g. if the MAC has changed since the backup
            # TODO: other operations may also need similar handling
            if configletName in genConfigletDict:
               server.addConfiglet( genConfigletDict[ configletName ] )
            elif configletName in reconcileConfigletDict:
               server.addConfiglet( reconcileConfigletDict[ configletName ] )
            else:
               configlet = server.getConfiglet( configletName )
               server.mapConfigletToDevice( device, [ configlet ] )
         except cvpServices.CvpError as e:
            # Should we skip all configlets for this device?
            print 'Failed to add configlet %s to device %s (%s): %s' \
                  % ( configletName, device.fqdn, device.ipAddress, e )
      if device.imageBundle:
         try:
            imageBundle = server.getImageBundle( device.imageBundle )
            server.mapImageBundleToDevice( device, imageBundle )
         except cvpServices.CvpError as e:
            print 'Failed to add image bundle to device %s (%s): %s' \
                  % ( device.fqdn, device.ipAddress, e )

def executeTasks( server ):
   '''Execute pending tasks.
   This method provides the ability to execute task individually one at a time
   or executes all the pending tasks
   '''
   pendingTaskCount = 0
   taskIdList = []
   taskList = server.getPendingTasksInfo()
   for task in taskList:
      task.taskId = re.findall( r'\d+', str( task.taskId ) )[ 0 ]
      print ' Task Id:', str( task.taskId ), ', description :', str(
                                                                   task.description )
      pendingTaskCount += 1
      taskIdList.append( task.taskId )
   if pendingTaskCount > 0 :
      userInput = ''
      while userInput != 'a' and userInput !='i' :
         userInput = ''
         userInput = raw_input( 'enter i to execute individual task or a for all'
                                ' task: ')
      if userInput == 'a':
         for task in taskList:
            server.executeTask( task )
      elif userInput == 'i':
         while True :
            if pendingTaskCount < 1 :
               print 'All task are executed'
               break
            userInput = raw_input(' Enter Id of task you want to execute or e to'
                                  ' exit: ')
            if userInput == 'e':
               print 'Exiting task execution'
               break
            elif userInput in taskIdList:
               task = server.Task( userInput )
               server.executeTask( task )
               taskIdList.remove( userInput )
               pendingTaskCount -= 1
            else:
               print 'invalid task Id'
   else:
      print 'No task is in pending state'

def executeAllTasks( server ):
   '''Executes all the pending tasks
   Arguments:
   '''
   taskList = server.getPendingTasksList()
   print "Found %d task(s)" % len( taskList )
   # TODO: executeTask.do API now takes a list of IDs, so we should be able to
   # do this in one call
   for task in taskList:
      server.executeTask( task )
   print "Monitoring task status"
   server.monitorTaskStatus( taskList )
   print "Task execution completed"

def addRoles( server, db ):
   '''This method adds all the roles present in backup of the cvp instance.
   This method catches allowable exceptions for smooth execution of the Cvp restore.
   But it raises all other exception denoting error situations. CvpError class object
   contains information about the occured exception
   Raises:
      CvpError -- If error occur while role addtion
   '''
   if 'Roles' in db:
      for roleInfo in db[ 'Roles' ]:
         role = cvp.Role( roleInfo[ 'name' ], roleInfo[ 'description' ],
            roleInfo[ 'moduleList' ] )
         if role.name == "network-admin" or role.name == "network-operator":
            continue
         try:
            server.addRole( role )
         except cvpServices.CvpError as err:
            if err.errorCode == errorCodes.ROLE_ALREADY_EXISTS:
               print "Role already exists:", role.name
               currRole = server.getRole( role.name )
               if role.moduleList != currRole.moduleList:
                  print role.name + " Role is updated "
                  server.updateRole( role )
            else:
               raise

def reset( server, objects, skipVersionCheck=False ):
   '''Removes the objects specified in the "objects" list from the Cvp Instance.
   Note:
      It is essential to remove objects in logical order else will raise exceptions
   Arguments:
      server -- object of class Cvp
      objects -- Cvp objects list
   Raises:
      CvpError -- when unsuccessful deletion of elements occurs
   '''
   if not _performVersionCheck( server, skipVersionCheck ):
      return
   print 'Clearing CVP instance'
   if 'devices' in objects:
      removeDevices( server )
   if 'containers' in objects:
      removeContainers( server )
   if 'imagebundles' in objects:
      removeImageBundles( server )
   if 'configlets' in objects:
      removeConfiglets( server )
   if 'roles' in objects:
      removeRoles( server )
   print 'Done.'

def removeDevices( server ):
   ''' Removes the devices from the cvp instance
   Raises:
      CvpError -- when unsuccessful deletion of elements occurs
   '''
   deviceList = server.getDevices()
   print 'Deleting all devices'
   if deviceList:
      for device in deviceList:
         server.deleteDevice( device )

def removeContainers( server ):
   ''' Removes the Containers from the cvp instance
   Raises:
      CvpError -- when unsuccessful deletion of elements occurs
   '''
   print 'Deleting all containers'
   containerList = server.getContainers()
   rootContainerInfo = server.getRootContainerInfo()
   if containerList:
      for container in containerList:
         if container.name == rootContainerInfo.name:
            configletList = []
            for configletName in container.configlets:
               configletList.append( server.getConfiglet( configletName) )
            server.removeConfigletAppliedToContainer( container, configletList )
            if container.imageBundle:
               imageBundle = server.getImageBundle( container.imageBundle )
               server.removeImageBundleAppliedToContainer( container, imageBundle )
            continue
         server.deleteContainer( container )
   if rootContainerInfo.name != 'Tenant':
      server.renameContainer( rootContainerInfo, 'Tenant' )

def removeConfiglets( server ):
   ''' Removes the Configlets from the cvp instance
   Raises:
      CvpError -- when unsuccessful deletion of elements occurs
   '''
   print 'Deleting all configlets'
   configlets = server.getConfiglets()
   for configlet in configlets:
      server.deleteConfiglet( configlet )

def removeImageBundles( server ):
   ''' Removes the image bundles from the cvp instance
   Raises:
      CvpError -- when unsuccessful deletion of elements occurs
   '''
   print 'Deleting all image bundles'
   imageBundles = server.getImageBundles()
   for imageBundle in imageBundles:
      server.deleteImageBundle( imageBundle )

def removeRoles( server ):
   ''' Removes all roles from the cvp instance
   Raises:
      CvpError -- when unsuccessful deletion of elements occurs
   '''
   print 'Deleting all roles'
   roles = server.getRoles()
   for role in roles:
      if role.name != 'network-admin' and role.name != 'network-operator':
         server.deleteRole( role.name )

def parseArgs():
   '''Parses all the parameters provided by the user and calls corresponding
   methods to either backup the Cvp, restore the Cvp or add image bundle to
   Cvp instance '''
   parser = argparse.ArgumentParser( description='CVP management tool' )
   parser.add_argument( '--host', required=True, help='Hostname or IP address of'
                        ' cvp' )
   parser.add_argument( '--user', required=True, help='Cvp user username' )
   parser.add_argument( '--tarFile', help='*.tar file to save/retrieve Cvp'
                        ' state information' )
   parser.add_argument( '--port', default=80, help='Cvp web-server port number' )
   parser.add_argument( '--ssl', choices=[ 'true', 'false' ], default='false',
                        type=str.lower, help='Connect via HTTPS' )
   parser.add_argument( '--password', default=None, help='password corresponding to'
                        ' the username' )
   parser.add_argument( '--action', choices=[ 'backup', 'restore', 'reset' ],
                        default='backup', type=str.lower,
                        help='Type of action to be performed on Cvp instance' )
   parser.add_argument( '--tasks', choices=[ 'true', 'false' ], default='false',
                        type=str.lower, help='Execute tasks' )
   parser.add_argument( '--objects', nargs='*', choices=objList, default=objList,
                        type=str.lower, help='List of objects on which action is '
                        'to be performed' )
   parser.add_argument( '--objNames', nargs='*', help='Name of the cvp object',
                        type=str.lower, default=None )
   parser.add_argument( '--skipVersionCheck', default=False, action='store_true',
                        help='skip backup version compatibility check' )
   args = parser.parse_args()
   args.port = int( args.port )
   return checkArgs( args )

def askPass( user, host ):
   prompt = "Password for user {} on host {}: ".format( user, host )
   password = getpass.getpass( prompt )
   return password

def checkArgs( args ):
   '''check the correctness of the input arguments'''
   if args.password is None:
      args.password = askPass( args.user, args.host )
   if ( ( args.action == 'backup' or args.action == 'restore' ) and
        args.tarFile is None ):
      print "Error: argument --tarFile is required for " + args.action
      sys.exit( 1 )
   if args.objNames and ( ( len( args.objects ) > 1 ) or ( 'configlets' not in
                                                           args.objects ) ):
      print "Error: Only configlets can be specified along with --objNames"
      sys.exit( 1 )
   if args.action == 'restore' and args.tasks == 'true':
      args.objects.append( 'tasks' )
   return args

def main( ):
   options = parseArgs()
   tmpDir = tempfile.mkdtemp()
   server = cvp.Cvp( options.host, options.ssl == 'true', options.port, tmpDir )
   server.authenticate( options.user, options.password )
   try:
      if options.action == 'restore':
         print 'Restoring objects:', ', '.join( options.objects )
         restore( server, options.tarFile, options.objects, options.objNames,
                  options.skipVersionCheck )
      elif options.action == 'backup':
         print 'Backing up objects:', ', '.join( options.objects )
         backup( server, options.tarFile, options.host, options.objects,
                 options.objNames, options.skipVersionCheck )
      elif options.action == 'reset':
         print 'Removing objects:', ', '.join( options.objects )
         reset( server, options.objects, options.skipVersionCheck )
   finally:
      shutil.rmtree( tmpDir )

if __name__ == '__main__':
   main()
