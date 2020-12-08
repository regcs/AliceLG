# Alice/LG - Unofficial Looking Glass Addon for Blender

Let Alice take your Blender artworks through the Looking Glass. This guide is to get you started. 

## Background
This addon was created for the use with the Looking Glass lightfield display. I am not associated with the Looking Glass Factory and devoloped this tool in my freetime because I love Blender and this new amazing display technology created by the Looking Glass Factory. 

If you like this addon, I would be grateful if you would support its development with a donation. Thank you!

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

2. Install Alice/LG by opening Blender:
   - In the menu, navigate to _Edit → Preferences → Add-ons → Install → Install Add-on_
   - Select the zip file and click "Install"
   - Enable the addon by activating the check box next on the left

## Usage

### Addon Controls

After the installation you find a _Looking Glass_ tab in each Blender viewport. Depending on the current selections, the tab has four control categories:

**General**
Contains the display selection, a view resolution selection, a button to turn on/off the Lightfield Window, and the buttons to start quilt rendering.

**Camera Settings**
The option to select one of the cameras in the scene, which defines the camera view for the lightfield viewport and the quilt rendering.

**Lightfield Window**
The lightfield / hologram is rendered to a separate window, which needs to be placed inside your Looking Glass display. In this category you find options to switch between two different modes for the lightfield Window: _Viewport_ and _Quilt Viewer_.

**Shading & Overlay Settings**
If the lightfield window is in _Viewport_ mode, it basically acts like a native Blender viewport - except that it's a holographic viewport. The settings for this (lightfield) viewport are defined here.

### Lightfield Window & Viewport

The lightfield window is the place where the hologram is rendered. It can be opened via a click on the button: _Looking Glass → General → Lightfield Window_. After it was opened, move the window to your Looking Glass screen and click the _Looking Glass → General → Toggle Fullscreen Mode_ button, which appeared after the lightfield window was opened.

### Rendering

The addon can be used without having a Looking Glass connected. You can still render out complete quilt images and animation frames. To start the rendering, you follow the Blender workflow:

- set up a camera and a camera view you would like to render
- adjust the render settings (and the animation settings)
- enter the compositor settings

Instead of pressing _F12_ or _Alt + F12_ or choosing the _Render Image/Animation_, respectively, click on _Looking Glass → General → Render Quilt_ or _Looking Glass → General → Render Animation Quilt_ in the addon controls.
