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

# ------------------ INTERNAL MODULES --------------------
from .globals import *

# ------------------- EXTERNAL MODULES -------------------
import bpy
from bpy.types import AddonPreferences

# ---------------- GLOBAL ADDON LOGGER -------------------
import logging
LookingGlassAddonLogger = logging.getLogger('Alice/LG')

# ------------- DEFINE ADDON PREFERENCES ----------------
# an operator that installs the python dependencies
class LOOKINGGLASS_OT_install_dependencies(bpy.types.Operator):
	bl_idname = "lookingglass.install_dependencies"
	bl_label = "Install Dependencies"
	bl_description = "Install all Python dependencies required by this add-on to the add-on directory."
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# if dependencies are missing
		if not LookingGlassAddon.check_dependecies():

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
			for module in LookingGlassAddon.external_dependecies:
				if not LookingGlassAddon.is_installed(module):

					subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', module[1], '--target', LookingGlassAddon.libpath], stdout=logfile)
				# subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'cbor>=1.0.0', '--target', LookingGlassAddon.libpath], stdout=logfile)
				# subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'cffi>=1.12.3', '--target', LookingGlassAddon.libpath], stdout=logfile)
				# subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'pycparser>=2.19', '--target', LookingGlassAddon.libpath], stdout=logfile)
				# subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'sniffio>=1.1.0', '--target', LookingGlassAddon.libpath], stdout=logfile)
				# subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'pillow', '--target', LookingGlassAddon.libpath], stdout=logfile)
				# subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'pynng', '--target', LookingGlassAddon.libpath], stdout=logfile)

			logfile.write("###################################" + '\n')
			logfile.write("Installed: " + str(datetime.datetime.now()) + '\n')
			logfile.write("###################################" + '\n')

			# close logfile
			logfile.close()

		return {'FINISHED'}

# Preferences pane for this Addon in the Blender preferences
class LOOKINGGLASS_PT_install_dependencies(AddonPreferences):
	bl_idname = __package__

	# draw function
	def draw(self, context):

		# Notify the user and provide an option to install
		layout = self.layout
		layout.alert = True

		# draw an Button for Installation of python dependencies
		if not LookingGlassAddon.check_dependecies():

			row = layout.row()
			row.alignment = 'EXPAND'
			row.scale_y = 0.5
			row.label(text="Some Python dependencies are missing for Alice/LG to work. These modules are")
			row = layout.row(align=True)
			row.alignment = 'EXPAND'
			row.scale_y = 0.5
			row.label(text="required to communicate with HoloPlay Service. If you click the button below,")
			row = layout.row(align=True)
			row.alignment = 'EXPAND'
			row.scale_y = 0.5
			row.label(text="the required modules will be installed to the addon's path. This may take a few")
			row = layout.row(align=True)
			row.alignment = 'EXPAND'
			row.scale_y = 0.5
			row.label(text="minutes, during which the Blender user interface will be unresponsive.")
			row = layout.row(align=True)
			row.alignment = 'EXPAND'
			row.operator("lookingglass.install_dependencies", icon='PLUS')

		else:

			row = layout.row()
			row.label(text="All required Python modules were installed.")
			row = layout.row()
			row.label(text="Please restart Blender to activate the changes!", icon='ERROR')


# Preferences pane for this Addon in the Blender preferences
class LOOKINGGLASS_PT_render_settings(AddonPreferences):
	bl_idname = __package__
	bl_label = "Render Settings" # display name in the interface.

	# render mode
	render_mode: bpy.props.EnumProperty(
									items = [('0', 'Single Camera Mode', 'The quilt is rendered using a single moving camera.'),
											 ('1', 'Multiview Camera Mode', 'The quilt is rendered using Blenders multiview mechanism.')],
									default='0',
									name="Render Mode",
									)
	# draw function
	def draw(self, context):

		layout = self.layout
		row_render_mode = layout.row()
		row_render_mode.prop(self, "render_mode")
