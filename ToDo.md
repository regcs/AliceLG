## REFACTORING OF ALICE

- handle installation of pyLightIO and its dependencies from preference pane or
  install automatic on startup (?)

  => check: if 'pip install' to defined path, are dependencies also installed there?

- decide: move all panel / ui related things to an extra file 'ui.py' (?)

- decide: how to handle the case if no LookingGlassCamera is activated? Use viewport matrix?

## BUGS / ENHANCEMENTS

- BUG: Loading a file, where the lightfield viewport was active is not initialized correctly

## DOCUMENTATION

- document the custom preset functionality
