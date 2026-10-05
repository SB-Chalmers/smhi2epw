smhi2epw documentation
======================

``smhi2epw`` creates Actual Meteorological Year (AMY) EnergyPlus Weather files
from open data published by the Swedish Meteorological and Hydrological
Institute (SMHI). It combines quality-controlled station observations with
STRÅNG solar radiation at the coordinates you request.

The documentation begins with installation and a small working example. The
pipeline and scientific-method pages explain why the converter makes each
decision, while the numbered notebooks turn those concepts into reproducible
analyses suitable for students and practitioners.

.. important::

   Generated files use Local Standard Time and deliberately ignore daylight
   saving transitions, as required for continuous EPW simulation calendars.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   installation
   quickstart
   cli
   python_api
   tutorials

.. toctree::
   :maxdepth: 2
   :caption: Concepts and methods

   pipeline
   limitations
   provenance
   weather_recovery
   troubleshooting
   bibliography

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api
   internals

