# Alice/LG - Unofficial Looking Glass Addon for Blender
**Version:** 1.0 (last updated: December 08th, 2020)

**Author:** Christian Stolze (mail: ...)

Let Alice take your Blender artworks through the Looking Glass. This guide is to get you started. 

## Background
This addon was created for the use with the Looking Glass lightfield display. I am not associated with the Looking Glass Factory and devoloped this tool privately in my freetime because I love Blender and the amazing new display technology created by the [Looking Glass Factory](https://lookingglassfactory.com/). 

If you like this addon, I would be grateful if you would support its development with a donation. *LINK MISSING*

## Features
- seamless integration into the common Blender workflow
- lightfield viewport in the Looking Glass with automatic and manual view refresh
- option to display a viewcone representing the Looking Glass volume in the scene
- render any camera view as single quilt image or animation

## System Requirements
- Windows or macOS (Linux not tested yet)
- Blender 2.9x
- Holoplay Service App
- Holoplay Core SDK

## Installation

1. Install the Holoplay Service App and the Holoplay Core SDK on your PC or Mac.

2. Install the Alice/LG addon:
   - Open Blender
   - In the main menu, navigate to _Edit → Preferences → Add-ons → Install → Install Add-on_
   - Select the zip file and click "Install"
   - Enable the addon by activating the check box next on the left

## Usage

### Addon Controls

After the installation you find a _Looking Glass_ tab in each Blender viewport. Depending on the current selections, the tab has four control categories:

**General.** Contains the display selection, a view resolution selection, a button to turn on/off the Lightfield Window, and the buttons to start quilt rendering.

**Camera Settings.** The option to select one of the cameras in the scene, which defines the camera view for the lightfield viewport and the quilt rendering.

**Lightfield Window.** The lightfield / hologram is rendered to a separate window, which needs to be placed inside your Looking Glass display. In this category you find options to switch between two different modes for the lightfield Window: _Viewport_ and _Quilt Viewer_.

**Shading & Overlay Settings.** If the lightfield window is in _Viewport_ mode, it basically acts like a native Blender viewport - except that it's a holographic viewport. The settings for this (lightfield) viewport are defined here.

### Lightfield Window & Viewport

The lightfield window is the place where the hologram is rendered. It can be opened via a click on the button: _Looking Glass → General → Lightfield Window_. After it was opened, move the window to your Looking Glass screen and click the _Looking Glass → General → Toggle Fullscreen Mode_ button, which appeared after the lightfield window was opened. Only in fullscreen mode the hologram will be displayed correctly. The lightfield window can operate in two modes:

**Viewport.** In viewport mode, it basically acts like a native Blender viewport in the Looking Glass - except that it displays it as a hologram. You can choose between _Auto_ and _Manual_ refresh mode: In _Auto_ mode the hologram is re-rendered everytime something in the scene changes, while in _Manual_ mode the hologram is only rendered if you click the refresh button. **NOTE: Due to the restrictions in the rendering pipeline Blender currently has for addon developers, this mode can be quite slow. Hopefully, their will be a solution for that provided in future versions of Blender.**

**Quilt Viewer.** In the quilt viewer mode, you can load or select a rendered quilt image and display it as a hologram in the Looking Glass. So, this mode is basically here to enjoy the fruits of your work. Playing animations is not supported ... yet.

### Rendering

You can render complete quilt images and animation frames. To start the rendering process, you basically follow the known Blender workflow:

- set up a camera and a camera view you would like to render
- adjust the render settings (and the animation settings)
- enter the compositor settings (if needed)

Instead of pressing _F12_ or _Alt + F12_ or choosing the _Render Image/Animation_, respectively, click on _Looking Glass → General → Render Quilt_ or _Looking Glass → General → Render Animation Quilt_ in the addon controls. The _Render Quilt_ option will render the different different views separately. After the last view has been rendered, a quilt will be automatically assembled. For the _Render Animation Quilt_ option, the same will happen for each frame of the animation, which will result in one quilt per frame. 

This functionality of the addon can be used even if no Looking Glass is connected.

## License

The Blender addon part of this project is licensed under the [GNU GPL v3 License](LICENSE).

The HoloPlay Core SDK provides the fundamental software basis for the communication between the operating system and the Looking Glass display hardware and is required for the basic functionality of a Looking Glass display. As a consequence, the linked libraries of this API are distributed in a compiled form with this addon in agreement with the system library exception defined by the GNU GPL v3 License. The HoloPlayCore API libraries are property of the Looking Glass Factory and are licensed under the following agreement: **LINK TO LICENSE**.
