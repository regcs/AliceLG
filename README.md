# Alice/LG 2.0 - The Blender Add-on for Looking Glass Displays

### Let [Alice/LG](https://github.com/regcs/AliceLG/releases) take your Blender artworks through the Looking Glass! This short guide is to get you started.

## About the Add-on
This add-on was created for the use of Blender with the Looking Glass holographic displays. I initially developed this add-on privately in my free time because I'm a fan of [Blender](https://www.blender.org/) as well as the amazing new holographic display technology created by the [Looking Glass Factory](https://lookingglassfactory.com/). The version 2.0 of Alice/LG was developed in collaboration with the Looking Glass Factory.

## Main Features
- integration into the common Blender workflow
- an optional view frustum representing the Looking Glass volume in the scene
- lightfield viewport in the Looking Glass with automatic and manual refresh modes
- render any camera view as single quilt image or quilt animation
- decide if you want to keep the separate view files or just the final quilt
- support for multiple scenes and view layers
- camera & quilt settings are saved with your Blender file
- support for all available Looking Glass displays (including the new Looking Glass Portrait)
- _Experimental feature:_ Detect incomplete render jobs (see below for details)

## System Requirements
- Windows, Linux, or macOS
- [Blender 2.93.6 or later](https://www.blender.org/download/)
- [Holoplay Service App](https://lookingglassfactory.com/software)

## Installation

1. [Download](https://lookingglassfactory.com/software) and install the Holoplay Service App on your PC or Mac.

2. Download the [zip file of the latest release](https://github.com/regcs/AliceLG/releases/) of this add-on.

3. Install _Alice/LG_ in Blender:
   - Open Blender
   - In the main menu, navigate to _Edit → Preferences → Add-ons → Install → Install Add-on_
   - Select the downloaded zip file and click "Install"
   - Enable the add-on by activating the check box on the left
   - Expand the preferences of the add-on by clicking on the small arrow next to the checkbox
   - Click the "Install" button to install required Python modules to the add-on directory
   - Restart Blender

## How to Use

The following provides some basic information which is going to help you to get started. But make sure, you also check out the [Getting Started Guide](https://docs.lookingglassfactory.com/artist-tools/blender) as well as the [very helpful tutorial](https://learn.lookingglassfactory.com/tutorials/blender) on the Looking Glass Factory website!

### Add-on Controls

After the installation you find a _Looking Glass_ tab in each Blender viewport. Depending on your current selections, the tab shows up to four control panels & subpanels:

- **Looking Glass.** Contains the Looking Glass display selection, a view resolution selection, and a button to turn on/off the lightfield window. Furthermore, it has two subpanels:

   - **Camera Setup.** Select one of the cameras in the scene to setup a view for the Looking Glass and the quilt rendering.

   - **Quilt Setup & Rendering.** Controls for starting a quilt render.

- **Lightfield Window.** The lightfield / hologram is displayed on your Looking Glass display via the HoloPlay Service App in a separate window. In this category you find options to switch between two different modes for the lightfield Window: _Viewport_ and _Quilt Viewer_. It has the following sub-panel:

   - **Shading & Overlay Settings.** If the lightfield window is in _Viewport_ mode, it acts as your holographic Blender viewport. The settings for this (lightfield) viewport are defined here.

### Lightfield Window & Viewport

The lightfield window is the place where the hologram is rendered. It can be opened via a click on the button: _Looking Glass → Lightfield Window_, if you have a Looking Glass connected and HoloPlay Service is running. The lightfield window can operate in two modes:

- **Viewport.** In viewport mode, it basically acts like a normal Blender viewport in the Looking Glass - except that it is holographic. You can choose between _Auto_ and _Manual_ refresh mode: In _Auto_ mode, the hologram is re-rendered everytime something in the scene changes, while in _Manual_ mode the hologram is only rendered if you click the refresh button. _NOTE: Due to some limitations of the rendering pipeline of Blender, this mode can be quite slow (< 5 fps). We are working on improving Blender with regard to this and, hopefully, future versions of Blender will increase the live view performance of Alice/LG._

- **Quilt Viewer.** In the quilt viewer mode, you can load or select a rendered quilt image and display it as a hologram in the Looking Glass. So, this mode is basically here to enjoy the fruits of your work. Playing animations is not supported yet. _NOTE: To display the quilt correctly, the correct quilt preset must be selected under _Looking Glass → Resolution_

### Camera Setup & Quilt Rendering

You can render still scenes and animation frames as complete quilt images. You can render for your currently connected device or for any other Looking Glass:

**(1) Rendering for your currently connected device**
- select your connected Looking Glass (if not already selected) and a quilt resolution under _Looking Glass → Resolution_
- select an existing camera in _Looking Glass → Camera Setup → Camera_ or create a new camera by clicking "+" in the same panel
- check the _Looking Glass → Quilt Setup & Rendering → Use Device Settings_ checkbox
- locate the camera to the specific view you would like to render
- adjust the render and post-processing settings in the usual Blender panels (_NOTE: Image dimensions are overwritten by the add-on based on your connected Looking Glass or your manual settings under _Looking Glass → Quilt Setup & Rendering__)
- click on _Looking Glass → Quilt Setup & Rendering → Render Quilt_ or _Looking Glass → Quilt Setup & Rendering → Render Animation Quilt_ in the add-on controls.

**(2) Rendering for other Looking Glasses**
- select an existing camera in _Looking Glass → Camera Setup → Camera_ or create a new camera by clicking "+" in the same panel
- uncheck the _Looking Glass → Quilt Setup & Rendering → Use Device Settings_ checkbox, if it is checked
- choose the Looking Glass you want to render for from the list _Looking Glass → Quilt Setup & Rendering → Device_
- choose the quilt preset/resolution you want to render for from the list _Looking Glass → Quilt Setup & Rendering → Quilt
- locate the camera to the specific view you would like to render
- adjust the render and post-processing settings in the usual Blender panels (_NOTE: Image dimensions are overwritten by the add-on based on your connected Looking Glass or your manual settings under _Looking Glass → Quilt Setup & Rendering__)
- click on _Looking Glass → Quilt Setup & Rendering → Render Quilt_ or (if you want to render animation frames) _Looking Glass → Quilt Setup & Rendering → Render Animation Quilt_ in the add-on controls.

The _Render Quilt_ option will render the different views separately. After the last view has been rendered, a quilt will be automatically assembled. For the _Render Animation Quilt_ option, the same will happen for each frame of the animation, which will result in one quilt per frame. After rendering, the created quilt image or animation frames have to be handled in the same way as normal renders. You can still render normal (non-holographic) images in Blender as you usually do.

_NOTE: Option (2) can be used even if no Looking Glass is connected._

### Incomplete Render Jobs (Experimental)

The add-on attempts to detect Blender crashes during quilt rendering as well as quilt animation rendering and prompts you with an option to continue or to discard an incomplete render job the next time you open the crashed file. The successful detection of an incomplete render job and its continuation requires that:

- the filename of the .blend-file did not change
- the file was saved before starting the render job **OR** no significant changes happened to the setup (e.g., camera position, render settings, etc.)
- the (temporary) view files of the incomplete render job are still on disk and not corrupted

While the add-on tries to check some basic settings, the user is highly recommended to check if the current render settings fit to the settings used for the incomplete render job before clicking the "Continue" button.

If you decide to discard the incomplete render jobs, the add-on will try to delete the view files of the incomplete render job.

_NOTE: This feature is considered to be 'experimental'. It might not detect crashes under all circumstances and might not succeed to continue the rendering always. If you encounter a situation were this feature failed, please submit a detailed bug report._

## Renderfarm Implementation (Experimental)

The rendering of still holograms and holographic animations can be a time-consuming task on. Therefore, this add-on provides a command line mechanism that was created for render farms which want to support the quilt rendering by Alice/LG on their systems. Since it has not been tested on a render farm environment yet, this feature is considered experimental. If you are working at a render farm and need help to implement this mechanism on your system, please [open an issue on the add-on's GitHub repository](https://github.com/regcs/AliceLG/issues).

### Basic Command Line Calls

As a first prerequisite, Alice/LG needs to be installed and activated on the render farm's Blender installation. To initiate a quilt rendering from the command line, there are two main calls which are understood by Alice/LG:

- `-alicelg-render`: Start the rendering of a single quilt.
- `-alicelg-render-anim`: Start the rendering of a quilt animation.

Both arguments require that Blender is started in background mode (i.e., using the '-b' command line argument) and with a .blend-file specified, which contains all the necessary render settings. Furthermore, both arguments must be preceded by a `--`. An example, which opens the file 'my_lg_hologram.blend' and starts rendering a single quilt looks like that:

`blender -b my_lg_hologram.blend -- -alicelg-render`

### Additional Parameters

The add-on also understands the some additional parameters to fine-tune the rendering process. These parameters are very similar to Blender's internal command line rendering parameters:

- `-o`  or `--render-output` `<path>`: Set the render path and file name. Automatically disables the "Add Metadata" option.
- `-s`  or `--frame-start` `<frame>`: Set start to frame `<frame>`, supports +/- for relative frames too.
- `-e`  or `--frame-end` `<frame>`: Set end to frame `<frame>`, supports +/- for relative frames too.
- `-j`  or `--frame-jump` `<frame>`: Set number of frames to step forward after each rendered frame
- `-f`  or `--render-frame`: Specify a single frame to render

**It is important that these arguments are specified after the mandatory `--`** to notify Blender that the arguments are meant for the add-on. An example call which would start Blender in background mode, load the 'my_lg_hologram.blend' file, and render a quilt animation from frame 10 to 24 with the base file name `quilt_anim` would look like this:

`blender -b my_lg_hologram.blend -- -alicelg-render-anim -o /tmp/quilt_anim.png -s 10 -e 24`

Another example, which would only render the frame 16 as a single quilt, would like this:

`blender -b my_lg_hologram.blend -- -alicelg-render -o /tmp/quilt.png -f 16`

## License & Dependencies

The Blender add-on part of this project is licensed under the [GNU GPL v3 License](LICENSE).

This Blender add-on partially relies on the following GPL-compatible open-source libraries / modules and their dependencies:

- pyLightIO licensed under Apache Software License 2.0
