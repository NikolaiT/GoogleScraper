"""
 persistentdict module $Revision: 98 $ $Date: 2011-07-23 14:01:04 +0200 (za, 23 jul 2011) $

 (c) 2011 Michel J. Anders

 This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http: www.gnu.org="" licenses="">.

"""

from collections import UserDict
import sqlite3 as sqlite
from pickle import dumps,loads
import threading 

class PersistentDict(UserDict):

 """
 PersistentDict  a MutableMapping that provides a thread safe,
     SQLite backed persistent storage.
 
 db  name of the SQLite database file, e.g.
   '/tmp/persists.db', default to 'persistentdict.db'
 table name of the table that holds the persistent data,
   usefull if more than one persistent dictionary is
   needed. defaults to 'dict'
 
 PersistentDict tries to mimic the behaviour of the built-in
 dict as closely as possible. This means that keys should be hashable.
 
 Usage example:
 
 >>> from persistentdict import PersistentDict
 >>> a=PersistentDict()
 >>> a['number four'] = 4
 
 ... shutdown and then restart applicaion ...
 
 >>> from persistentdict import PersistentDict
 >>> a=PersistentDict()
 >>> print(a['number four'])
 4
 
 Tested with Python 3.2 but should work with 3.x and 2.7.x as well.
 
 run module directly to run test suite:
 
 > python PersistentDict.py
 
 """
 
 def __init__(self, dict=None, **kwargs):
  
  self.db    = kwargs.pop('db','persistentdict.db')
  self.table = kwargs.pop('table','dict')
  #self.local = threading.local()
  self.conn = None
  self.lock = threading.Lock()
  
  with self.lock:
   with self.connect() as conn:
    conn.execute('create table if not exists %s (hash unique not null,key,value);'%self.table)
    
  if dict is not None:
   self.update(dict)
  if len(kwargs):
   self.update(kwargs)
 
 def connect(self):
  if self.conn is None:
   self.conn = sqlite.connect(self.db,check_same_thread=False)
  return self.conn
   
 def __len__(self):
  with self.lock:
   cursor = self.connect().cursor()
   cursor.execute('select count(*) from %s'%self.table)
   return cursor.fetchone()[0]
 
 def __getitem__(self, key):
  with self.lock:
   cursor = self.connect().cursor()
   h=hash(key)
   print('selecting with hash={}'.format(h))
   cursor.execute('select value from %s where hash = ?'%self.table,(h,))
   try:
    return loads(cursor.fetchone()[0])
   except TypeError:
    if hasattr(self.__class__, "__missing__"):
     return self.__class__.__missing__(self, key)
   raise KeyError(key)
   
 def __setitem__(self, key, item):
  h=hash(key)
  print('__setitem__() inserts a row with hash={}'.format(h))
  with self.lock:
   with self.connect() as conn:
    conn.execute('insert or replace into %s values(?,?,?)'%self.table,(h,dumps(key),dumps(item)))

 def __delitem__(self, key):
  h=hash(key)
  with self.lock:
   with self.connect() as conn:
    conn.execute('delete from %s where hash = ?'%self.table,(h,))

 def __iter__(self):
  with self.lock:
   cursor = self.connect().cursor()
   cursor.execute('select key from %s'%self.table)
   rows = list(cursor.fetchall())
  for row in rows:
   yield loads(row[0])

 def __contains__(self, key):
  h=hash(key)
  with self.lock:
   cursor = self.connect().cursor()
   cursor.execute('select value from %s where hash = ?'%self.table,(h,))
   return not ( None is cursor.fetchone())

 # not implemented def __repr__(self): return repr(self.data)
 
 def copy(self):
  c = self.__class__(db=self.db)
  for key,item in self.items():
   c[key]=item
  return c