#!/usr/bin/env python3
""" index pdf files from bibtex """
# pylint: disable=bad-indentation,line-too-long,invalid-name

import pickle
import hashlib
import pathlib
import argparse
import bibtexparser
import pypdfium2 as pdfium
import xapian
from common import * 

parser = argparse.ArgumentParser(description='create bibtexapian index')
parser.add_argument('datapath', required=True, metavar='filename', type=pathlib.Path, help='directory where to store the index')
parser.add_argument('paperpath', required=True, metavar='filename', type=pathlib.Path, help='directory where the papers are stored')
parser.add_argument('bibfile', required=True, metavar='filename', type=argparse.FileType('r', encoding='utf-8'), help='bibtex file to index')
args = parser.parse_args()

args.paperpath.mkdir(parents=True, exist_ok=True)


def bibtex_file_attribute_to_paths(bibtex_entry, paperpath):
	""" takes an bibtex entry and reports all readable files associated with this entry """
	return filter_readable_filepaths(bibtex_entry['file'].split(':'), paperpath)

def filter_readable_filepaths(paths, paperpath):
	""" filters a list of filepaths by only readable ones """
	readable_paths = []
	for filename in paths:
		path = Path(filename)
		if not filename.is_absolute():
				path = paperpath / path
		if not os.path.isfile(path) or not os.access(path, os.R_OK):
			continue
		readable_paths.append(path)
	return readable_paths

def equal_dicts(dict_a, dict_b) -> bool:
    """ check whether two dictionaries are equal """
    if len(dict_a) == len(dict_b):
        for file in dict_a:
            if file not in dict_b:
                return False
            if dict_a[file] != dict_b[file]:
                return False
    return True


def save_to_filepath(path, data):
    """ serialize object to file """
    with open(path, 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)

def bibtexlist_to_dic(bibtexlist) -> dict:
    """ converts a bibtexlist into a dictionary whose keys are the bibtex-ids """
    r = {}
    for bibentry in bibtexlist:
        r[bibentry['ID']] = bibentry
    return r


stored_entries = load_from_filepath(args.datapath / STORED_ENTRIES_PATH)
checksum_dict = load_from_filepath(args.datapath / CHKSUM_DICT_PATH)


# Create or open the database we're going to be writing to.
db = xapian.WritableDatabase(args.datapath / XAPIAN_DB_PATH, xapian.DB_CREATE_OR_OPEN)

# Set up a TermGenerator that we'll use in indexing.
termgenerator = xapian.TermGenerator()
termgenerator.set_stemmer(xapian.Stem("en"))

entries = []
with open(args.bibfile, 'r', encoding='utf-8') as bibtex_file:
    arxiv_db = bibtexparser.load(bibtex_file)
    entries = arxiv_db.entries

# remove entries that are no longer in the bibtex file
indexed_entries = bibtexlist_to_dic(entries)
if len(stored_entries) > 0:
    for bibtexkey in stored_entries:
        if bibtexkey not in indexed_entries:
            print(f'deleting {bibtexkey}')
            db.delete_document(bibtexkey)
            del stored_entries[bibtexkey]
            if bibtexkey in checksum_dict:
                del checksum_dict[bibtexkey]

def unindex_document(bibtexid):
    """ remove bibtexid from the bibtex-index if present """
    if bibtexid in indexed_entries:
        del indexed_entries[bibtexid]
    if bibtexid in checksum_dict:
        del checksum_dict[bibtexid]

for entry in entries:
    entryid = entry['ID']
    if 'file' not in entry:
        unindex_document(entryid)
        continue
    filepaths = bibtex_file_attribute_to_paths(entry, args.paperpath)
    if len(filepaths) == 0:
        unindex_document(entryid)
        continue
    entry['file'] = filepaths


    doc = xapian.Document()
    doc.add_value(0, entryid)
    termgenerator.set_document(doc)

    # Index each field with a suitable prefix.
    termgenerator.index_text(entry['title'], 1, str(QueryFields.TITLE))
    termgenerator.index_text(entryid, 1, str(QueryFields.BIBKEY))
    termgenerator.index_text(entry['author'].replace(' and ',', ') , 1, str(QueryFields.AUTHOR))

    hashes = {}
    for filepath in filepaths:
        with open(filepath, 'rb') as f:
            hashes[filepath] = hashlib.sha256(f.read()).hexdigest()

    if entryid in checksum_dict:
        if equal_dicts(checksum_dict[entryid], hashes):
            continue

    checksum_dict[entryid] = hashes

    for filepath in filepaths:
        print(f"index {filepath}")
        pdf = pdfium.PdfDocument(filepath)
        for pdfpage in pdf:
            text = pdfpage.get_textpage().get_text_range()
            termgenerator.index_text(text)
        termgenerator.increase_termpos()

    checksum_dict[entryid] = hashes

    # We use the identifier to ensure each object ends up in the
    # database only once no matter how many times we run the
    # indexer.
    doc.add_boolean_term(entryid)
    db.replace_document(entryid, doc)

save_to_filepath(args.datapath / STORED_ENTRIES_PATH, indexed_entries)
save_to_filepath(args.datapath / CHKSUM_DICT_PATH, checksum_dict)

