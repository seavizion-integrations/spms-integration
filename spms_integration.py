#!/usr/bin/env python3
import subprocess
import sys
import json

installed_dependencies = subprocess.check_output([sys.executable, '-m', 'pip', 'install', '-r', 'python_dependencies.ini']).decode().strip()
if 'Successfully installed' in installed_dependencies:
    raise Exception('Some required dependent libraries were installed. ' \
                    'Module execution has to be terminated now to use installed libraries on the next scheduled launch.')

import json
import os
import onevizion
#import shutil
#import pysftp
import sys
from sftpmanager import SFTPManager

# Read settings
with open('settings','r') as p:
	params = json.loads(p.read())

try:
	OvUserName = params['OV']['UserName']
	OvPassword = params['OV']['Password']
	OvUrl      = params['OV']['Url']
	SftpHost   = params['SFTP']['Host']
	SftpUN     = params['SFTP']['UserName']
	SftpPWD    = params['SFTP']['Password']
	SftpKEY    = params['SFTP']['Key']
	SftpInDir  = params['SFTP']['InboundDirectory']
	SftpOutDir = params['SFTP']['OutboundDirectory']
except Exception as e:
	raise "Please check settings"


class MyCnOpts:  #used by sftp connection
	pass

# connect to SFTP
try:
	sftp = SFTPManager(SftpHost, SftpUN, password=SftpPWD, private_key=SftpKEY)
	'''	#not best practice, but avoids needing entry in .ssh/known_hosts
	#from Joe Cool near end of https://bitbucket.org/dundeemt/pysftp/issues/109/hostkeysexception-no-host-keys-found-even
	cnopts = MyCnOpts()
	cnopts.log = False
	cnopts.compression = False
	cnopts.ciphers = None
	cnopts.hostkeys = None
	print(len(SftpPWD))

	if len(SftpPWD) > 0:
		sftp = pysftp.Connection(SftpHost,
			username=SftpUN,
			password=SftpPWD,
			cnopts = cnopts
			)
	else:
		onevizion.Message('kilroy was here')
		#cnopts = pysftp.CnOpts()
		#cnopts.hostkeys = None
		with open('key.txt', 'w') as the_file:
			the_file.write(SftpKEY)

		sftp = pysftp.Connection(SftpHost,
			username=SftpUN,
			private_key='key.txt',
			cnopts = cnopts
			)'''
except:
	onevizion.Message('could not connect')
	onevizion.Message(sys.exc_info())
	quit(1)

# make sure api user has RE on the tab with checkbox and the field list of blobs and RE for the trackor type(sometimes Checklist) and R for WEB_SERVICES 
Req = onevizion.Trackor(trackorType = 'SPMSINTERFACE', URL = OvUrl, userName=OvUserName, password=OvPassword)
Req.read(filters = {'SI_READY_FOR_DELIVERY': 1}, 
		fields = ['TRACKOR_KEY','SI_READY_FOR_DELIVERY','SI_INTERFACE_FILE'], 
		sort = {'TRACKOR_KEY':'ASC'}, page = 1, perPage = 1000)

if len(Req.errors)>0:
	# If can not read list of efiles then must be upgrade or something.  Quit and try again later.
	print(Req.errors)
	print ('kilroy was here 2')
	quit(1)

# send files to Outbound directory
for f in Req.jsonData:
	f1 = open(f['TRACKOR_KEY'],'w')
	f1.write(f['SI_INTERFACE_FILE'])
	f1.close()
	print ('kilroy was here 3')
	sftp.upload(f['TRACKOR_KEY'], SftpOutDir+'/'+f['TRACKOR_KEY'])
	#with sftp.cd(SftpOutDir) :
	##	s.put(SftpOutDir+"/"+f['TRACKOR_KEY'])
	#	sftp.put(f['TRACKOR_KEY'])

	print ('kilroy was here 4')
	Req.update(filters = {'TRACKOR_ID': f['TRACKOR_ID']}, fields = {'SI_READY_FOR_DELIVERY': 0})
	os.remove(f['TRACKOR_KEY'])

# get complete list of files in directory
for f in sftp.list_directory(SftpInDir):
	if f in ['Archive','100_202011021753_JY.csv']:
		continue
	print(f'getting {f}')
	sftp.retrieve(SftpInDir+'/'+f, f)
	with open(f,'r') as x:
		interface_file = x.read()
	print ('kilroy was here 6')
	Req.create(fields = {"TRACKOR_KEY": f, 'SI_INTERFACE_FILE': interface_file})
	if len(Req.errors)==0:
		try:
			sftp.delete(SftpInDir+'/Archive/'+f)
		except:
			pass # file should not be there, but if it is, we will move it to archive and delete local copy
		sftp.move(SftpInDir+'/'+f, SftpInDir+'/Archive/'+f)
	print ('kilroy was here 7')
	os.remove(f)

print ('kilroy was here 8')

sftp.disconnect()
