# -*- coding: utf-8 -*-
import sqlite3
pinyin_csv = 'pinyin_simp.dict.csv'
pinyin_list = []
with open(pinyin_csv) as f:
    for line in f.readlines():
        chars, py, freq = line.split('\t')
        py = py.replace(' ', '')
        pinyin_list.append([chars, py, freq])

conn = sqlite3.connect('wubi-jidian86.db')
c = conn.cursor()
# Create table
c.execute('''CREATE TABLE pinyins
        (id INTEGER PRIMARY KEY, phrase TEXT, pinyin TEXT,
        freq INTEGER);''')

# Insert a row of data
for i, row in enumerate(pinyin_list):
    c.execute("INSERT INTO pinyins VALUES ({}, '{}','{}', {})".format(i, *row))

# Save (commit) the changes
conn.commit()

# We can also close the connection if we are done with it.
# Just be sure any changes have been committed or they will be lost.
conn.close()