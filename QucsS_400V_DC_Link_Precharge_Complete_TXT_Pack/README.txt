DC-LINK PRECHARGE TEXT PACKAGE
==============================

This package intentionally uses .txt extensions for the library, common core,
simulation cases, design document, and summary template.

Ngspice accepts a .txt file in a relative .include statement.

Keep all files in one project directory.

Recommended execution order:
  1. case_01_precharge_sequence.txt
  2. case_02_safe_discharge.txt
  3. case_03_dc_link_short_fault.txt
  4. case_04_main_contactor_weld_fault.txt

For Qucs-S:
  - Recreate the common power stage using native editable components.
  - Use the values and node names from dc_link_precharge_common_core.txt.
  - Add the switch models from dc_link_precharge_models.txt.
  - Use the PWL sources from each case for command and contact-state signals.
