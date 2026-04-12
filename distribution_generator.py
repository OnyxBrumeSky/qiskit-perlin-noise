"""
Générateur de distribution de probabilité pour circuit quantique (Qiskit)
=========================================================================
Utilisation :
    gen = DistributionGenerator(n_states=4, dist_type="random", seed=42)
    probs      = gen.probabilities       # numpy array
    gen.summary()                        # affiche un résumé
    gen.plot()                           # histogramme matplotlib
"""

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Types de distributions disponibles
# ─────────────────────────────────────────────────────────────────────────────

DIST_TYPES = ("uniform", "random", "gaussian", "exponential", "custom")


def _generate_weights(
    n: int,
    dist_type: str,
    rng: np.random.Generator,
    custom_weights: list | None = None,
    
) -> np.ndarray:
    """Génère des poids bruts (non normalisés) selon le type choisi."""

    if dist_type == "uniform":
        return np.ones(n)

    elif dist_type == "random":
        return rng.random(n)

    elif dist_type == "gaussian":
        mu = (n - 1) / 2
        sigma = max(n / 4, 0.5)
        x = np.arange(n)
        weights = np.exp(-0.5 * ((x - mu) / sigma) ** 2)
        weights += 0.02 * rng.random(n)   # légère perturbation aléatoire
        return weights

    elif dist_type == "exponential":
        lam = 0.3 + 0.4 * rng.random()    # taux tiré aléatoirement dans [0.3, 0.7]
        return np.exp(-lam * np.arange(n))

    elif dist_type == "custom":
        if custom_weights is None:
            raise ValueError("custom_weights requis pour dist_type='custom'")
        w = np.array(custom_weights, dtype=float)
        if len(w) < n:
            raise ValueError(
                f"custom_weights doit contenir au moins {n} valeurs, "
                f"reçu {len(w)}"
            )
        if np.any(w < 0):
            raise ValueError("custom_weights ne peut pas contenir de valeurs négatives")
        return w[:n]

    else:
        raise ValueError(
            f"dist_type inconnu : '{dist_type}'. "
            f"Valeurs acceptées : {DIST_TYPES}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Classe principale
# ─────────────────────────────────────────────────────────────────────────────

class DistributionGenerator:
    """
    Génère une distribution de probabilité et construit le circuit
    quantique Qiskit correspondant.

    Paramètres
    ----------
    n_states : int
        Nombre d'états de la distribution (≥ 2).
    dist_type : str
        Type de distribution parmi :
        'uniform', 'random', 'gaussian', 'exponential', 'custom'.
    seed : int | str | None
        Seed pour la reproductibilité.
        - None  → aléatoire (non reproductible)
        - int   → seed numérique directe
        - str   → hashé en entier (ex. seed="experience_1")
    custom_weights : list | None
        Poids personnalisés, utilisés uniquement si dist_type='custom'.
        Seront normalisés automatiquement.

    Attributs générés
    -----------------
    probabilities : np.ndarray   — tableau de probabilités (somme = 1)
    amplitudes    : np.ndarray   — amplitudes quantiques (√P)
    n_qubits      : int          — nombre de qubits nécessaires
    """

    def __init__(
        self,
        n_states: int = 4,
        dist_type: str = "random",
        seed: int | str | None = None,
        custom_weights: list | None = None,
    ):
        if n_states < 2:
            raise ValueError("n_states doit être ≥ 2")
        if dist_type not in DIST_TYPES:
            raise ValueError(f"dist_type doit être parmi {DIST_TYPES}")

        self.n_states      = n_states
        self.dist_type     = dist_type
        self.seed          = seed
        self.custom_weights = custom_weights

        # Résolution de la seed
        self._rng_seed = self._resolve_seed(seed)
        self._rng      = np.random.default_rng(self._rng_seed)

        # Génération
        self.probabilities = self._build_probabilities()
        self.amplitudes    = self._build_amplitudes()
        self.n_qubits      = int(np.ceil(np.log2(max(self.n_states, 2))))

    # ── Méthodes privées ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_seed(seed) -> int | None:
        if seed is None:
            return None
        if isinstance(seed, int):
            return seed
        if isinstance(seed, str):
            # FNV-1a 32-bit
            h = 2166136261
            for c in seed.encode():
                h ^= c
                h = (h * 16777619) & 0xFFFFFFFF
            return h
        raise TypeError(f"seed doit être int, str ou None, reçu {type(seed)}")

    def _build_probabilities(self) -> np.ndarray:
        weights = _generate_weights(
            self.n_states, self.dist_type, self._rng, self.custom_weights
        )
        total = weights.sum()
        if total == 0:
            raise ValueError("Les poids sont tous nuls")
        return weights / total

    def _build_amplitudes(self) -> np.ndarray:
        full_size = 2 ** int(np.ceil(np.log2(max(self.n_states, 2))))
        amps = np.sqrt(self.probabilities)
        if self.n_states < full_size:
            amps = np.pad(amps, (0, full_size - self.n_states))
        norm = np.linalg.norm(amps)
        return amps / norm

    # ── API publique ──────────────────────────────────────────────────────────

    def summary(self) -> None:
        """Affiche un résumé de la distribution dans le terminal."""
        entropy     = -sum(p * np.log2(p) for p in self.probabilities if p > 0)
        max_entropy = np.log2(self.n_states)
        uniformity  = entropy / max_entropy * 100 if max_entropy > 0 else 100.0

        seed_info = (
            f"{self.seed!r} → entier {self._rng_seed}"
            if isinstance(self.seed, str)
            else str(self._rng_seed)
        )

        print("=" * 48)
        print("  Distribution generator — résumé")
        print("=" * 48)
        print(f"  Type          : {self.dist_type}")
        print(f"  Seed          : {seed_info if self.seed is not None else 'None (aléatoire)'}")
        print(f"  n_states      : {self.n_states}")
        print(f"  n_qubits      : {self.n_qubits}")
        print(f"  Entropie      : {entropy:.4f} bits / {max_entropy:.4f} max")
        print(f"  Uniformité    : {uniformity:.1f}%")
        print("-" * 48)
        print(f"  {'État':<10} {'Amplitude':>12} {'P(x)':>10}")
        print("-" * 48)
        for i, (amp, prob) in enumerate(
            zip(self.amplitudes[: self.n_states], self.probabilities)
        ):
            label = f"|{i:0{self.n_qubits}b}⟩"
            print(f"  {label:<10} {amp:>12.6f} {prob:>10.6f}")
        print("=" * 48)

    def plot(self, title: str | None = None) -> None:
        """Affiche un histogramme matplotlib de la distribution."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib non installé : pip install matplotlib")
            return

        labels = [f"|{i:0{self.n_qubits}b}⟩" for i in range(self.n_states)]
        fig, ax = plt.subplots(figsize=(max(6, self.n_states), 4))
        bars = ax.bar(labels, self.probabilities, color="#378ADD", alpha=0.85, width=0.6)
        for bar, p in zip(bars, self.probabilities):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.005,
                f"{p:.3f}",
                ha="center", va="bottom", fontsize=10,
            )
        ax.set_ylabel("Probabilité")
        ax.set_ylim(0, max(self.probabilities) * 1.25)
        ax.set_title(title or f"Distribution '{self.dist_type}' — seed={self.seed}")
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        plt.show()

    def regenerate(self, seed=None) -> "DistributionGenerator":
        """
        Retourne une nouvelle instance avec une seed différente
        (ou aléatoire si seed=None) en conservant les autres paramètres.
        """
        return DistributionGenerator(
            n_states=self.n_states,
            dist_type=self.dist_type,
            seed=seed,
            custom_weights=self.custom_weights,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Démonstration
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n── 1. Aléatoire (sans seed) ──────────────────────")
    g1 = DistributionGenerator(n_states=4, dist_type="random")
    g1.summary()

    print("\n── 2. Reproductible (seed entière) ───────────────")
    g2 = DistributionGenerator(n_states=4, dist_type="random", seed=42)
    g2.summary()

    print("\n── 3. Même seed → même résultat ──────────────────")
    g3 = DistributionGenerator(n_states=4, dist_type="random", seed=42)
    identical = np.allclose(g2.probabilities, g3.probabilities)
    print(f"  g2 == g3 : {identical}")

    print("\n── 4. Seed en chaîne de caractères ───────────────")
    g4 = DistributionGenerator(n_states=6, dist_type="gaussian", seed="experience_1")
    g4.summary()

    print("\n── 5. Distribution personnalisée ─────────────────")
    g5 = DistributionGenerator(
        n_states=4, dist_type="custom", custom_weights=[1, 3, 2, 4]
    )
    g5.summary()

