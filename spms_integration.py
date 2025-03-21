#!/usr/bin/env python3

import json
import os
import onevizion
import shutil
import pysftp
import sys

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
	#not best practice, but avoids needing entry in .ssh/known_hosts
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
			)
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

# send files to Inbound directory
for f in Req.jsonData:
	f1 = open(f['TRACKOR_KEY'],'w')
	f1.write(f['SI_INTERFACE_FILE'])
	f1.close()
	print ('kilroy was here 3')
	with sftp.cd(SftpOutDir) :
	#	s.put(SftpOutDir+"/"+f['TRACKOR_KEY'])
		sftp.put(f['TRACKOR_KEY'])

	print ('kilroy was here 4')
	Req.update(filters = {'TRACKOR_ID': f['TRACKOR_ID']}, fields = {'SI_READY_FOR_DELIVERY': 0})

# get complete list of files in directory
with sftp.cd(SftpInDir) as s:
	print ('kilroy was here 5 '+SftpInDir)
	files = sftp.listdir()

	print(files)

	for f in files:
		if f in ['Archive','100_202011021753_JY.csv']:
			continue
		print(f'getting {f}')
		sftp.get(f)
		with open(f,'r') as x:
			interface_file = x.read()
		print ('kilroy was here 6')
		Req.create(fields = {"TRACKOR_KEY": f, 'SI_INTERFACE_FILE': interface_file})
		if len(Req.errors)==0:
			sftp.rename(f,'Archive/'+f)
	print ('kilroy was here 7')
print ('kilroy was here 8')

sftp.close()
