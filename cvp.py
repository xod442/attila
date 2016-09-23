# Copyright (c) 2015 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
'''
@Copyright: 2015-2016 Arista Networks, Inc.
Arista Networks, Inc. Confidential and Proprietary.

Cvp.py is a library which can be used to perform various
actions over the cvp instance. There are numerous methods each
corresponding to each action. Methods are listed below in the Cvp class.
'''
import os
import Queue
import cvpServices
import errorCodes
import time

def encoder( obj ):
   '''Returns JSON-serializable version of the obj'''
   if hasattr( obj, 'jsonable' ):
      return obj.jsonable()
   else:
      raise TypeError

class Jsonable( object ):
   '''This class represents a JSON-serializable object. The default serialization
   is to just return the class' __dict__.'''

   def __init__( self ):
      pass

   def jsonable( self ):
      ''' Returns modules namespace as dictionary'''
      return self.__dict__

class Image( Jsonable ):
   '''Image class, stores all required information about
   an image.

   state variables:
      name -- name fo the image
      rebootRequired -- Reboot required after applying this image( True/False )
   '''
   def __init__( self, name, rebootRequired=False ):
      super( Image, self ).__init__( )
      self.name = name
      self.rebootRequired = rebootRequired

class Container( Jsonable ):
   '''Container class, stores all required information about
   a container

   State variables:
      name -- name of the container
      configlets -- list of configlet name assigned to container
      imageBundle -- name of the image bundle assigned to container
      parentName -- Name of the parent container
   '''

   def __init__( self, name, parentName, configlets='', imageBundle=''):
      super( Container, self ).__init__( )
      self.name = name
      self.configlets = configlets
      self.imageBundle = imageBundle
      self.parentName = parentName

class Task( Jsonable ):
   ''' Task class, Stores information about a Task

   State variables:
      taskId -- work order Id assigned to the task
      description -- information explaining what task is about
   '''
   COMPLETED = 'Completed'
   PENDING = 'Pending'
   FAILED = 'Failed'
   CANCELED = 'Cancelled'

   def __init__( self, taskId, status, description='' ):
      super( Task, self ).__init__( )
      self.taskId = int( taskId )
      self.status = status
      self.description = description

class Device( Jsonable ):
   ''' Device class helps store all the information about a particular device

   state variables:
      ipAddress -- ip address of the device
      fqdn -- fully qualified domain name for the device
      macAddress -- mac address of the device
      containerName -- name of the parent container
      containerId -- uniqu Id assigned to the parent container
      imageBundle -- name of the imageBundle assigned to device
      configlets -- list of names of configlets assigned to the device
   '''
   def __init__( self, ipAddress, fqdn, macAddress, containerName, imageBundle='',
      configlets='' ):
      super( Device, self ).__init__( )
      self.ipAddress = ipAddress
      self.fqdn = fqdn
      self.macAddress = macAddress
      self.containerName = containerName
      self.imageBundle = imageBundle
      self.configlets = configlets

class Configlet( Jsonable ):
   '''Configlet class stores all the information necessary about the
   configlet

   state variables:
      name -- name of the configlet
      config -- configuration information inside configlet
      type -- to store the type of the configlet
   '''
   def __init__( self, name, config, configletType='Static', reconciled=False ):
      super( Configlet, self ).__init__( )
      self.name = name
      self.config = config
      self.configletType = configletType
      self.reconciled = reconciled

class ConfigletBuilder( Configlet ):
   ''' ConfigletBuilder class stores all the information about the Configlet
   builder

   state variables:
      name -- name of the Configlet Builder
      formList -- list of forms part of configlet builder
      mainScript -- the configlet builder mainscript
   '''
   def __init__( self, name, formList, mainScript ):
      super( ConfigletBuilder, self ).__init__( name, '', 'Builder' )
      self.formList = formList
      self.mainScript = mainScript

class GeneratedConfiglet( Configlet ):
   '''GeneratedConfiglet class stores information about the generated configlets.
   Mapping between the generated configlet, configlet builder, container and device

   State variables:
      builderName -- name of the configlet builder that generated this configlet
      ContainerName -- Name of the container to which the builder was assigned
      deviceMac -- Mac address of the device to which this configlet is assigned
   '''

   def __init__( self, name, config, builderName, containerName, deviceMac ):
      super( GeneratedConfiglet, self ).__init__( name, config, 'Generated' )
      self.builderName = builderName
      self.containerName = containerName
      self.deviceMac = deviceMac

class ReconciledConfiglet( Configlet ):
   '''GeneratedConfiglet class stores information about the reconciled configlets.
   State variables:
      deviceMac -- Mac address of the devices
   '''
   def __init__( self, name, config, deviceMac ):
      super( ReconciledConfiglet, self ).__init__( name, config, 'Reconciled', True )
      self.deviceMac = deviceMac

class User( Jsonable ):
   ''' User class stores all the information about an users

   State variables:
      userId -- unique user id of the user
      firstName -- first name of user
      LastName -- last name of the user
      emailID -- email ID of the user
      contactNumber -- contact number for the user
      password -- password set by the user

   '''
   def __init__( self, userId, firstName, LastName, emailId, contactNumber,
      password ):
      super( User, self ).__init__( )
      self.userId = userId
      self.firstName = firstName
      self.LastName = LastName
      self.emailId = emailId
      self.contactNumber = contactNumber
      self.password = password

class Role( Jsonable ):
   ''' Stores all essential information about a specific role

   State variables:
      name -- name of the role
      description -- Description about the Role
      moduleList -- list of permissions
   '''

   def __init__( self, name, description, moduleList ):
      super( Role, self ).__init__( )
      self.name = name
      self.description = description
      self.moduleList = moduleList

class ImageBundle( Jsonable ):
   '''ImageBundle class objects stores all necessary information about the
   bundle

   state variables:
      name -- name of the image bundle
      imageNames -- keys corresponding to images present in this image bundle
      certified -- indicates whether image bundle is certified or not
   '''
   def __init__( self, name, imageNames, certified=False ):
      super( ImageBundle, self ).__init__( )
      self.name = name
      self.imageNames = imageNames
      self.certified = certified

class Cvp( Jsonable ):
   '''Class Cvp contains all the methods essentials for downloading the
   Cvp state, restoring the Cvp State, deletion of Cvp State, modification of
   cvp state

   Public methods:
      authenticate( username, password )
      getDevices()
      getDevice( deviceMacAddress )
      addDevice( device )
      addDevices( deviceList )
      deviceComplianceCheck( deviceIpAddress )
      deleteDevice( device )
      getConfiglets()
      getConfiglet( configletName )
      addConfiglet( configlet )
      updateConfiglet( configlet )
      deleteConfiglet( configlet )
      mapConfigletToDevice( device , configletNameList )
      addContainer( container )
      getContainers()
      getContainer( containerName )
      getRootContainerInfo()
      renameContainer( container, newContainerName )
      addContainers( containerList )
      deleteContainer( container )
      getImages( storageDirPath )
      getImage(  imageName , storageDirPath )
      addImage( imageName, strDirPath )
      getImageBundles()
      getImageBundle( imageBundleName )
      deleteImageBundle( imageBundle )
      addImageBundle( imageBundle, imageList )
      updateImageBundle( imageBundle, imageList )
      mapImageBundleToDevice( device, imageBundle )
      mapImageBundleToContainer( container, imageBundle )
      mapConfigletToContainer( container , configletList )
      removeConfigletFromContainer( container, configletList )
      executeAllPendingTask()
      executeTask( task )
      monitorTaskStatus( taskList, status, timeout )
      getPendingTasksList()
      deployDevice( device, targetContainer, configletList, image )
      getTasks()
      cancelTask( task )
      addNoteToTask( task, note )
      getCvpVersionInfo()
      getRoles()
      getRole( roleName )
      addRole( role )
      updateRole( role )

   State variables:
      cvpService -- CvpService class instance
      '''

   def __init__( self, host, ssl=False, port=80, tmpDir='' ):
      super( Cvp, self ).__init__( )
      self.cvpService = cvpServices.CvpService( host, ssl, port, tmpDir )

   def authenticate( self, username, password ):
      '''Authenticate the user login credentials
      Arguments:
         username -- username for login ( type : string )
         password -- login pasword (type : String )
      Raises:
         CvpError -- If invalid login creedentials
      '''
      self.cvpService.authenticate( username, password )

   def _getContainerConfigletMap( self, configletNameList ):
      '''Finds which configlets are  mapped to which containers'''
      configletMap = {}
      for configletName in configletNameList:
         containersInfo = self.cvpService.configletAppliedContainers( configletName )
         for containerInfo in containersInfo:
            configletNameList = []
            key = containerInfo[ 'containerName' ]
            if key in configletMap:
               configletNameList = configletMap[ containerInfo[ 'containerName' ] ]
               configletNameList.append( configletName )
               configletMap[ containerInfo[ 'containerName' ] ] = configletNameList
            else :
               configletNameList.append( configletName )
               configletMap[ containerInfo[ 'containerName' ] ] = configletNameList
      return configletMap

   def _getContainerImageBundleMap( self, imageBundleNameList ):
      '''Finds which image bundle is mapped to which containers.'''
      imageBundleMap = {}
      for imageBundleName in imageBundleNameList:
         containersInfo = self.cvpService.imageBundleAppliedContainers(
                                                                    imageBundleName )
         for containerInfo in containersInfo:
            imageBundleMap[ containerInfo[ 'containerName' ] ] = imageBundleName
      return imageBundleMap

   def _getDeviceImageBundleMap( self, imageBundleNameList ):
      '''Finds which image bundle is mapped to which devices.'''
      imageBundleMap = {}
      for imageBundleName in imageBundleNameList:
         devicesInfo = self.cvpService.imageBundleAppliedDevices( imageBundleName )
         for deviceInfo in devicesInfo:
            imageBundleMap[ deviceInfo [ 'ipAddress' ] ] = imageBundleName
      return imageBundleMap

   def _getImageBundleNameList( self ):
      ''' finds the list of image bundles present in the cvp instance'''
      imageBundleNameList = []
      imageBundlesInfo = self.cvpService.getImageBundles()
      for imageBundleInfo in imageBundlesInfo:
         imageBundleNameList.append( imageBundleInfo[ 'name' ] )
      return imageBundleNameList

   def _getConfigletNameList( self ):
      '''finds the list of configlets present in the cvp instance'''
      configletNameList = []
      configletsInfo = self.cvpService.getConfigletsInfo()
      for configletInfo in configletsInfo:
         configletNameList.append( configletInfo[ 'name' ] )
      return configletNameList

   def getDevices( self ):
      '''Collect information of all the devices. Information of device consist
      of the device specifications like ip address, mac address( key ), configlets
      and image bundle applied to device.
      Returns:
         deviceList -- List of device ( type : List of Device ( class ) )
      '''
      imageBundleNameList = self._getImageBundleNameList()
      imageBundleMap = self._getDeviceImageBundleMap( imageBundleNameList )
      devicesInfo, containersInfo = self.cvpService.getInventory()
      deviceParentContainer = {}
      deviceList = []
      for deviceMacAddress, containerName in containersInfo.iteritems():
         deviceParentContainer[ deviceMacAddress ] = containerName
      for deviceInfo in devicesInfo:
         if deviceInfo[ 'key' ] not in deviceParentContainer:
            raise cvpServices.CvpError( errorCodes.INVALID_CONTAINER_NAME )
         parentContainerName = deviceParentContainer[ deviceInfo[ 'key' ] ]
         deviceMac = deviceInfo[ 'systemMacAddress' ]
         configletsInfo = self.cvpService.getDeviceConfiglets( deviceMac )
         configletNames = [ configlet[ 'name' ] for configlet in configletsInfo ]
         appliedImageBundle = []
         if deviceInfo[ 'ipAddress' ] in imageBundleMap:
            appliedImageBundle = imageBundleMap[ deviceInfo[ 'ipAddress' ] ]
         deviceList.append( Device( deviceInfo[ 'ipAddress' ], deviceInfo[ 'fqdn' ],
                            deviceMac , parentContainerName, appliedImageBundle,
                            configletNames ) )
      return deviceList

   def _getContainerInfo( self, containerName ):
      '''Returns container information for given container name'''
      containersInfo = self.cvpService.searchContainer( containerName )
      if not containersInfo:
         raise cvpServices.CvpError( errorCodes.INVALID_CONTAINER_NAME )
      for containerInfo in containersInfo:
         if containerInfo[ 'name' ] == containerName:
            return containerInfo

   def getDevice( self , deviceMacAddress ):
      '''Retrieve information about device like ip address, mac address,
      configlets and image bundle applied to device.
      Returns:
         device -- Information about the device ( type : Device ( class ) )
      '''
      imageBundleNameList = self._getImageBundleNameList()
      imageBundleMap = self._getDeviceImageBundleMap( imageBundleNameList )
      configletsInfo = self.cvpService.getDeviceConfiglets( deviceMacAddress )
      configletNames = [ configlet[ 'name' ] for configlet in configletsInfo ]
      devicesInfo, containersInfo = self.cvpService.getInventory()
      for deviceInfo in devicesInfo:
         if deviceInfo[ 'systemMacAddress' ] != deviceMacAddress:
            continue
         for deviceMacAddress, containerName in containersInfo.iteritems():
            if deviceMacAddress == deviceInfo[ 'systemMacAddress' ]:
               parentContainerName = containerName
               break
         if not parentContainerName:
            raise cvpServices.CvpError( errorCodes.INVALID_CONTAINER_NAME )
         appliedImageBundle = []
         if deviceInfo[ 'ipAddress' ] in imageBundleMap:
            appliedImageBundle = imageBundleMap[ deviceInfo[ 'ipAddress' ] ]
         device = Device( deviceInfo[ 'ipAddress' ], deviceInfo[ 'fqdn' ],
                          deviceMacAddress, parentContainerName,
                          appliedImageBundle, configletNames )
         break
      return device

   def getConfiglets( self, configletNames='' ):
      '''Retrieve the full set of Configlets
      Returns:
         configletList -- information of all configlets
            ( type : List of Configlet ( class ) )
      '''
      configletList = []
      configlets = []
      configletsInfo = self.cvpService.getConfigletsInfo()
      for configletInfo in configletsInfo:
         configletList.append( self.getConfiglet( configletInfo[ 'name' ] ) )
      if configletNames:
         configlets = [ configlet for configlet in configletList if
                        str( configlet.name ).lower() in configletNames ]
      else:
         configlets = configletList
      return configlets

   def getContainers( self ):
      '''Retrieve the hierarchy of the containers and store information on all
      of these containers. Information of container consist of specifications
      like container name, configlets and image bundle applied to container.
      Returns:
         containers -- list of container informations
            ( type : List of Container ( class ) )
      '''
      imageBundleNameList = self._getImageBundleNameList()
      imageBundleMap = self._getContainerImageBundleMap( imageBundleNameList )
      containersInfo, _ = self.cvpService.retrieveInventory()
      rawContainerInfoList = []
      rawContainerInfoList.append( containersInfo )
      containers = []
      containers = self._recursiveParse( containers, rawContainerInfoList,
                                         imageBundleMap, '' )
      return containers

   def _recursiveParse( self, containers, childContainerInfoList,
                        imageBundleMap, parentContainerName):
      ''' internal function for recursive depth first search to obtain container
      information from the container hierarchy. It handles different cases
      like the configlet applied or not, image bundle applied or not to containers'''
      for containerInfo in childContainerInfoList:
         if containerInfo[ 'childContainerList' ]:
            containers = self._recursiveParse( containers,
                                 containerInfo[ 'childContainerList' ],
                                 imageBundleMap, containerInfo[ 'name' ] )
         containerName = containerInfo[ 'name' ]
         containerKey = containerInfo[ 'key' ]
         configletsInfo = self.cvpService.getContainerConfiglets( containerKey )
         configletNames = [ configlet[ 'name' ] for configlet in configletsInfo ]
         appliedImageBundle = None
         if containerName in imageBundleMap:
            appliedImageBundle = imageBundleMap[ containerName ]
         containers.append( Container( containerName, parentContainerName,
                                       configletNames, appliedImageBundle ) )
      return containers

   def getContainer( self, containerName ):
      '''Retrieve container Information like container name, configlets and
      image bundle applied to the container
      Arguments
         ContainerName -- name of the container ( type : String )
      Raises:
         CvpError -- If container name is invalid
      Returns:
         containerInfo -- Information about the container
         ( type : Container( class ) )
      '''
      containerInfo = self._getContainerInfo( containerName )
      imageBundleNameList = self._getImageBundleNameList()
      imageBundleMap = self._getContainerImageBundleMap( imageBundleNameList )
      parentContainerName = ''
      containerName = containerInfo[ 'name' ]
      containerKey = containerInfo[ 'key' ]
      if containerInfo[ 'key' ] != 'root':
         self._getparentInfo( containerInfo[ 'parentId' ] )
      configletsInfo = self.cvpService.getContainerConfiglets( containerKey )
      configletNames = [ configlet[ 'name' ] for configlet in configletsInfo ]
      appliedImageBundle = None
      if containerName in imageBundleMap:
         appliedImageBundle = imageBundleMap[ containerName ]
      return Container( containerName, parentContainerName, configletNames,
                        appliedImageBundle )

   def getImages( self , storageDirPath='' ):
      '''Images are downloaded and saved in directory path given by "storageDirPath"
      Argument:
         storageDirPath -- path to directory for storing image files ( optional )
            ( type : String )
      Returns:
         imageNameList -- List of inforamtion of images downloaded
            ( type : List of Image ( class ) )'''
      imageList = []
      imagesInfo = self.cvpService.getImagesInfo()
      for imageInfo in imagesInfo:
         rebootRequired = ( imageInfo[ 'isRebootRequired' ] == 'true' )
         imageList.append( Image( imageInfo[ 'name' ], rebootRequired ) )
         self.cvpService.downloadImage( imageInfo[ 'name' ], imageInfo[ 'imageId' ],
                                        storageDirPath )
      return imageList

   def getImage( self, imageName , storageDirPath='' ):
      ''' Image is downloaded and saved in directory path given by "storageDirPath"
      Argument :
         imageName -- name of image to be downloaded ( type : String )
         storageDirPath -- path to directory for storing image files ( optional )
         ( type : String )
      Raises:
         CvpError -- If image name is incorrect
      '''
      imagesInfo = self.cvpService.getImagesInfo()
      imagePresentFlag = False
      for imageInfo in imagesInfo:
         if imageInfo[ 'name' ] == imageName:
            rebootRequired = ( imageInfo[ 'isRebootRequired' ] == 'true' )
            image = Image( imageInfo[ 'name' ], rebootRequired )
            imagePresentFlag = True
            self.cvpService.downloadImage( image[ 'name' ], image[ 'imageId' ],
                                           storageDirPath )
            break
      if imagePresentFlag == False:
         raise cvpServices.CvpError( errorCodes.INVALID_IMAGE_NAME )
      return image

   def getConfiglet( self, configletName ):
      '''Retrieve a specific configlet.
      Argument:
         configletName -- name of the configlet ( type : String )
      Raises:
         CvpError : If configlet name is invalid
      Returns:
         Configlet -- information of the configlet ( type : Configlet ( class ) )
      '''
      configletInfo = self.cvpService.getConfigletByName( configletName )
      genConfigMapInfo = self.cvpService.getConfigletMapper()
      if ( configletInfo[ 'type' ] == 'Static' and
           configletInfo[ 'reconciled' ] == False ):
         return Configlet( configletInfo[ 'name' ], configletInfo[ 'config' ],
                           configletInfo[ 'type' ] )
      elif ( configletInfo[ 'type' ] == 'Static' and
             configletInfo[ 'reconciled' ] == True ):
         for configlet in genConfigMapInfo[ 'configletMappers' ]:
            if configlet[ 'configletId' ] == configletInfo[ 'key' ]:
               return ReconciledConfiglet( configletInfo[ 'name' ],
                                 configletInfo[ 'config' ], configlet[ 'objectId' ] )
         #The reconciled configlets don't get deleted after deleting the device
         # BUG158316
         return ReconciledConfiglet( configletInfo[ 'name' ],
                                     configletInfo[ 'config' ], '' )
      elif configletInfo[ 'type' ] == 'Generated':
         for genConfiglet in genConfigMapInfo[ 'generatedConfigletMappers' ]:
            if configletInfo[ 'key' ] == genConfiglet[ 'configletId' ]:
               builderInfo = self.cvpService.getConfigletBuilder(
                                    genConfiglet[ 'configletBuilderId' ] )
               containerInfo = self.cvpService.getContainerInfo(
                                    genConfiglet[ 'containerId' ] )
               containerName = containerInfo[ 'name' ]
               return GeneratedConfiglet( configletInfo[ 'name' ],
                                    configletInfo[ 'config' ], builderInfo[ 'name' ],
                                    containerName, genConfiglet[ 'netElementId' ] )
         #Generated Configlets don't get deleted when device is deleted
         # BUG158317
         return GeneratedConfiglet( configletInfo[ 'name' ],
                                    configletInfo[ 'config' ], '', '', '' )
      else:
         configletBuilderInfo = self.cvpService.getConfigletBuilder(
                                  configletInfo[ 'key' ] )
         self._removeFormKeys( configletBuilderInfo )
         return ConfigletBuilder( configletInfo[ 'name' ],
                                  configletBuilderInfo[ 'formList' ],
                                  configletBuilderInfo[ 'main_script' ][ 'data' ] )

   def _removeFormKeys( self, configletBuilderInfo ):
      '''remove keys from the forms'''
      for form in configletBuilderInfo[ 'formList' ]:
         if 'configletBuilderId' in form:
            del form[ 'configletBuilderId' ]
         if 'key' in form:
            del form[ 'key' ]

   def _getparentInfo( self , parentId ):
      ''' retrieve information of parent for newly added container using the
      recursive Depth First Search returns name of the parent container'''
      if parentId == None:
         return ''
      containers, _ = self.cvpService.retrieveInventory()
      rawContainersInfo = []
      rawContainersInfo.append( containers )
      parentName = self._recursiveParentInfo( rawContainersInfo, parentId )
      return parentName

   def _recursiveParentInfo( self, childContainerList, parentId ):
      ''' internal function for getting parent container info in the hierarchy'''
      for container in childContainerList:
         if container[ 'key' ] == parentId:
            return container[ 'name' ]
         elif len( container[ 'childContainerList' ] ) > 0 :
            parentName = self._recursiveParentInfo(
                                        container[ 'childContainerList' ], parentId )
            return parentName

   def addContainers( self, containerList ):
      '''Add containers to the inventory by maintaining the hierarchy of the
      containers
      Argument:
         containerList -- List of container inforamtion
            ( type : List of Container ( class ) )
      Raise :
         CvpError -- If container already exists or invalid parent container name
      Returns None
      '''
      assert all ( isinstance( container, Container ) for container in
                                                                      containerList )
      currRootContainerInfo = self.getRootContainerInfo()
      containerCount = len( containerList )
      parentQueue = Queue.Queue()
      parentName = currRootContainerInfo.name
      while containerCount > 1 :
         for container in containerList:
            if container.parentName == parentName:
               self.addContainer( container )
               parentQueue.put( container.name )
               containerCount = containerCount - 1
         parentName = parentQueue.get()

   def addConfiglet( self, configlet ):
      '''Add a configlet to cvp inventory
      Argument:
         configlet -- information of the new configlet
            ( type : Configlet ( class ) )
      Raises:
         CvpError -- If configlet name is invalid
      '''
      assert isinstance( configlet, Configlet )
      if isinstance( configlet, ConfigletBuilder ):
         self.cvpService.addConfigletBuilder( configlet.name,
                                           configlet.formList, configlet.mainScript )
      # Configlet object has type not but not used as payoda api doesn't suport it.
      elif isinstance( configlet, GeneratedConfiglet ):
         self._addGeneratedConfiglet( configlet )
      elif isinstance( configlet, ReconciledConfiglet ):
         self._addReconciledConfiglet( configlet )
      else:
         self.cvpService.addConfiglet( configlet.name, configlet.config )

   def _addGeneratedConfiglet( self, configlet ):
      '''Adds the mapping be the generated configlets, devices and containers'''
      containerInfo = self._getContainerInfo( configlet.containerName )
      containerId = containerInfo[ 'key' ]
      builderInfo = self.cvpService.getConfigletByName( configlet.builderName )
      builderId = builderInfo[ 'key' ]
      self.cvpService.addGeneratedConfiglet( configlet.name, configlet.config,
                                             containerId, configlet.deviceMac,
                                             builderId )

   def _addReconciledConfiglet( self, configlet ):
      '''Adds the mapping between the reconciled configlet and device'''
      assert isinstance( configlet, Configlet )
      self.cvpService.addReconciledConfiglet( configlet.name, configlet.config,
                                              configlet.deviceMac )

   def updateConfiglet( self, configlet ):
      ''' updating an existing configlet in Cvp instance
      Argument:
          configlet -- updated information of the configlet
            ( type : Confgilet ( class ) )
      Raises:
         CvpError -- If configlet name is invalid
      '''
      assert isinstance( configlet, Configlet )
      configletInfo = self.cvpService.getConfigletByName( configlet.name )
      configletKey = configletInfo[ 'key' ]
      if isinstance( configlet, ConfigletBuilder ):
         self._insertCBFormKeys( configlet, configletKey )
         return self.cvpService.updateConfigletBuilder( configlet.name,
            configlet.formList, configlet.mainScript, configletKey )
      else:
         self.cvpService.updateConfiglet( configlet.name, configlet.config,
                                          configletKey )

   def _insertCBFormKeys( self, configlet, configletKey ):
      '''Retrieves the keys of the forms'''
      currCB = self.cvpService.getConfigletBuilder( configletKey )
      currForms = currCB[ 'formList' ]
      formKeys = {}
      for form in currForms:
         formKeys[ form[ 'fieldId' ] ] = form[ 'key' ]
      for form in configlet.formList:
         if form[ 'fieldId' ] in formKeys:
            form[ 'key' ] = formKeys[ form[ 'fieldId' ] ]

   def deleteConfiglet( self, configlet ):
      '''Remove a configlet from the Cvp instance
      Argument:
         configlet -- information of the configlet to be removed
            ( type : Confgilet ( class ) )
      Raises:
         CvpError -- If configlet name is invalid
      '''
      assert isinstance( configlet, Configlet )
      #Bug Arista trakker item 452 - 2016.1.2
      #if configlet.configletType == 'Generated':
      #   return
      configletInfo = self.cvpService.getConfigletByName( configlet.name )
      configletKey = configletInfo[ 'key' ]
      self.cvpService.deleteConfiglet( configlet.name, configletKey )

   def updateImageBundle( self, imageBundle, imageList ):
      '''update an image bundle in Cvp instance
      Argument:
         imageBundle -- updated image bundle information.
            ( type : ImageBundle ( class ) )
         imageList -- image objects list ( type : List Image Class )
      Raises:
         CvpError -- If image bundle name is invalid
      '''
      assert isinstance( imageBundle, ImageBundle )
      assert all ( isinstance( image, Image ) for image in imageList )
      currImageBundle = self.cvpService.getImageBundleByName( imageBundle.name )
      imageBundleKey = currImageBundle[ 'id' ]
      imageInfoList = []
      for image in imageList:
         imageData = self._addImage( str( image.name ) )
         if image.rebootRequired == True:
            imageData[ 'isRebootRequired' ] = 'true'
         else:
            imageData[ 'isRebootRequired' ] = 'false'
         imageInfoList.append( imageData )
      self.cvpService.updateImageBundle( imageBundle.name, imageBundle.certified,
                                         imageInfoList, imageBundleKey )

   def addImageBundle( self, imageBundle, imageList ):
      ''' Add an image bundle with an image.
      Arguments:
         imageBundle -- image bundle inforamtion object ( type: ImageBundle class )
         imageList -- image objects list ( type : List Image Class )
      Raises:
         CvpError -- If image bundle with same name already exists
      '''
      assert isinstance( imageBundle, ImageBundle )
      assert all ( isinstance( image, Image ) for image in imageList )
      imageInfoList = []
      for image in imageList:
         imageData = self._addImage( str( image.name ) )
         if image.rebootRequired == True:
            imageData[ 'isRebootRequired' ] = 'true'
         else:
            imageData[ 'isRebootRequired' ] = 'false'
         imageInfoList.append( imageData )
      self.cvpService.saveImageBundle( imageBundle.name, imageBundle.certified,
                                       imageInfoList )

   def _addImage( self, imageName ):
      '''Check if image is already present in CVP instance or not.
      If not then add the image to the CVP in instance.
      Returns:
         imageData -- information of the added image
      '''
      imageAddFlag = False
      imagesInfo = self.cvpService.getImagesInfo()
      for imageInfo in imagesInfo:
         if imageInfo[ 'name' ] == imageName:
            imageAddFlag = True
            break
      if imageAddFlag == False:
         imageInfo = self.cvpService.addImage( imageName )
         imageData = { 'name' : os.path.basename( imageName ),
                       'imageSize' : imageInfo[ 'imageSize' ],
                       'imageId' : imageInfo[ 'imageId' ],
                       'md5' : imageInfo[ 'md5' ],
                       'version' : imageInfo[ 'version' ],
                       'key' : None }
         return imageData
      else:
         for imageInfo in imagesInfo:
            if imageName == imageInfo['name']:
               imageData = { 'name' : os.path.basename( imageName ),
                             'imageSize' : imageInfo[ 'imageSize' ],
                             'imageId' : imageInfo[ 'imageId' ],
                             'md5' : imageInfo[ 'md5' ],
                             'version' : imageInfo[ 'version' ],
                             'key' : imageInfo[ 'key' ] }
         return imageData

   def addImage( self, image, strDirPath='.' ):
      '''Adds image to the Cvp Instance'''
      assert isinstance( image, Image )
      self.cvpService.addImage( image.name, strDirPath )

   def mapImageBundleToDevice( self, device, imageBundle ):
      '''Map image Bundle to device
      Arguments:
         imageBundle -- image bundle object ( type : ImageBundle( class ) )
         device -- name of the device ( type : Device ( class ) )
      Raises:
         CvpError -- If image bundle name is invalid
      '''
      assert isinstance( device, Device )
      assert isinstance( imageBundle, ImageBundle )
      imageBundleKey = ''
      imageBundleInfo = self.cvpService.getImageBundleByName( imageBundle.name )
      imageBundleKey = imageBundleInfo[ 'id' ]
      if imageBundleKey == '':
         raise cvpServices.CvpError( errorCodes.INVALID_IMAGE_BUNDLE_NAME )
      self.cvpService.applyImageBundleToDevice( device.macAddress, device.fqdn,
                                                imageBundle.name, imageBundleKey )

   def mapImageBundleToContainer( self, container, imageBundle ):
      '''Map imageBundle to container
      Arguments:
         container -- type : Container class
         imageBundle --  type : ImageBundle Class
      Raises:
         CvpError -- If container name or image bundle name is invalid
      '''
      assert isinstance( container, Container )
      assert isinstance( imageBundle, ImageBundle )
      imageBundleKey = ''
      containerInfo = self._getContainerInfo( container.name )
      containerKey = containerInfo[ 'key' ]
      imageBundleInfo = self.cvpService.getImageBundleByName( imageBundle.name )
      imageBundleKey = imageBundleInfo[ 'id' ]
      if imageBundleKey == '':
         raise cvpServices.CvpError( errorCodes.INVALID_IMAGE_BUNDLE_NAME )
      self.cvpService.applyImageBundleToContainer( container.name, containerKey,
                                                   imageBundle.name, imageBundleKey )

   def removeImageBundleAppliedToContainer( self, container, imageBundle ):
      '''Removes image bundle applied to the Container
      Arguments:
         container -- type : Container class
         imageBundle -- type : ImageBundle Class
      '''
      assert isinstance( container, Container )
      assert isinstance( imageBundle, ImageBundle )
      imageBundleKey = ''
      containerInfo = self._getContainerInfo( container.name )
      containerKey = containerInfo[ 'key' ]
      imageBundleInfo = self.cvpService.getImageBundleByName( imageBundle.name )
      imageBundleKey = imageBundleInfo[ 'id' ]
      if imageBundleKey == '':
         raise cvpServices.CvpError( errorCodes.INVALID_IMAGE_BUNDLE_NAME )
      self.cvpService.removeImageBundleAppliedToContainer( container.name,
                                     containerKey, imageBundle.name, imageBundleKey )

   def _getConfigletKeys( self, configletNameList ):
      '''Returns keys for corresponding configlet names in the
      configletNameList'''
      configletKeyList = []
      configletNum = len( configletNameList )
      configletsInfo = self.cvpService.getConfigletsInfo()
      for configletInfo in configletsInfo:
         if configletInfo[ 'name' ] in configletNameList:
            configletNum -= 1
            configletKeyList.append( configletInfo[ 'key' ] )
      if configletNum > 0:
         raise cvpServices.CvpError( errorCodes.INVALID_CONFIGLET_NAME )
      return configletKeyList

   def mapConfigletToContainer( self, container, configletList ):
      '''Map the configlets to container
      Arguments:
         container -- type : Container class
         configletList -- List of configlet objects to be applied
               ( type : List of Configlet Class )
      Raises:
         CvpError -- If the configlet names or container name are invalid
      '''
      assert isinstance( container, Container )
      assert all ( isinstance( configlet, Configlet ) for configlet in
                                                                      configletList )
      cnl = []
      ckl = []
      cbnl = []
      cbkl = []
      aplyConfigletNames = []
      containerInfo = self._getContainerInfo( container.name )
      containerKey = containerInfo[ 'key' ]
      configletsInfo = self.cvpService.getContainerConfiglets( containerKey )
      aplyConfigletNames = [ configlet[ 'name' ] for configlet in configletsInfo ]
      for configlet in configletList:
         if configlet.name not in aplyConfigletNames:
            if ( configlet.configletType == 'static' or
                 configlet.configletType == 'generated' ):
               cnl.append( configlet.name )
            else:
               cbnl.append( configlet.name )
      cnl.extend( aplyConfigletNames )
      ckl = self._getConfigletKeys( cnl )
      cbkl = self._getConfigletKeys( cbnl )
      self.cvpService.applyConfigletToContainer( container.name, containerKey,
                                                 cnl, ckl, cbnl, cbkl )

   def removeConfigletAppliedToContainer( self, container, configletList ):
      '''remove configlet mapped to containers
      Arguments:
         container -- type : Container class
         configletList -- List of configlet objects to be removed
            ( type : List of Configlet Class )
      Raises:
         CvpError -- If the configlet names or container name are invalid
      '''
      assert isinstance( container, Container )
      assert all ( isinstance( configlet, Configlet ) for configlet in
                                                                      configletList )
      configletNameList = []
      for configlet in configletList:
         configletNameList.append( configlet.name )
      if not configletNameList:
         return 'No configlets to map'
      configletKeyList = self._getConfigletKeys( configletNameList )
      containerInfo = self._getContainerInfo( container.name )
      containerKey = containerInfo[ 'key' ]
      self.cvpService.removeConfigletFromContainer( container.name, containerKey,
                                                configletNameList, configletKeyList )

   def addContainer( self, container ):
      '''Add container to the inventory
      Arguments:
         container -- container to be added ( type : Container( class ) )
      Raises:
         CvpError -- If container parent name ( parentName ) is invalid
         CvpError -- If container name ( name ) is invalid
         CvpError -- If container already exists.
      '''
      assert isinstance( container, Container )
      parentContainerName = container.parentName
      parentContainerInfo = self._getContainerInfo( parentContainerName )
      parentContainerId = parentContainerInfo[ 'key' ]
      self.cvpService.addContainer( container.name,
                                    container.parentName, parentContainerId )

   def addDevice( self, device ):
      '''Add the device in proper container in Cvp Inventory
      Arguments:
         device -- devices to be added to inventory ( type : Device( class ) )
      Raises:
         CvpError -- If device status is login after connection attempt
         CvpError -- If device stauts is failed after connection attempt
      '''
      assert isinstance( device, Device )
      self._addDevice( device )
      self.cvpService.saveInventory()

   def _addDevice( self, device ):
      '''Add device internal function. This method checks the status of the
      first attempt of device addition. If status is duplicate it deletes the
      recently added device. If status is login it raises exception of unauthorised
      user. If status is failure then it raises exception of connection failure
      '''
      parentContainerName = device.containerName
      if parentContainerName == 'Undefined':
         parentContainerId = 'undefined_container'
      else:
         parentContainerInfo = self._getContainerInfo( parentContainerName )
         parentContainerId = parentContainerInfo[ 'key' ]
      status = self._getDeviceStatus( device )
      # Cleanup any previous additions of this device that could be in an
      # incomplete state
      if status:
         # Note that the above call returns only temp devices, not connected ones
         self.cvpService.deleteTempDevice( status[ 'key' ] )
         status = self._getDeviceStatus( device )

      if not status:
         self.cvpService.addToInventory( device.ipAddress, parentContainerName,
                                         parentContainerId )
         status = self._getDeviceStatus( device )
         while status[ 'status' ] == 'Connecting':
            status = self._getDeviceStatus( device )
      self.cvpService.saveInventory()
      if status[ 'status' ] == 'Duplicate' :
         self.cvpService.deleteTempDevice( status[ 'key' ] )
      elif status[ 'status' ] == 'Connected' :
         self.cvpService.saveInventory()
      elif status[ 'status' ] == 'Unauthorized access':
         raise cvpServices.CvpError( errorCodes.DEVICE_LOGIN_UNAUTHORISED )
      else:
         raise cvpServices.CvpError( errorCodes.DEVICE_CONNECTION_ATTEMPT_FAILURE )

   def addDevices( self, deviceList ):
      '''Adding devices to the inventory in pipeline manner
      Argument:
         deviceList -- List of devices to be added to inventory
               ( type : List of Device objects )
      Raises:
         CvpError -- If parent container name is invalid
      Returns:
         connectedDeviceList -- List of device successfully connected
               ( type : List of Device( class ) )
         unauthorisedDeviceList -- List of devices for whom user doen't have
               authentication ( type : List of Device( class ) )
         connFailureDeviceList --  Failure to connect device list
               ( type : List of Device( class ) )
      '''
      # TODO: Merge this with addDevice()
      assert all ( isinstance( device, Device ) for device in deviceList )
      connectedDeviceList = []
      unauthorisedDeviceList = []
      connFailureDeviceList = []
      for device in deviceList:
         parentContainerName = device.containerName
         if parentContainerName == 'Undefined':
            parentContainerId = 'undefined_container'
         else:
            parentContainerInfo = self._getContainerInfo( parentContainerName )
            parentContainerId = parentContainerInfo[ 'key' ]

         status = self._getDeviceStatus( device )
         # Cleanup any previous additions of this device that could be in an
         # incomplete state
         if status:
            # Note that the above call returns only temp devices, not connected ones
            self.cvpService.deleteTempDevice( status[ 'key' ] )
            status = self._getDeviceStatus( device )

         if not status:
            self.cvpService.addToInventory( device.ipAddress, parentContainerName,
                                            parentContainerId )

      for device in deviceList:
         status = self._getDeviceStatus( device )
         while status[ 'status' ] == 'Connecting' :
            status = self._getDeviceStatus( device )
         if status[ 'status' ] == 'Connected':
            connectedDeviceList.append( device )
         elif status[ 'status' ] == 'Unauthorized access':
            unauthorisedDeviceList.append( device )
         elif status[ 'status' ] == 'Duplicate':
            connectedDeviceList.append( device )
            self.cvpService.deleteTempDevice( status[ 'key' ] )
         else:
            connFailureDeviceList.append( device )
      self.cvpService.saveInventory()
      return ( connectedDeviceList, unauthorisedDeviceList, connFailureDeviceList )

   def _getDeviceStatus( self, device ):
      '''Retrieve the device status from the Cvp instance
      Returns:
         deviceInfo -- Information about the device.( type : Dict )
      '''
      assert isinstance( device, Device )
      _, connFailureDevices = self.cvpService.retrieveInventory()
      for deviceInfo in connFailureDevices:
         if ( deviceInfo[ 'fqdn' ] == device.fqdn.split('.')[ 0 ] or
              deviceInfo[ 'ipAddress' ] == device.ipAddress ):
            return deviceInfo

   def mapConfigletToDevice( self, device , configletList ):
      '''applying configs mentioned in configletNameList to the device.
      Arguments:
         device -- device information object ( type : Device( class ) )
         configletList -- List of configlets objects to be applied
         ( type : List of Configlet Objects )
      Raises:
         CvpError -- If device information is incorrect
         CvpError -- If configletNameList contains invalid configlet name
      '''
      assert isinstance( device, Device )
      assert all ( isinstance( configlet, Configlet ) for configlet in
                                                                      configletList )
      self.cvpService.saveInventory()
      cnl = []
      ckl = []
      aplyConfigletNames = []
      configletsInfo = self.cvpService.getDeviceConfiglets( device.macAddress )
      aplyConfigletNames = [ configlet[ 'name' ] for configlet in configletsInfo ]
      cnl.extend( aplyConfigletNames )
      for configlet in configletList:
         if configlet.name not in cnl:
            cnl.append( configlet.name )
      ckl = self._getConfigletKeys( cnl )
      self.cvpService.applyConfigletToDevice( device.ipAddress,
                                              device.fqdn, device.macAddress, cnl,
                                              ckl )

   def executeAllPendingTask( self ):
      '''Executes all the pending tasks.
      '''
      tasksInfo = self.getPendingTasksList()
      for taskInfo in tasksInfo:
         self.executeTask( taskInfo )

   def executeTask( self, task ):
      '''Executes a task object.
      Arguments:
         task - a task object
      Raises:
         CvpError -- if task is invalid
      '''
      assert isinstance( task, Task )
      taskNum = int( task.taskId )
      self.cvpService.executeTask( taskNum )

   def getPendingTasksList( self ):
      '''Finds all the pending tasks from the Cvp instance '''
      return self.getTasks( Task.PENDING )

   def monitorTaskStatus( self, taskList, status=Task.COMPLETED, timeout=300 ):
      '''Poll for tasks to be in the state described by status
      Returns:
         nothing on success
      Raises:
         CvpError -- on timeout
      '''
      assert all ( isinstance( task, Task ) for task in taskList )
      end = time.time() + timeout

      for monitorTask in taskList:
         while time.time() < end:
            task = self.cvpService.getTaskById( monitorTask.taskId )
            taskStatus = task[ 'workOrderUserDefinedStatus' ]
            if taskStatus == status:
               break
            elif taskStatus in [ Task.FAILED, Task.CANCELED ]:
               raise cvpServices.CvpError( errorCodes.TASK_EXECUTION_ERROR,
                                           'Task %d %s' %
                                           ( monitorTask.taskId, taskStatus ) )
            # back off and try again
            time.sleep( 1 )

         if time.time() >= end:
            # raise timeout error
            raise cvpServices.CvpError( errorCodes.TIMEOUT )

   def _getImageNameList( self, imageBundleInfo ):
      '''Return list of images present in image bundle'''
      imagesInfo = imageBundleInfo[ 'images' ]
      imageNameList = []
      for imageInfo in imagesInfo:
         imageNameList.append( imageInfo[ 'name' ] )
      return imageNameList

   def getImageBundles( self ):
      '''Retrieves information on all the image bundles.Image bundle information
      consist of images information, image bundle name, devices and
      containers to which the image bunudle is mapped to.
      Returns:
         imageBundleList -- List of ImageBundle object, each object providing
         information about an image bundle ( type: List of ImageBundle objects )
      '''
      imageBundlesInfo = self.cvpService.getImageBundles()
      imageBundleList = []
      for bundleInfo in imageBundlesInfo:
         imageBundleInfo = self.cvpService.getImageBundleByName(
                                                               bundleInfo[ 'name' ] )
         imageNameList = self._getImageNameList( imageBundleInfo )
         certified = ( imageBundleInfo[ 'isCertifiedImage' ] == 'true' )
         imageBundleList.append( ImageBundle( bundleInfo[ 'name' ],
                                 imageNameList, certified ) )
      return imageBundleList

   def getImageBundle( self, imageBundleName ):
      '''Retrieves image bundle from Cvp instance. Image bundle information
      consist of images information, image bundle name, devices and
      containers to which the image bunudle is mapped to.
      Arguments:
         imageBundleName -- name of image bundle ( type : String )
      Raises:
         CvpError -- If imageBundleName is invalid
      Returns:
         ImageBundle -- ImageBundle object contains all required image bundle
         information ( type : ImageBundle( class ) )
      '''
      imageBundleInfo = self.cvpService.getImageBundleByName( imageBundleName )
      imageNameList = self._getImageNameList( imageBundleInfo )
      certified = ( imageBundleInfo[ 'isCertifiedImage' ] == 'true' )
      return ImageBundle( imageBundleName, imageNameList, certified )

   def deleteImageBundle( self, imageBundle ):
      '''Deletes image bundle from cvp instance
      Arguments:
         imageBundle -- image bundle to be deleted ( type : ImageBundle( class ) )
      Raises:
         CvpError -- If image bundle key is invalid
         CvpError -- If image bundle is applied to any entity
      '''
      assert isinstance( imageBundle, ImageBundle )
      imageBundleInfo = self.cvpService.getImageBundleByName( imageBundle.name )
      imageBundleKey = imageBundleInfo[ 'id' ]
      self.cvpService.deleteImageBundle( imageBundleKey, imageBundle.name )

   def deviceComplianceCheck( self, deviceMacAddress ):
      '''Run compliance check on the device
      Returns:
         complianceCheck -- Boolean flag indicating successful or un-successful
                            compliance check
      Raises:
         CvpError -- If device mac address ( deviceMacAddress ) is invalid
      '''
      complianceReport = self.cvpService.deviceComplianceCheck( deviceMacAddress )
      if complianceReport[ 'complianceIndication' ] != 'NONE' :
         complianceCheck = False
      else:
         complianceCheck = True
      return complianceCheck

   def renameContainer( self, container, newContainerName ):
      ''' Renames the container to desired new name
      Arguments:
         container -- current information of the container
         newContainerName -- New desired name of the container
      Returns: None
      Raises:
         CvpError -- If the oldContainerName is invalid
      '''
      assert isinstance( container, Container )
      containerInfo = self._getContainerInfo( container.name )
      containerKey = containerInfo[ 'key' ]
      self.cvpService.changeContainerName( container.name, newContainerName,
                                           containerKey )

   def getRootContainerInfo( self ):
      ''' Returns information about the root container
      Returns:
         container -- Container object containing information about root container
      '''
      container, _ = self.cvpService.retrieveInventory()
      return self.getContainer( container[ 'name' ] )

   def deleteContainer( self, container ):
      '''delete the container from the Cvp inventory
      Argument:
         container -- container to be deleted. ( type : Container(class) )
      Raises:
         CvpError -- If parent container name ( parentName )is invalid
         CvpError -- If container name ( name ) is invalid
      '''
      assert isinstance( container, Container )

      # Can't delete the Tenant container
      if container.name == self.getRootContainerInfo().name:
         raise cvpServices.CvpError( errorCodes.INVALID_CONTAINER_NAME )

      containerKey = ''
      parentKey = ''
      containerInfo = self._getContainerInfo( container.name )
      containerKey = containerInfo[ 'key' ]
      parentInfo = self._getContainerInfo( container.parentName )
      parentKey = parentInfo[ 'key' ]
      self.cvpService.deleteContainer( container.name, containerKey,
                                       container.parentName, parentKey )

   def deleteDevice( self, device ):
      '''Delete the device from the Cvp inventory.
      Arguments:
         device -- device to be deleted.( type : Device(class) )
      Raises:
         CvpError -- If parent container name ( containerName ) is invalid
      Returns: None
      '''
      assert isinstance( device, Device )
      if device.containerName == 'Undefined':
         containerKey = 'undefined_container'
      else:
         containerInfo = self._getContainerInfo( device.containerName )
         containerKey = containerInfo[ 'key' ]
      self.cvpService.deleteDevice( device.macAddress,
                                    device.containerName, containerKey )

   def deployDevice( self, device, deviceTargetIp, container,
                     configletList=None, configletBuilderList=None,
                     imageBundle=None ):
      ''' Move a device from the undefined container to a target container.
      Optionally, apply any device-specific configlets and an image to the device.
      Return a Task that can be executed to complete the action
      Arguments:
         device -- The device to be moved from the undefined container to the
                   targetConatiner
         deviceTargetIp -- The IP address of the device after all the configlets
                           have been applied
         container -- The container to move the device to
         configletList -- Optional, a list of configlets to apply to the device
         configletBuilderList -- Optional, a list of configlet builders to be used to
                                 generate device specific configlets
         image -- Optional, an image to apply to the device
      Returns: A list of Tasks that can be executed to complete the action
      '''
      assert isinstance( device, Device )
      assert isinstance( container, Container )
      assert imageBundle is None or isinstance( imageBundle, ImageBundle )
      ckl = []
      cnl = []
      cbnl = []
      cbkl = []
      if configletList:
         assert all( isinstance( configlet, Configlet ) for configlet in
                     configletList )
         # add in any device specific configlets
         cnl = [ configlet.name for configlet in configletList ]
         if cnl:
            ckl = self._getConfigletKeys( cnl )

      if configletBuilderList:
         assert all( isinstance( builder, ConfigletBuilder ) for builder in
                     configletBuilderList )
         # add in any device specific configlets generated using builders
         cbnl = [ builder.name for builder in configletBuilderList ]
         if cbnl:
            cbkl = self._getConfigletKeys( cbnl )

      containerInfo = self._getContainerInfo( container.name )
      containerKey = containerInfo[ 'key' ]
      imageBundleKey = None
      imageBundleName = None
      if imageBundle:
         imageBundleInfo = self.cvpService.getImageBundleByName( imageBundle.name )
         imageBundleKey = imageBundleInfo[ 'id' ]
         imageBundleName = imageBundle.name

      response = self.cvpService.deployDevice( device.macAddress,
                                       device.fqdn, device.ipAddress, deviceTargetIp,
                                       containerKey, container.name, ckl, cnl, cbkl,
                                       cbnl, imageBundleKey, imageBundleName )

      tids = [ int(t) for t in response[ 'taskIds' ] ]
      assert len( tids ) == 1, "Only one task expected"
      tid = tids[ 0 ]
      info = self.cvpService.getTaskById( tid )
      task = Task( tid, info[ 'workOrderUserDefinedStatus' ], info[ 'description' ] )
      return task

   def getTasks( self, status=None ):
      ''' Retrieve all tasks filtered by status.
      Arguments:
         status --  None, Task.COMPLETED, Task.PENDING, Task.CANCELED,
                    Task.FAILED
      Returns: A list of tasks
      '''
      assert status in ( None, Task.COMPLETED, Task.PENDING, Task.CANCELED,
                         Task.FAILED )
      tasks = self.cvpService.getTasks( status )
      return [ Task( t[ 'workOrderId'], t[ 'workOrderUserDefinedStatus' ],
                     t[ 'description' ] ) for t in  tasks ]

   def cancelTask( self, task ):
      ''' Cancel a pending task
      Raises:
         CvpError -- if the task is invalid
      '''
      assert isinstance( task, Task )
      self.cvpService.cancelTask( task.taskId )

   def addNoteToTask( self, task, note ):
      ''' Add a note to a task
      Raises:
         CvpError -- If task is invalid
      '''
      assert isinstance( task, Task )
      self.cvpService.addNoteToTask( task.taskId, note )

   def getCvpVersionInfo( self ):
      ''' Finds the current version of CVP'''
      return self.cvpService.cvpVersionInfo()

   def getRoles( self ):
      '''Downloads information about all the roles'''
      roleList = []
      rolesInfo = self.cvpService.getRoles()
      for roleInfo in rolesInfo:
         roleList.append( Role( roleInfo[ 'name' ], roleInfo[ 'description' ],
                                roleInfo[ 'moduleList' ] ) )
      return roleList

   def getRole( self, roleName ):
      '''Download information about a specific role with name as roleName
      Raises:
         CvpError -- If the role name is invalid
      '''
      roles = self.getRoles()
      for role in roles:
         if role.name == roleName:
            return role

   def addRole( self, role ):
      ''' Add a Role to the Cvp instance
      Raises:
         CvpError -- If the role with same name already exists
      '''
      assert isinstance( role, Role )
      self.cvpService.addRole( role.name, role.moduleList )

   def updateRole( self, role ):
      ''' Update the information about the Role
      Raises:
         CvpError -- if role name is invalid
      '''
      assert isinstance( role, Role )
      rolesInfo = self.cvpService.getRoles()
      for roleInfo in rolesInfo:
         if roleInfo[ 'name' ] == role.name:
            roleKey = roleInfo[ 'key' ]
      self.cvpService.updateRole( role.name, role.description, role.moduleList,
                                  roleKey )

   def deleteRole( self, roleName ):
      '''deletes role from the cvp instance'''
      roleKey = ''
      rolesInfo = self.cvpService.getRoles()
      for roleInfo in rolesInfo:
         if roleInfo[ 'name' ] == roleName:
            roleKey = roleInfo[ 'key' ]
      if roleKey:
         self.cvpService.deleteRole( roleKey )
      else:
         raise cvpServices.CvpError( errorCodes.INVALID_ROLE_NAME )

