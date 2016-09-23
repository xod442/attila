#!/usr/bin/env python
'''
2016 wookieware.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.


__author__ = "@netwookie"
__credits__ = ["Rick Kauffman"]
__license__ = "Apache2"
__version__ = "1.0.0"
__maintainer__ = "Rick Kauffman"
__email__ = "rick@rickkauffman.com"
__status__ = "Prototype"

test connectivity to the CSV API

'''
import cvp
import json
host = '10.132.0.117'
user ='cvpadmin'
password = 'Grape123'
ip = '10.132.0.7'
fqdn='lab.local'
mac = '00-00-00-00-00-00'
contain ='Wookieware'
cont_id =''
img = ''
configlets = []
server = cvp.Cvp(host)
server.authenticate(user,password)

list = []

result = cvp.Device(ip,fqdn,mac,contain,img,configlets)
print type(result)
print ( dir(result) )
print result.fqdn

devices = server.getDevices()
print type(devices)

for dev in devices:
	ip = dev.ipAddress
	mac = dev.macAddress
	img = dev.imageBundle
	fqdn = dev.fqdn
	c_name = dev.containerName
	letz = dev.configlets
	list = [ip,mac,img,fqdn,c_name,letz]
	print list
