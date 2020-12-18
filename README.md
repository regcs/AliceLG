# Alice/LG - A Blender Add-on for Looking Glass Displays

**Author:** Christian Stolze

### Let Alice/LG take your Blender artworks through the Looking Glass! This short guide is to get you started.

## About the Add-on
This add-on was created for the use of Blender with the Looking Glass holographic displays. I am not associated with the Looking Glass Factory and devoloped this add-on privately in my freetime because I'm a fan of [Blender](https://www.blender.org/) as well as the amazing new holographic display technology created by the [Looking Glass Factory](https://lookingglassfactory.com/). 

If you like this add-on and want to do a private donation, thank you for your support! I will most-likely invest it into new hardware, since rendering with an Quad-Core Intel Core i7 increases my coffee consumption way too much ...

[![Donate](https://www.paypalobjects.com/en_US/DK/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=N2TKY97VJJL96)

## Main Features
- integration into the common Blender workflow
- an optional viewcone representing the Looking Glass volume in the scene
- lightfield viewport in the Looking Glass with:
   - automatic and manual refresh modes
   - a holographic mouse cursor
   - most of the features of a native Blender viewport
- render any camera view as single quilt image or animation
- support for multiple scenes and view layers
- addon settings are saved in & loaded from your Blender file
- support for all available Looking Glass displays (including the new Looking Glass Portrait)

## System Requirements
- Windows or macOS (Linux not tested yet)
- Blender 2.9x
- Holoplay Service App

## Installation


1. Install the Holoplay Service App on your PC or Mac (if not already done).

2. Download the [zip file](LINK MISSING) of this addon.

3. Install _Alice/LG_ in Blender:
   - Open Blender
   - In the main menu, navigate to _Edit → Preferences → Add-ons → Install → Install Add-on_
   - Select the downloaded zip file and click "Install"
   - Enable the add-on by activating the check box on the left

## How to Use

### Add-on Controls

After the installation you find a _Looking Glass_ tab in each Blender viewport. Depending your current selections, the tab shows up to four control panels & subpanels:

- **Looking Glass.** Contains the Looking Glass display selection, a view resolution selection, and a button to turn on/off the Lightfield Window. Furthermore, it has two subpanels:

   - **Camera Setup.** Select one of the cameras in the scene to setup a view for the Looking Glass and the quilt rendering. Once

   - **Quilt Setup & Rendering.** Controls for starting a quilt render.

- **Lightfield Window.** The lightfield / hologram is rendered to a separate window, which needs to be placed inside your Looking Glass display. In this category you find options to switch between two different modes for the lightfield Window: _Viewport_ and _Quilt Viewer_.

   - **Lightfield Cursor.** In _Viewport_ mode you have the option to display a lightfield mouse cursor in the lightfield window. Only works if the lightfield window is the active window.

   - **Shading & Overlay Settings.** If the lightfield window is in _Viewport_ mode, it basically acts like a native Blender viewport - except that it's a holographic viewport. The settings for this (lightfield) viewport are defined here.

### Lightfield Window & Viewport

The lightfield window is the place where the hologram is rendered. It can be opened via a click on the button: _Looking Glass → Lightfield Window_, if you have a Looking Glass connected and HoloPlay Service is running. After the window was opened, move it to your Looking Glass screen and click the _Looking Glass → Toggle Fullscreen Mode_ button, which appeared in the add-on controls after the lightfield window was opened. Only in fullscreen mode the hologram will be displayed correctly in your Looking Glass. The lightfield window can operate in two modes:

- **Viewport.** In viewport mode, it basically acts like a normal Blender viewport in the Looking Glass - except that it is holographic. You can choose between _Auto_ and _Manual_ refresh mode: In _Auto_ mode, the hologram is re-rendered everytime something in the scene changes, while in _Manual_ mode the hologram is only rendered if you click the refresh button. _NOTE: Due to the restrictions in the rendering pipeline Blender currently has for add-on developers, this mode can be quite slow. Hopefully, their will be a solution for that provided in future versions of Blender._

- **Quilt Viewer.** In the quilt viewer mode, you can load or select a rendered quilt image and display it as a hologram in the Looking Glass. So, this mode is basically here to enjoy the fruits of your work. Playing animations is not supported ... yet.

### Camera Setup & Quilt Rendering

You can render still scenes and animation frames as complete quilt images. To start the rendering process, you basically follow the usual Blender workflow:

- select an existing camera in _Looking Glass → Camera Setup → Camera_ or create a new camera by clicking "+" in the same panel
- select _Looking Glass → Quilt Setup & Rendering → Use Device Settings_ to adjust the render settings based on your currently selected Looking Glass or use the controls below the checkbox to manually control the quilt output
- locate the camera to the specific view you would like to render
- adjust the render and post-processing settings in the usual Blender panels (_NOTE: Image dimensions are overwritten by the add-on based on your connected Looking Glass or your manual settings under _Looking Glass → Quilt Setup & Rendering__)
- click on _Looking Glass → Quilt Setup & Rendering → Render Quilt_ or _Looking Glass → Quilt Setup & Rendering → Render Animation Quilt_ in the add-on controls.

The _Render Quilt_ option will render the different different views separately. After the last view has been rendered, a quilt will be automatically assembled. For the _Render Animation Quilt_ option, the same will happen for each frame of the animation, which will result in one quilt per frame. After rendering, the created quilt image or animation frames have to be handled in the same way as normal renders. You can still render normal (non-holographic) images in Blender as you usually do. 

_NOTE: This functionality of the add-on can be used even if no Looking Glass is connected._

## License

The Blender add-on part of this project is licensed under the [GNU GPL v3 License](LICENSE).

The HoloPlay Core SDK libraries are property of the Looking Glass Factory and are licensed under the [HOLOPLAY CORE LICENSE AGREEMENT](lib/LICENSE). The HoloPlay Core SDK provides the fundamental software basis for the communication between the Looking Glass display hardware and any app created for it. It is, therefore, considered a system library. As a consequence, the linked libraries of this API are distributed in a compiled (non open-source) form with this free software in agreement with the system library exception defined by the GNU GPL v3 License.
