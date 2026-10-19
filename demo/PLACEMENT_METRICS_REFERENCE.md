# PCB/IC Placement Optimization: Complete Metrics Reference

## Quick Reference Table

| Metric | Formula | Typical Range | Weight | Purpose |
|--------|---------|----------------|--------|---------|
| **HPWL** | (x_max - x_min) + (y_max - y_min) per net | Normalized 0-1 | 1.0 | Wirelength minimization |
| **Density Cost** | avg(top 10% grid densities) × 0.5 | 0-1 | 0.5-1.0 | Prevent congestion hotspots |
| **Congestion Cost** | avg(top 5% grid congestion values) | 0-∞ | 0.5 | Routing feasibility |
| **Net Crossing** | count(nets_crossing_other_nets) | 0-n² | N/A | Layout complexity indicator |

---

## Metric 1: HPWL (Half-Perimeter Wirelength)

### Definition
Estimated wirelength based on bounding box of net components. Called "half-perimeter" because it assumes optimal L-shaped routing (half of full perimeter).

### Mathematical Formulation

**Single Net HPWL:**
```
net_hpwl = (x_max - x_min) + (y_max - y_min)

Where:
  x_min = minimum x-coordinate of all pins in net
  x_max = maximum x-coordinate of all pins in net
  y_min = minimum y-coordinate of all pins in net
  y_max = maximum y-coordinate of all pins in net
```

**Total Design HPWL (Weighted):**
```
HPWL = Σ(net_i.weight × net_i.hpwl) for all nets i

Cost_wirelength = HPWL / [net_count × (canvas_height + canvas_width)]
```

### Implementation Example (Python)

```python
def compute_net_hpwl(pins):
    """Compute HPWL for a single net given pin positions."""
    if len(pins) < 2:
        return 0
    
    x_coords = [pin.x for pin in pins]
    y_coords = [pin.y for pin in pins]
    
    hpwl = (max(x_coords) - min(x_coords)) + (max(y_coords) - min(y_coords))
    return hpwl

def compute_wirelength_cost(nets, canvas_width, canvas_height):
    """Compute normalized wirelength cost across entire design."""
    total_hpwl = 0
    total_net_weight = 0
    
    for net in nets:
        net_hpwl = compute_net_hpwl(net.pins)
        total_hpwl += net.weight * net_hpwl
        total_net_weight += net.weight
    
    normalization_factor = total_net_weight * (canvas_height + canvas_width)
    cost_wirelength = total_hpwl / normalization_factor if normalization_factor > 0 else 0
    
    return cost_wirelength, total_hpwl
```

### Properties
- **Computational Complexity:** O(n) where n = number of nets
- **Accuracy:** ±15-20% vs actual routed wirelength
- **Advantage:** Fast computation, good correlation with routability
- **Limitation:** May underestimate wirelength for highly congested areas

### Historical References
- Introduced in early placement research (1980s-1990s)
- Extensively validated in ePlace (Lu et al., 2015)
- Standard metric in ISPD/ICCAD benchmarks

---

## Metric 2: Density Cost (Placement Density)

### Definition
Measures how uniformly components are distributed across the chip. Ensures no extreme density concentrations that block routing.

### Mathematical Formulation

**Gridcell Density:**
```
For each grid cell (i, j):
  density[i][j] = (sum of overlapped areas of cells with grid) / grid_area
  
Range: [0.0, 1.0] where 1.0 = completely filled
```

**Density Cost Computation:**
```
1. n = num_grid_rows × num_grid_columns
2. k = max(1, floor(n × 0.1))  # Top 10% of densest grids
3. sorted_densities = sort(density values in descending order)
4. Cost_density = (average of top k densities) × 0.5

The 0.5 factor empirically corrects for standard cell cluster bloating.
```

### Implementation Example (Python)

```python
import numpy as np

def compute_density_cost(cells, grid_rows, grid_cols, 
                         grid_width, grid_height, canvas_width, canvas_height):
    """Compute density cost using grid-based approach."""
    
    # Initialize grid
    density_grid = np.zeros((grid_rows, grid_cols))
    grid_area = (canvas_width / grid_cols) * (canvas_height / grid_rows)
    
    # Accumulate cell areas in each grid
    for cell in cells:
        # Find grid cells that overlap with this cell
        grid_x_min = int(cell.x / (canvas_width / grid_cols))
        grid_x_max = int((cell.x + cell.width) / (canvas_width / grid_cols))
        grid_y_min = int(cell.y / (canvas_height / grid_rows))
        grid_y_max = int((cell.y + cell.height) / (canvas_height / grid_rows))
        
        # Clamp to grid bounds
        grid_x_min = max(0, min(grid_x_min, grid_cols - 1))
        grid_x_max = max(0, min(grid_x_max, grid_cols - 1))
        grid_y_min = max(0, min(grid_y_min, grid_rows - 1))
        grid_y_max = max(0, min(grid_y_max, grid_rows - 1))
        
        # Add overlapped area to each grid cell
        for gi in range(grid_x_min, grid_x_max + 1):
            for gj in range(grid_y_min, grid_y_max + 1):
                # Compute overlapped area (simplified)
                cell_area = cell.width * cell.height
                density_grid[gj][gi] += cell_area / grid_area
    
    # Compute top 10% density average
    flat_densities = density_grid.flatten()
    k = max(1, int(len(flat_densities) * 0.1))
    top_k_densities = np.sort(flat_densities)[-k:]
    avg_top_density = np.mean(top_k_densities)
    
    cost_density = avg_top_density * 0.5
    
    return cost_density, density_grid
```

### Key Parameters
- **Grid Size:** Typically 64×64, 128×128, or 256×256
- **Top k Selection:** Exactly top 10% (or minimum 1 cell)
- **Correction Factor:** 0.5 (empirically determined)

### Properties
- **Range:** [0.0, 0.5] under ideal conditions
- **Sensitivity:** Detects micro-density variations
- **Objective:** Keep max density < 0.9-0.95 to allow routing

---

## Metric 3: Congestion Cost (Routing Congestion)

### Definition
Estimates routing resource demand in each grid cell. Predicts where routing violations are likely to occur.

### Mathematical Formulation

**Grid-Based Net Routing:**
```
For each net spanning multiple grids:
  - Identify source grid and sink grids
  - Route using Manhattan path (L-shaped or Steiner)
  - Accumulate horizontal and vertical edge usage

Grid edge utilization = (sum of net weights crossing edge) / edge_capacity
```

**Congestion Due to Two-Grid Nets:**
```
For net from (i₁, j₁) to (i₂, j₂) with weight w:

1. Horizontal segment: from min(i₁, i₂) to max(i₁, i₂) at row j₁
   → Add w to horizontal congestion of grids in segment

2. Vertical segment: from min(j₁, j₂) to max(j₁, j₂) at column i₂
   → Add w to vertical congestion of grids in segment
```

**Congestion Due to Multi-Grid Nets:**
```
For nets spanning >2 grids, use Steiner-tree-like routing:
  - Route horizontally first to x_sink, then vertically to y_sink
  - Or alternate routing pattern for balanced congestion
  - Weight each segment by net weight
```

**Final Congestion Cost:**
```
1. Concatenate horizontal_congestion_values and vertical_congestion_values
2. sorted_congestions = sort(concatenated values in descending order)
3. top_5_percent = ceil(len(sorted_congestions) × 0.05)
4. Cost_congestion = average(sorted_congestions[0:top_5_percent])
```

### Implementation Example (Python)

```python
import numpy as np

def compute_congestion_cost(nets, grid_rows, grid_cols, 
                            canvas_width, canvas_height):
    """Compute routing congestion cost."""
    
    h_congestion = np.zeros((grid_rows, grid_cols))  # Horizontal
    v_congestion = np.zeros((grid_rows, grid_cols))  # Vertical
    
    grids_per_x = canvas_width / grid_cols
    grids_per_y = canvas_height / grid_rows
    
    # Process each net
    for net in nets:
        # Find unique grids occupied by pins
        pin_grids = set()
        for pin in net.pins:
            gi = int(pin.x / grids_per_x)
            gj = int(pin.y / grids_per_y)
            gi = max(0, min(gi, grid_cols - 1))
            gj = max(0, min(gj, grid_rows - 1))
            pin_grids.add((gi, gj))
        
        if len(pin_grids) < 2:
            continue  # Single-grid nets don't contribute to congestion
        
        # For each pair of grids in net, add congestion
        pin_list = sorted(pin_grids)
        source = pin_list[0]
        
        for sink in pin_list[1:]:
            si, sj = source
            ti, tj = sink
            
            # Horizontal segment
            if si <= ti:
                for gi in range(si, ti):
                    h_congestion[sj][gi] += net.weight
            else:
                for gi in range(ti, si):
                    h_congestion[sj][gi] += net.weight
            
            # Vertical segment
            if sj <= tj:
                for gj in range(sj, tj):
                    v_congestion[gj][ti] += net.weight
            else:
                for gj in range(tj, sj):
                    v_congestion[gj][ti] += net.weight
    
    # Compute final cost from top 5% congestion
    all_congestion = np.concatenate([h_congestion.flatten(), v_congestion.flatten()])
    top_5_pct = max(1, int(len(all_congestion) * 0.05))
    top_5_values = np.sort(all_congestion)[-top_5_pct:]
    cost_congestion = np.mean(top_5_values)
    
    return cost_congestion, h_congestion, v_congestion
```

### Key Parameters (from RePlAce)
```
RC Metric = K1 × h_congestion + K2 × v_congestion + K3 × macro_h + K4 × macro_v

Default:
  K1 = 1.0  (horizontal weight)
  K2 = 1.0  (vertical weight)
  K3 = 0.0  (macro horizontal, usually 0)
  K4 = 0.0  (macro vertical, usually 0)
```

### Properties
- **Range:** [0, ∞] (unbounded, usually 0-10)
- **Interpretation:** >1.5 often indicates routing violations
- **Correlation:** ~0.8-0.9 with actual routing utilization

---

## Metric 4: Composite Proxy Cost

### Formula
```
Proxy Cost = W_wl × Cost_wirelength 
           + W_dens × Cost_density 
           + W_cong × Cost_congestion

Default weights (Circuit Training):
  W_wl = 1.0
  W_dens = 1.0 (production: 0.5)
  W_cong = 0.5
```

### Implementation

```python
def compute_proxy_cost(cells, nets, grid_rows, grid_cols,
                       canvas_width, canvas_height,
                       w_wl=1.0, w_dens=1.0, w_cong=0.5):
    """Compute composite proxy cost."""
    
    # Cost components
    cost_wl, _ = compute_wirelength_cost(nets, canvas_width, canvas_height)
    cost_dens, _ = compute_density_cost(cells, grid_rows, grid_cols,
                                        canvas_width, canvas_height)
    cost_cong, _, _ = compute_congestion_cost(nets, grid_rows, grid_cols,
                                              canvas_width, canvas_height)
    
    # Composite cost
    proxy_cost = (w_wl * cost_wl + 
                  w_dens * cost_dens + 
                  w_cong * cost_cong)
    
    return proxy_cost, {
        'wirelength': cost_wl,
        'density': cost_dens,
        'congestion': cost_cong
    }
```

---

## Secondary Metrics

### Net Crossing Number
**Formula:**
```
For each pair of nets (i, j):
  If their Manhattan paths cross: count++

Net_crossings = count of crossing net pairs
```

**Purpose:** Indicates layout complexity; high crossing often correlates with high congestion.

### Steiner Tree Length (for comparison)
**Definition:** Optimal tree connecting net pins with minimal additional points (Steiner points).

**Accuracy:** 5-10% more accurate than HPWL, but O(n²) computation vs O(n) for HPWL.

---

## Optimization Algorithm Parameters

### OpenROAD Global Placement (`global_placement` command)

```tcl
# Wirelength control
-init_wirelength_coef 0.25        # Start with 25% wirelength emphasis
-reference_hpwl 446000000         # Normalization baseline

# Density control
-density 0.7                       # Target 70% utilization
-init_density_penalty 0.00008      # Initial penalty coefficient
-min_phi_coef 0.95                 # Min density threshold
-max_phi_coef 1.05                 # Max density threshold

# Iteration control
-nesterov_place_max_iter 5000      # Max Nesterov iterations
-overflow 0.1                      # Stop when overflow < 10%

# Routability control
-routability_driven                # Enable RUDY congestion
-routability_target_rc_metric 1.01 # Target RC = 1.01
-routability_inflation_ratio_coef 2 # Cell expansion factor
-routability_max_density 0.99      # Max grid density allowed

# Timing control
-timing_driven                     # Enable timing optimization
-timing_driven_nets_percentage 10  # Consider 10% critical nets
-timing_driven_net_weight_max 5    # Weight multiplier range
```

---

## References

| Source | Type | URL |
|--------|------|-----|
| ePlace (Lu et al., 2015) | Paper | https://cseweb.ucsd.edu/~jlu/papers/eplace-todaes14/paper.pdf |
| RePlAce (Cheng et al., 2019) | Paper | https://vlsicad.ucsd.edu/Publications/Journals/j126.pdf |
| RUDY (Spindler & Johannes, 2007) | Paper | https://past.date-conference.com/proceedings-archive/2007/DATE07/PDFFILES/08.7_1.PDF |
| Circuit Training | Code | https://github.com/google-research/circuit_training |
| OpenROAD | Code | https://github.com/The-OpenROAD-Project/OpenROAD |
| MacroPlacement | Code+Docs | https://github.com/TILOS-AI-Institute/MacroPlacement |

---

## Quick Start for Implementation

1. **Start with HPWL** - Simplest, O(n) computation
2. **Add Density** - Prevents concentration hotspots
3. **Add Congestion** - For routability prediction
4. **Weight appropriately** - Usually (1.0, 1.0, 0.5) or (1.0, 0.5, 0.5)
5. **Iterate** - Adjust weights based on DRC/routing results

