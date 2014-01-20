'''
..moduleauthor: Oliver Kunst <oliver.kunst@met.fu-berlin.de>

This module creates SLURM scheduler files
'''
from evaluation_system.misc import py27, config


class slurm_file(object):
    SHELL_CMD  = "#!/bin/bash"
    SLURM_CMD  = "#SBATCH "
    MLOAD_CMD  = "module load "
    EXPORT_CMT = "EXPORT"
    
    class entry_format:
        """
        This class describes the format of an option for SLURM.
        """
        def __init__(self, indicator, separator):
            """
            initialize the member variables
            """
            self._ind = indicator
            self._sep = separator
            
        def indicator(self):
            """
            returns the option indicator usually "-" or "--"
            """
            return self._ind
        
        def separator(self):
            """
            returns the separator between optione and value.
            (e.g. " " or "=")
            """
            return self._sep
        
        def format(self, opt, val):
            """
            this applies the saved format to a given option
            :param opt: option name
            :param val: the value of the option
            :return: a formatted string
            """
            string = str(self._ind) + str(opt) + str(self._sep)
            
            if not val is None:
                string = string + str(val)
                
            return string
            
        
    def __init__(self):
        """
        set the member variables
        """
        #: the options to be set, dictionary of string, (string, entry_format)
        self._options = py27.OrderedDict()
        
        #: shell variables to be set, a dictionary of string, string
        self._variables = py27.OrderedDict()

        #: a list of modules to be load
        self._modules = []
        
        #: the command to start in the scheduler
        self._cmdstring = ""
        
    def set_envvar(self, var, value):
        """
        Adds an environment variable to be set
        :param var: Variable to be set
        :param value: the value (will be converted to string)
        """
        self._variables[var] = str(value)
    
    def add_dash_option(self, opt, val):
        """
        Adds an option beginning with a dash
        :param opt: option to be set
        :param value: the value (will be converted to string)
        """
        e = None
        
        if val is None:
            e = self.entry_format('-', '')
        else:
            e = self.entry_format('-', ' ')
            
        self._options[opt] = (val, e)
        
    def  add_ddash_option(self, opt, val):
        """
        Adds an option beginning with a double dash
        :param opt: option to be set
        :param value: the value (will be converted to string)
        """
        
        e = None
        
        if val is None:
            e = self.entry_format('--', '')
        else:
            e = self.entry_format('--', '=')
            
        self._options[opt] = (val, e)

    def add_module(self, mod):
        """
        Adds a module to be loaded by slurm
        :param mod: the module name
        :type mod: string
        """
        self._modules.append(mod) 
        
    def set_cmdstring(self, cmdstring):
        """
        Sets the command string to be executed by slurm
        :param cmdstring: the command
        :type cmdstring: string
        """
        self._cmdstring = cmdstring
        
    def set_default_options(self, user, cmdstring, outdir=None):
        """
        Sets the default options for a given user and a
        given commandstring.
        :param user: an user object
        :type user: evaluation_system.model.user.User 
        :param cmdstring: the command
        :type cmdstring: string
        """
        
        # read output directory from configuration
        if not outdir:
            outdir = user.getUserSchedulerOutputDir()

        email = user.getEmail()
        
        # set the default options
        self.add_dash_option("D", outdir)
        self.add_dash_option("p", "serial")
        if email:
            self.add_ddash_option("mail-user", email)
        self.add_ddash_option("ntasks-per-node", 24)
        self.add_ddash_option("mem", "48000mb")
        self.add_ddash_option("share", None)
        self.add_ddash_option("ntasks", 1)
        self.add_ddash_option("time", "240:00")
        self.add_ddash_option("cpus-per-task", 1)
        self.add_module("evaluation_system")
        self.set_cmdstring(cmdstring)
        
      
    def write_to_file(self, fp):
        """
        Write the configuration to the SLURM scheduler to a given file handler
        
        :param fp: file to write to
        :type fp: file handler
        """
        # Execute with bash
        fp.write(self.SHELL_CMD + "\n")
        
        # Workaround for Slurm in www-miklip
        fp.write("source /client/etc/profile.miklip\n")
        
        # write options
        opts = self._options.items()

        for opt in opts:
            # use the stored format
            optf   = opt[1][1]
            option = opt[0]
            value  = opt[1][0]
            
            string = self.SLURM_CMD + optf.format(option, value) + "\n"
            fp.write(string)
            
        # write the modules to be loaded
        for mod in self._modules:
            fp.write(self.MLOAD_CMD + mod + "\n")
            
        # variables to export
        variables = self._variables.items()
        
        for var in variables:
            fp.write("%s %s=%s" % (self.EXPORT_CMT, var[0], var[1]) + "\n")
        
        # write the execution command
        fp.write(self._cmdstring + "\n")
        
        
