## REFACTORING OF ALICE
- get rid of the lightfield window and handle the context override
  => if we don't have a lughtfield window anymore, can we keep the full add-on
     functionality that enables separate Viewport settings for the vightfield Viewport?

- add an set_view_data() to pylio's BaseLightfieldImageFormat to update view data
  (or should we use the views property?)

- handle installation of pyLightIO and its dependencies from preference pane or
  install automatic on startup (?)

  => check: if 'pip install' to defined path, are dependencies also installed there?

- store user defined presets

- decide: move all panel / ui related things to an extra file 'ui.py' (?)

- decide: remove the quilt debug view button or find a way to activate from within Alice?

## BUGS / ENHANCEMENTS

- if no LG is connected the preset can't be read, which results in an exception
  as soon as a camera is selected in the add-on panel



## DOCUMENTATION

- document the custom preset functionality
