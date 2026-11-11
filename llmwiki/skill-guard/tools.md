# Skill Guard tools

## skillguard_scan_installed

Scan every installed skill and list each as clean, approved, quarantined or flagged, with file and line. Inputs: `include_clean` (optional).

## skillguard_decide

Record the user's decision for one skill's exact current version. Always requires a person to confirm. Inputs: `skill`, `decision` (`approve` or `quarantine`), both required.
