import paramiko
import os
import tempfile
#import stat
import json

class SFTPManager:
	"""
	A class for managing SFTP file operations over SSH using Paramiko,
	without establishing a shell. Supports upload, retrieve, move (with workaround for SETSTAT), and delete.
	"""
	
	def __init__(self, host, user, password=None, private_key=None, port=22, auto_add_policy=True):
		"""
		Initialize the SFTPManager.
		
		Args:
			host (str): Remote host.
			user (str): Username.
			password (str, optional): Password for auth. Use either this or private_key.
			private_key (str, optional): Private key content as a string.
			port (int): SSH port (default 22).
			auto_add_policy (bool): Auto-accept unknown host keys (use with caution).
		"""
		self.host = host
		self.user = user
		self.password = password
		self.private_key = private_key
		self.port = port
		self.ssh = None
		self.sftp = None
		
		# Set host key policy
		self.ssh = paramiko.SSHClient()
		if auto_add_policy:
			self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		else:
			self.ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
		
		# Connect
		self.connect()
	
	def connect(self):
		"""Establish SSH connection and open SFTP session."""
		if self.ssh is None:
			raise ValueError("SSH client not initialized.")
		
		if self.password:
			self.ssh.connect(hostname=self.host, username=self.user, password=self.password, port=self.port)
		elif self.private_key:
			pkey = self._get_key_from_content()
			self.ssh.connect(hostname=self.host, username=self.user, pkey=pkey, port=self.port)
		else:
			raise ValueError("Must provide either password or private_key.")
		
		self.sftp = self.ssh.open_sftp()
	
	def _get_key_from_content(self):
		"""Parse private key content and return paramiko key object."""
		import io
		try:
			# Try RSA key
			return paramiko.RSAKey.from_private_key(io.StringIO(self.private_key))
		except paramiko.ssh_exception.SSHException:
			try:
				# Try Ed25519 key
				return paramiko.Ed25519Key.from_private_key(io.StringIO(self.private_key))
			except paramiko.ssh_exception.SSHException:
				raise ValueError("Unable to parse private key. Ensure it's in PEM format.")
	
	def disconnect(self):
		"""Close SFTP and SSH connections."""
		if self.sftp:
			self.sftp.close()
			self.sftp = None
		if self.ssh:
			self.ssh.close()
			self.ssh = None
	
	def __enter__(self):
		"""Context manager entry: ensure connected."""
		if not self.sftp:
			self.connect()
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		"""Context manager exit: disconnect."""
		self.disconnect()
	
	def upload(self, local_file, remote_file):
		"""
		Upload a local file to remote.
		
		Args:
			local_file (str): Path to local file.
			remote_file (str): Destination path on remote.
		"""
		if not self.sftp:
			raise ValueError("Not connected. Use connect() or context manager.")
		if not os.path.exists(local_file):
			raise FileNotFoundError(f"Local file not found: {local_file}")
		self.sftp.put(local_file, remote_file)
		print(f"Uploaded {local_file} to {remote_file}")
	
	def retrieve(self, remote_file, local_destination):
		"""
		Retrieve (download) a remote file to local.
		
		Args:
			remote_file (str): Path to remote file.
			local_destination (str): Local destination path.
		"""
		if not self.sftp:
			raise ValueError("Not connected. Use connect() or context manager.")
		self.sftp.get(remote_file, local_destination)
		print(f"Retrieved {remote_file} to {local_destination}")
	
	def move(self, old_remote_path, new_remote_path):
		"""
		Move (rename) a remote file. Uses direct rename if possible; falls back to workaround.
		
		Args:
			old_remote_path (str): Original remote path.
			new_remote_path (str): New remote path.
		"""
		if not self.sftp:
			raise ValueError("Not connected. Use connect() or context manager.")
		
		# Try direct rename first
		try:
			self.sftp.rename(old_remote_path, new_remote_path)
			print(f"Renamed {old_remote_path} to {new_remote_path} (direct)")
			return
		except OSError as e:
			if "SETSTAT unsupported" not in str(e):
				raise  # Re-raise unexpected errors
		
		print("Direct rename failed; using workaround...")
		# Workaround: Download to temp, delete old, upload to new
		with tempfile.NamedTemporaryFile(delete=False) as temp_local:
			temp_path = temp_local.name
			self.sftp.get(old_remote_path, temp_path)
		
		self.sftp.remove(old_remote_path)
		self.sftp.put(temp_path, new_remote_path)
		
		os.unlink(temp_path)
		print(f"Moved {old_remote_path} to {new_remote_path} (workaround)")
	
	def delete(self, remote_file):
		"""
		Delete a remote file.
		
		Args:
			remote_file (str): Path to remote file to delete.
		"""
		if not self.sftp:
			raise ValueError("Not connected. Use connect() or context manager.")
		self.sftp.remove(remote_file)
		print(f"Deleted {remote_file}")
	
	def list_directory(self, remote_path="."):
		"""
		List contents of a remote directory.
		
		Args:
			remote_path (str): Path to remote directory (default is current directory ".").
		
		Returns:
			list: List of file/directory names in the remote path.
		"""
		if not self.sftp:
			raise ValueError("Not connected. Use connect() or context manager.")
		return self.sftp.listdir(remote_path)
