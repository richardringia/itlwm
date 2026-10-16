# BE200 (Intel Wi-Fi 7, PCI 8086:272b) port notes

Branch `be200` of laobamac/itlwm. Plan and research: `~/hackintosh/docs/06-wifi-be200.md`.
Reference trees: `~/hackintosh/wifi/ref/linux-6.12/drivers/net/wireless/intel/iwlwifi` (mvm era, BZ fw API 90–93),
`~/hackintosh/wifi/ref/openbsd-iwx/`. Firmware: `~/hackintosh/wifi/firmware/` (`iwlwifi-gl-c0-fm-c0-92.ucode`, `.pnvm`).

## Baseline facts (itlwm as cloned, 2026-10-16)
- `itlwm/hal_iwx/ItlIwx.cpp` (~13.7k lines) = OpenBSD `if_iwx.c` port; firmware API **-68** (AX210 `so-a0-gf-a0-68`), `-63` for Ma.
- Device families: `IWX_DEVICE_FAMILY_22000`, `IWX_DEVICE_FAMILY_AX210` (`if_iwxvar.h:653`). Need `IWX_DEVICE_FAMILY_BZ`.
- Config tables: `iwl_cfg_trans_params` / `iwl_cfg` (`if_iwxvar.h` ~470–495), `iwx_devices[]` (`ItlIwx.cpp:12329`), `iwl_dev_info` matching by mac_type/rf_type/step (`ItlIwx.cpp` ~12360+).
- Interrupts: MSI-X *handler* exists (`iwx_intr_msix`, `sc_msix`) but attach hard-codes `if (0) sc_msix = 1` and maps plain MSI (`pci_intr_map_msi`). BE200 needs MSI-X → Phase 1 task.
- gen3 context info + PNVM already implemented (`iwx_ctxt_info_gen3_init` ~1158, `pnvm_dram`).
- Firmware embedded via `scripts/fw_gen.sh` → zlib-compressed blobs → `getFWDescByName(sc_fwname)`.

## Linux → itlwm porting map (fill in as we go)
| Linux (6.12) | itlwm | status |
|---|---|---|
| `cfg/bz.c: iwl_gl_trans_cfg`, `iwl_cfg_gl` | `ItlIwx.cpp` cfg tables | done 2f3e21f |
| `pcie/drv.c: 0x272b → iwl_gl_trans_cfg`, `_IWL_DEV_INFO(GL, FM)` rows | `iwx_devices[]`, `iwl_dev_info_table[]` | done 2f3e21f |
| `iwl-csr.h` Bz bits/registers (see NOTES-BZ-PORTING-MAP §0) | `if_iwxreg.h` | done 1097b26 (D3/CNVI/CRF regs still todo) |
| `pcie/trans.c` 11 BZ branches (reset, mac access, sw_reset, power, interrupts) | `iwx_sw_reset`, `iwx_nic_lock/unlock`, `iwx_apm_stop`, `iwx_stop_device`, `iwx_conf_msix_hw`, bc_tbl size | done 1097b26 (D3 paths deferred to Phase 5) |
| `pcie/rx.c` 4 BZ branches (RBD/queue regs) | RX wr ptr via HBUS_TARG_WRPTR, used_bd 4 B | done 1097b26 (completion descs still not read — itlwm drains in order) |
| `pcie/trans-gen2.c` 2 (fw start / IML) ; `pcie/tx-gen2.c` 1 | gen3 boot: FUNC_SCRATCH + ROM_START + IML spin; apm_stop MAC_INIT | done 1097b26 (tx-gen2 A-step quirk n/a for GL) |
| `iwl-io.c` 2 (grab NIC access, finish_nic_init) | `iwx_nic_lock`, `iwx_finish_nic_init` | done 1097b26 (force_nmi via CSR_DOORBELL_VECTOR todo) |
| MSI-X vector allocation (`iwl_pcie_set_interrupt_capa`) | `pci_intr_map_msix` (compat.cpp) + `iwx_attach` | done 1c120df/1097b26 — single shared vector |
| fw API 68 → 92: TLVs, MLD cmds (Phase 3) | many | todo |

## Phase 1 status (2026-10-16)
All attach/boot-path branches ported; **not compiled yet** (no Xcode). Next: build, fix errors, then test boot from the USB stick EFI and look for `IML load: irq=1` and ALIVE in the log. Open: `mac_addr_from_csr` fallback, `iwx_intr_msix` logging of RESET_DONE/TOP_FATAL_ERR, TLV parsing for -92 ucode.

## Decisions
- Firmware API target: **92** (Linux 6.12 BZ range 90–93).
- MSI-X: single vector (shared causes) first.
