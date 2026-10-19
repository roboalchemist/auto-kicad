# PCB Component Placement Optimization: Metrics & Objective Functions

## Overview
Research in PCB and integrated circuit (IC) placement uses standardized metrics to evaluate and optimize component positioning. The primary sources for this research include academic papers and open-source tools like RePlAce, OpenROAD, and Circuit Training.

## Key Metrics

### 1. HPWL (Half-Perimeter Wirelength)
**Metric Name:** Half-Perimeter Wirelength (HPWL)

**Formula:**
- For a single net with bounding box:
  - net_hpwl = (x_max - x_min) + (y_max - y_min)
  
- For entire design (weighted by net weight):
  - HPWL = Σ(net_weight × net_hpwl)
  - Cost_wirelength = HPWL / [net_count × (canvas_height + canvas_width)]

**Purpose:** Measures the total estimated routing length needed to connect components. Lower values indicate better placement.

**Reference:** 
- ePlace paper (Lu et al., 2015, ACM TODAES 20(2))
- RePlAce paper (Cheng et al., 2019, IEEE TCAD 38(9))
- Circuit Training (Google, Nature 2021)

---

### 2. Density Cost (Placement Density)
**Metric Name:** Placement Density Cost

**Formula:**
- Gridcell density = (sum of overlapped areas with grid / total gridcell area)
- n = number of grid rows × number of grid columns
- k = floor(n × 0.1), minimum k = 1
- Cost_density = (average density of top k densest gridcells) × 0.5

**Purpose:** Ensures components are distributed evenly across the board to avoid congestion hotspots.

**Key Parameters:**
- Weights in optimization: W_density typically 0.5-1.0
- The 0.5 factor corrects for standard cell cluster bloating

**Reference:** Circuit Training proxy cost documentation (TILOS AI Institute MacroPlacement)

---

### 3. Congestion Cost (Routing Congestion)

**Metric Name:** Routing Congestion Cost / RC (Routing Congestion) Metric

**Components:**
- Horizontal congestion due to net routing
- Vertical congestion due to net routing
- Macro congestion (blocked routing resources)

**Formula Structure:**
- Grid-based routing: Considers nets that span multiple grid cells
- Two-grid nets: Direct horizontal/vertical segments with weight w
- Multi-grid nets: Steiner-tree-like approximations
- Final cost = Average of top 5% congestion values across all grids

**RC Metric Coefficients (in RePlAce):**
- Weighted sum: RC = K1×horizontal + K2×vertical + K3×macro_h + K4×macro_v
- Default: K1=1.0, K2=1.0, K3=0.0, K4=0.0

**Purpose:** Predicts routing feasibility and identifies areas likely to have routing violations.

**Reference:** 
- RUDY (Spindler & Johannes, 2007, DATE)
- RePlAce routability-driven mode
- OpenROAD GlobalPlacer documentation

---

## Proxy Cost (Composite Objective Function)

**Formula:**
```
Proxy Cost = W_wirelength × Cost_wirelength 
           + W_density × Cost_density 
           + W_congestion × Cost_congestion
```

**Default Weights (Circuit Training):**
- W_wirelength = 1.0
- W_density = 1.0 (or 0.5 in production Google flows)
- W_congestion = 0.5

**Purpose:** Single composite metric combining multiple placement quality dimensions.

---

## Secondary Metrics

### 4. Net Crossing Numbers
**Definition:** Count of crossing nets (for non-hierarchical layouts)

**Relevance:** 
- Indicates potential routing complexity
- High crossing counts can indicate poor placement
- Minimizing crossings can reduce congestion

**Formula:**
- Net_crossings = count(nets_i × nets_j where routing_paths_cross)

---

### 5. Steiner Tree Approximations
**Definition:** Approximation of optimal routing trees to connect net pins

**Types:**
- Manhattan Steiner Tree (rectilinear)
- Rectilinear Minimal Steiner Tree (RMST)

**Usage:**
- More accurate wirelength estimation than HPWL
- Computational cost: O(n²) to O(n³) vs HPWL O(n)
- Used in detailed routing prediction

**Reference:**
- RePlAce uses fast FFT-based approximations
- ePlace uses Nesterov's method with electrostatic models

---

### 6. Timing-Driven Metrics (Secondary)
**Net Weight Scaling:**
- Nets with critical timing paths get higher weights
- Weight multiplier based on timing slack

**Formula:**
- weight = base + (timing_weight_max - 1) × (1 - slack_ratio)
- Applied before HPWL calculation

**Reference:** RePlAce timing-driven mode

---

## Related Academic References

### Core Papers:
1. **ePlace** (Lu et al., 2015)
   - "ePlace: Electrostatics based Placement using Fast Fourier Transform and Nesterov's Method"
   - ACM TODAES 20(2), article 17
   - PDF: https://cseweb.ucsd.edu/~jlu/papers/eplace-todaes14/paper.pdf

2. **RePlAce** (Cheng et al., 2019)
   - "RePlAce: Advancing Solution Quality and Routability Validation in Global Placement"
   - IEEE TCAD 38(9):1717-1730
   - PDF: https://vlsicad.ucsd.edu/Publications/Journals/j126.pdf

3. **RUDY** (Spindler & Johannes, 2007)
   - "Fast and accurate routing demand estimation for efficient routability-driven placement"
   - DATE 2007
   - PDF: https://past.date-conference.com/proceedings-archive/2007/DATE07/PDFFILES/08.7_1.PDF

4. **Circuit Training** (Google Brain)
   - "Chip Design with Reinforcement Learning"
   - Nature 2021
   - Proxy cost computation: https://github.com/google-research/circuit_training

5. **MacroPlacement Assessment** (TILOS AI Institute, 2023)
   - "An Updated Assessment of Reinforcement Learning for Macro Placement"
   - IEEE TCAD (accepted Dec 2025, early access)
   - ISPD-2023: https://vlsicad.ucsd.edu/Publications/Conferences/396/c396.pdf

---

## Open-Source Tools & Implementations

### OpenROAD Global Placer (gpl)
- **Module:** src/gpl/
- **Algorithm:** RePlAce-based
- **Key Features:**
  - Electrostatics-based placement
  - Timing-driven mode
  - Routability-driven mode with RUDY
  - Supports timing and congestion cost weighting
- **Reference:** https://github.com/The-OpenROAD-Project/OpenROAD

### RePlAce (Standalone)
- **Original Source:** https://github.com/kunalghosh/RePlAce
- **Based on:** ePlace algorithm
- **Key Implementations:**
  - Nesterov's method solver
  - HPWL estimation via FFT
  - Routability metrics

### Circuit Training (Google Brain)
- **Source:** https://github.com/google-research/circuit_training
- **Includes:** plc_wrapper_main (proxy cost calculator)
- **Metrics Implemented:**
  - Cost_wirelength (HPWL-based)
  - Cost_density (gridcell-based)
  - Cost_congestion (grid-based routing)

### MacroPlacement (TILOS AI Institute)
- **Documentation:** Detailed proxy cost breakdown
- **Python Implementation:** plc_client_os.py
- **Reference:** https://github.com/TILOS-AI-Institute/MacroPlacement

---

## Parameter Tuning in OpenROAD

### Global Placement Parameters:
```tcl
global_placement
    [-init_wirelength_coef 0.25]      # Initial WL coefficient
    [-reference_hpwl 446000000]        # Reference HPWL for normalization
    [-init_density_penalty 0.00008]    # Initial density penalty
    [-min_phi_coef 0.95]               # Min density target
    [-max_phi_coef 1.05]               # Max density target
    [-timing_driven]                   # Enable timing optimization
    [-routing_driven]                  # Enable routability optimization
    [-routability_target_rc_metric 1.01]  # Target congestion
    [-routability_inflation_ratio_coef 2] # Cell area inflation factor
```

---

## Key Insights from Research

1. **Metric Trade-offs:** HPWL minimization alone can increase congestion; balanced multi-objective optimization is necessary

2. **Congestion Prediction:** RUDY-based grid congestion is computationally efficient and correlates well with actual routing difficulty

3. **Density vs Wirelength:** There's often tension between minimizing wirelength and maintaining uniform density; careful weighting is crucial

4. **Steiner Tree Approximation:** For placement, HPWL is sufficient; detailed Steiner tree calculation is reserved for detailed routing phase

5. **Timing Considerations:** Critical path nets should be weighted more heavily to reduce delay; simulated annealing and RL-based methods can learn optimal weightings

