"""
Created on 18.05.2016

@author: Sebastian Illing
"""
import os
import sys
from pathlib import Path
import pytest
from evaluation_system.tests import run_command_with_capture, similar_string

os.environ['EVALUATION_SYSTEM_CONFIG_FILE'] = str(Path(__file__).parent / 'test.conf')

def test_list_tools(stdout, plugin_command):
    plugin_list = run_command_with_capture(plugin_command, stdout, [])
    assert 'DummyPlugin: A dummy plugin\n' in plugin_list

def test_help(plugin_command, stdout):
    sys.stdout = stdout
    stdout.startCapturing()
    stdout.reset()
    with pytest.raises(SystemExit):
        plugin_command.run(['--help'])
    stdout.stopCapturing()
    help_str= stdout.getvalue()
    assert similar_string(help_str, '''Applies some analysis to the given data.
See https://code.zmaw.de/projects/miklip-d-integration/wiki/Analyze for more information.

The "query" part is a key=value list used for configuring the tool. It's tool dependent so check that tool help.

For Example:
freva --plugin pca eofs=4 bias=False input=myfile.nc outputdir=/tmp/test

Usage: %s %s [options]

Options:
-d, --debug           turn on debugging info and show stack trace on
                    exceptions.
-h, --help            show this help message and exit
--repos-version       show the version number from the repository
--caption=CAPTION     sets a caption for the results
--save                saves the configuration locally for this user.
--save-config=FILE    saves the configuration at the given file path
--show-config         shows the resulting configuration (implies dry-run).
--scheduled-id=ID     Runs a scheduled job from database
--dry-run             dry-run, perform no computation. This is used for
                    viewing and handling the configuration.
--batchmode=BOOL      creates a SLURM job
--unique_output=BOOL  If true append the freva run id to every output folder
--pull-request        issue a new pull request for the tool (developer
                    only!)
--tag=TAG             The git tag to pull
''' % (os.path.basename(sys.argv[0]), sys.argv[1]))

    sys.stdout = stdout
    stdout.startCapturing()
    stdout.reset()
    with pytest.raises(SystemExit):
        plugin_command.run(['dummyplugin', '--help'])
    stdout.stopCapturing()
    help_str= stdout.getvalue()
    assert similar_string(help_str, '''DummyPlugin (v0.0.0): A dummy plugin
Options:
number     (default: <undefined>)
       This is just a number, not really important
the_number (default: <undefined>) [mandatory]
       This is *THE* number. Please provide it
something  (default: test)
       No help available.
other      (default: 1.4)
       No help available.
input      (default: <undefined>)
       No help available.
''')

def test_run_plugin(stdout, plugin_command, dummy_history):

    sys.stdout = stdout
    stdout.startCapturing()
    stdout.reset()
    with pytest.raises(SystemExit):
        plugin_command.run(['dummyplugin'])
    stdout.stopCapturing()
    help_str= stdout.getvalue()
    assert 'Error found when parsing parameters. Missing mandatory parameters: the_number' in help_str

    sys.stdout = stdout
    # test run tool
    output_str = run_command_with_capture(plugin_command, stdout, ['dummyplugin',
                                                'the_number=32',
                                                '--caption="Some caption"'])
    assert similar_string('Dummy tool was run with: {\'input\': None, \'other\': 1.4, \'number\': None, \'the_number\': 32, \'something\': \'test\'}',  output_str, 0.7)
    # test get version
    
    sys.stdout = stdout
    output_str = run_command_with_capture(plugin_command, stdout, ['dummyplugin', '--repos-version'])
    # test batch mode
    sys.stdout = stdout
    output_str = run_command_with_capture(plugin_command, stdout, ['dummyplugin', '--batchmode=True', 'the_number=32'])
    # test save config
    sys.stdout = stdout
    output_str = run_command_with_capture(plugin_command, stdout, ['dummyplugin', 'the_number=32', '--save', '--debug'])
    fn = Path('~').expanduser() / 'evaluation_system/config/dummyplugin/dummyplugin.conf'
    assert fn.is_file()
    fn.unlink()
    # test show config
    output_str = run_command_with_capture(plugin_command, stdout, ['dummyplugin', 'the_number=42', '--show-config'])
    output_str = '\n'.join([l.strip() for l in output_str.split('\n') if l.strip()])
    assert similar_string(output_str, '''    number: -
the_number: 42
something: test
 other: 1.4
 input: -
''')

def test_handle_pull_request(plugin_command, stdout):
    from evaluation_system.model.plugins.models import ToolPullRequest
    ToolPullRequest.objects.all().delete()
    import time

    def sleep_mock(v):
        t = ToolPullRequest.objects.get(tool='murcss', tagged_version='1.0')
        t.status = 'failed'
        t.save()
    time.sleep = sleep_mock

    stdout.startCapturing()
    stdout.reset()
    cmd_out = run_command_with_capture(plugin_command, stdout, ['murcss', '--pull-request', '--tag=1.0'])
    assert cmd_out == """Please wait while your pull request is processed
The pull request failed.
Please contact the admins.
"""

    def sleep_mock_success(v):
        t = ToolPullRequest.objects.get(tool='murcss', tagged_version='2.0')
        t.status = 'success'
        t.save()
    time.sleep = sleep_mock_success
    cmd_out = run_command_with_capture(plugin_command, stdout, ['murcss', '--pull-request', '--tag=2.0'])
    assert cmd_out == """Please wait while your pull request is processed
murcss plugin is now updated in the system.
New version: 2.0
"""
