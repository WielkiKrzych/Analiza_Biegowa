"""
Genetic Fitness Profile Module.

Analyzes genetic data from 23andMe/Ancestry to provide
personalized training recommendations based on:
- ACTN3 (muscle fiber type)
- ACE (endurance vs power)
- PPARGC1A (mitochondrial efficiency)
"""
from dataclasses import dataclass
from typing import Optional, List, Literal, Dict
from enum import Enum


class GeneVariant(Enum):
    """Common fitness-related gene variants."""
    ACTN3_RR = "RR"  # Power athlete
    ACTN3_RX = "RX"  # Mixed
    ACTN3_XX = "XX"  # Endurance athlete
    
    ACE_II = "II"    # Endurance
    ACE_ID = "ID"    # Mixed
    ACE_DD = "DD"    # Power/strength
    
    PPARGC1A_GG = "GG"  # Normal
    PPARGC1A_GA = "GA"  # Enhanced
    PPARGC1A_AA = "AA"  # Highly enhanced


@dataclass
class GeneticProfile:
    """Complete genetic fitness profile."""
    actn3: Optional[Literal["RR", "RX", "XX"]] = None
    ace: Optional[Literal["II", "ID", "DD"]] = None
    ppargc1a: Optional[Literal["GG", "GA", "AA"]] = None
    
    # Calculated scores (0-100)
    endurance_score: float = 50.0
    power_score: float = 50.0
    recovery_score: float = 50.0
    injury_risk_score: float = 50.0
    
    def __post_init__(self):
        self._calculate_scores()
    
    def _calculate_scores(self):
        """Calculate fitness scores based on genetic variants."""
        endurance_points = 0
        power_points = 0
        recovery_points = 0
        
        # ACTN3 scoring
        if self.actn3 == "XX":
            endurance_points += 30
            power_points -= 10
        elif self.actn3 == "RR":
            power_points += 30
            endurance_points -= 10
        elif self.actn3 == "RX":
            endurance_points += 10
            power_points += 10
        
        # ACE scoring
        if self.ace == "II":
            endurance_points += 25
            recovery_points += 10
        elif self.ace == "DD":
            power_points += 25
        elif self.ace == "ID":
            endurance_points += 10
            power_points += 10
        
        # PPARGC1A scoring (mitochondrial efficiency)
        if self.ppargc1a == "AA":
            endurance_points += 20
            recovery_points += 15
        elif self.ppargc1a == "GA":
            endurance_points += 10
            recovery_points += 5
        
        # Normalize to 0-100
        self.endurance_score = max(0, min(100, 50 + endurance_points))
        self.power_score = max(0, min(100, 50 + power_points))
        self.recovery_score = max(0, min(100, 50 + recovery_points))
    
    @property
    def athlete_type(self) -> str:
        """Determine primary athlete type."""
        if self.endurance_score > self.power_score + 20:
            return "🏃 Wytrzymałościowiec"
        elif self.power_score > self.endurance_score + 20:
            return "💪 Sprinter/Siłowiec"
        else:
            return "⚖️ Wszechstronny"


class GeneticAnalyzer:
    """Analyzes genetic data and provides recommendations."""
    
    # SNP identifiers for 23andMe
    SNPS = {
        'ACTN3': 'rs1815739',
        'ACE': 'rs1799752',
        'PPARGC1A': 'rs8192678',
    }
    
    def parse_23andme(self, raw_data: str) -> GeneticProfile:
        """Parse 23andMe raw data file.
        
        Args:
            raw_data: Contents of 23andMe raw data file
            
        Returns:
            GeneticProfile with detected variants
        """
        profile = GeneticProfile()
        
        for line in raw_data.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            
            parts = line.split('\t')
            if len(parts) < 4:
                continue
            
            rsid = parts[0]
            genotype = parts[3].strip()
            
            # ACTN3 (rs1815739)
            if rsid == self.SNPS['ACTN3']:
                if genotype in ['CC']:
                    profile.actn3 = "RR"
                elif genotype in ['CT', 'TC']:
                    profile.actn3 = "RX"
                elif genotype in ['TT']:
                    profile.actn3 = "XX"
            
            # ACE (rs1799752) - Note: This is actually a deletion, simplified
            elif rsid == self.SNPS['ACE']:
                if genotype in ['II', '--']:
                    profile.ace = "II"
                elif genotype in ['DD']:
                    profile.ace = "DD"
                else:
                    profile.ace = "ID"
            
            # PPARGC1A (rs8192678)
            elif rsid == self.SNPS['PPARGC1A']:
                if genotype in ['GG']:
                    profile.ppargc1a = "GG"
                elif genotype in ['GA', 'AG']:
                    profile.ppargc1a = "GA"
                elif genotype in ['AA']:
                    profile.ppargc1a = "AA"
        
        # Recalculate scores with parsed data
        profile._calculate_scores()
        
        return profile
    
    def parse_ancestry(self, raw_data: str) -> GeneticProfile:
        """Parse Ancestry DNA raw data file.
        
        Similar format to 23andMe.
        """
        # Ancestry uses similar format
        return self.parse_23andme(raw_data)
    
    def get_recommendations(
        self, 
        profile: GeneticProfile
    ) -> List[Dict[str, str]]:
        """Generate personalized training recommendations.
        
        Args:
            profile: Genetic profile
            
        Returns:
            List of recommendation dicts with 'category', 'title', 'description'
        """
        recommendations = []
        
        # ACTN3-based recommendations
        if profile.actn3 == "XX":
            recommendations.append({
                'category': 'Trening',
                'title': '🏃 Optymalizuj wytrzymałość',
                'description': """
Twój genotyp ACTN3 (XX) wskazuje na przewagę włókien wolnokurczliwych.
- Koncentruj się na długich, stabilnych treningach Z2
- Interwały 8-20 min na progu
- Unikaj zbyt wielu sesji sprintowych
- Dobrze reagujesz na duży wolumen treningowy
"""
            })
        elif profile.actn3 == "RR":
            recommendations.append({
                'category': 'Trening',
                'title': '💪 Wykorzystaj moc',
                'description': """
Twój genotyp ACTN3 (RR) wskazuje na przewagę włókien szybkokurczliwych.
- Włącz regularne sesje sprintowe
- Krótkie, intensywne interwały (30s-2min)
- Możesz potrzebować więcej czasu regeneracji po treningach siłowych
- Rozważ periodyzację mocy przed sezonem
"""
            })
        
        # ACE-based recommendations
        if profile.ace == "II":
            recommendations.append({
                'category': 'Regeneracja',
                'title': '⚡ Szybka regeneracja',
                'description': """
Genotyp ACE (II) sprzyja efektywnej regeneracji.
- Możesz tolerować wyższy wolumen
- Rozważ treningi 2x dziennie
- Monitoruj HRV dla optymalnego obciążenia
"""
            })
        elif profile.ace == "DD":
            recommendations.append({
                'category': 'Siła',
                'title': '🏋️ Trening siłowy',
                'description': """
Genotyp ACE (DD) sprzyja adaptacji siłowej.
- Regularny trening siłowy na siłowni
- Wysokie momenty obrotowe na rowerze
- Treningi górskie/wzniesienia
"""
            })
        
        # PPARGC1A-based recommendations
        if profile.ppargc1a in ["GA", "AA"]:
            recommendations.append({
                'category': 'Metabolizm',
                'title': '🔋 Efektywne mitochondria',
                'description': """
Twój wariant PPARGC1A sprzyja biogenezie mitochondriów.
- Szczególnie dobrze reagujesz na trening Z2
- Długie sesje bazowe (2-4h) są dla Ciebie idealne
- Możesz efektywniej spalać tłuszcze
"""
            })
        
        # General recommendation based on overall profile
        recommendations.append({
            'category': 'Ogólne',
            'title': f'🎯 {profile.athlete_type}',
            'description': f"""
**Twój profil genetyczny:**
- Wytrzymałość: {profile.endurance_score:.0f}/100
- Moc: {profile.power_score:.0f}/100
- Regeneracja: {profile.recovery_score:.0f}/100

{"Skup się na budowaniu bazy tlenowej i długich dystansach." if profile.endurance_score > profile.power_score else "Wykorzystaj potencjał mocy i regularnie trenuj siłę."}
"""
        })
        
        return recommendations
    
    def get_zone_adjustments(
        self, 
        profile: GeneticProfile,
        cp: float
    ) -> Dict[str, tuple]:
        """Suggest personalized power zone adjustments.
        
        Args:
            profile: Genetic profile
            cp: Current Critical Power
            
        Returns:
            Dict with zone names and (lower%, upper%) of CP
        """
        # Base zones (Coggan)
        zones = {
            'Z1': (0.0, 0.55),
            'Z2': (0.55, 0.75),
            'Z3': (0.75, 0.90),
            'Z4': (0.90, 1.05),
            'Z5': (1.05, 1.20),
            'Z6': (1.20, 1.50),
        }
        
        # Adjust for endurance athletes (XX genotype)
        if profile.actn3 == "XX":
            # Slightly lower threshold zones (fatigue faster at high intensity)
            zones['Z4'] = (0.88, 1.02)
            zones['Z5'] = (1.02, 1.15)
        
        # Adjust for power athletes (RR genotype)
        elif profile.actn3 == "RR":
            # Can sustain higher relative intensities
            zones['Z4'] = (0.92, 1.08)
            zones['Z5'] = (1.08, 1.25)
        
        return zones
