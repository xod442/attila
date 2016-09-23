# Copyright (c) 2015 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.
'''
@Copyright: 2015-2016 Arista Networks, Inc.
Arista Networks, Inc. Confidential and Proprietary.

Error codes for the cvp python APIs
'''

NO_ERROR_CODE = 0
UNKNOWN_ERROR_CODE = 1
UNKNOWN_REQUEST_RESPONSE = 2
INVALID_ARGUMENT = 3
TIMEOUT = 4
TASK_EXECUTION_ERROR = 5
INVALID_CONFIGLET_NAME = 1002
INVALID_CONFIGLET_TYPE = 1003
CONFIGLET_GENERATION_ERROR = 1004
INVALID_IMAGE_BUNDLE_NAME = 2002
INVALID_IMAGE_ADDITION = 2003
INVALID_CONTAINER_NAME = 3002
DEVICE_ALREADY_EXISTS = 4001
DEVICE_LOGIN_UNAUTHORISED = 4002
DEVICE_INVALID_LOGIN_CREDENTIALS = 4003
DEVICE_CONNECTION_ATTEMPT_FAILURE = 4005
INVALID_IMAGE_NAME = 5001
INVALID_ROLE_NAME = 6001
USER_UNAUTHORISED = 122401
DATA_ALREADY_EXISTS = 122518
CONFIGLET_ALREADY_EXIST = 132518
ENTITY_DOES_NOT_EXIST = 132801
CONFIG_BUILDER_ALREADY_EXSIST = 132823
IMAGE_BUNDLE_ALREADY_EXIST = 162518
CANNOT_DELETE_IMAGE_BUNDLE = 162854
ROLE_ALREADY_EXISTS = 232518

ERROR_MAPPING = { NO_ERROR_CODE : "No error code provided",
                  UNKNOWN_ERROR_CODE : "Unknown error code",
                  TASK_EXECUTION_ERROR : "Task did not complete",
                  UNKNOWN_REQUEST_RESPONSE : "Request response is not Json" ,
                  INVALID_ARGUMENT : "Unsupported parameter type" ,
                  TIMEOUT : "Timeout" ,
                  INVALID_CONFIGLET_NAME : "Invalid Configlet name",
                  INVALID_CONFIGLET_TYPE : "Configlet type is not correct",
                  CONFIGLET_GENERATION_ERROR : "Unable to generate configlet using"
                     " configlet builder",
                  INVALID_IMAGE_BUNDLE_NAME : "Invalid Image Bundle name",
                  INVALID_IMAGE_ADDITION : "Image name or directory path containing"
                     " image is incorrect",
                  INVALID_CONTAINER_NAME : "Invalid container name",
                  DEVICE_ALREADY_EXISTS : "Device already exists",
                  DEVICE_LOGIN_UNAUTHORISED : "User unauthorised to login into the"
                     " device",
                  DEVICE_INVALID_LOGIN_CREDENTIALS : "Incorrect device login"
                     " credentials",
                  DEVICE_CONNECTION_ATTEMPT_FAILURE : "Failure to setup connection"
                     " with device",
                  INVALID_IMAGE_NAME : "Invalid Image Name",
                  INVALID_ROLE_NAME : "Invalid Role Name",
                  USER_UNAUTHORISED : "User unauthorised to perform this action",
                  CONFIGLET_ALREADY_EXIST : "Configlet already exists ",
                  CONFIG_BUILDER_ALREADY_EXSIST : "Configlet Builder already exists",
                  IMAGE_BUNDLE_ALREADY_EXIST : "Image bundle already exists",
                  ROLE_ALREADY_EXISTS : "Role already exists ",
                  CANNOT_DELETE_IMAGE_BUNDLE : "image bundle is applied to object in"
                     " cvp",
                  DATA_ALREADY_EXISTS : "Data already exists in Database",
                  ENTITY_DOES_NOT_EXIST: "Entity does not exist",
                }

