# PCB Component Placement Optimization: Complete Source Repository

## Academic Papers (PDF Available)

### Core Research Papers

#### 1. ePlace: Electrostatics-Based Placement (Lu et al., 2015)
- **Title:** ePlace: Electrostatics based Placement using Fast Fourier Transform and Nesterov's Method
- **Authors:** J. Lu, P. Chen, C.-C. Chang, L. Sha, D. J.-H. Huang, C.-C. Teng, C.-K. Cheng
- **Publication:** ACM TODAES 20(2), Article 17 (2015)
- **Link:** https://cseweb.ucsd.edu/~jlu/papers/eplace-todaes14/paper.pdf
- **Status:** ✅ Directly Accessible
- **Key Contribution:** Foundation for HPWL minimization using electrostatics; Nesterov's method solver
- **Metrics Covered:** HPWL, density, electrostatic force-based objective

#### 2. RePlAce: Advancing Solution Quality and Routability (Cheng et al., 2019)
- **Title:** RePlAce: Advancing Solution Quality and Routability Validation in Global Placement
- **Authors:** C.-K. Cheng, A. B. Kahng, I. Kang, L. Wang
- **Publication:** IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems, Vol. 38(9), pp. 1717-1730 (2019)
- **DOI:** 10.1109/TCAD.2018.2859389
- **Link:** https://vlsicad.ucsd.edu/Publications/Journals/j126.pdf
- **Status:** ✅ Directly Accessible
- **Key Contribution:** RePlAce algorithm; routability-driven placement; comprehensive metric framework
- **Metrics Covered:** HPWL, density, routability cost, timing-driven weighting

#### 3. RUDY: Fast and Accurate Routing Demand Estimation (Spindler & Johannes, 2007)
- **Title:** Fast and accurate routing demand estimation for efficient routability-driven placement
- **Authors:** P. Spindler, F. M. Johannes
- **Publication:** Design, Automation & Test in Europe (DATE) 2007
- **Link:** https://past.date-conference.com/proceedings-archive/2007/DATE07/PDFFILES/08.7_1.PDF
- **Status:** ✅ Directly Accessible
- **Key Contribution:** RUDY congestion estimation algorithm; grid-based routing resource prediction
- **Metrics Covered:** Routing congestion, grid edge utilization, congestion prediction

#### 4. ePlace-MS: Mixed-Size Circuit Placement (Lu et al., 2015)
- **Title:** ePlace-MS: Electrostatics based Placement for Mixed-Size Circuits
- **Authors:** J. Lu, H. Zhuang, P. Chen, H. Chang, C.-C. Chang, Y.-C. Wong, L. Sha, D. J.-H. Huang, Y. Luo, C.-C. Teng, C.-K. Cheng
- **Publication:** IEEE TCAD 34(5), pp. 685-698 (2015)
- **Link:** https://cseweb.ucsd.edu/~jlu/papers/eplace-ms-tcad14/paper.pdf
- **Status:** ✅ Directly Accessible
- **Key Contribution:** Mixed-size placement; density control for macro cells; area inflation techniques
- **Metrics Covered:** Density cost, area-weighted HPWL, macro congestion

#### 5. Improved Flop Tray-Based Design (Kahng et al., 2016)
- **Title:** Improved Flop Tray-Based Design Implementation for Power Reduction
- **Authors:** A. B. Kahng, J. Li, L. Wang
- **Publication:** IEEE/ACM ICCAD 2016, pp. 20:1-20:8
- **Key Contribution:** Clustering techniques; placement constraint handling

#### 6. Scalable Flip-Flop Clustering (Kahng et al., 2024)
- **Title:** Scalable Flip-Flop Clustering Using Divide and Conquer For Capacitated K-Means
- **Authors:** A. B. Kahng, S. Kundu, S. Thumathy
- **Publication:** ACM GLSVLSI 2024, pp. 177-184
- **Link:** https://vlsicad.ucsd.edu/Publications/Conferences/409/c409.pdf
- **Status:** ✅ Directly Accessible
- **Key Contribution:** Clustering for hierarchical placement; divide-and-conquer optimization

#### 7. Circuit Training & Macro Placement (MacroPlacement ISPD-2023)
- **Title:** An Updated Assessment of Reinforcement Learning for Macro Placement
- **Authors:** Multiple (TILOS AI Institute, UC San Diego)
- **Publication:** IEEE TCAD (Early Access Dec 2025); ISPD 2023 (peer-reviewed)
- **Links:**
  - IEEE Xplore: https://ieeexplore.ieee.org/document/11300304
  - ISPD 2023: https://vlsicad.ucsd.edu/Publications/Conferences/396/c396.pdf
  - arXiv: https://arxiv.org/abs/2302.11014
- **Status:** ✅ Directly Accessible
- **Key Contribution:** Comprehensive proxy cost computation; detailed metric documentation
- **Metrics Covered:** HPWL cost, density cost, congestion cost, composite proxy cost

#### 8. Circuit Training Nature Paper (Mirhoseini et al., 2021)
- **Title:** Chip Design with Deep Reinforcement Learning
- **Authors:** A. Mirhoseini et al. (Google Brain)
- **Publication:** Nature 2021
- **Key Contribution:** RL-based placement; metric definitions and weighting schemes
- **Access Note:** Original paper requires subscription; methodology implemented in open-source Circuit Training repo

---

## Open-Source Tools & Implementations

### 1. OpenROAD Global Placer (GPL)
- **Repository:** https://github.com/The-OpenROAD-Project/OpenROAD
- **Module:** `src/gpl/`
- **Algorithm:** RePlAce-based (Cheng et al., 2019)
- **Status:** ✅ Production Ready
- **Key Features:**
  - Electrostatics-based placement
  - Nesterov's method solver
  - Timing-driven mode
  - Routability-driven mode (RUDY integration)
  - Supports mixed-size designs
- **Documentation:** https://openroad.readthedocs.io/
- **Relevant Files:**
  - `include/gpl/Replace.h` - Header with metric definitions
  - `src/gpl/README.md` - Command documentation
  - `src/gpl/src/replace.cpp` - Implementation

### 2. RePlAce (Standalone)
- **Repository:** https://github.com/kunalghosh/RePlAce
- **Status:** ✅ Active Research
- **Key Features:**
  - Pure RePlAce algorithm implementation
  - Fast FFT-based HPWL computation
  - Routability metrics
  - Timing-driven placement
- **References:** https://vlsicad.ucsd.edu/Publications/Journals/j126.pdf

### 3. Circuit Training (Google Brain)
- **Repository:** https://github.com/google-research/circuit_training
- **Status:** ✅ Open Source (Active Development)
- **Key Components:**
  - `plc_wrapper_main` - Proxy cost calculator binary
  - Metric implementations:
    - Cost_wirelength (normalized HPWL)
    - Cost_density (gridcell-based)
    - Cost_congestion (grid-based routing)
  - Environment for RL-based placement
- **Documentation:** https://github.com/google-research/circuit_training/tree/main/docs
- **Relevant Files:**
  - `circuit_training/environment/environment.py` - Metric weighting (W_wl=1.0, W_dens=1.0, W_cong=0.5)
  - `circuit_training/environment/plc_client.py` - PLC file format and metric computation

### 4. MacroPlacement (TILOS AI Institute)
- **Repository:** https://github.com/TILOS-AI-Institute/MacroPlacement
- **Status:** ✅ Research & Benchmarking
- **Key Contributions:**
  - Detailed proxy cost documentation: https://tilos-ai-institute.github.io/MacroPlacement/Docs/ProxyCost/
  - Python implementation: `CodeElements/Plc_client/plc_client_os.py`
  - Comprehensive metric formulas with validation against Google's implementation
  - Testcases with reference solutions (Ariane, MemPool, NVDLA)
- **Metrics Validation:**
  - Verification against Google's plc_wrapper_main
  - ±0.0001% accuracy on HPWL cost
  - Validation table: https://tilos-ai-institute.github.io/MacroPlacement/Docs/ProxyCost/#comparison-with-googles-plc_client

---

## Metric Definitions by Source

### HPWL (Half-Perimeter Wirelength)

**Primary Source:** ePlace (Lu et al., 2015)
- Equation: net_hpwl = (x_max - x_min) + (y_max - y_min)
- Normalization: Cost = HPWL / [net_count × (height + width)]

**Implementation Reference:** Circuit Training
- File: `circuit_training/environment/environment.py`
- Function: Computes weighted sum of net HPWL values

**Validation:** MacroPlacement proxy cost documentation
- Empirical validation on Ariane (7-pin to 2000-pin benchmarks)
- Expected range: 0.05-0.40 (normalized)

---

### Density Cost

**Primary Source:** Circuit Training / Google Brain
- Formula: Cost_density = (average of top 10% gridcell densities) × 0.5
- Grid-based: Overlapping cell areas divided by grid cell area
- Correction factor: 0.5 (empirically determined to correct cluster bloating)

**Implementation Reference:** MacroPlacement
- File: `CodeElements/Plc_client/plc_client_os.py`
- Detailed step-by-step algorithm with examples
- URL: https://tilos-ai-institute.github.io/MacroPlacement/Docs/ProxyCost/#density-cost-computation

**Key Parameters:**
- Grid resolution: Typically 64×64, 128×128, or 256×256
- Top k selection: max(1, floor(num_grids × 0.1))

---

### Congestion Cost

**Primary Source:** RUDY (Spindler & Johannes, 2007)
- Grid-based routing resource estimation
- Separates horizontal and vertical congestion

**Implementation Reference:** RePlAce / OpenROAD
- File: `src/gpl/` in OpenROAD
- Metric coefficients: K1=1.0, K2=1.0, K3=0.0, K4=0.0 (horizontal, vertical, macro_h, macro_v)
- Integration with density-based inflation

**Detailed Algorithm:** MacroPlacement proxy cost documentation
- Separate procedures for 2-grid nets, 3-grid nets, and multi-grid nets
- Steiner-tree-like routing approximation
- Final cost: Average of top 5% grid congestion values
- URL: https://tilos-ai-institute.github.io/MacroPlacement/Docs/ProxyCost/#congestion-cost-computation

---

## Key Parameter Values

### Weights for Proxy Cost Optimization

| Implementation | W_wirelength | W_density | W_congestion |
|---|---|---|---|
| Circuit Training (public) | 1.0 | 1.0 | 0.5 |
| Google Production (private) | 1.0 | 0.5 | 0.5 |
| RePlAce Default | 1.0 | Adaptive | Adaptive |
| OpenROAD Default | 0.25 (init) | 0.00008 (penalty) | 0.5 (routability) |

### OpenROAD Global Placement Command

```tcl
global_placement \
    -init_wirelength_coef 0.25 \
    -reference_hpwl 446000000 \
    -init_density_penalty 0.00008 \
    -min_phi_coef 0.95 \
    -max_phi_coef 1.05 \
    -timing_driven \
    -routability_driven \
    -routability_target_rc_metric 1.01 \
    -routability_inflation_ratio_coef 2 \
    -nesterov_place_max_iter 5000
```

---

## Benchmark Datasets

### ISPD Benchmarks
- **Source:** International Symposium on Physical Design
- **Availability:** https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts
- **Designs:** Adaptec, IBM, ICCAD04 benchmarks

### MacroPlacement Testcases
- **Source:** https://github.com/TILOS-AI-Institute/MacroPlacement
- **Open Designs:**
  - Ariane (RISC-V processor, NanGate45 and ASAP7)
  - MemPool (memory-centric design)
  - NVDLA (NVIDIA Deep Learning Accelerator)
  - BlackParrot (RISC-V)
- **Technology Nodes:** 45nm, 12nm, 7nm, 5nm

### Circuit Training Reference Designs
- **Ariane:** Available in Circuit Training repo
- **TPU Blocks:** Internal Google designs (20 TPU v3/v4 blocks for pre-training)

---

## Implementation Guidance

### Incremental Implementation Strategy

1. **Phase 1: HPWL Only** (Week 1)
   - Implement basic HPWL computation
   - References: ePlace paper + Circuit Training code
   - Expected results: ±15-20% accuracy vs routed wirelength

2. **Phase 2: Add Density** (Week 2)
   - Implement grid-based density computation
   - References: MacroPlacement documentation + Circuit Training
   - Handle edge cases: boundary cells, zero-area cells

3. **Phase 3: Add Congestion** (Week 3)
   - Implement RUDY-based congestion
   - References: RUDY paper + MacroPlacement implementation
   - Validate against actual routing utilization

4. **Phase 4: Optimize Weights** (Week 4)
   - Tune W_wl, W_dens, W_cong
   - A/B test against reference implementations
   - Validate on benchmark designs

---

## Citation Format

### For RePlAce/ePlace Metrics
```bibtex
@article{cheng2019replace,
  title={RePlAce: Advancing solution quality and routability validation in global placement},
  author={Cheng, Chung-Kuan and Kahng, Andrew B and Kang, Ilgweon and Wang, Lutong},
  journal={IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems},
  volume={38},
  number={9},
  pages={1717--1730},
  year={2019},
  publisher={IEEE}
}
```

### For RUDY Congestion
```bibtex
@inproceedings{spindler2007fast,
  title={Fast and accurate routing demand estimation for efficient routability-driven placement},
  author={Spindler, Peter and Johannes, Frank M},
  booktitle={Design, Automation \& Test in Europe Conference \& Exhibition},
  year={2007}
}
```

### For Circuit Training
```bibtex
@article{mirhoseini2021chip,
  title={Chip design with deep reinforcement learning},
  author={Mirhoseini, Azalia and others},
  journal={Nature},
  year={2021}
}
```

---

## Quick Access Links

| Resource | URL |
|----------|-----|
| ePlace Paper (PDF) | https://cseweb.ucsd.edu/~jlu/papers/eplace-todaes14/paper.pdf |
| RePlAce Paper (PDF) | https://vlsicad.ucsd.edu/Publications/Journals/j126.pdf |
| RUDY Paper (PDF) | https://past.date-conference.com/proceedings-archive/2007/DATE07/PDFFILES/08.7_1.PDF |
| OpenROAD Documentation | https://openroad.readthedocs.io/ |
| Circuit Training Repo | https://github.com/google-research/circuit_training |
| MacroPlacement Proxy Cost Docs | https://tilos-ai-institute.github.io/MacroPlacement/Docs/ProxyCost/ |
| MacroPlacement Code | https://github.com/TILOS-AI-Institute/MacroPlacement |

