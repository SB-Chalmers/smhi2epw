Installation and setup
======================

Requirements
------------

``smhi2epw`` requires Python 3.11 or newer and internet access when compiling
live SMHI data. Reading an existing EPW file works offline. A virtual
environment is strongly recommended so the package and notebook tools do not
interfere with other projects.

Create a virtual environment
----------------------------

On macOS or Linux::

   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip

On Windows PowerShell::

   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip

If PowerShell blocks activation, either adjust the current user's execution
policy according to Microsoft guidance or call ``.venv\Scripts\python``
directly.

Install for normal use
----------------------

Install the released command line and Python API::

   python -m pip install smhi2epw

Install the optional tutorial environment when working through notebooks::

   python -m pip install "smhi2epw[tutorials]"
   jupyter lab

Install from a source checkout
------------------------------

Contributors and readers of the bundled notebooks should clone the repository
and use an editable installation::

   git clone https://github.com/snjsomnath/smhi2epw.git
   cd smhi2epw
   python -m pip install -e ".[dev,docs,tutorials]"

Verify the environment
----------------------

The following commands should report a version and display CLI help::

   python -c "import smhi2epw; print(smhi2epw.__version__)"
   smhi2epw --help

Inside Jupyter, verify that ``import sys; print(sys.executable)`` points to the
same virtual environment. If it does not, select the matching Python kernel or
register one with ``python -m ipykernel install --user --name smhi2epw``.

