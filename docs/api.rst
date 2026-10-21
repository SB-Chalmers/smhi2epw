Public API reference
====================

The symbols below form the supported application-facing interface.

.. automodule:: smhi2epw

Compiler
--------

.. autoclass:: smhi2epw.EPWConfig
   :members:

.. autoclass:: smhi2epw.compiler.CompileResult
   :members:

.. autofunction:: smhi2epw.compile_epw

Reader
------

.. autofunction:: smhi2epw.read_epw

.. autodata:: smhi2epw.EPW_COLUMNS

Weather batches and morphing
----------------------------

.. autoclass:: smhi2epw.WeatherLocation
   :members:

.. autofunction:: smhi2epw.plan_amy_batch

.. autofunction:: smhi2epw.compile_amy_batch

.. autoclass:: smhi2epw.BatchResult
   :members:

.. autoclass:: smhi2epw.MorphConfig
   :members:

.. autofunction:: smhi2epw.morph_epw

.. autoclass:: smhi2epw.MorphResult
   :members:

.. autoclass:: smhi2epw.MorphingError
   :show-inheritance:

Station and diagnostics
-----------------------

.. autoclass:: smhi2epw.StationMeta
   :members:

.. autoclass:: smhi2epw.processing.ProcessingReport
   :members:

Exceptions
----------

.. autoclass:: smhi2epw.Smhi2EpwError
   :show-inheritance:

.. autoclass:: smhi2epw.IngestionError
   :show-inheritance:

.. autoclass:: smhi2epw.DataGapError
   :show-inheritance:

.. autoclass:: smhi2epw.ValidationError
   :show-inheritance:
