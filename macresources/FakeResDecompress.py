def GetEncoding(inf):
	if not inf.startswith(b'\xA8\x9F\x65\x72'):
		encoding = 'unknown'
	elif inf[6] == 8:
		encoding = 'DonnBits'
	elif inf[6] == 9:
		defprocID = int.from_bytes(len[8:10], byteorder='big', signed=True)
		encoding = 'GreggyBits%d' % defprocID
	return encoding


def DecompressResource(inf):
	return inf


def CompressResource(inf, encoding):
	return inf
