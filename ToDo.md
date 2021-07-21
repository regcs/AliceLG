## REFACTORING OF ALICE

- handle installation of pyLightIO and its dependencies from preference pane or
  install automatic on startup (?)

- handle multiview camera support

  => use write_still in multiview only if output filename is specificed

## BUGS / ENHANCEMENTS

- BUG: Shading & Overlay settings - the "CUSTOM" setting also changes the current viewport
- BUG: Low-res preview for Lightfield Window is not working
- BUG: The color management for the Offscreen management in the live view is wrong

    => the will be easy to handle if Gottfrieds commit is implemented in Blender 3.0

- select the default quilt based on the device type automatically when selecting a device

## DOCUMENTATION

- document the custom preset functionality
- add the doc_url property to the add-on as soon as the documentation is ready
