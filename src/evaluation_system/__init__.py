import os
import sys
import api.plugin as plugin

#get the tools directory from the current one
tools_dir = os.path.join(__file__[:-len('src/evaluation_system/__init__.py')-1],'tools')

#all plugins modules will be dynamically loaded here.
__plugin_modules__ = {}
for plugin_imp in os.listdir(tools_dir):
    if not plugin_imp.startswith('.'):
        #check if api available
        int_dir = os.path.join(tools_dir,plugin_imp,'integration') 
        if os.path.isdir(int_dir):
            #we have a plugin_imp with defined api
            sys.path.append(int_dir)
            __plugin_modules__[plugin_imp] = __import__(plugin_imp + '.api')

__plugins__ = {}
for plug_class in plugin.PluginAbstract.__subclasses__():
    __plugins__[plug_class.__name__] = plug_class

print __plugins__['PCA'].__short_description__