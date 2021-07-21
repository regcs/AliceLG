## REFACTORING OF ALICE

- handle installation of pyLightIO and its dependencies from preference pane or
  install automatic on startup (?)


- handle multiview camera support

  => separate functions for camera setup, (view) rendering, and quilt assembly
  => use write_still in multiview only if output filename is specificed

## BUGS / ENHANCEMENTS

- BUG: Shading & Overlay settings - the "CUSTOM" setting also changes the current viewport

- select the default quilt based on the device type automatically when selecting a device

## DOCUMENTATION

- document the custom preset functionality
- add the doc_url property to the add-on as soon as the documentation is ready
