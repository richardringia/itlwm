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
| `cfg/bz.c: iwl_gl_trans_cfg`, `iwl_cfg_gl` | `ItlIwx.cpp` cfg tables | todo |
| `pcie/drv.c: 0x272b → iwl_gl_trans_cfg`, `_IWL_DEV_INFO(GL, FM)` rows | `iwx_devices[]`, `iwl_dev_info_table[]` | todo |
| `iwl-csr.h: CSR_GP_CNTRL_REG_FLAG_BZ_MAC_ACCESS_REQ (BIT21)`, `MSIX_HW_INT_CAUSES_REG_SW_ERR_BZ (BIT5)` | `if_iwxreg.h` | todo |
| `pcie/trans.c` 11 BZ branches (reset, mac access, sw_reset, power, interrupts) | `iwx_*` equivalents | todo |
| `pcie/rx.c` 4 BZ branches (RBD/queue regs) | `iwx_rx_*` | todo |
| `pcie/trans-gen2.c` 2 (fw start / IML) ; `pcie/tx-gen2.c` 1 | `iwx_start_fw`, `iwx_tx` | todo |
| `iwl-io.c` 2 (grab NIC access for BZ) | `iwx_nic_lock` | todo |
| MSI-X vector allocation (`iwl_pcie_set_interrupt_capa`) | `iwx_attach` interrupt setup | todo |
| fw API 68 → 92: TLVs, MLD cmds (Phase 3) | many | todo |

## Decisions
- Firmware API target: **92** (Linux 6.12 BZ range 90–93).
- MSI-X: single vector (shared causes) first.
