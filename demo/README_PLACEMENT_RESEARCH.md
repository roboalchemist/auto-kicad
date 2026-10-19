# PCB Component Placement Optimization - Research Documentation

This directory contains comprehensive research documentation on objective functions and scoring metrics for PCB and integrated circuit (IC) component placement optimization.

## Document Overview

### 1. PCB_PLACEMENT_METRICS_RESEARCH.md (7.8 KB)
**Overview of placement optimization metrics**

Quick reference for all major metrics used in academic research and industry tools:
- **HPWL (Half-Perimeter Wirelength)** - Core metric for routing cost estimation
- **Density Cost** - Ensures uniform component distribution
- **Congestion Cost** - Predicts routing feasibility and violations
- **Proxy Cost** - Composite objective function combining all metrics
- Secondary metrics (net crossing, Steiner trees, timing-driven weights)

**Best for:** Getting a 20-minute overview of what metrics exist and why they matter

---

### 2. PLACEMENT_METRICS_REFERENCE.md (13 KB)
**Detailed technical reference with implementation examples**

Complete implementation guide with Python code examples:
- Metric definitions with mathematical formulas
- Step-by-step algorithms with pseudocode
- Python implementations for HPWL, density, and congestion computation
- Parameter tuning guidance for OpenROAD global placer
- Properties, ranges, and interpretation guidance for each metric

**Best for:** Implementing placement metrics from scratch; understanding algorithm details

---

### 3. RESEARCH_SOURCES.md (13 KB)
**Complete bibliography with direct links to papers and tools**

Academic foundation and tools:
- 8 peer-reviewed academic papers (all with direct PDF links)
- 4 major open-source tool repositories (OpenROAD, RePlAce, Circuit Training, MacroPlacement)
- Implementation cross-references showing where each metric is coded
- Benchmark datasets (ISPD, MacroPlacement testcases)
- Implementation timeline and phased approach

**Best for:** Finding original research, accessing papers, discovering tools and code

---

## Key Metrics Summary

| Metric | Formula | Weight | Source Paper |
|--------|---------|--------|--------------|
| **HPWL** | (x_max - x_min) + (y_max - y_min) per net | 1.0 | ePlace (2015) |
| **Density Cost** | avg(top 10% grid densities) × 0.5 | 1.0 | Circuit Training (2021) |
| **Congestion Cost** | avg(top 5% congestion values) | 0.5 | RUDY (2007) |
| **Proxy Cost** | W_wl×Cost_wl + W_dens×Cost_dens + W_cong×Cost_cong | Combined | Google Brain |

---

## Quick Links

### Academic Papers (All Directly Accessible)
1. **ePlace** (Lu et al., 2015) - Electrostatics-based placement
   - https://cseweb.ucsd.edu/~jlu/papers/eplace-todaes14/paper.pdf

2. **RePlAce** (Cheng et al., 2019) - Routability-driven placement
   - https://vlsicad.ucsd.edu/Publications/Journals/j126.pdf

3. **RUDY** (Spindler & Johannes, 2007) - Routing congestion estimation
   - https://past.date-conference.com/proceedings-archive/2007/DATE07/PDFFILES/08.7_1.PDF

4. **MacroPlacement Assessment** (TILOS AI, 2023) - Detailed metric documentation
   - https://vlsicad.ucsd.edu/Publications/Conferences/396/c396.pdf
   - https://tilos-ai-institute.github.io/MacroPlacement/Docs/ProxyCost/

### Open-Source Tools
1. **OpenROAD Global Placer** - RePlAce algorithm, production-ready
   - https://github.com/The-OpenROAD-Project/OpenROAD
   - Documentation: https://openroad.readthedocs.io/

2. **Circuit Training** - Google Brain's RL-based placement
   - https://github.com/google-research/circuit_training

3. **MacroPlacement** - Research benchmarks and metric validation
   - https://github.com/TILOS-AI-Institute/MacroPlacement

---

## How These Metrics Are Used

### In Academic Research
- **Benchmark comparisons** - Standard metrics for evaluating placement quality
- **Algorithm validation** - Measuring improvement over baselines
- **Metric weighting studies** - Finding optimal trade-offs between objectives

### In Industrial Tools
- **OpenROAD**: Uses RePlAce algorithm with HPWL + density + congestion
- **Cadence Innovus**: Proprietary metrics (similar structure publicly unknown)
- **Google's Circuit Training**: Uses all three metrics in RL reward function

### In Your PCB/IC Design Flow
1. Run placement optimizer with objective function
2. Compute metrics for result evaluation
3. Compare against reference implementations
4. Iterate weights to improve specific metric

---

## Implementation Roadmap

If implementing from scratch:

**Week 1: HPWL Only**
- Reference: `PLACEMENT_METRICS_REFERENCE.md` (Metric 1 section)
- Time: 2-3 hours
- Complexity: Low (O(n) per net)
- Accuracy: ±15-20% vs actual routed wirelength

**Week 2: Add Density**
- Reference: `PLACEMENT_METRICS_REFERENCE.md` (Metric 2 section)
- Time: 4-6 hours
- Complexity: Medium (grid-based computation)
- Benefit: Prevents routing congestion hotspots

**Week 3: Add Congestion**
- Reference: `PLACEMENT_METRICS_REFERENCE.md` (Metric 3 section)
- Time: 6-8 hours
- Complexity: High (multi-grid net routing)
- Benefit: Predicts routing violations before detailed routing

**Week 4: Tune & Validate**
- Reference: `RESEARCH_SOURCES.md` (benchmark datasets section)
- Validation against MacroPlacement implementation
- A/B testing against reference solutions

---

## Default Parameters

### Circuit Training (Research Standard)
```
W_wirelength = 1.0
W_density = 1.0
W_congestion = 0.5
```

### Google Production (Private, Inferred)
```
W_wirelength = 1.0
W_density = 0.5      # Less aggressive density control
W_congestion = 0.5
```

### OpenROAD Global Placer
```
init_wirelength_coef = 0.25
init_density_penalty = 0.00008
routability_target_rc_metric = 1.01
```

---

## Validation Approach

To verify your implementation:

1. **Against MacroPlacement** (recommended)
   - Compute metrics on Ariane benchmark
   - Compare output within ±0.001% accuracy
   - Reference: https://tilos-ai-institute.github.io/MacroPlacement/Docs/ProxyCost/#comparison-with-googles-plc_client

2. **Against Circuit Training**
   - Use public Ariane testcase
   - Compare proxy cost components
   - Reference: https://github.com/google-research/circuit_training

3. **Against OpenROAD**
   - Run on ISPD benchmarks
   - Compare final placement metrics
   - Reference: https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts

---

## File Relationships

```
README_PLACEMENT_RESEARCH.md (this file)
├── PCB_PLACEMENT_METRICS_RESEARCH.md
│   └── Quick overview of all metrics
│       (Reference for: what metrics exist, why they matter)
│
├── PLACEMENT_METRICS_REFERENCE.md
│   └── Detailed technical guide with code
│       (Reference for: how to implement, algorithm details)
│
└── RESEARCH_SOURCES.md
    └── Complete bibliography and tools
        (Reference for: finding papers, accessing code, benchmarks)
```

---

## Academic Context

This research synthesizes findings from:
- **2015-2019**: ePlace family algorithms establishing HPWL + density + congestion framework
- **2021**: Google's Nature paper on RL-based placement with detailed metric definitions
- **2023-2025**: TILOS AI Institute's comprehensive metric validation and open-source implementations

All papers are freely accessible (not behind paywalls) and all tools are open-source.

---

## Key Insights from Research

1. **HPWL alone is insufficient** - Optimizing only wirelength increases congestion
2. **Density control is essential** - Uniform distribution prevents routing violations
3. **Early congestion estimation saves time** - RUDY's grid-based approach is fast and accurate (80-90% correlation with actual routing)
4. **Weights matter significantly** - Tuning W_wl, W_dens, W_cong can trade off different optimization goals
5. **Metric trade-offs are inherent** - You cannot simultaneously minimize all three without compromise

---

## Contact / Attribution

Research compilation created: March 2026

Sources:
- ePlace research group (UC San Diego)
- RePlAce/Circuit Training team (Google Brain, UC San Diego)
- TILOS AI Institute (UC San Diego)
- The OpenROAD Project

---

**Next Steps:**
1. Read `PCB_PLACEMENT_METRICS_RESEARCH.md` for overview (15 minutes)
2. Review implementation examples in `PLACEMENT_METRICS_REFERENCE.md` (30 minutes)
3. Access papers in `RESEARCH_SOURCES.md` for detailed understanding (as needed)
4. Implement metrics incrementally following the 4-week roadmap
5. Validate against MacroPlacement reference implementation

