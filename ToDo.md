## REFACTORING OF ALICE
- add an set_view_data() to pylio's BaseLightfieldImageFormat to update view data
  (or should we use the views property?)

- handle installation of pyLightIO and its dependencies from preference pane or
  install automatic on startup (?)

  => check: if 'pip install' to defined path, are dependencies also installed there?

- store user defined presets

- decide: move all panel / ui related things to an extra file 'ui.py' (?)

- decide: remove the quilt debug view button or find a way to activate from within Alice?

- handle the holographic cursor correctly
  => only show it, if the user is in camera mode and the mouse hovers over the active viewport
  => calculations are wrong at the moment

- decide: how to handle the case if no LookingGlassCamera is activated? Use viewport matrix?


## BUGS / ENHANCEMENTS

- BUG: quilt viewer is not updated under all circumstances

- BUG: Loading a file, where the lightfield viewport was active is not initialized correctly

- BUG: after adding a new scene, if the lightfield viewport was active, it is closed

- when opening a quilt image in quilt viewer, check for the metadata suffix

- overwrite the `sys.excepthook` to add unhandled exceptions to the log files; by default only WARNINGS and higher should be written to log, but we need a preferences option to make additional debugging info toggable by the user



## DOCUMENTATION

- document the custom preset functionality
