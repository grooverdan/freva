"""
Created on 23.05.2016

@author: Sebastian Illing
"""
import gzip
import os
from pathlib import Path

import pytest


def test_dump_to_file(dummy_solr):
      from evaluation_system.model.solr_core import SolrCore, META_DATA
      assert os.path.isfile(dummy_solr.dump_file)
      dump_str = open(dummy_solr.dump_file, 'r').read()
      assert '%s\t%s' % (META_DATA.CRAWL_DIR, dummy_solr.tmpdir) in dump_str
      for fn in dummy_solr.files:
          assert fn in dump_str
      SolrCore.dump_fs_to_file(dummy_solr.tmpdir +\
              '/cmip5/output1/MOHC/HadCM3/historical', dummy_solr.dump_file)

      assert os.path.isfile(dummy_solr.dump_file)
      dump_str = open(dummy_solr.dump_file, 'r').read()
      assert '%s\t%s' % (META_DATA.CRAWL_DIR, dummy_solr.tmpdir) in dump_str
      assert dummy_solr.files[0] in dump_str
      dump_file = str(Path(dummy_solr.dump_file).with_suffix('.gz'))
      # check gzipped creation
      Path(dummy_solr.tmpdir + '/cmip5').mkdir(exist_ok=True, parents=True)
      print(dump_file, dummy_solr.tmpdir, META_DATA.CRAWL_DIR)
      SolrCore.dump_fs_to_file(dummy_solr.tmpdir + '/cmip5', dump_file)
      assert os.path.isfile(dump_file)
      dump_gzip_header = open(dump_file, 'rb').read(2)
      gzip_header = b'\037\213'
      assert dump_gzip_header == gzip_header
      dump_str = gzip.open(dump_file, 'rt').read()
      assert '%s\t%s' % (META_DATA.CRAWL_DIR, dummy_solr.tmpdir) in dump_str
      for fn in dummy_solr.files:
          assert fn in dump_str

def test_ingest(dummy_solr):
      from evaluation_system.model.solr_core import SolrCore
      from evaluation_system.model.solr import SolrFindFiles
      from evaluation_system.misc.utils import supermakedirs
      from evaluation_system.model.file import DRSFile, CMIP5
      from copy import deepcopy
      latest_versions = [dummy_solr.files[0], dummy_solr.files[1], dummy_solr.files[3]]
      multiversion_latest = dummy_solr.files[3]
      old_versions = [dummy_solr.files[2], dummy_solr.files[4]]
      dump_file = dummy_solr.tmpdir + '/dump1.csv'
      SolrCore.dump_fs_to_file(dummy_solr.tmpdir + '/cmip5', dump_file, check=True, abort_on_errors=True)
      # test instances, check they are as expected
      SolrCore.load_fs_from_file(dump_file, abort_on_errors=True,
                                 core_all_files=dummy_solr.all_files,
                                 core_latest=dummy_solr.latest)
      # check
      ff_all = SolrFindFiles(core='files', host=dummy_solr.solr_host,
                             port=dummy_solr.solr_port)
      ff_latest = SolrFindFiles(core='latest', host=dummy_solr.solr_host,
                                port=dummy_solr.solr_port)
      all_entries = [i for i in ff_all._search()]
      latest_entries = [i for i in ff_latest._search()]
      # old version should be only on the general core
      assert all([dummy_solr.tmpdir + '/' + e in all_entries for e in dummy_solr.files])
      assert all([dummy_solr.tmpdir + '/' + e in latest_entries for e in latest_versions])
      assert all([dummy_solr.tmpdir + '/' + e not in latest_entries for e in old_versions])

      # add new version
      new_version = dummy_solr.tmpdir + '/' + 'cmip5/output1/MOHC/HadCM3/decadal2009/mon/atmos/Amon/r7i2p1/v20120419/ua/ua_Amon_HadCM3_decadal2009_r7i2p1_200911-201912.nc'
      with open(dump_file, 'r') as f: content = f.readlines()
      content.insert(3, new_version + ',1564083682.09\n')
      with open(dump_file, "w") as f:
          contents = "".join(content)
          f.write(contents)
          f.close()
      SolrCore.load_fs_from_file(dump_file, abort_on_errors=True,
                                 core_all_files=dummy_solr.all_files,
                                 core_latest=dummy_solr.latest)
      assert set(ff_all._search()).symmetric_difference(set(all_entries)).pop() == new_version
      assert (set(ff_latest._search()) - set(latest_entries)).pop() == new_version
      assert (set(latest_entries) - set(ff_latest._search())).pop() == dummy_solr.tmpdir + '/' + multiversion_latest

      # test get_solr_fields (facets)
      facets = dummy_solr.all_files.get_solr_fields().keys()
      facets_to_be = ['model', 'product', 'realm', 'version', 'data_type', 'institute', 'file_name', 'creation_time',
                      'cmor_table', 'time_frequency', 'experiment', 'timestamp', 'file', 'time', 'variable',
                      '_version_', 'file_no_version', 'project', 'ensemble']
      assert sorted(facets) == sorted(facets_to_be)

def test_reload(dummy_solr):
      res = dummy_solr.all_files.reload()
      assert ['responseHeader'] == list(res.keys())

def test_unload_and_create(dummy_solr):

     res = dummy_solr.all_files.unload()
     status = dummy_solr.all_files.status()
     print(dummy_solr.all_files.core, dummy_solr.all_files.instance_dir, dummy_solr.all_files.data_dir)
     assert {} == status
     with pytest.raises(FileNotFoundError):
         dummy_solr.all_files.create()
     dummy_solr.all_files.create(check_if_exist=False)
     assert len(dummy_solr.all_files.status()) == 9

