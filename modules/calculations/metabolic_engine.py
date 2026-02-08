"""
Metabolic Engine & Training Strategy Module.

# ============================================================================
# CRITICAL: Metabolic Engine uses canonical physiology only.
# VO2max is READ-ONLY and resolved upstream.
# This module DOES NOT calculate VO2max - it receives it from canonical source.
# ============================================================================

Analyzes metabolic profile and generates periodized training blocks:
- VO2max / VLaMax ratio analysis (using CANONICAL VO2max)
- Athlete phenotype classification
- 6-8 week training block design
- KPI monitoring recommendations
"""
from typing import Dict, Any, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("Tri_Dashboard.MetabolicEngine")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MetabolicProfile:
    """Container for metabolic profile data."""
    # Core metrics - VO2max is READ-ONLY from canonical source
    vo2max: float = 0.0                   # ml/kg/min - FROM CANONICAL ONLY
    vo2max_source: str = "unknown"        # Source tracking
    vo2max_confidence: float = 0.0        # Confidence from canonical
    
    vlamax: float = 0.0                   # mmol/L/s (estimated from power)
    cp_watts: float = 0.0                 # Critical Power
    ftp_watts: float = 0.0                # FTP (if different from CP)
    w_prime_kj: float = 0.0               # W' in kJ
    
    # Derived
    vo2max_vlamax_ratio: float = 0.0      # Higher = more aerobic
    anaerobic_reserve_pct: float = 0.0    # (Pmax - CP) / CP
    
    # Classification
    phenotype: str = "unknown"            # diesel, puncher, sprinter, allrounder
    limiter: str = "unknown"              # aerobic, glycolytic, mixed
    limiter_confidence: float = 0.0
    
    # Strategy
    adaptation_target: str = "unknown"    # increase_vo2max, lower_vlamax, maintain
    strategy_interpretation: str = ""


@dataclass
class TrainingSession:
    """Single training session prescription."""
    name: str = ""
    power_range: str = ""                 # e.g., "220-250W"
    duration: str = ""                    # e.g., "2x20min"
    adaptation_goal: str = ""
    expected_smo2: str = ""
    expected_hr: str = ""
    expected_ve: str = ""
    failure_criteria: str = ""            # When to stop / regress signal
    frequency: str = ""                   # e.g., "1x/week"


@dataclass
class TrainingBlock:
    """6-8 week training block."""
    name: str = ""
    duration_weeks: int = 6
    primary_focus: str = ""
    sessions: List[TrainingSession] = field(default_factory=list)
    kpi_progress: List[str] = field(default_factory=list)
    kpi_regress: List[str] = field(default_factory=list)


@dataclass
class MetabolicStrategy:
    """Complete metabolic strategy output."""
    profile: MetabolicProfile = field(default_factory=MetabolicProfile)
    training_block: TrainingBlock = field(default_factory=TrainingBlock)


# =============================================================================
# VLaMax ESTIMATION (only metric calculated locally)
# =============================================================================

def estimate_vlamax(
    cp_watts: float,
    w_prime_kj: float,
    pmax_watts: float,
    weight_kg: float = 75
) -> float:
    """
    Estimate VLaMax from power profile.
    
    NOTE: VLaMax is the ONLY metric estimated locally.
    VO2max comes from canonical source.
    
    Higher W' and anaerobic capacity = higher VLaMax.
    Simplified model based on INSCYD principles.
    """
    if pmax_watts <= 0 or cp_watts <= 0:
        return 0.0
    
    # Anaerobic reserve
    anaerobic_reserve = pmax_watts - cp_watts
    
    # W' contribution (higher W' = higher glycolytic capacity)
    w_prime_factor = w_prime_kj / 20  # Normalize around 20kJ
    
    # Estimate VLaMax (mmol/L/s) - simplified model
    # Reference: 0.3-0.5 for endurance, 0.6-0.8 for sprinters
    vlamax = 0.3 + (anaerobic_reserve / pmax_watts) * 0.5 + (w_prime_factor - 1) * 0.1
    
    return max(0.2, min(1.0, vlamax))


# =============================================================================
# RATIO & CLASSIFICATION (uses canonical VO2max)
# =============================================================================

def calculate_vo2max_vlamax_ratio(vo2max: float, vlamax: float) -> float:
    """
    Calculate VO2max/VLaMax ratio.
    
    USES CANONICAL VO2max - does not calculate it.
    
    Higher ratio = more aerobic dominant.
    Reference: 
    - < 100: Glycolytic dominant
    - 100-150: Balanced
    - > 150: Aerobic dominant
    """
    if vlamax <= 0 or vo2max <= 0:
        return 0.0
    return vo2max / vlamax


def classify_phenotype(
    vo2max: float,
    vlamax: float,
    anaerobic_reserve_pct: float
) -> str:
    """
    Classify athlete phenotype.
    
    USES CANONICAL VO2max - does not calculate it.
    """
    if vo2max <= 0:
        return "unknown"
    
    ratio = vo2max / vlamax if vlamax > 0 else 0
    
    if vo2max >= 65 and vlamax < 0.4:
        return "diesel"  # High VO2max, low glycolytic
    elif vo2max >= 60 and 0.4 <= vlamax < 0.6:
        return "allrounder"
    elif anaerobic_reserve_pct > 0.5 and vlamax >= 0.6:
        return "sprinter"
    elif 50 <= vo2max < 65 and vlamax >= 0.5:
        return "puncher"
    else:
        return "allrounder"


def diagnose_limiter(
    vo2max: float,
    vlamax: float,
    cp_watts: float,
    weight_kg: float
) -> tuple:
    """
    Diagnose primary metabolic limiter.
    
    USES CANONICAL VO2max - does not calculate it.
    
    Returns:
        (limiter, confidence, interpretation)
    """
    if vo2max <= 0:
        return "unknown", 0.0, "Brak danych VO₂max – nie można określić limitera."
    
    ratio = vo2max / vlamax if vlamax > 0 else 0
    cp_per_kg = cp_watts / weight_kg if weight_kg > 0 else 0
    
    scores = {"aerobic": 0.0, "glycolytic": 0.0, "mixed": 0.0}
    
    # VO2max analysis
    if vo2max < 50:
        scores["aerobic"] += 3.0
    elif vo2max < 60:
        scores["aerobic"] += 1.5
        scores["mixed"] += 1.0
    else:
        scores["glycolytic"] += 1.0  # Good aerobic = glycolytic may be limiter
    
    # VLaMax analysis
    if vlamax > 0.6:
        scores["glycolytic"] += 2.5  # High VLaMax limits endurance
        scores["aerobic"] += 0.5
    elif vlamax > 0.45:
        scores["mixed"] += 2.0
    else:
        scores["aerobic"] += 1.0  # Low VLaMax = aerobic capacity limiting
    
    # Ratio analysis
    if ratio < 100:
        scores["glycolytic"] += 1.5
    elif ratio > 150:
        scores["aerobic"] += 1.5
    else:
        scores["mixed"] += 1.5
    
    # Determine winner
    total = sum(scores.values()) or 1.0
    max_score = max(scores.values())
    limiter = max(scores, key=scores.get)
    confidence = max_score / total
    
    # Interpretation
    if limiter == "aerobic":
        interp = (
            f"Niska pojemność tlenowa (VO₂max: {vo2max:.0f}) ogranicza wydolność. "
            "Priorytet: budowa bazy aerobowej i interwały VO₂max."
        )
    elif limiter == "glycolytic":
        interp = (
            f"Wysoka glikoliza (VLaMax: {vlamax:.2f}) obniża efektywność tlenową. "
            "Priorytet: długie jazdy Z2 na obniżenie VLaMax."
        )
    else:
        interp = (
            "Zbalansowany profil metaboliczny. "
            "Priorytet: utrzymanie proporcji przy podnoszeniu obu parametrów."
        )
    
    return limiter, confidence, interp


def determine_adaptation_target(limiter: str, phenotype: str) -> tuple:
    """
    Determine primary adaptation target based on limiter and phenotype.
    
    Returns:
        (target, strategy_description)
    """
    if limiter == "aerobic":
        return "increase_vo2max", (
            "ZWIĘKSZ VO₂max\n"
            "Główny cel: podniesienie pułapu tlenowego przez interwały VO₂max "
            "i budowę bazy aerobowej. Spodziewany wzrost CP o 3-5%."
        )
    elif limiter == "glycolytic":
        return "lower_vlamax", (
            "OBNIŻ VLaMax\n"
            "Główny cel: redukcja produkcji mleczanu przez długie sesje Z2 "
            "i treningi na czczo. Spodziewany wzrost FatMax o 15-25W."
        )
    else:
        return "maintain_balance", (
            "UTRZYMAJ BALANS\n"
            "Główny cel: proporcjonalna poprawa obu systemów. "
            "Polaryzacja 80/20 z akcentem na jakość interwałów."
        )


# =============================================================================
# TRAINING BLOCK GENERATION
# =============================================================================

def generate_training_block(
    profile: MetabolicProfile,
    weeks: int = 6
) -> TrainingBlock:
    """
    Generate a periodized training block based on metabolic profile.
    """
    block = TrainingBlock()
    block.duration_weeks = weeks
    
    target = profile.adaptation_target
    cp = profile.cp_watts
    
    if target == "increase_vo2max":
        block.name = "VO₂max Development Block"
        block.primary_focus = "Podniesienie pułapu tlenowego"
        
        block.sessions = [
            TrainingSession(
                name="VO₂max Intervals",
                power_range=f"{int(cp*1.06)}-{int(cp*1.20)}W",
                duration="4-6 × 4min @ 4min rest",
                adaptation_goal="Wzrost rzutu serca i pojemności minutowej",
                expected_smo2="Spadek do 30-40% w interwale, recovery >60%",
                expected_hr="92-100% HRmax",
                expected_ve="Blisko VE max (>120 L/min)",
                failure_criteria="Niemożność utrzymania mocy w 3+ interwałach",
                frequency="2×/tydzień"
            ),
            TrainingSession(
                name="Tempo Long",
                power_range=f"{int(cp*0.80)}-{int(cp*0.88)}W",
                duration="60-90min ciągłe",
                adaptation_goal="Gęstość mitochondriów, kapilaryzacja",
                expected_smo2="Stabilne 55-65%",
                expected_hr="78-85% HRmax",
                expected_ve="60-80 L/min, stabilne",
                failure_criteria="HR Drift >8% lub spadek mocy",
                frequency="1×/tydzień"
            ),
            TrainingSession(
                name="Endurance Base",
                power_range=f"{int(cp*0.55)}-{int(cp*0.70)}W",
                duration="3-4h",
                adaptation_goal="Objętość tlenowa, FatMax",
                expected_smo2=">65%, stabilne",
                expected_hr="65-75% HRmax",
                expected_ve="40-60 L/min",
                failure_criteria="Głód, spadek mocy >10%",
                frequency="1-2×/tydzień"
            )
        ]
        
        block.kpi_progress = [
            "HR przy CP spada o 3-5 bpm",
            "SmO₂ baseline wzrasta o 2-3%",
            "VE/VO₂ spada (lepsza ekonomia)",
            "Ramp test: wyższy peak power"
        ]
        block.kpi_regress = [
            "HRV spada >15% przez 3+ dni",
            "HR spoczynkowe wzrasta >8 bpm",
            "Niemożność ukończenia interwałów",
            "Przewlekłe zmęczenie nóg"
        ]
    
    elif target == "lower_vlamax":
        block.name = "VLaMax Reduction Block"
        block.primary_focus = "Optymalizacja metabolizmu tłuszczowego"
        
        block.sessions = [
            TrainingSession(
                name="Fasted Z2",
                power_range=f"{int(cp*0.55)}-{int(cp*0.68)}W",
                duration="2-3h na czczo",
                adaptation_goal="Obniżenie VLaMax, wzrost FatMax",
                expected_smo2=">70%, stabilne",
                expected_hr="65-72% HRmax",
                expected_ve="35-50 L/min",
                failure_criteria="Hipoglikemia, drżenie rąk",
                frequency="2×/tydzień"
            ),
            TrainingSession(
                name="Sub-LT1 Long",
                power_range=f"{int(cp*0.60)}-{int(cp*0.72)}W",
                duration="4-5h",
                adaptation_goal="Maksymalna objętość bez aktywacji glikolizy",
                expected_smo2=">65%",
                expected_hr="68-76% HRmax",
                expected_ve="45-60 L/min",
                failure_criteria="Lactate >2.0 mmol/L",
                frequency="1×/tydzień (weekend)"
            ),
            TrainingSession(
                name="Strength Endurance",
                power_range=f"{int(cp*0.65)}-{int(cp*0.75)}W @ 50-60rpm",
                duration="4 × 10min",
                adaptation_goal="Rekrutacja włókien, adaptacja nerwowo-mięśniowa",
                expected_smo2="55-65%",
                expected_hr="75-82% HRmax",
                expected_ve="50-70 L/min",
                failure_criteria="Ból kolan, spadek kadencji",
                frequency="1×/tydzień"
            )
        ]
        
        block.kpi_progress = [
            "FatMax przesuwa się w prawo o 10-20W",
            "RER przy Z2 spada <0.85",
            "SmO₂ przy LT1 wzrasta",
            "Lactate przy CP spada"
        ]
        block.kpi_regress = [
            "Utrata mocy w sprintach >10%",
            "Uczucie 'płaskich nóg' w interwałach",
            "Spadek masy ciała >2% (niezamierzony)",
            "Anemia (sprawdź ferrytynę)"
        ]
    
    else:  # maintain_balance
        block.name = "Polarized Maintenance Block"
        block.primary_focus = "Zbalansowany rozwój obu systemów"
        
        block.sessions = [
            TrainingSession(
                name="Threshold Intervals",
                power_range=f"{int(cp*0.95)}-{int(cp*1.02)}W",
                duration="3-4 × 8-12min",
                adaptation_goal="Podniesienie progu, tolerancja mleczanu",
                expected_smo2="45-55%",
                expected_hr="88-94% HRmax",
                expected_ve="90-110 L/min",
                failure_criteria="Spadek mocy >5% w serii",
                frequency="1×/tydzień"
            ),
            TrainingSession(
                name="VO₂max Touch",
                power_range=f"{int(cp*1.10)}-{int(cp*1.18)}W",
                duration="5 × 3min",
                adaptation_goal="Utrzymanie pułapu tlenowego",
                expected_smo2="35-45%",
                expected_hr="93-98% HRmax",
                expected_ve=">110 L/min",
                failure_criteria="Niemożność recovery między seriami",
                frequency="1×/tydzień"
            ),
            TrainingSession(
                name="Long Endurance",
                power_range=f"{int(cp*0.55)}-{int(cp*0.70)}W",
                duration="3-4h",
                adaptation_goal="Utrzymanie bazy tlenowej",
                expected_smo2=">65%",
                expected_hr="65-75% HRmax",
                expected_ve="40-55 L/min",
                failure_criteria="Znaczący HR drift >7%",
                frequency="1-2×/tydzień"
            )
        ]
        
        block.kpi_progress = [
            "CP wzrasta o 2-3%",
            "Peak power w rampie stabilny lub rosnący",
            "HRV stabilne lub rosnące",
            "SmO₂ recovery poprawia się"
        ]
        block.kpi_regress = [
            "Plateau CP przez 4+ tygodnie",
            "Spadek peak power w sprintach",
            "Rosnące zmęczenie subiektywne",
            "Zaburzenia snu"
        ]
    
    return block


# =============================================================================
# MAIN ANALYSIS FUNCTION - USES CANONICAL VO2max ONLY
# =============================================================================

def analyze_metabolic_engine(
    vo2max: float = 0.0,
    vo2max_source: str = "unknown",
    vo2max_confidence: float = 0.0,
    cp_watts: float = 0.0,
    w_prime_kj: float = 15.0,
    pmax_watts: float = 0.0,
    weight_kg: float = 75.0,
    ftp_watts: float = 0.0
) -> MetabolicStrategy:
    """
    Perform complete metabolic engine analysis.
    
    CRITICAL: vo2max MUST come from canonical source.
    This function does NOT calculate VO2max - it uses the value passed in.
    
    Args:
        vo2max: CANONICAL VO2max value (from canonical_physio.py)
        vo2max_source: Source of canonical VO2max
        vo2max_confidence: Confidence of canonical VO2max
        cp_watts: Critical Power
        w_prime_kj: W' in kJ
        pmax_watts: Peak power
        weight_kg: Athlete weight
        ftp_watts: FTP (if different from CP)
    """
    strategy = MetabolicStrategy()
    profile = strategy.profile
    
    # =========================================================================
    # CRITICAL: Use CANONICAL VO2max - DO NOT CALCULATE LOCALLY
    # =========================================================================
    profile.vo2max = vo2max
    profile.vo2max_source = vo2max_source
    profile.vo2max_confidence = vo2max_confidence
    
    # Power metrics
    profile.cp_watts = cp_watts
    profile.ftp_watts = ftp_watts or cp_watts
    profile.w_prime_kj = w_prime_kj
    
    # Estimate VLaMax (only locally estimated metric)
    profile.vlamax = estimate_vlamax(cp_watts, w_prime_kj, pmax_watts, weight_kg)
    
    # Calculate ratios (using canonical VO2max)
    profile.vo2max_vlamax_ratio = calculate_vo2max_vlamax_ratio(vo2max, profile.vlamax)
    profile.anaerobic_reserve_pct = (pmax_watts - cp_watts) / cp_watts if cp_watts > 0 else 0
    
    # Classifications (using canonical VO2max)
    profile.phenotype = classify_phenotype(vo2max, profile.vlamax, profile.anaerobic_reserve_pct)
    
    limiter, confidence, interp = diagnose_limiter(vo2max, profile.vlamax, cp_watts, weight_kg)
    profile.limiter = limiter
    profile.limiter_confidence = confidence
    
    target, strategy_desc = determine_adaptation_target(limiter, profile.phenotype)
    profile.adaptation_target = target
    profile.strategy_interpretation = strategy_desc
    
    # Generate training block
    strategy.training_block = generate_training_block(profile)
    
    return strategy


def format_metabolic_strategy_for_report(strategy: MetabolicStrategy) -> Dict[str, Any]:
    """
    Format strategy for inclusion in JSON/PDF reports.
    
    NOTE: VO2max source tracking is included for transparency.
    """
    profile = strategy.profile
    block = strategy.training_block
    
    return {
        "profile": {
            # CANONICAL VO2max (read-only, from upstream)
            "vo2max": round(profile.vo2max, 1) if profile.vo2max > 0 else None,
            "vo2max_source": profile.vo2max_source,
            "vo2max_confidence": round(profile.vo2max_confidence, 2),
            
            # VLaMax (locally estimated)
            "vlamax": round(profile.vlamax, 3),
            
            # Power metrics
            "cp_watts": round(profile.cp_watts, 0),
            "ftp_watts": round(profile.ftp_watts, 0),
            "w_prime_kj": round(profile.w_prime_kj, 1),
            
            # Derived
            "vo2max_vlamax_ratio": round(profile.vo2max_vlamax_ratio, 1) if profile.vo2max > 0 else None,
            "anaerobic_reserve_pct": round(profile.anaerobic_reserve_pct * 100, 1),
            
            # Classification
            "phenotype": profile.phenotype,
            "limiter": profile.limiter,
            "limiter_confidence": round(profile.limiter_confidence, 2),
            "adaptation_target": profile.adaptation_target,
            "strategy_interpretation": profile.strategy_interpretation
        },
        "training_block": {
            "name": block.name,
            "duration_weeks": block.duration_weeks,
            "primary_focus": block.primary_focus,
            "sessions": [
                {
                    "name": s.name,
                    "power_range": s.power_range,
                    "duration": s.duration,
                    "adaptation_goal": s.adaptation_goal,
                    "expected_smo2": s.expected_smo2,
                    "expected_hr": s.expected_hr,
                    "expected_ve": s.expected_ve,
                    "failure_criteria": s.failure_criteria,
                    "frequency": s.frequency
                }
                for s in block.sessions
            ],
            "kpi_progress": block.kpi_progress,
            "kpi_regress": block.kpi_regress
        }
    }


__all__ = [
    "MetabolicProfile",
    "TrainingSession",
    "TrainingBlock",
    "MetabolicStrategy",
    "analyze_metabolic_engine",
    "format_metabolic_strategy_for_report",
]
