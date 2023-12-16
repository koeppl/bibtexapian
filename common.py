""" common """
# pylint: disable=bad-indentation,line-too-long,invalid-name

import os
import pickle
import enum

class QueryFields(enum.IntEnum):
	""" enumerate the different types of queries that can be issued """
	FULLTEXT = 0
	BIBKEY = 1
	AUTHOR = 2
	TITLE = 3
	NONE = 4
	def __str__(self):
		if self == QueryFields.BIBKEY:
			return 'k'
		if self == QueryFields.AUTHOR:
			return 'a'
		if self == QueryFields.TITLE:
			return 't'
		return ''

class FilePaths(enum.StrEnum):
    """ static filenames of the data directory used to index and query """
    XAPIAN_DB_PATH = "xapian"
    CHKSUM_DICT_PATH = "paper.dict"
    STORED_ENTRIES_PATH = "bibtex.dat"

def load_from_filepath(path):
	""" deserialize object from file """
	if os.path.isfile(path) and os.access(path, os.R_OK):
		with open(path, 'rb') as handle:
			try:
				return pickle.load(handle)
			except IOError:
				return {}
	return {}
