Numbered tutorials
==================

The notebooks form a progressive course. Start with installation and one file,
then move into comparison, extreme-weather analysis, data quality, solar
physics, and batch work. Network-dependent notebooks say so at the top and use
the normal cache. Notebook 05 explicitly downloads the linked OneBuilding
Gothenburg TMYx archive once, extracts only its EPW member, and then reuses it.
Set ``SMHI2EPW_TMY_PATH`` to choose a different local TMY.

Launch from the repository root::

   python -m pip install -e ".[tutorials]"
   jupyter lab examples/

.. toctree::
   :maxdepth: 1
   :caption: Tutorials

   notebooks/00_getting_started
   notebooks/01_inspect_an_epw
   notebooks/02_compare_locations
   notebooks/03_compare_years
   notebooks/04_identify_heatwaves
   notebooks/05_compare_amy_to_tmy
   notebooks/06_data_quality_and_gap_filling
   notebooks/07_solar_components
   notebooks/08_batch_generation
   notebooks/09_run_energyplus

Notebook outputs belong under ``examples/output`` and are intentionally not
version-controlled. This keeps examples reproducible and prevents old plots or
large weather files from being mistaken for current results.
