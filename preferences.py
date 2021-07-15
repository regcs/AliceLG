# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Copyright © 2021 Christian Stolze
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

# MODULE DESCRIPTION:
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# This includes everything that is related to the add-on preferences,
# installation of requirements, etc.

# -------------------- LOAD MODULES ----------------------
import bpy
from bpy.types import AddonPreferences, PropertyGroup
from .globals import *

# ---------------- GLOBAL ADDON LOGGER -------------------
import logging
LookingGlassAddonLogger = logging.getLogger('Alice/LG')

# ------------- DEFINE ADDON PREFERENCES ----------------
# an operator that installs the python dependencies
class LOOKINGGLASS_OT_install_dependencies(bpy.types.Operator):
	bl_idname = "lookingglass.install_dependencies"
	bl_label = "Install (This may take a few minutes)"
	bl_description = "Install all Python dependencies required by this add-on to the add-on directory."
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# if dependencies are missing
		if LookingGlassAddon.python_dependecies == False:

			# NOTE: - pip should be preinstalled for Blender 2.81+
			#		  therefore we don't check for it anymore
			import subprocess
			import datetime

			# path to python (NOTE: bpy.app.binary_path_python was deprecated since 2.91)
			if bpy.app.version < (2, 91, 0): python_path = bpy.path.abspath(bpy.app.binary_path_python)
			if bpy.app.version >= (2, 91, 0): python_path = bpy.path.abspath(sys.executable)

			# generate logfile
			logfile = open(bpy.path.abspath(LookingGlassAddon.logpath + 'side-packages-install.log'), 'a')
			LookingGlassAddonLogger.info("Installing missing side-packages. See '%s' for details." % (LookingGlassAddon.logpath + 'side-packages-install.log',))

			# install the dependencies to the add-on's library path
			subprocess.call([python_path, '-m', 'pip', 'install', 'cbor>=1.0.0', '--target', LookingGlassAddon.libpath], stdout=logfile)
			subprocess.call([python_path, '-m', 'pip', 'install', 'cffi>=1.12.3', '--target', LookingGlassAddon.libpath], stdout=logfile)
			subprocess.call([python_path, '-m', 'pip', 'install', 'pycparser>=2.19', '--target', LookingGlassAddon.libpath], stdout=logfile)
			subprocess.call([python_path, '-m', 'pip', 'install', 'sniffio>=1.1.0', '--target', LookingGlassAddon.libpath], stdout=logfile)
			subprocess.call([python_path, '-m', 'pip', 'install', 'pillow', '--target', LookingGlassAddon.libpath], stdout=logfile)
			if platform.system() == "Windows": subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'pynng', '--target', LookingGlassAddon.libpath], stdout=logfile)

			logfile.write("###################################" + '\n')
			logfile.write("Installed: " + str(datetime.datetime.now()) + '\n')
			logfile.write("###################################" + '\n')

			# close logfile
			logfile.close()

			try:

				from .lib import pynng
				from .lib import cbor

				# all python dependencies are fulfilled
				LookingGlassAddon.python_dependecies = True

			except:

				# not all python dependencies are fulfilled
				LookingGlassAddon.python_dependecies = False
				pass

		return {'FINISHED'}

# Preferences pane for this Addon in the Blender preferences
class LookingGlassAddonPreferences(AddonPreferences):
	bl_idname = __name__

	# draw function
	def draw(self, context):

		# Notify the user and provide an option to install
		layout = self.layout
		row = layout.row()

		# draw an Button for Installation of python dependencies
		if LookingGlassAddon.python_dependecies == False:

			row.label(text="Some Python modules are missing for AliceLG to work. Install them to the add-on path?")
			row = layout.row()
			row.operator("lookingglass.install_dependencies", icon='PLUS')

		else:

			row.label(text="All required Python modules were installed.")
			row = layout.row()
			row.label(text="Please restart Blender to activate the changes!", icon='ERROR')
