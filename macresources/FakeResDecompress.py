def GetEncoding(inf):
	try:
		if inf[6] == 8:
			encoding = 'DonnBits'
		elif inf[6] == 9:
			defprocID = int.from_bytes(inf[8:10], byteorder='big', signed=True)
			encoding = 'GreggyBits%d' % defprocID
		else:
			raise ValueError
		# print('GetEncoding', encoding)
		return encoding
	except:
		return 'UnknownCompression'


def DecompressResource(inf):
	# print('DecompressResource', GetEncoding(inf))
	if GetEncoding(inf) == 'UnknownCompression': return inf
	return b'decompressed    ' + inf


def CompressResource(inf, encoding):
	# print('CompressResource', encoding)
	if encoding == 'UnknownCompression': return inf
	if inf.startswith(b'decompressed    '): inf = inf[16:]
	return inf
