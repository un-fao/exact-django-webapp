# Scenario Compilation Script: Mathematical Methodology Documentation

## Overview

The `minitool__compile_scenarios.py` script implements a comprehensive statistical analysis framework for evaluating agricultural management scenarios. It employs rigorous mathematical methods to quantify the environmental impacts of management transitions and provides robust statistical characterization of the effect distributions.

## Mathematical Framework

### Data Aggregation Methodology

The script uses Django Q-objects with logical OR operations to construct complex queries that aggregate multiple management transitions within each scenario:

```python
q_objects = Q()
for change in scenario["changes"]:
    q_objects |= Q(
        module_type=scenario["module_type"],
        field=change["start"]["field"],
        from_value=change["start"]["value"],
        to_value=change["end"]["value"],
    )
```

This approach ensures that all relevant management transitions are captured in a single, efficient database query.

## Statistical Analysis

### Descriptive Statistics

The `stats_for()` function implements a comprehensive suite of statistical measures using both Django ORM aggregations and Python statistical computations:

#### Basic Aggregates
- **Count (n)**: `COUNT(id)` - Sample size
- **Sum (Σx)**: `SUM(total)` - Total impact across all records
- **Mean (μ)**: `AVG(total)` - Central tendency measure
- **Range**: `MIN(total)` and `MAX(total)` - Data bounds

#### Variance and Standard Deviation

**Sample Variance** (Bessel's correction applied):
```
var = (SS - (S²/n)) / (n-1)
```

Where:
- `SS = Σ(xi²)` - Sum of squares
- `S = Σ(xi)` - Sum of values
- `n` - Sample size

**Standard Deviation**:
```
σ = √var
```

**Standard Error**:
```
SE = σ/√n
```

### Percentile Calculations

The script implements robust percentile calculation with adaptive methodologies:

#### For Large Datasets (n ≥ 4)
Uses Python's `statistics.quantiles()` with quartile method:
- **Q1**: 25th percentile
- **Median**: 50th percentile  
- **Q3**: 75th percentile

#### For Small Datasets (n < 4)
Implements linear interpolation for precise percentile estimation:

**Median Calculation**:
```
if n % 2 == 0:
    median = (x[n/2-1] + x[n/2]) / 2
else:
    median = x[n/2]
```

**Quartile Interpolation**:
```
q_idx = (n-1) × percentile
if q_idx is integer:
    q = sorted_values[q_idx]
else:
    lower_idx = floor(q_idx)
    upper_idx = min(lower_idx + 1, n-1)
    weight = q_idx - lower_idx
    q = sorted_values[lower_idx] × (1-weight) + sorted_values[upper_idx] × weight
```

### Confidence Intervals

**95% Confidence Interval**:
```
CI₉₅ = ±1.96 × SE
```

**99% Confidence Interval**:
```
CI₉₉ = ±2.58 × SE
```

### Distribution Symmetry Analysis

The script employs a quantitative test for distribution symmetry:

**Symmetry Criterion**:
```
|mean - median| < 0.25 × σ
```

#### Symmetric Distribution
- **Condition**: Data follows approximately normal distribution
- **Range Reporting**: `[μ - σ, μ + σ]`
- **Interpretation**: 68% of values fall within one standard deviation

#### Skewed Distribution  
- **Condition**: Significant deviation from normality
- **Range Reporting**: `[Q1, Q3]` (Interquartile Range)
- **Interpretation**: Robust range containing central 50% of data

## Scenarios Analyzed

### 1. Reducing Tillage
**Module**: Perennial Cropland
**Management Transitions**:
- Full Tillage → Reduced Tillage
- Reduced Tillage → No Tillage  
- Full Tillage → No Tillage

### 2. Increasing Carbon Input
**Module**: Annual Cropland
**Management Transitions**:
- Low C input → Medium C input
- Medium C input → High C input (no manure)
- High C input (no manure) → High C input (with manure)
- Low C input → High C input (no manure)
- Low C input → High C input (with manure)
- Medium C input → High C input (with manure)

### 3. Stopping Residue Burning
**Module**: Annual Cropland
**Management Transitions**:
- Burned → Retained
- Burned → Exported

## Computational Implementation

### Data Source
Queries the `ChangeRecord` model containing individual impact measurements for each management transition, filtered by:
- Module type specification
- Field name (management practice type)
- Transition direction (from_value → to_value)

### Statistical Output

The analysis produces a comprehensive statistical profile for each scenario:

```python
{
    "count": n,                    # Sample size
    "sum_total": Σx,              # Total impact
    "mean": μ,                    # Mean impact
    "median": M,                  # Median impact
    "min": min(x),                # Minimum value
    "max": max(x),                # Maximum value
    "std": σ,                     # Standard deviation
    "q1": Q1,                     # First quartile
    "q3": Q3,                     # Third quartile
    "iqr": Q3-Q1,                 # Interquartile range
    "ci_95": ±1.96×SE,            # 95% confidence interval
    "ci_99": ±2.58×SE,            # 99% confidence interval
}
```

## Usage

### Prerequisites
- Django environment with minitool app configured
- `ChangeRecord` model populated with individual impact data
- Python `statistics` module (standard library)

### Running the Script
```bash
cd djangoexact
python manage.py shell -c "exec(open('scripts/minitool__compile_scenarios.py').read())"
```

### Output Interpretation

#### Sample Output
```
Reducing Tillage
{'count': 960, 'sum_total': -601.08, 'mean': -0.626, 'median': -0.513, 
 'min': -2.647, 'max': 0.094, 'std': 0.530, 'q1': -0.828, 'q3': -0.262, 
 'iqr': 0.565, 'ci_95': 0.034, 'ci_99': 0.044}
Dataset is symmetric
Range: -1.156 to -0.097
```

#### Interpretation:
- **Sample Size**: 960 management transition records
- **Mean Impact**: -0.626 (negative indicates beneficial environmental effect)
- **Distribution**: Symmetric (normal-like distribution)
- **Confidence**: 95% CI indicates high precision (±0.034)
- **Range**: 68% of impacts fall between -1.156 and -0.097

## Mathematical Validation

### Robustness Features

1. **Adaptive Percentile Calculation**: Automatically switches between standard quantile methods and interpolation based on sample size
2. **Bessel's Correction**: Applies (n-1) denominator for unbiased variance estimation
3. **Distribution-Aware Ranging**: Uses appropriate range measures based on symmetry analysis
4. **Confidence Interval Estimation**: Provides uncertainty quantification for mean estimates

### Numerical Stability

- Single-pass sum of squares calculation: `SS = Σ(xi²)`
- Avoids numerical instability from naive variance formulas
- Handles edge cases (n=0, n=1) gracefully
- Uses robust percentile interpolation for small samples

## Data Requirements

The script requires the `ChangeRecord` model with the following structure:
- `module_type`: Agricultural module classification
- `field`: Management practice field name
- `from_value`: Initial management state
- `to_value`: Target management state  
- `total`: Individual impact measurement (continuous variable)

## Computational Complexity

- **Time Complexity**: O(n log n) due to sorting for percentile calculation
- **Space Complexity**: O(n) for storing sorted values
- **Database Queries**: Single optimized query per scenario using Q-objects

## Statistical Assumptions

1. **Independence**: Individual impact measurements are independent
2. **Numerical Scale**: Impact values are continuous and meaningful on interval scale
3. **Sample Representativeness**: Data represents the population of interest
4. **Outlier Sensitivity**: Uses both robust (IQR) and parametric (mean±σ) range estimates

## Related Documentation

- `minitool/models.py`: Data model definitions
- `minitool/management/commands/import_changes.py`: Data import pipeline
- Django ORM documentation for Q-object usage
