#!/usr/bin/env python3
""" index pdf files from bibtex """

import os
from pathlib import Path
import pickle
import hashlib
import bibtexparser
import pypdfium2 as pdfium
import xapian

def equal_dicts(dict_a, dict_b) -> bool:
    """ check whether two dictionaries are equal """
    if len(dict_a) == len(dict_b):
        for file in dict_a:
            if file not in dict_b:
                return False
            if dict_a[file] != dict_b[file]:
                return False
    return True


def filter_readable_filepaths(paths):
    """ filters a list of filepaths by only readable ones """
    readable_paths = []
    for filename in paths:
        path = PAPER_PATH / filename
        if not os.path.isfile(path) or not os.access(path, os.R_OK):
            continue
        readable_paths.append(path)
    return readable_paths



PAPER_PATH = Path.home() / "paper"
XAPIAN_PATH = "xapian"
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

def save_to_filepath(path, data):
    """ serialize object to file """
    with open(path, 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)


stored_entries = load_from_filepath(STORED_ENTRIES_PATH)
checksum_dict = load_from_filepath(CHKSUM_DICT_PATH)

# Create or open the database we're going to be writing to.
db = xapian.WritableDatabase(XAPIAN_PATH, xapian.DB_CREATE_OR_OPEN)

# Set up a TermGenerator that we'll use in indexing.
termgenerator = xapian.TermGenerator()
termgenerator.set_stemmer(xapian.Stem("en"))

entries = []
with open('paper.bib', 'r', encoding='utf-8') as bibtex_file:
    arxiv_db = bibtexparser.load(bibtex_file)
    entries = arxiv_db.entries

# remove entries that are no longer in the bibtex file
if len(stored_entries) > 0:
    indexed_entries = {}
    for entry in entries:
        indexed_entries[entry['ID']] = entry
    for entry in stored_entries:
        if entry['ID'] not in indexed_entries:
            db.delete_document(entry['ID'])
            print('del')


for entry in entries:
    if 'file' not in entry:
        continue
    filepaths = filter_readable_filepaths(entry['file'].split(':'))
    if len(filepaths) == 0:
        continue

    entryid = entry['ID']

    doc = xapian.Document()
    doc.add_value(0, entryid)
    termgenerator.set_document(doc)

    # Index each field with a suitable prefix.
    termgenerator.index_text(entry['title'], 1, 'title')
    termgenerator.index_text(entryid, 1, 'key')
    termgenerator.index_text(entry['author'].replace(' and ',', ') , 1, 'author')


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

save_to_filepath(STORED_ENTRIES_PATH, entries)
save_to_filepath(CHKSUM_DICT_PATH, checksum_dict)
