AUTOMOTIVE INPUT-PROTECTION MODEL PACK
======================================

Main model library:
  automotive_protection_models.lib

Complete common design:
  automotive_input_protection_core.inc

Runnable cases:
  case_nominal_12V.cir
  case_high_battery_16V.cir
  case_reverse_battery_minus14V.cir
  case_load_dump_60V.cir

Reference nominal design:
  automotive_input_protection_reference.cir

Documentation:
  automotive_input_protection_design_document.txt
  qucs_s_component_mapping.txt
  automotive_input_protection_summary_template.txt

Use all files from the same folder so the relative .include paths resolve.

The provided .cir/.inc files are ngspice-compatible reference design files.
Recreate the visual schematic in Qucs-S with native passives and map the PMOS,
TVS, and zener models using the supplied mapping guide.
