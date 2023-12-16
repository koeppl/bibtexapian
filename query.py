#!/usr/bin/python3
""" query the database """
# pylint: disable=bad-indentation,line-too-long,invalid-name

import sys
import os
import subprocess
import tty
import termios
import enum
import pathlib
import argparse
import xapian

from common import * 

parser = argparse.ArgumentParser(description='create bibtexapian index')
parser.add_argument('datapath', required=True, metavar='filename', type=pathlib.Path, help='directory where to store the index')
args = parser.parse_args()


class bcolors(enum.StrEnum):
	""" background color escape sequences """
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKCYAN = '\033[96m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'


def get_getch():
	""" get an input character from stdin without waiting for flush """
	fd = sys.stdin.fileno()
	old_settings = termios.tcgetattr(fd)
	try:
		tty.setraw(sys.stdin.fileno())
		ch = sys.stdin.read(1)
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
	return ch

def config_queryparser():
	""" sets the query parser """
	q = xapian.QueryParser()
	q.set_stemmer(xapian.Stem("en"))
	q.set_stemming_strategy(q.STEM_SOME)
	# prefix configuration.
	for k in range(QueryFields.FULLTEXT+1,QueryFields.NONE):
		q.add_prefix(str(QueryFields(k)), str(QueryFields(k)))
	return q

stored_entries = load_from_filepath(args.datapath / STORED_ENTRIES_PATH)
queryparser = config_queryparser()

xapian_db = xapian.Database(args.datapath / XAPIAN_DB_PATH)
# Set up a QueryParser with a stemmer and suitable prefixes

def xapian_query(querystring : str, limit : int, offset = 0):
	""" query xapian database """
	# And parse the query
	query_object = queryparser.parse_query(querystring)

	# Use an Enquire object on the database to run the query
	enquire = xapian.Enquire(xapian_db)
	enquire.set_query(query_object)

	# And print out something about each match
	bibtex_ids = []
	for doc in enquire.get_mset(offset, limit):
		bibtexid = xapian_db.get_document(doc.docid).get_value(0).decode('utf-8')
		if bibtexid in stored_entries:
			bibtex_ids.append(bibtexid)
	return bibtex_ids


fileseletions=[]
query_result_num = 10

def query(querystring : str):
	""" query xapers for the given querystring """
	fileseletions.clear()
	for bibtexid in xapian_query(querystring, limit=query_result_num):
		entry = stored_entries[bibtexid]
	# docs = xapian_query(querystring, limit=query_result_num)
	# for doc in docs:
		print('')
		print(bcolors.OKBLUE + entry['author'] + bcolors.ENDC)
		print(bcolors.OKGREEN + '"' + entry['title'] + '"' + bcolors.ENDC)
		for file in entry['file']:
			print(bcolors.WARNING + bcolors.UNDERLINE + str(len(fileseletions)) + bcolors.ENDC + bcolors.WARNING + " -> " + str(file) + bcolors.ENDC)
			fileseletions.append(file)


def build_querystring(querystrings) -> str:
	""" transforms queryfields to xapian query string considering the add_prefix methods """
	querystring = querystrings[QueryFields.FULLTEXT]
	for k in range(QueryFields.FULLTEXT+1,QueryFields.NONE):
		if len(querystrings[k]) > 0:
			querystring += " " + str(QueryFields(k)) + ":" + querystrings[k]
	return querystring

queryfields = [""] * QueryFields.NONE
queryfield_cursor = 0

while True:
	while True:
		c = get_getch()
		if c in ['\x04',  '\x1B', '\x03']:
			sys.exit(2)
		if c in  ['\x09']: #escape
			queryfield_cursor = (queryfield_cursor + 1) % QueryFields.NONE
		if c in  ['\x0d', '\x0c']: #escape
			break
		if c in  ['\x08', '\x7f']: #backspace
			if len(queryfields[queryfield_cursor]) == 0:
				continue
			queryfields[queryfield_cursor] = queryfields[queryfield_cursor][:-1]
		elif c == '+':
			query_result_num += 1
		elif c == '-':
			if query_result_num > 1:
				query_result_num -= 1
			else:
				continue
		elif c.isprintable():
			queryfields[queryfield_cursor] += c
		os.system('clear')
		query(build_querystring(queryfields))
		for fieldid, queryfield in enumerate(queryfields):
			print(f" {str(QueryFields(fieldid))}: {queryfield}", end='')
			if fieldid == queryfield_cursor:
				print('#',end='')
			print(' ',end='')
		print("")

	if len(fileseletions) == 0:
		print('no matches!')
		sys.exit(1)

	num = -1
	while(num < 0 or num >= len(fileseletions)):
		try:
			num = int(input(f"\nenter paper number: [0-{len(fileseletions)-1}] "))
		except ValueError:
			print("Invalid input. Please enter an integer.")
	subprocess.run(['open', fileseletions[num]], check=False)
