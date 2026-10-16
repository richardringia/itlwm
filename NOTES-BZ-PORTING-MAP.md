# Bz / Gl (BE200) porting map — Linux 6.12 iwlwifi → itlwm `hal_iwx`

Scope: everything needed to reach firmware **ALIVE** on `IWX_DEVICE_FAMILY_BZ`. Linux paths are relative to
`ref/linux-6.12/drivers/net/wireless/intel/iwlwifi/`; itlwm lines refer to `itlwm/hal_iwx/ItlIwx.cpp` on branch `be200`
(after commit 2f3e21f). "missing" = no `IWX_` define in `if_iwxreg.h` / `if_iwxvar.h`.

## 0. Register/define inventory (add to `if_iwxreg.h`)

| Linux define | value | itlwm | note |
|---|---|---|---|
| `CSR_GP_CNTRL_REG_FLAG_MAC_INIT` | BIT(6) | **missing** | Bz replacement for `INIT_DONE` (bit 2) |
| `CSR_GP_CNTRL_REG_FLAG_ROM_START` | BIT(7) | **missing** | Bz replacement for `UREG_CPU_INIT_RUN=1` |
| `CSR_GP_CNTRL_REG_FLAG_MAC_STATUS` | BIT(20) | **missing** | Bz "MAC ready" poll bit (replaces `MAC_CLOCK_READY`/`VAL_MAC_ACCESS_EN`) |
| `CSR_GP_CNTRL_REG_FLAG_BZ_MAC_ACCESS_REQ` | BIT(21) | present (2f3e21f) | |
| `CSR_GP_CNTRL_REG_FLAG_BUS_MASTER_DISABLE_STATUS` | BIT(28) | **missing** | |
| `CSR_GP_CNTRL_REG_FLAG_BUS_MASTER_DISABLE_REQ` | BIT(29) | **missing** | replaces `CSR_RESET_REG_FLAG_STOP_MASTER` |
| `CSR_GP_CNTRL_REG_FLAG_SW_RESET` | BIT(31) | **missing** | replaces `CSR_RESET_REG_FLAG_SW_RESET` (0x80 in CSR_RESET) |
| `CSR_FUNC_SCRATCH` | CSR_BASE+0x02c | **missing** | |
| `CSR_FUNC_SCRATCH_INIT_VALUE` | 0x01010101 | **missing** | |
| `CSR_IPC_SLEEP_CONTROL` / `_SUSPEND` / `_RESUME` | CSR_BASE+0x114 / 0x3 / 0 | **missing** | D3 only (Phase 5) |
| `CSR_DOORBELL_VECTOR` | CSR_BASE+0x130 | **missing** | NMI on Bz |
| `HBUS_TARG_WRPTR_RX_Q(q)` | `((q)+512) << HBUS_TARG_WRPTR_Q_SHIFT` | **missing** (`IWX_HBUS_TARG_WRPTR` exists) | RX write ptr on Bz |
| `MSIX_HW_INT_CAUSES_REG_RESET_DONE` | BIT(2) | **missing** (itlwm has `IML=BIT(2)` — Linux: `IML=BIT(1)`, `RESET_DONE=BIT(2)`; fix) | |
| `MSIX_HW_INT_CAUSES_REG_TOP_FATAL_ERR` | BIT(3) | **missing** | |
| `MSIX_HW_INT_CAUSES_REG_SW_ERR_BZ` | BIT(5) | present as `IWX_MSIX_HW_INT_CAUSES_REG_SW_ERR_V2` | |
| `TFD_QUEUE_BC_SIZE_GEN3_BZ` | 1024*4 | **missing** (`IWX_TFD_QUEUE_BC_SIZE_GEN3` = AX210 1024) | byte-count table size |
| `struct iwl_rx_completion_desc_bz` | `{__le16 rbid; u8 flags; u8 reserved[1];}` (4 B) | **missing** (`iwx_rx_completion_desc` = AX210 32 B) | |
| `IWL_RX_CD_FLAGS_FRAGMENTED` | BIT(0) | **missing** | |
| `CNVI_AUX_MISC_CHIP` / `_MAC_STEP(v)` / `_PROD_TYPE(v)` | 0xA2B800 (via `iwl_read_prph_no_grab`) / `(v&0xf000000)>>24` / `v&0xfff` | **missing** | GL prod type 0x910 |
| `CNVI_PMU_STEP_FLOW` / `_FORCE_URM` | 0xA2D588 / BIT(2) | **missing** | post-ALIVE only |
| `WFPM_OTP_CFG1_ADDR` | 0x00a03098 | **missing** | cdb/jacket info |
| `REG_CRF_ID_TYPE_FM` / `REG_CRF_ID_TYPE(v)` / `_STEP(v)` | 0x910 / `v&0xfff` / `(v&0x0f000000)>>24` | **missing** | RF id when no OTP |
| `IWL_PRPH_SCRATCH_SCU_FORCE_ACTIVE` | BIT(29) | check `iwx_prph_scratch` flags | GL only, opt-in |
| `CSR_CTXT_INFO_ADDR`/`CSR_IML_DATA_ADDR`/`CSR_IML_SIZE_ADDR`/`CSR_IML_RESP_ADDR`/`CSR_CTXT_INFO_BOOT_CTRL` | 0x118/0x120/0x128/0x12c/0x0 | present (gen3 path, verify names) | |
| `UREG_DOORBELL_TO_ISR6*`, `UREG_CHICK_MSIX_ENABLE`, `UREG_CPU_INIT_RUN`, `CSR_MSIX_IVAR`, `RFH_Q_FRBDCB_WIDX_TRG` | — | present | |

## 1. `pcie/trans.c` (11 branches)

| Linux fn : line | Bz behaviour | itlwm fn : line | action |
|---|---|---|---|
| `iwl_trans_pcie_sw_reset` :133 | set `CSR_GP_CNTRL.SW_RESET`(bit31), sleep 10–20 ms (pre-Bz: `CSR_RESET.SW_RESET` 0x80, 5 ms); then `prepare_card_hw` if retake | `iwx_start_hw` :3204 (`IWX_SETBITS(CSR_RESET, SW_RESET)` ×2), `iwx_stop_device` :3257 | add `iwx_sw_reset(sc)` helper branching on family; call from both |
| `iwl_pcie_apm_stop_master` :471 | set `GP_CNTRL.BUS_MASTER_DISABLE_REQ`(29), poll `BUS_MASTER_DISABLE_STATUS`(28) 100 µs, sleep 10–20 ms (pre-Bz: `CSR_RESET.STOP_MASTER`, poll `MASTER_DISABLED`) | `iwx_apm_stop` :3074 | branch |
| `iwl_pcie_map_non_rx_causes` :1155 | IVAR cause list: common + `SW_ERR_BZ`(bit5) instead of `SW_ERR`(bit25); common list also has `RESET_DONE`(2) and `TOP_FATAL_ERR`(3) which itlwm lacks | `iwx_conf_msix_hw` :3117 | map `SW_ERR_V2` for Bz, `SW_ERR` otherwise; add `RESET_DONE`, `TOP_FATAL_ERR`; fix `IML` bit (1 not 2) |
| `_iwl_trans_pcie_stop_device` :1281 | clear `BZ_MAC_ACCESS_REQ`(21) instead of `MAC_ACCESS_REQ`(3) before `apm_stop` + `sw_reset(true)` | `iwx_stop_device` :3257 (`IWX_CLRBITS(GP_CNTRL, MAC_ACCESS_REQ)`) | branch |
| `iwl_trans_pcie_d3_suspend` :1507 | clear `BZ_MAC_ACCESS_REQ` + `MAC_INIT`(6) (pre-Bz: `MAC_ACCESS_REQ` + `INIT_DONE`) | no itlwm D3 path | Phase 5 |
| `iwl_pcie_d3_handshake` :1540 | write `CSR_IPC_SLEEP_CONTROL` (not `UREG_DOORBELL_TO_ISR6_SUSPEND/RESUME`), wait sx_complete | — | Phase 5 |
| `iwl_trans_pcie_d3_resume` :1595 | set `BZ_MAC_ACCESS_REQ` then `iwl_finish_nic_init` | — | Phase 5 |
| `__iwl_trans_pcie_grab_nic_access` :2209 | write=`BZ_MAC_ACCESS_REQ`(21), mask=poll=`MAC_STATUS`(20); pre-Bz: write `MAC_ACCESS_REQ`(3), poll `VAL_MAC_ACCESS_EN` with mask `MAC_CLOCK_READY|GOING_TO_SLEEP` | `iwx_nic_lock` :2311 | branch bits; 150 ms timeout unchanged |
| `iwl_trans_pcie_release_nic_access` :2297 | clear `BZ_MAC_ACCESS_REQ` | `iwx_nic_unlock` :2344 | branch |
| `iwl_trans_pcie_sync_nmi` :3517 | MSI-X sw_err bit = `SW_ERR_BZ`(5) | `iwx_intr_msix` :12012 already ORs `SW_ERR` and `SW_ERR_V2` | OK (keep both) |
| `iwl_trans_pcie_alloc` :3578 | `bc_tbl_size = sizeof(iwl_gen3_bc_tbl_entry) * 4096` (AX210: 1024) | TX byte-count table alloc (`IWX_TFD_QUEUE_BC_SIZE_GEN3` users; see `iwx_enable_txq` :3416, `iwx_alloc_tx_ring`) | add `IWX_TFD_QUEUE_BC_SIZE_GEN3_BZ`, size by family |

## 2. `pcie/rx.c` (4)

| Linux fn : line | Bz behaviour | itlwm fn : line | action |
|---|---|---|---|
| `iwl_pcie_rxq_inc_wr_ptr` :195 | write `HBUS_TARG_WRPTR = write_actual \| HBUS_TARG_WRPTR_RX_Q(q)` (AX210: `RFH_Q_FRBDCB_WIDX_TRG(q)`) | `iwx_update_rx_desc` :5114 (writes `IWX_RFH_Q_FRBDCB_WIDX_TRG`) | branch |
| `iwl_pcie_used_bd_size` :669 | used-BD entry = `iwl_rx_completion_desc_bz` (4 B) vs AX210 `iwl_rx_completion_desc` (32 B) | `iwx_alloc_rx_ring` :2488 (`used_bd` alloc with `sizeof(iwx_rx_completion_desc)`), `iwx_reset_rx_ring` :2577 | size by family |
| `iwl_pcie_get_rxb` :1463 | read `cd[i].rbid` (le16) + `flags & FRAGMENTED` from the 4-byte desc | `iwx_rx_pkt`/`iwx_notif_intr` :11394/:11829 where `used_bd` is read | branch on family |
| `iwl_pcie_irq_msix_handler` :2292 | `sw_err = inta_hw & SW_ERR_BZ`; `TOP_FATAL_ERR` logged | `iwx_intr_msix` :12012 | already handles `SW_ERR_V2`; add `TOP_FATAL_ERR` log |

## 3. `pcie/trans-gen2.c` (2) + `pcie/tx-gen2.c` (1)

| Linux fn : line | Bz behaviour | itlwm fn : line | action |
|---|---|---|---|
| `iwl_pcie_gen2_apm_stop` :90 | clear `MAC_INIT`(6) instead of `INIT_DONE`(2) | `iwx_apm_stop` :3074 (`IWX_CLRBITS(GP_CNTRL, INIT_DONE)`) | branch |
| `iwl_trans_pcie_gen2_start_fw` :528 | after `ctxt_info_gen3_init` + `set_ltr`: read+write `CSR_FUNC_SCRATCH = 0x01010101`, set `GP_CNTRL.ROM_START`(7). AX210: `iwl_write_umac_prph(UREG_CPU_INIT_RUN, 1)`. Then `spin_for_iml` if `keep_ram_busy` (poll `CSR_MSIX_HW_INT_CAUSES_AD & IML`, write `CSR_LTR_LAST_MSG` loop, ≤100 ms) | `iwx_start_fw` :4936 (`UREG_CPU_INIT_RUN`), `iwx_set_ltr` :1050, `iwx_ctxt_info_gen3_init` :1158 | branch start method; add IML spin |
| `iwl_txq_dyn_alloc` (tx-gen2.c) :1044 | Bz **A-step** only: fixed TXQ size 4096 | `iwx_enable_txq` :3416 / dyn-alloc path | GL is C-step → skip (note only) |

## 4. `iwl-io.c` (2)

| Linux fn : line | Bz behaviour | itlwm fn : line | action |
|---|---|---|---|
| `iwl_force_nmi` :220 | `iwl_write32(CSR_DOORBELL_VECTOR, UREG_DOORBELL_TO_ISR6_NMI_BIT)` (AX210: umac prph `UREG_DOORBELL_TO_ISR6`) | grep `IWX_UREG_DOORBELL_TO_ISR6_NMI_BIT` users (error-dump path) | branch |
| `iwl_finish_nic_init` :461 | set `BZ_MAC_ACCESS_REQ \| MAC_INIT`, poll `MAC_STATUS`(20) (pre-Bz: set `INIT_DONE`, poll `MAC_CLOCK_READY`), 25 ms; then `UREG_CHICK` MSI/MSIX enable via `conf_msix_hw` | `iwx_apm_init` :3025 (`SETBITS INIT_DONE; poll MAC_CLOCK_READY 25000`), `iwx_start_hw` :3204 (same pattern repeated) | branch both sites |

## 5. Misc files

| Linux : line | Bz behaviour | itlwm | action |
|---|---|---|---|
| `pcie/drv.c` :1605 | resume: if `CSR_FUNC_SCRATCH == 0` the device lost power → full re-init | — | Phase 5 |
| `iwl-dbg-tlv.c` :610 | Bz allows DBGC alloc ids > DBGC3 | no ini-debug in itlwm | ignore |
| `fw/dump.c` :525 | error dump prints `CSR_FUNC_SCRATCH` | `iwx_nic_error` dump | nice-to-have |
| `mvm/ops.c` :1307 | `max_rx_aggregation_subframes = 512` (vs 256 HE) | reorder buffer sizing (`iwx_reorder_buffer`) | Phase 3/4 |
| `mvm/mvm.h` :1766 | AC→TX FIFO map `iwl_mvm_ac_to_bz_tx_fifo` (Bz has its own fifo numbering) | `iwx_ac_to_tx_fifo`/queue setup | Phase 3 (needed before data TX) |
| `mvm/fw.c` :653 | after ALIVE: `step_urm = CNVI_PMU_STEP_FLOW & FORCE_URM` | `iwx_load_ucode_wait_alive` :5017 | Phase 2 |
| `mvm/tx.c` :545, `mvm/rxmq.c` :174 | rate-selection / checksum quirks (< Bz only) | — | Phase 4 |
| `cfg/bz.c`, `iwl-config.h` | `iwl_gl_trans_cfg`, `iwl_cfg_gl`, `IWL_DEVICE_FAMILY_BZ`, `mac_addr_from_csr = 0x30`, `umac_prph_offset = 0x300000`, `IWL_NUM_RBDS_BZ_EHT 8192`, `min_txq_size 128`, `gp2_reg_addr 0xd02c68` | done in 2f3e21f except `mac_addr_from_csr`, `gp2_reg_addr`, rbds | add `mac_addr_from_csr` to `iwl_cfg` |

## 6. Check (a): MSI-X setup — Linux vs itlwm attach

Linux `iwl_pcie_set_interrupt_capa` (pcie/trans.c :1651): if `mq_rx_supported` → `pci_enable_msix_range(min=MSIX_MIN_INTERRUPT_VECTORS, max=min(ncpu+2, 16))`; on success `msix_enabled=true`, `def_irq` = last vector, `shared_vec_mask` = `NON_RX|FIRST_RSS` when fewer vectors; **falls back to MSI only if MSI-X allocation fails**. `iwl_pcie_conf_msix_hw` (:1193) then writes `UREG_CHICK = MSIX_ENABLE` and programs the IVAR table (`iwl_pcie_map_rx_causes` + `map_non_rx_causes`).

itlwm `iwx_attach` (:13427–13485): `if (0) { sc_msix = 1; }` → always `pci_intr_map_msi` (compat.cpp :90, a no-op shim) and selects the first `kIOInterruptTypePCIMessaged` (MSI) index; `iwx_conf_msix_hw` :3117 has the full IVAR programming and `UREG_CHICK_MSIX_ENABLE`, `iwx_intr_msix` :12012 the handler — both dead because `sc_msix` is never set.
Needed:
1. Before interrupt lookup, for `IWX_DEVICE_FAMILY_BZ` call `IOPCIDevice::configureInterrupts(kIOInterruptTypePCIMessagedX /*0x20000*/, 1, 1, 0)` — not in MacKernelSDK; declare via mangled symbol `__ZN11IOPCIDevice19configureInterruptsEjjjj` (present in Apple SDK `IOPCIDevice.h` :728).
2. Search `getInterruptType` for `kIOInterruptTypePCIMessagedX` (0x00020000) instead of `kIOInterruptTypePCIMessaged`; set `sc_msix = 1`; register `iwx_intr_msix`.
3. Single vector: all causes share vector 0 → IVAR values `0 | IWX_MSIX_NON_AUTO_CLEAR_CAUSE` as `iwx_conf_msix_hw` already does; add `RESET_DONE`/`TOP_FATAL_ERR` causes and the Bz `SW_ERR_V2` selection.
4. Keep the "hardware bug workaround" (clear `PCI_COMMAND_INTERRUPT_DISABLE`) out of the MSI-X path (Linux only does it for MSI failure).

## 7. Check (b): HW_REV / RF_ID / MAC address

Linux (`iwl_trans_pcie_alloc` :3689–3705, `get_crf_id` drv.c :1170–1215, `map_crf_id` :1221): `hw_rev = CSR_HW_REV`; `hw_rev_step = hw_rev & 0xF` (≥8000). Then with NIC access: set `WFPM_CTRL_REG |= AUX_IF_MAC_OWNER`, `hw_crf_id = prph(SD_REG_VER_GEN2 0xa2b800)`, `hw_cnv_id = prph(CNVI_AUX_MISC_CHIP)`, `hw_wfpm_id = umac_prph(WFPM_OTP_CFG1_ADDR 0xa03098)`. For `MAC_TYPE_BZ` (0x46) the step is taken from `CNVI_AUX_MISC_CHIP_MAC_STEP`; for **GL (0x47) hw_rev is used as-is** (GL C-step). RF id: `CSR_HW_RF_ID`; if 0 → `map_crf_id` (`REG_CRF_ID_TYPE_FM 0x910` → `IWL_CFG_RF_TYPE_FM<<12`). MAC address: `cfg->mac_addr_from_csr = 0x30` → `iwl_set_hw_address_from_csr` reads `CSR 0x38/0x3c` (STRAP), falls back to `0x30/0x34` (OTP), flips bytes (`iwl_flip_hw_address`).

itlwm `iwx_attach` :13520–13535: reads `CSR_HW_REV`, rewrites it into "old format" `(hw_rev & 0xfff0) | (STEP(hw_rev<<2)<<2)`, reads `CSR_HW_RF_ID`, matches `iwl_dev_info_table` on `CSR_HW_REV_TYPE`/`CSR_HW_RFID_TYPE` (:13523–13528). No crf/cnv/wfpm reads, no `map_crf_id`, no CSR MAC-address path (MAC comes from NVM_GET_INFO in `iwx_nvm_get`).
Needed for GL: `IWL_CFG_MAC_TYPE_GL` row matches via `CSR_HW_REV_TYPE == 0x47` (done); verify `IWX_CSR_HW_REV_TYPE_MSK 0x000FFF0` + the step rewrite keep type 0x47 intact; add `mac_addr_from_csr` + `iwx_set_hw_address_from_csr()` as fallback if NVM has no MAC (Linux: `nvm->hw_addr` empty on these parts); optional `map_crf_id` for robustness.

## 8. Check (c): firmware TLVs missing in `iwx_read_firmware` (:1422)

Linux `iwl_ucode_tlv_type` (fw/file.h) vs `IWX_UCODE_TLV_*` defines: missing by name/value — `MEM_DESC = 7` (alias of PAN), `PHY_INTEGRATION_VERSION = 61`, `SEC_TABLE_ADDR = 66`, `D3_KEK_KCK_ADDR = 67`, `CURRENT_PC = 68`, `FW_NUM_BEACONS = 0x100+2`, `FW_DBG_DUMP_LST = 0x1000`, plus the `IWL_UCODE_TLV_TYPE_*` debug-ini TLVs (0x1000000+, base exists as `IWX_UCODE_TLV_DEBUG_BASE`). Defines present but **not parsed** by `iwx_read_firmware` (not in its `case` list): `CMD_VERSIONS = 48`, `IML = 52`, `FW_FMAC_API_VERSION = 53`, `FW_RECOVERY_INFO = 57`, `HW_TYPE = 58`, `FW_FMAC_RECOVERY_INFO = 59`, `FW_FSEQ_VERSION = 60`, `PNVM_VERSION = 62`, `PNVM_SKU = 64`, `SEC_TABLE_ADDR = 66`, `D3_KEK_KCK_ADDR = 67`, `CURRENT_PC = 68`. A -92 GL ucode carries at least `IML` (required — Bz boots the IML from `CSR_IML_DATA_ADDR`), `CMD_VERSIONS` (needed to pick command versions), `PNVM_VERSION/SKU`, `PHY_INTEGRATION_VERSION`, `FW_FSEQ_VERSION`, `CURRENT_PC`, `SEC_TABLE_ADDR`, `D3_KEK_KCK_ADDR`, `FW_NUM_BEACONS`, and ini-debug TLVs. Unknown TLVs are skipped silently by both drivers (Linux iwl-drv.c :1312), so only `IML` and `CMD_VERSIONS` block ALIVE; verify how itlwm's gen3 path currently obtains the IML image (grep `iml` in `iwx_ctxt_info_gen3_init` :1158–1260 — AX210 firmware also ships TLV 52, so a parser may already exist outside the main switch).
