# Copyright (c) 2015 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
'''
@Copyright: 2015-2016 Arista Networks, Inc.
Arista Networks, Inc. Confidential and Proprietary.

CvpServices script is used for making request to the Cvp web-serves.
These requests comprise of  addition, modification, deletion and retrieval of
Cvp instance.

It contains 2 classes
   CvpError -- Handles exceptions
   CvpService -- Handles requests
'''
import requests_2_4_0 as requests
import json
import urllib
import uuid
import os
import errorCodes

DEFAULT_USER = "cvpadmin"
DEFAULT_PASSWORD = "cvpadmin"
trace = ( os.getenv( 'TRACE', '' ) == '1' )

class CvpError( Exception ):
   '''CvpError is a class for containing the exception information and passing that
   exception information upwards to the application layer

   Public methods:
      __str__()

   Instance variables:
      errorMessage -- information corresponding to the error code in response
      errorCode -- error code value provided in response to the HTTP/HTTPS request
   '''
   def __init__( self, errorCode, errorMessage='' ):
      super( CvpError, self ).__init__()
      self.errorCode = int( errorCode )
      if not errorMessage:
         if self.errorCode in errorCodes.ERROR_MAPPING:
            self.errorMessage = errorCodes.ERROR_MAPPING.get( self.errorCode )
         else:
            self.errorMessage = 'Unknown Error Code: ' + str( errorCode ) + ' not' \
            ' listed in errorCodes.py'
      else:
         self.errorMessage = errorMessage

   def __str__( self ):
      '''returns string value of the object'''
      return str( self.errorCode ) + ( ': ' + self.errorMessage if self.errorMessage
                                                                else '' )

class CvpService( object ):
   '''CvpService class is responsible for hitting endpoints of the Cvp web-server
   for retrieving, updating, adding and deleting state of Cvp

   Public methods:
      authenticate(  username, password )
      getConfigletsInfo()
      getConfigletBuilder( configletBuilderKey )
      imageBundleAppliedContainers(imageBundleName  )
      searchContainer( containerName )
      imageBundleAppliedDevices( imageBundleName )
      addImage( imageName )
      downloadImage( imageName, imageId, filePath )
      firstLoginDefaultPasswordReset( newPassword, emaildId )
      getInventory()
      configAppliedContainers( configletName )
      configAppliedDevices ( configletName )
      retrieveInventory()
      getImagesInfo()
      addConfiglet( configletName, configletContent )
      addConfigletBuilder( ConfigletBuilder )
      getConfigletByName( configletName )
      updateConfiglet( configletName, configletContent, configletKey )
      deleteConfiglet( configletName, configletKey )
      deleteConfigletBuilder( ConfigletBuilder )
      saveImageBundle( imageBundleName, imageBundleCertified, imageInfoList )
      getImageBundleByName( imageBundleName )
      updateImageBundle( imageBundleName, imageBundleCertified, imageInfoList,
          imageBundleKey )
      addToInventory( deviceIpAddress, parentContainerName, parentContainerId )
      saveInventory()
      retryAddToInventory( deviceKey, deviceIpAddress, username, password )
      executeTask( taskId )
      getTasks( status )
      addNoteToTask( taskId, note )
      getImageBundles()
      deleteImageBundle( imageBundleKey, imageBundleName )
      deleteDuplicateDevice( tempDeviceId )
      deleteContainer(  containerName, containerKey, parentContainerName,
         parentKey )
      deleteDevice( deviceKey, parentContainerName, containerKey )
      applyConfigToDevice( deviceIpAddress, deviceFqdn, deviceKey,
         configNameList, configKeyList )
      applyConfigToContainer( containerName, containerKey, configNameList,
         configKeyList )
      removeConfigFromContainer( containerName, containerKey, configNameList,
         configKeyList )
      addContainer( containerName, containerParentName, parentContainerId )
      applyImageBundleToDevice( deviceKey, deviceFqdn, imageBundleName,
         imageBundleKey )
      applyImageBundleToContainer( containerName, containerKey,imageBundleName,
         imageBundleKey )
      deviceComplianceCheck( deviceConfigIdList, deviceMacAddress )
      changeContainerName( oldName, newName, containerKey )
      deployDevice( self, device, targetContainer, info, configletList, image )
      cvpVersionInfo()
      getRoles()
      addRole( roleName, roleModuleList )
      getRole( roleId )
      updateRole( roleName, description, moduleList, roleKey )
      updateConfigletBuilder( ConfigletBuilderName, formList, mainScript,
         configletBuilderId )

   Instance variables:
      port -- Port where Http/Https request made to web server
      url -- denotes the host sub-part of the URL
      headers -- headers required for the Http/Https requests
      hostname -- name of the host
      cookies -- cookies of the session establised
      tmpDir -- temporary directory enclosing file operations
   '''

   def __init__( self, hostname, ssl=False, port=80, tmpDir='' ):
      self.hostname = hostname
      self.tmpDir = tmpDir
      self.port = port
      self.cookies = None
      if ssl == True:
         self.url = 'https://%s:%d' % ( self.hostname, self.port )
      else:
         self.url = 'http://%s:%d' % ( self.hostname, self.port )
      self.headers = { 'Accept' : 'application/json',
                       'Content-Type' : 'application/json' }

   def doRequest( self, method, url, *args, **kwargs ):
      '''Issues an Http request
      Arguments:
         method -- Http method
         url -- endpoint of the request
         *args --  multiple arguments passed
         **kwargs -- multiple arguments passed that need to be handled using name
      Returns:
         response -- Json response from the endpoint
      Raises:
         CvpError -- If response is not json or response contains error code
                     If parameter data structures are incorrect
      '''
      if not 'cookies' in kwargs:
         kwargs[ 'cookies' ] = self.cookies
      response = method( url, *args, **kwargs )
      response.raise_for_status()
      responseJson = response.json()
      if 'errorCode' in responseJson:
         if trace:
            print responseJson
         errorCode = responseJson.get( 'errorCode', 0 )
         errorMessage = responseJson.get( 'errorMessage', '' )
         raise CvpError( errorCode, errorMessage )
      return responseJson

   def _authenticationRequest( self, method, url, *args, **kwargs ):
      '''Issues an Http request for authentication
      Arguments:
         method -- Http method
         url -- endpoint of the request
         *args -- multiple arguments passed
         **kwargs -- multiple arguments passed that need to be handled using name
      Returns:
         response -- Information of the established session
                     (cookies, session_id etc.)
      Raises:
         CvpError -- If response contains error code or response is not json
                     If parameter data structures are incorrect
      '''
      response = method( url, *args, **kwargs )
      response.raise_for_status()
      if 'errorCode' in response.text:
         errorCode = response.json().get( 'errorCode', 0 )
         errorMessage = response.json().get( 'errorMessage', '' )
         raise CvpError( errorCode, errorMessage )
      return response

   def getConfigletsInfo( self ):
      '''Retrieves information of all configlets.
      Returns:
         configlets[ 'data' ] -- List of configlets with details
                                 ( type : List of Dict )
      '''
      configlets = self.doRequest( requests.get,
                        '%s/web/configlet/getConfiglets.do?startIndex=%d&endIndex=%d'
                        % ( self.url, 0, 0 ) )
      return configlets[ 'data' ]

   def getConfigletBuilder( self, configletBuilderKey ):
      ''' Retrieves information about a particular Configlet Builder
      Arguments:
         configletBuilderKey -- unique key associated with the Configlet Builder
      Response:
         Information like name, form list, mainscript about Configlet Builder
      '''
      configletBuilderData = self.doRequest( requests.get,
                                '%s/web/configlet/getConfigletBuilder.do?type=&id=%s'
                                % ( self.url, configletBuilderKey ) )
      return configletBuilderData[ 'data' ]

   def deviceComplianceCheck( self, deviceMacAddress ):
      ''' Runs compliance check on the device. Finds differences in
      designed configuration according to Cvp application and actual
      running configuration on the device.
      Arguments:
         deviceConfigIdList -- Configlet Id list of configlets applied to device
                               as per the Designed configuration
         deviceMacAddress -- Mac address of the device
      Returns:
         complianceReport -- Information about the compliance check of the
                             device.
      Raises:
         CvpError -- If device Mac-Address is invalid
                     If parameter data structures are incorrect
      '''
      data = { 'nodeId' : deviceMacAddress,
               'nodeType' : 'netelement'
             }
      complianceReport = self.doRequest( requests.post,
                 '%s/web/ztp/checkCompliance.do' % self.url, data=json.dumps( data ),
                 cookies=self.cookies )
      return complianceReport

   def authenticate( self, username, password ):
      '''Authentication with the web server
      Arguments:
         username -- login username ( type : String )
         password -- login password ( type : String )
      Raises:
         CvpError -- If username and password combination is invalid
                     If parameter data structures are incorrect
      '''
      authData = { 'userId' : username, 'password' : password }
      authentication =  self._authenticationRequest( requests.post,
            '%s/web/login/authenticate.do' % self.url, data=json.dumps( authData ),
            headers=self.headers )
      self.cookies = authentication.cookies

   def imageBundleAppliedContainers( self, imageBundleName ):
      '''Retrieves containers to which the image bundle is applied to.
      Warning -- Method deosn't check existence of the image bundle
      Arguments:
         imageBundleName -- name of the image bundle ( type : String )
      Returns:
         containers[ 'data' ] -- List of containers ( type : List of Dict )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      containers = self.doRequest( requests.get,
                             '%s/web/image/getImageBundleAppliedContainers.do?'
                             'imageName=%s&startIndex=%d&endIndex=%d&queryparam=null'
                             % ( self.url, imageBundleName, 0, 0 ) )
      return containers[ 'data' ]

   def changeContainerName( self, oldName, newName, containerKey ):
      '''Changes the container name from old container name to
      the new name
      Arguments:
         oldName -- original name of the container
         containerKey -- unique Id associated with the container
         newName -- desired new name of the container
      Raises:
         CvpError -- If the oldName is invalid
         CvpError -- If containerKey is invalid
      '''
      data = { "data" :
                    [ { "info" : "Container " + newName + " renamed from " + oldName,
                        "infoPreview" : "Container " + newName + " renamed from " +
                           oldName,
                        "action" : "update",
                        "nodeType" : "container",
                        "nodeId" : containerKey,
                        "toId" : "",
                        "fromId" : "",
                        "nodeName" : newName,
                        "fromName" : "",
                        "toName" : "",
                        "toIdType" : "container",
                        "oldNodeName" : oldName
                      } ] }
      self.doRequest( requests.post,
                '%s/web/ztp/addTempAction.do?format=topology&queryParam=&nodeId=%s' %
                ( self.url, containerKey ), data=json.dumps( data ),
                cookies=self.cookies )
      self._saveTopology( [] )

   def searchContainer( self, containerName ):
      '''Retrieves information about a container
      Arguments:
         containerName -- name of the container ( type : String )
      Returns:
         container[ 'data' ] -- Complete information about the container
                                ( type : Dict )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      container = self.doRequest( requests.get,
               '%s/web/inventory/add/searchContainers.do?queryparam=%s&startIndex=%d'
               '&endIndex=%d' % ( self.url, containerName, 0, 0 ) )
      return container[ 'data' ]

   def imageBundleAppliedDevices( self, imageBundleName):
      '''Retrieves devices to which the image bundle is applied to.
      Warning -- Method deosn't check existence of the image bundle
      Arguments:
         imagebundleName -- name of the image bundle ( type : String )
      Returns:
         devices[ 'data' ] -- List of devices ( type : List of Dict )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      devices = self.doRequest( requests.get,
                             '%s/web/image/getImageBundleAppliedDevices.do?'
                             'imageName=%s&startIndex=%d&endIndex=%d&queryparam=null'
                             % ( self.url, imageBundleName, 0, 0 ) )
      return devices[ 'data' ]

   def addImage( self, imageName, strDirPath='' ):
      '''Add image to Cvp instance
      Warning -- image file with imageName as file should exist
      Argument:
         imageName -- name of the image ( type : String )
      Raises:
         CvpError -- If image already exists in Cvp instance
      Returns:
         imageInfo -- information of image added to the cvp instance
      '''
      assert isinstance( imageName, str )
      if strDirPath:
         image = open( os.path.join( strDirPath, imageName ), 'r' )
      elif self.tmpDir:
         image = open( os.path.join( self.tmpDir, imageName ), 'r' )
      elif os.path.isfile( imageName ):
         image = open( imageName, 'r' )
      else:
         raise CvpError( errorCodes.INVALID_IMAGE_ADDITION )
      imageInfo = self.doRequest( requests.post,
                    '%s/web/image/addImage.do' % self.url, files={ 'file' : image } )
      return imageInfo

   def downloadImage( self, imageName, imageId, filePath='' ):
      '''Download the image file from Cvp Instance and stores at corresponding
      file path or current directory
      Arguments:
         imageName -- name of image (type : string )
         imageId -- unique Id assigned to the image ( type : string )
         filePath -- storage path in the local system (optional)( type : string )
      '''
      fileName = os.path.join( filePath, imageName )
      URL =  '%s/web/services/image/getImagebyId/%s' % ( self.url, imageId )
      imageSWI = urllib.URLopener()
      imageSWI.retrieve( URL, fileName )

   def firstLoginDefaultPasswordReset( self,  newPassword, emailId ):
      '''Reset the password for the first login into the Cvp Web-UI
      Warning -- Method doesn;t check the validity of emailID
      Arguments:
         newPassword -- new password for password reset ( type : String )
         emailId -- emailId assigned to the user ( type : String )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      data = { "userId" : DEFAULT_USER,
               "oldPassword" : DEFAULT_PASSWORD,
               "currentPassword" : newPassword,
               "email" : emailId
             }
      self.doRequest( requests.post, '%s/web/login/changePassword.do'
                        % self.url, data=json.dumps( data ) )

   def getInventory( self ):
      '''Retrieve information about devices provisioned by the Cvo instance
      Returns:
         inventory[ 'netElementList' ] -- List of information of all devices
         ( type : List of Dict )
         inventory[ 'containerList' ] -- Information of parent container of devices
         ( type : List of Dict )
      '''
      inventory = self.doRequest( requests.get,
                        '%s/web/inventory/getInventory.do?queryparam=.&startIndex=%d'
                        '&endIndex=%d' % ( self.url, 0, 0 ), cookies=self.cookies )
      return ( inventory[ 'netElementList' ], inventory[ 'containerList' ] )

   def configletAppliedContainers( self, configletName ):
      '''Retrieves containers to which the configlet is applied to.
      Warning -- Method deosn't check existence of the configlet
      Arguments:
         configletName -- name of the configlet ( type : String )
      Returns:
         containers[ 'data' ] -- List of container to which configlet is applied
         ( type : List of Dict )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      containers = self.doRequest( requests.get,
                          '%s/web/configlet/getAppliedContainers.do?configletName=%s'
                          '&startIndex=%d&endIndex=%d&queryparam=null'
                          '&configletId=1'
                          % ( self.url, configletName, 0, 0 ) )
      return containers[ 'data' ]

   def configletAppliedDevices( self, configletName ):
      '''Retrieves devices to which the configlet is applied to.
      Warning -- Method deosn't check existence of the configlet
      Arguments:
         configletName -- name of the configlet ( type : String )
      Returns:
         devices[ 'data' ] -- List of devices to which configlet is applied
         ( type : List of Dict )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      devices = self.doRequest( requests.get,
                             '%s/web/configlet/getAppliedDevices.do?configletName=%s'
                             '&startIndex=%d&endIndex=%d&queryparam=null'
                             '&configletId=1'
                             % ( self.url, configletName, 0, 0 ) )
      return devices[ 'data' ]

   def retrieveInventory( self ):
      '''Retrieves information about containers and temporary devices present
      in Cvp inventory

      Arguments: None

      Returns:
         inventory[ 'containers' ] -- complete information of all containers
         ( type : List of Dict )
         inventory[ 'tempNetElement' ] -- List of information of all temporary
                                          devices (type : List of Dict )
      '''
      inventory = self.doRequest(requests.get,
                '%s/web/inventory/add/retrieveInventory.do?startIndex=%d&endIndex=%d'
                %( self.url, 0, 0 ) )
      return (inventory[ 'containers' ], inventory[ 'tempNetElement' ] )

   def getImagesInfo( self ):
      '''Get information about all the images
      Returns:
         images[ 'data' ] -- List of details of all the images
                             ( type : List of Dict )
      '''
      images = self.doRequest( requests.get,
                    '%s/web/image/getImages.do?queryparam=&startIndex=%d&endIndex=%d'
                    % ( self.url, 0, 0 ) )
      return images[ 'data' ]

   def addConfiglet( self, configletName, configletContent ):
      '''Add configlet to Cvp inventory
      Arguments:
         configletName -- name of the configlet ( type : String )
         configletContent -- content of the configlet ( type : String )
      Raises:
         CvpError -- If configlet with same name already exists
                     If parameter data structures are incorrect
      '''
      configlet = { 'config' : configletContent,
                    'name' : configletName
                  }
      self.doRequest( requests.post,
                        '%s/web/configlet/addConfiglet.do' % self.url,
                        data=json.dumps( configlet ) )

   def addGeneratedConfiglet( self, configletName, config, containerId, deviceMac,
                           builderId ):
      '''Adds the mapping between the generated configlets, containers and devices'''
      data = { "data" : {
                  "configlets" : [ {
                     "config" : config,
                     "name" : configletName,
                     "type" : "Generated" } ]
                     } }
      self.doRequest( requests.post,
                      '%s/web/configlet/addConfigletsAndAssociatedMappers.do'
                      % self.url, data=json.dumps( data ) )

      configletInfo = self.getConfigletByName( configletName )
      configletId = configletInfo[ 'key' ]
      data = { "data" : {
                  "generatedConfigletMappers" : [ {
                     "containerId" : containerId,
                     "configletId" : configletId,
                     "netElementId" : deviceMac,
                     "configletBuilderId" : builderId,
                     "action" : 'assign',
                     "previewValues" : [],
                     "previewValuesListSize": 0,
                     "objectType": None,
                     "key": ""
                     } ],
                  "configletMappers" : [ {
                     "objectId" : deviceMac,
                     "containerId" : None,
                     "configletId" : configletId,
                     "configletType": "Generated",
                     "type": "netelement"
                     } ] } }
      self.doRequest( requests.post,
                        '%s/web/configlet/addConfigletsAndAssociatedMappers.do'
                        % self.url, data=json.dumps( data ) )

   def addReconciledConfiglet( self, configletName, config, deviceMac ):
      '''Adds the mapping between the generated configlets, containers and devices'''
      data = { "data" : {
                  "configlets" : [ {
                     "config" : config,
                     "name" : configletName,
                     "type" : "Static",
                     "reconciled" : True
                     } ] } }
      self.doRequest( requests.post,
                      '%s/web/configlet/addConfigletsAndAssociatedMappers.do'
                      % self.url, data=json.dumps( data ) )

      configletInfo = self.getConfigletByName( configletName )
      configletId = configletInfo[ 'key' ]
      data = { "data" : {
                  "configletMappers" : [ {
                     "objectId" : deviceMac,
                     "containerId" : None,
                     "configletId" : configletId,
                     "configletType": "Static",
                     "type": "netelement"
                     } ] } }
      self.doRequest( requests.post,
                        '%s/web/configlet/addConfigletsAndAssociatedMappers.do'
                        % self.url, data=json.dumps( data ) )

   def addConfigletBuilder( self, configBuilderName, formList, mainScript ):
      '''Add configlet Builder to Cvp inventory
      Arguments:
         configletBuilder -- Information of the Configlet Builder to be
            added ( type : ConfigletBuilder( class ) )
      Raises:
         CvpError -- If Configlet Builder information format is invalid
      '''

      data = { "name" : configBuilderName,
               "data" : { "formList" : formList,
                          "main_script" : { 'data' : mainScript, 'key': None }
                        }
             }
      self.doRequest( requests.post,
                        '%s/web/configlet/addConfigletBuilder.do?isDraft=false'
                        % self.url, data=json.dumps( data ) )


   def deleteConfigletBuilder( self, configletBuilderKey ):
      '''Remove a configlet from the Cvp instance
      Arguments:
         configletBuilder -- Information of the Configlet Builder to be
            removed ( type : ConfigletBuilder( class ) )
      Raises:
         CvpError -- If Configlet Builder name or key is invalid
      '''
      self.doRequest( requests.post,
                        '%s/web/configlet/cancelConfigletBuilder.do?id=%s'
                        % ( self.url, configletBuilderKey ) )

   def getConfigletByName( self, configletName ):
      '''Get information about configlet
      Arguments:
         configName -- name of the configlet ( type : String )
      Returns:
         configlet -- information about the configlet ( type : Dict )
      Raises:
         CvpError -- If configlet name is invalid
                     If parameter data structures are incorrect
      '''
      configlet = self.doRequest( requests.get,
                                    '%s/web/configlet/getConfigletByName.do?name=%s'
                                    % ( self.url, configletName ) )
      return configlet

   def getConfigletMapper( self ):
      '''Retrieves the mapping between the configlets, devices and containers'''
      mapperInfo = self.doRequest( requests.get,
                        '%s/web/configlet/getConfigletsAndAssociatedMappers.do' %
                        self.url )
      return mapperInfo[ 'data' ]

   def updateConfiglet( self, configletName, configletContent, configletKey ):
      '''Update configlet information

      Arguments:
         configletName -- name of configlet( type : String )
         configletContent -- content of the configlet ( type : String )
         configletKey -- key assigned to the configlet ( type : String )
      Raises:
         CvpError -- If configlet key is invalid
                     If parameter data structures are incorrect
      '''
      configlet = { 'config' : configletContent,
                    'name' : configletName ,
                    'key' : configletKey
                  }
      self.doRequest( requests.post,
                        '%s/web/configlet/updateConfiglet.do' % ( self.url ),
                        data=json.dumps( configlet ) )

   def deleteConfiglet( self, configletName, configletKey ):
      '''Removes the configlet from Cvp instance
      Arguments:
         configletName -- name of the configlet ( type : String )
         configletKey -- Key assigned to the configlet ( type : String )
      Raises:
         CvpError -- If the configlet key is invalid
                     If parameter data structures are incorrect
      '''
      configlet = [ { 'key' : configletKey,
                      'name' : configletName
                    } ]
      self.doRequest( requests.post,
                        '%s/web/configlet/deleteConfiglet.do' % self.url,
                        data=json.dumps( configlet ) )

   def saveImageBundle( self, imageBundleName, imageBundleCertified,
         imageInfoList ):
      '''Add image bundle to Cvp instance.
      Arguments:
         imageBundleName -- Name of image Bundle ( type : String )
         imageBundleCertified -- image bundle certified ( type : bool )
         imageInfoList -- details of images present in image bundle
                          ( type : List of Dict )
      Raises:
         CvpError -- If image bundle name is invalid
                     If image details are invalid
                     If parameter data structures are incorrect
      '''
      data = { 'name' : imageBundleName,
               'isCertifiedImage' :  str( imageBundleCertified ).lower(),
               'images' : imageInfoList
             }
      self.doRequest( requests.post,
                        '%s/web/image/saveImageBundle.do' % self.url,
                        data=json.dumps( data ) )

   def getImageBundleByName( self, imageBundleName ):
      '''Returns image bundle informations
      Arguments:
         imageBundleName -- Name of the Image bundle ( type : String )
      Returns:
         imageBundle -- Complete information about the imagebundle ( type : Dict )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      imageBundle = self.doRequest( requests.get,
                                       '%s/web/image/getImageBundleByName.do?name=%s'
                                       % ( self.url, imageBundleName ) )
      return imageBundle

   def updateImageBundle( self, imageBundleName, imageBundleCertified,
                          imageInfoList, imageBundleKey ):
      '''Update image bundle information.

      Arguments:
         imageBundleName -- Name of image Bundle ( type : String )
         imageBundleCertified -- image bundle certified ( type : bool )
         imageInfoList -- details of images present in image bundle
                          ( type : List of dict )
         imageBundleKey -- key assigned to image bundle ( type : String )
      Raises:
         CvpError -- If image bundle name or key are invalid
                     If information of image to be mapped to image bundle is invalid
                     If parameter data structures are incorrect
      '''
      data = { 'name' : imageBundleName,
               'isCertifiedImage' :  str( imageBundleCertified ).lower(),
               'images' : imageInfoList,
               'id' : imageBundleKey
             }
      self.doRequest( requests.post,
                        '%s/web/image/updateImageBundle.do' % ( self.url ),
                        data=json.dumps( data ) )

   def addToInventory( self, deviceIpAddress, parentContainerName,
                       parentContainerId ):
      '''Add device to the Cvp inventory. Warning -- Method doesn't check the
      existance of the parent container

      Arguments:
         deviceIpAddress -- ip address of the device to be added ( type : String )
         parentContainerName -- name of parent container ( type : String )
         parentContainerId -- Id of parent container ( type : String )
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''

      data = { 'data' : [
                           { 'containerName' : parentContainerName,
                             'containerId' : parentContainerId,
                             'containerType' : 'Existing',
                             'ipAddress' : deviceIpAddress,
                             'containerList' : []
                           } ] }
      self.doRequest(requests.post,
                   '%s/web/inventory/add/addToInventory.do?startIndex=%d&endIndex=%d'
                   % ( self.url, 0, 0 ), data=json.dumps( data ) )

   def saveInventory( self ):
      '''Saves the current CVP inventory state
      '''
      self.doRequest( requests.post,
                        '%s/web/inventory/add/saveInventory.do' % ( self.url ) )

   def retryAddToInventory( self, deviceKey, deviceIpAddress, username,
                            password ):
      '''Retry addition of device to Cvp inventory

      Arguments:
         deviceKey -- mac address of the device ( type : String )
         deviceIpAddress -- ip address assigned to the device ( type : String )
         username -- username for device login ( type : String )
         password -- password for corresponding username ( type : String )
      Raises:
         CvpError -- If device  key is invalid
                     If parameter data structures are incorrect
      '''
      loginData = { "key" : deviceKey,
                    "ipAddress" : deviceIpAddress,
                    "userName" : username,
                    "password" : password
                  }
      self.doRequest( requests.post,
                   '%s/web/inventory/add/retryAddDeviceToInventory.do' %( self.url ),
                   data=json.dumps( loginData ) )

   def _saveTopology( self, data ):
      '''Schedule tasks for many operations like configlet and image bundle
      mapping/removal to/from device or container, addition/deletion of containers,
      deletion of device. Return a list of taskIds created in response to saving
      the topology.
      '''
      tasks = self.doRequest( requests.post,
                             '%s/web/ztp/v2/saveTopology.do' % ( self.url ),
                             data=json.dumps( data ) )
      return tasks[ 'data' ]

   def executeTask( self, taskId ):
      '''Execute particular task in Cvp instance
      Argument:
         taskId -- Work order Id of the task ( type : int )
      Raises:
         CvpError -- If work order Id of task is invalid
                     If parameter data structures are incorrect
      '''
      data = { 'data' : [ taskId ] }
      self.doRequest( requests.post,
                        '%s/web/workflow/executeTask.do' % ( self.url ),
                        data=json.dumps( data ) )

   def getTasks( self, status=None ):
      '''Retrieve information about all the tasks in Cvp Instance
      Arguments:
         status -- Filter the results by status
      Returns:
         tasks[ 'data' ] -- List of details of tasks ( type: dict of dict )
      '''
      status = '' if not status else status
      tasks = self.doRequest( requests.get,
                '%s/web/workflow/getTasks.do?queryparam=%s&startIndex=%d&endIndex=%d'
                % ( self.url, status, 0, 0 ) )
      return tasks[ 'data' ]

   def getImageBundles( self ):
      '''Get all details of all image bundles from Cvp instance
      Returns:
         imageBundles[ 'data' ] -- List of details of image bundles
                                   ( type: dict of dict )
      '''
      imageBundles = self.doRequest( requests.get,
              '%s/web/image/getImageBundles.do?queryparam=&startIndex=%d&endIndex=%d'
              % ( self.url, 0, 0 ) )
      return imageBundles[ 'data' ]

   def deleteImageBundle( self, imageBundleKey, imageBundleName ):
      '''Delete image bundle from Cvp instance
      Argument:
         imageBundleKey -- unique key assigned to image bundle ( type : String )
         imageBundleName -- name of the image bundle ( type : String )
      Raises:
         CvpError -- If image bundle key is invalid
                     If image bundle is applied to any entity
                     If parameter data structures are incorrect
      '''
      data = { 'data' :
                  [ { 'key' : imageBundleKey,
                      'name' : imageBundleName
                    } ] }
      self.doRequest( requests.post,
                        '%s/web/image/deleteImageBundles.do' % self.url,
                        data=json.dumps( data ) )

   def deleteTempDevice( self, tempDeviceId ):
      '''Delete a device that's not completely added, but in a temporary state.
      The states we know of are: Connecting, Unauthorized access, Duplicate, Retry,
      Upgrade required.
      Warning -- This method doesn't check for presence of the device.

      Argument:
         tempDeviceId -- temporary Id assigned to device ( type : String )
      Raises:
         CvpError -- If parameter data structures are inconsistent
      '''

      self.doRequest( requests.get,
                        '%s/web/inventory/add/deleteFromInventory.do?netElementId=%s'
                        % ( self.url, tempDeviceId ) )

   def deleteContainer( self, containerName, containerKey, parentContainerName,
                        parentKey ):
      '''Delete container from Cvp inventory. Warning -- doesn't check
      existance of the parent containers

      Arguments:
         containerName -- name of the container (type: string)
         containerKey -- unique key assigned to container (type: string)
         parentContainerName -- parent container name (type: string)
         parentKey -- unique key assigned to parent container (type: string)
      Raises:
         CvpError -- If container key is invalid
                     If parameter data structures are incorrect
      '''

      data = { "data" : [ { "id" : 1,
                 "info" : "Container " + containerName + " deleted",
                 "action" : "delete",
                 "nodeType" : "container",
                 "nodeId" : containerKey,
                 "toId" : "",
                 "fromId" : parentKey,
                 "nodeName" : containerName,
                 "fromName" : parentContainerName,
                 "toName" : "",
                 "childTasks" : [],
                 "parentTask" : "",
                 "toIdType" : "container"
               } ] }
      self._addTempAction( data )
      self._saveTopology( [] )

   def getContainerInfo( self, containerKey ):
      '''Retrieves information about the container'''
      containerInfo = self.doRequest( requests.get,
                        '%s/web/provisioning/getContainerInfoById.do?containerId=%s'
                        % ( self.url, containerKey ) )
      return containerInfo

   def deleteDevice( self, deviceKey, parentContainerName, containerKey ):
      '''Delete the device from Cvp inventory
      Warning -- doesn't check the existence of the parent container

      Arguments:
         deviceKey -- mac address of the device (type: string)
         parentContainerName -- name of parent container of device (type: string)
         containerKey -- Key assigned to parent container (type: string)
      Raises:
         CvpError -- If device key is invalid
                     If parameter data structures are incorrect
      '''
      data = { "data" : [ { "id" : 1,
                 "info" : "Device Remove: undefined - To be Removed from"
                    "Container"  + parentContainerName,
                 "infoPreview" : "<b>Device Remove: undefined<b> - To be Removed "
                    "from Container" + parentContainerName,
                 "note" : "",
                 "action" : "remove",
                 "nodeType" : "netelement",
                 "nodeId" : deviceKey,
                 "toId" : "",
                 "fromId" : containerKey,
                 "fromName" : parentContainerName,
                 "toName" : "",
                 "childTasks" : [],
                 "parentTask" : "",
                 "toIdType" : "container"
               } ] }
      self._addTempAction( data )
      self._saveTopology( [] )

   def applyConfigletToDevice( self, deviceIpAddress, deviceFqdn, deviceMac,
                               cnl, ckl ):
      '''Applies configlets to device. Warning -- Method doesn't check existence of
      configlets

      Arguments:
         deviceIpAddress -- Ip address of the device (type: string)
         deviceFqdn -- Fully qualified domain name for device (type: string)
         deviceKey -- mac address of the device (type: string)
         cnl -- List of name of configlets to be applied
         (type: List of Strings)
         ckl -- Keys of configlets to be applied (type: List of Strings)
      Raises:
         CvpError -- If device ip key is invalid
                     If parameter data structures are incorrect
      '''
      data = { "data" : [ {
                 "info" : "Configlet Assign: to Device" + deviceFqdn +
                    " \nCurrent ManagementIP:" + deviceIpAddress +
                    "  \nTarget ManagementIP",
                 "infoPreview" : "<b>Configlet Assign:</b> to Device" + deviceFqdn,
                 "action" : "associate",
                 "nodeType" : "configlet",
                 "nodeId" : None,
                 "toId" : deviceMac,
                 "toIdType" : "netelement",
                 "fromId" : None,
                 "nodeName" : None,
                 "fromName" : None,
                 "toName" : deviceFqdn,
                 "nodeIpAddress" : deviceIpAddress,
                 "nodeTargetIpAddress" : deviceIpAddress,
                 "configletList" : ckl,
                 "configletNamesList" : cnl,
                 "ignoreConfigletList" : [],
                 "ignoreConfigletNamesList" : [],
                 "configletBuilderList" : [],
                 "configletBuilderNamesList" : [],
                 "ignoreConfigletBuilderList" : [],
                 "ignoreConfigletBuilderNamesList": []
               } ] }
      self._addTempAction( data )
      self._saveTopology( [] )

   def applyConfigletToContainer( self, containerName, containerKey, cnl, ckl, cbnl,
                                  cbkl ):
      '''Applies configlets to container. Warning -- Method doesn't check existence
      of container and the configlets

      Arguments:
         containerName --name of the container (type: string)
         containerKey -- unique key assigned to container (type: string)
         cnl -- List of name of configlets to be applied
         (type: List of Strings)
         ckl -- Keys of configlets to be applied (type: List of Strings)
         cbnl -- List of name of configlet builders to be applied
         (type: List of Strings)
         cbkl -- Keys of configlet builders to be applied (type: List of Strings)
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      data = { "data" : [ {
                 "info" : "Configlet Assign: to container " + containerName,
                 "infoPreview" : "<b>Configlet Assign:</b> to container " +
                    containerName,
                 "action" : "associate",
                 "nodeType" : "configlet",
                 "nodeId" : "",
                 "toId" : containerKey,
                 "toIdType" : "container",
                 "fromId" : "",
                 "nodeName" : "",
                 "fromName" : "",
                 "toName" : containerName,
                 "configletList" : ckl,
                 "configletNamesList" : cnl,
                 "ignoreConfigletList" : [],
                 "ignoreConfigletNamesList" : [],
                 "configletBuilderList" : cbkl,
                 "configletBuilderNamesList" : cbnl,
                 "ignoreConfigletBuilderList" : [],
                 "ignoreConfigletBuilderNamesList": []
               } ] }
      self._addTempAction( data )
      self._saveTopology( [] )

   def _addTempAction( self, data ):
      '''Add temporary action to the cvp instance'''
      self.doRequest( requests.post,
                      '%s/web/ztp/addTempAction.do?format=topology&queryParam=&'
                      'nodeId=root' % self.url, data=json.dumps( data ) )

   def removeConfigletFromContainer( self, containerName, containerKey,
                                     configNameList, configKeyList ):
      '''Remove configlets assigned to container. Warning -- Method doesn't check
      existence of configlets and containers

      Arguments:
         containerName --name of the container (type: string)
         containerKey -- unique key assigned to container (type: string)
         configNameList -- List of name of configlets to be removed
         (type: List of Strings)
         configKeyList -- Keys of configlets to be removed (type: List of Strings)
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''

      data = { "data" :
               [ { "id" : 1,
                   "info" : "Configlet Removal: from container " + containerName,
                   "infoPreview" : "<b>Configlet Removal:</b> from container " +
                      containerName + "Current ManagementIP : undefined\nTarget"
                      " ManagementIPundefined",
                   "note" : "",
                   "action" : "associate",
                   "nodeType" : "configlet",
                   "nodeId" : '',
                   "configletList" : [],
                   "configletNamesList" : [],
                   "configletBuilderList" : [],
                   "configletBuilderNameList" : [],
                   "ignoreConfigletList": configKeyList,
                   "ignoreConfigletNamesList" : configNameList,
                   "ignoreConfigletBuilderList" : [],
                   "ignoreConfigletBuilderNameList" : [],
                   "toId" : containerKey,
                   "toIdType" : "container",
                   "fromId" : '',
                   "nodeName" : '',
                   "fromName" : '',
                   "toName" : containerName,
                   "childTasks" : [],
                   "parentTask" : ""
                 } ] }
      self._addTempAction( data )
      self._saveTopology( [] )

   def addContainer( self, containerName, containerParentName,
                     parentContainerId ):
      '''Adds container to Cvp inventory
      Arguments:
         containerName -- name of container (type: string)
         containerParentName -- name of the parent container (type: string)
         parentContainerId -- Id of parent container (type: string)
      Raises:
         CvpError -- If container with same name already exists,
                     If Parent Id is invalid
                     If parameter data structures are incorrect
      '''


      data = { 'data' : [  {
                 "info" : "Container " + containerName + " created",
                 "infoPreview" : "Container " + containerName + " created",
                 "action" : "add",
                 "nodeType" : "container",
                 "nodeId" : "New_container1",
                 "toId" : parentContainerId,
                 "fromId" : "",
                 "nodeName" : containerName,
                 "fromName" : "",
                 "toName" : containerParentName,
                 } ] }
      self._addTempAction( data )
      self._saveTopology( [] )

   def applyImageBundleToDevice( self, deviceKey, deviceFqdn, imageBundleName,
                                 imageBundleKey ):
      '''Applies image bundle to devices. Warning -- Method doesn't check existence
      of image bundle

      Arguments:
         deviceKey -- mac address of device (type: string)
         deviceFqdn -- Fully qualified domain name for device (type: string)
         imageBundleName -- name of image bundle (type: string)
         imageBundleKey -- unique key assigned to image bundle (type: string)
      Raises:
         CvpError -- If device key is invalid,
                     If parameter data structures are incorrect
      '''

      data = [ { "id" : 1,
                 "info" : "Image Bundle Assign:" + imageBundleName + " - To be "
                    "assigned to Device " + deviceFqdn,
                 "infoPreview" : "<b>Image Bundle Assign:</b>" +
                    imageBundleName + " - To be assigned to Device" + deviceFqdn,
                 "note" : "",
                 "action" : "associate",
                 "nodeType" : "imagebundle",
                 "nodeId" : imageBundleKey,
                 "toId" : deviceKey,
                 "toIdType" : "netelement",
                 "fromId" : "",
                 "nodeName" : imageBundleName,
                 "fromName" : "",
                 "toName" : deviceFqdn,
                 "childTasks" : [],
                 "parentTask" : ""
               } ]
      self._saveTopology( data )

   def applyImageBundleToContainer( self, containerName, containerKey,
                                    imageBundleName, imageBundleKey ):
      '''Applies image bundle to a container. Warning -- Method doesn't check
      existence of container and image bundle

      Arguments:
         containerName -- name of the container (type: string)
         containerKey -- unique key assigned to container (type: string)
         imageBundleName -- name of the image bundle (type: string)
         imageBundleKey -- unique key assigned to image bundle (type: string)
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''

      data = [ { "id" : 1,
                 "info" : "Image Bundle Assign:" + imageBundleName + " - To be"
                    " assigned to devices under Container" + containerName,
                 "infoPreview" : "<b>Image Bundle Assign:</b>" + imageBundleName +
                    "- To be assigned to devices under Container" + containerName,
                 "action" : "associate",
                 "nodeType" : "imagebundle",
                 "nodeId" : imageBundleKey,
                 "toId" : containerKey,
                 "toIdType" : "container",
                 "fromId" : "",
                 "nodeName" : imageBundleName,
                 "fromName" : "",
                 "childTasks" : [],
                 "parentTask" : ""
               } ]
      self._saveTopology( data )

   def removeImageBundleAppliedToContainer( self, containerName, containerKey,
                                            imageBundleName, imageBundleKey ):
      '''Removes image bundles applied to the container.
      Arguments:
         containerName -- name of the container (type: string)
         containerKey -- unique key assigned to container (type: string)
         imageBundleName -- name of the image bundle (type: string)
         imageBundleKey -- unique key assigned to image bundle (type: string)
      Raises:
         CvpError -- If parameter data structures are incorrect
      '''
      data = [ { "info" : "Image Bundle Removal: from  container " + containerName,
                 "infoPreview" : "<b>Image Bundle Removal:</b> from container  "
                    + containerName,
                 "action" : "associate",
                 "nodeType" : "imagebundle",
                 "nodeId" : "",
                 "toId" : containerKey,
                 "fromId" : "",
                 "nodeName" : "",
                 "fromName" : "",
                 "toName" : containerName,
                 "toIdType" : "container",
                 "ignoreNodeId" : imageBundleKey,
                 "ignoreNodeName" : imageBundleName
               } ]
      self._saveTopology( data )

   def autoConfigletGenerator( self, devKey, cbKey, cbName, conKey ):
      ''' Generates configlet using the builder for the device
      Note: Doesn't work for manual configlet builders.

      Arguments:
         devKey -- key of device.
         cbKey -- key of the configlet builder
         cbName -- Name of the configlet builder
         conKey -- key of the parent container
      Returns:
         cInfo -- information on the generated configlets
      Raises:
         CvpError -- If failure occurs while generating the configlets
      '''
      data = {
               "netElementIds" : [ devKey ],
               "configletBuilderId" : cbKey,
               "containerId" : conKey,
               "pageType" : "netelementManagement"
               }
      cInfo = self.doRequest( requests.post,
                             '%s/web/configlet/autoConfigletGenerator.do' % self.url,
                             data=json.dumps( data ) )
      if 'pythonError' in cInfo[ 'data' ][ 0 ]:
         print ( 'error generating configlet using %s configlet builder' %
                  cbName )
         raise CvpError( errorCodes.CONFIGLET_GENERATION_ERROR,
                         str( cInfo[ 'data' ][ 0 ][ 'pythonError' ] ) )
      return cInfo

   def deployDevice( self, devKey, devFqdn, devIp, devTargetIp,
                     containerKey, containerName, configletKeyList=None,
                     configletNameList=None, configletBuilderKeys=None,
                     configletBuilderNames=None, imageBundleKey=None,
                     imageBundleName=None ):
      ''' Move a device from the undefined container to a target container.
      Optionally, applying device-specific configlets and an image to the
      device.

      Arguments:
         devKey -- unique key for the device
         devFqdn -- fqdn for the device
         devIp -- Current IP address of the device
         devTargetIp -- IP address of the device after configlets are applied
         containerKey -- unique key for the target container
         containerName -- name of the target container
         configletKeyList -- optional, list of keys for device-specific configlets
         configletNameList -- optional, list of names of device-specific configlets
         configletBuilderKeys --optional, list of key of configlet builders
         configletBuilderNames --optional, list of name of configlet builders
         imageKey -- optional, unique key for the image
         imageName -- optional, name of the image

      Returns:
         ( taskId, description )
      '''
      # generate a transaction ID and stuff it into the task info. This allows
      # us to find this task later
      transId = 'Automated Task ID: %s' % str( uuid.uuid1() )
      try:
         # move the device to target container
         data = { "data":
               [ { "info" : transId,
                   "infoPreview" : transId,
                   "action" : "update",
                   "nodeType" : "netelement",
                   "nodeId" : devKey,
                   "toId" : containerKey,
                   "fromId" : "undefined_container",
                   "nodeName" : devFqdn,
                   "toName" : containerName,
                   "toIdType" : "container" } ] }
         self.doRequest( requests.post,
               '%s/web/ztp/addTempAction.do?format=topology&queryParam=&nodeId=%s' %
               ( self.url, 'root' ), data=json.dumps( data ), cookies=self.cookies )

         # get hierarchial configlet builders list
         cblInfoList = self.doRequest( requests.get,
               '%s/web/configlet/getHierarchicalConfigletBuilders.do?containerId=%s'
               '&queryParam=&startIndex=%d&endIndex=%d' % ( self.url, containerKey,
               0, 0 ) )

         # generate configlets for the device using these configlet builders
         ckl = []
         cnl = []
         cbkl = []
         cbnl = []

         for cb in cblInfoList[ 'buildMapperList' ]:
            cbkl.append( cb[ 'builderId' ] )
            cbnl.append( cb[ 'builderName' ] )
            #skip the manual configlet builders
            if self.getConfigletBuilder( cb[ 'builderId' ] )[ 'formList' ]:
               continue
            cbInfo = self.autoConfigletGenerator( devKey, cb[ 'builderId' ],
                                                  cb[ 'builderName' ], containerKey )
            ckl.append( cbInfo[ 'data' ][ 0 ][ 'configlet' ][ 'key' ] )
            cnl.append( cbInfo[ 'data' ][ 0 ][ 'configlet' ][ 'name' ] )

         # get configlets applied to the parent container
         cinfoList = self.getContainerConfiglets( containerKey )

         for configlet in cinfoList:
            if configlet[ 'type' ] == 'static':
               ckl.append( configlet[ 'key' ] )
               cnl.append( configlet[ 'name' ] )
            elif configlet[ 'type' ] == 'Builder':
               if configlet[ 'key' ] not in cbkl:
                  cbkl.append( configlet[ 'key' ] )
                  cbkl.append( configlet[ 'name' ] )

         #apply the configlets to the device through container on netelement
         # management page
         data = { "data" :
                  [ { "info" : transId,
                      "infoPreview" : transId,
                      "action" : "associate",
                      "nodeType" : "configlet",
                      "nodeId" : None,
                      "toId" : containerKey,
                      "fromId" : None,
                      "nodeName" : None,
                      "fromName" : None,
                      "toName" : containerName,
                      "toIdType" : "container",
                      "configletList" : ckl,
                      "configletNamesList": cnl,
                      "ignoreConfigletList":[],
                      "ignoreConfigletNamesList":[],
                      "configletBuilderList" : cbkl,
                      "configletBuilderNamesList": cbnl,
                      "ignoreConfigletBuilderList":[],
                      "ignoreConfigletBuilderNamesList":[],
                      "pageType":"netelementManagement"
                    } ] }
         self.doRequest( requests.post,
               '%s/web/ztp/addTempAction.do?format=topology&queryParam=&nodeId=%s' %
               ( self.url, 'root' ), data=json.dumps( data ), cookies=self.cookies )

         #get the proposed list of configlet for the device at the target container
         configlets = self.doRequest( requests.get,
                      '%s/web/ztp/getTempConfigsByNetElementId.do?netElementId=%s' %
                      ( self.url, devKey ), cookies=self.cookies )
         ckl = []
         cnl = []
         for p in configlets[ 'proposedConfiglets' ]:
            if p[ 'type' ] == 'Static' or p[ 'type' ] == 'Generated':
               ckl.append( p[ 'key' ] )
               cnl.append( p[ 'name' ] )

         # Generate device specific configlet using the provided non hierarchal
         # configlet builders
         cbNum = 0
         if configletBuilderKeys and configletBuilderNames:
            for key in configletBuilderKeys:
               if key not in cbkl:
                  cbInfo = self.autoConfigletGenerator( devKey, key,
                              configletBuilderNames[ cbNum ],containerKey )
                  ckl.append( cbInfo[ 'data' ][ 0 ][ 'configlet' ][ 'key' ] )
                  cnl.append( cbInfo[ 'data' ][ 0 ][ 'configlet' ][ 'name' ] )
                  cbNum += 1

         # add the provided device specific configlets
         if configletKeyList and configletNameList:
            ckl.extend( configletKeyList )
            cnl.extend( configletNameList )

         # apply all these configlets to device
         data = { "data" : [ {
                     "info" : transId,
                     "infoPreview" : transId,
                     "action" : "associate",
                     "nodeType" : "configlet",
                     "nodeId" : None,
                     "toId" : devKey,
                     "fromId" : None,
                     "nodeName" : None,
                     "fromName" : None,
                     "toName" : devFqdn,
                     "toIdType" : "netelement",
                     "configletList": ckl,
                     "configletNamesList" : cnl,
                     "ignoreConfigletList":[],
                     "ignoreConfigletNamesList":[],
                     "configletBuilderList": cbkl,
                     "configletBuilderNamesList" : cbkl,
                     "ignoreConfigletBuilderList":[],
                     "ignoreConfigletBuilderNamesList":[],
                     "nodeIpAddress" : devIp,
                     "nodeTargetIpAddress" : devTargetIp,
                     } ] }
         self.doRequest( requests.post,
               '%s/web/ztp/addTempAction.do?format=topology&queryParam=&nodeId=%s' %
               ( self.url, 'root' ), data=json.dumps( data ), cookies=self.cookies )

         # apply image to the device
         if imageBundleKey:
            data = { "data":
                  [ { "info" : transId,
                     "infoPreview" : transId,
                     "action" : "associate",
                     "nodeType" : "imagebundle",
                     "nodeId" : imageBundleKey,
                     "toId" : devKey,
                     "fromId" : None,
                     "nodeName" : imageBundleName,
                     "fromName" : None,
                     "toName" : devFqdn,
                     "toIdType" : "netelement",
                     "ignoreNodeId" : None,
                     "ignoreNodeName" : None,
                    } ] }
            self.doRequest( requests.post,
               '%s/web/ztp/addTempAction.do?format=topology&queryParam=&nodeId=%s' %
               ( self.url, 'root' ), data=json.dumps( data ), cookies=self.cookies )

         # save all changes to the device and return the task list
         return self._saveTopology( [] )

      except:
         self.doRequest( requests.delete,
                          '%s/web/ztp/deleteAllTempAction.do' % self.url,
                           cookies=self.cookies )
         # try and clean up the transaction before passing the exception back to
         # the caller
         raise

   def cancelTask( self, taskId ):
      ''' Cancel a task
      Arguments:
         taskId -- the task to cancel
      '''
      self.doRequest( requests.post,
                       '%s/web/task/cancelTask.do' % self.url,
                        cookies=self.cookies, data=str( taskId ) )

   def addNoteToTask( self, taskId, note ):
      ''' Add a note to a task
      Arguments:
         taskId - the task add a note to
         note - the note to add to the task
      '''
      self.doRequest( requests.post,
                       '%s/web/task/addNoteToTask.do' % self.url,
                       cookies=self.cookies,
                       data=json.dumps( { 'workOrderId' : taskId, 'note' : note } ) )

   def getTaskById( self, tid ):
      ''' Get info for a task '''
      return self.doRequest( requests.get,
                          '%s/web/task/getTaskById.do?taskId=%d' % ( self.url, tid ),
                           cookies=self.cookies )

   def cvpVersionInfo( self ):
      ''' Finds the current version of CVP'''
      version = self.doRequest( requests.get,
                                '%s/web/cvpInfo/getCvpInfo.do' % self.url,
                                cookies=self.cookies )
      return version[ 'version' ]

   def getUsers( self ):
      ''' Retrieves information about all the users '''
      return self.doRequest( requests.get,
                      '%s/web/user/getUsers.do?queryparam=&startIndex=%d&endIndex=%d'
                      % ( self.url, 0, 0 ), cookies=self.cookies )

   def getUser( self, userName ):
      '''Retrieves infomation about a particular user'''
      return self.doRequest( requests.get,
                             '%s/web/user/getUser.do?userId=%s' % ( self.url,
                             userName ) )

   def getRoles( self ):
      ''' Retrieves information about all the roles'''
      roles = self.doRequest( requests.get,
                  '%s/web/role/getRoles.do?queryParam=null&startIndex=%d&endIndex=%d'
                  % ( self.url, 0, 0 ), cookies=self.cookies )
      roles = roles[ 'roles' ]
      roleList = []
      for role in roles:
         for module in role[ 'moduleList' ]:
            module.pop( "factoryId" )
            module.pop( "id" )
         roleInfo = {}
         roleInfo[ 'name' ] = role[ 'name' ]
         roleInfo[ 'key' ] = role[ 'key' ]
         roleInfo[ 'description' ] = role[ 'description' ]
         roleInfo[ 'moduleList' ] = role[ 'moduleList' ]
         roleList.append( roleInfo )
      return roleList

   def addRole( self, roleName, roleModuleList ):
      ''' Add a Role to the Cvp instance '''
      data = { "name" : roleName,
               "moduleList" : roleModuleList }
      self.doRequest( requests.post,
                     '%s/web/role/createRole.do' % self.url, data=json.dumps( data ),
                     cookies=self.cookies )

   def getRole( self, roleId ):
      '''Retrieves information about a particular role with Id as roleId'''
      return self.doRequest( requests.get, '%s/web/role/getRole.do?roleId=%s'
                             % ( self.url, roleId ), cookies=self.cookies )

   def updateRole( self, roleName, description, moduleList, roleKey ):
      ''' Updates the information about the role'''
      data = { "key" : roleKey,
               "name" : roleName,
               "description" : description,
               "moduleList" : moduleList
             }
      self.doRequest( requests.post,
                     '%s/web/role/updateRole.do' % self.url, data=json.dumps( data ),
                     cookies=self.cookies )

   def deleteRole( self, roleKey ):
      '''Deletes the roles from the cvp instance'''
      data = [ roleKey ]
      self.doRequest( requests.post, '%s/web/role/deleteRoles.do' % self.url,
                      data=json.dumps( data ) )

   def updateConfigletBuilder( self, ConfigletBuilderName, formList, mainScript,
                               configletBuilderKey ):
      ''' Updates the existing Configlet Builder'''
      data = { "name" : ConfigletBuilderName,
               "data" : { "formList" : formList,
                          "main_script" : { 'data' : mainScript, 'key': None }
                        }
             }
      self.doRequest( requests.post,
                      '%s/web/configlet/updateConfigletBuilder.do?isDraft=false&'
                      'id=%s' % ( self.url, configletBuilderKey ),
                      data=json.dumps( data ), cookies=self.cookies )

   def getContainerConfiglets( self, containerId ):
      ''' retrieves the list of configlets applied to the container'''
      resp = self.doRequest( requests.get,
                             '%s/web/provisioning/getConfigletsByContainerId.do?'
                             'containerId=%s&queryParam=&startIndex=%d&endIndex=%d'
                             % ( self.url, containerId, 0, 0 ) )
      return resp[ 'configletList' ]

   def getDeviceConfiglets( self, deviceMac ):
      '''retrieves the list of configlets applied to the device'''
      resp = self.doRequest( requests.get,
                             '%s/web/provisioning/getConfigletsByNetElementId.do?'
                             'netElementId=%s&queryParam=&startIndex=%d&endIndex=%d'
                             % ( self.url, deviceMac, 0, 0 ) )
      return resp[ 'configletList' ]

   def getDeviceTempConfiglets( self, deviceMac ):
      '''retireves the set of configlets inherited by the device from the congtainer
      '''
      resp = self.doRequest( requests.get,
                                   '%s/web/ztp/getTempConfigsByNetElementId.do?'
                                   'netElementId=%s' % ( self.url, deviceMac ) )
      return resp[ 'proposedConfiglets' ]

